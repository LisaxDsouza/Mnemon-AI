import unittest
import sys
import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Append parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from database import Base
import models
from session_service import SessionService

class TestSessionService(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        self.user = models.User(email="test@mnemon.ai")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_calculate_closeness(self):
        """Verifies multi-factor closeness score computation."""
        class MockVectorStore:
            def _get_embeddings(self, texts):
                import numpy as np
                # Return identical mock 384d vector so cosine similarity is ~1.0
                vec = np.zeros(384, dtype='float32')
                vec[0] = 1.0
                return [vec, vec]

        mock_vs = MockVectorStore()
        base_time = datetime.datetime.utcnow()

        # 1. Close search events in same tab
        event_a = models.MemoryEvent(
            created_at=base_time,
            url="https://www.google.com/search?q=docker+bridge",
            title="Search: docker bridge",
            metadata_json={"tab_id": 1, "search_query": "docker bridge"}
        )
        event_b = models.MemoryEvent(
            created_at=base_time + datetime.timedelta(seconds=30),
            url="https://docs.docker.com/network/bridge/",
            title="Docker Bridge Configuration Guide",
            metadata_json={"tab_id": 1}
        )

        closeness = SessionService.calculate_closeness(event_a, event_b, mock_vs)
        # Should be high (same tab, search term in title, close time, semantic similarity)
        self.assertTrue(closeness >= 0.50)

    def test_sessionize_and_threading(self):
        """Verifies grouping events, creating sessions, and linking/creating threads."""
        class MockVectorStore:
            def _get_embeddings(self, texts):
                import numpy as np
                # Return distinct vectors so they don't similarity match above 0.70
                # Use a simple mapping to yield distinct vectors
                ret = []
                for text in texts:
                    vec = np.zeros(384, dtype='float32')
                    if "React" in text or "react" in text or "useState" in text or "useState" in text:
                        vec[0] = 1.0
                    else:
                        vec[1] = 1.0  # orthogonal
                    ret.append(vec)
                return ret

        mock_vs = MockVectorStore()
        base_time = datetime.datetime.utcnow()

        # Two related events
        ev1 = models.MemoryEvent(
            user_id=self.user.id,
            created_at=base_time,
            url="https://react.dev/reference/react",
            title="React Hooks",
            source_type="web",
            metadata_json={"tab_id": 2}
        )
        ev2 = models.MemoryEvent(
            user_id=self.user.id,
            created_at=base_time + datetime.timedelta(minutes=2),
            url="https://react.dev/reference/react/useState",
            title="useState hook",
            source_type="web",
            metadata_json={"tab_id": 2}
        )

        # Unrelated event (different tab, time gap 40 minutes)
        ev3 = models.MemoryEvent(
            user_id=self.user.id,
            created_at=base_time + datetime.timedelta(minutes=45),
            url="https://cooking.com/recipes",
            title="Best lasagna recipes",
            source_type="web",
            metadata_json={"tab_id": 5}
        )

        self.db.add_all([ev1, ev2, ev3])
        self.db.commit()

        created = SessionService.sessionize_events(self.db, self.user.id, mock_vs)
        # Should create 2 sessions (one for React hooks, one for cooking)
        self.assertEqual(created, 2)

        # Verify threads
        threads = self.db.query(models.Thread).all()
        # Should create 2 threads
        self.assertEqual(len(threads), 2)
        
        sessions = self.db.query(models.Session).all()
        self.assertEqual(len(sessions), 2)
        
        # Verify events are linked to sessions
        self.assertIsNotNone(ev1.session_id)
        self.assertEqual(ev1.session_id, ev2.session_id)
        self.assertNotEqual(ev1.session_id, ev3.session_id)

if __name__ == "__main__":
    unittest.main()
