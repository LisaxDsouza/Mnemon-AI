import unittest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Append parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from database import Base
import models

class TestMnemonSchemas(unittest.TestCase):

    def setUp(self):
        # Create an in-memory SQLite database specifically for testing the schema
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_core_relations_and_cascade(self):
        """Verifies Thread -> Session -> MemoryEvent -> Artifact -> Reflection hierarchy and cascade deletions."""
        # 1. Create User
        user = models.User(email="test@mnemon.ai")
        self.db.add(user)
        self.db.commit()
        
        # 2. Create Thread
        thread = models.Thread(user_id=user.id, title="Test Thread Research")
        self.db.add(thread)
        self.db.commit()

        # 3. Create Session
        session = models.Session(user_id=user.id, thread_id=thread.id, title="Docker Network Session")
        self.db.add(session)
        self.db.commit()

        # 4. Create MemoryEvent
        event = models.MemoryEvent(
            user_id=user.id,
            session_id=session.id,
            event_type="ARTICLE",
            source_type="web",
            title="Docker Bridge Networks Guide",
            url="https://docs.docker.com/network/bridge/"
        )
        self.db.add(event)
        self.db.commit()

        # 5. Create Artifact
        artifact = models.Artifact(
            event_id=event.id,
            content="Docker uses bridge networks to communicate between containers.",
            location="Section: Overview"
        )
        self.db.add(artifact)
        
        # 6. Create Reflection
        reflection = models.Reflection(
            user_id=user.id,
            thread_id=thread.id,
            summary="User is learning container orchestration networks."
        )
        self.db.add(reflection)
        self.db.commit()

        # Assert items are in DB
        self.assertEqual(self.db.query(models.Thread).count(), 1)
        self.assertEqual(self.db.query(models.Session).count(), 1)
        self.assertEqual(self.db.query(models.MemoryEvent).count(), 1)
        self.assertEqual(self.db.query(models.Artifact).count(), 1)
        self.assertEqual(self.db.query(models.Reflection).count(), 1)

        # Check links
        self.assertEqual(artifact.memory_event.id, event.id)
        self.assertEqual(event.session.id, session.id)
        self.assertEqual(session.thread.id, thread.id)
        self.assertEqual(reflection.thread.id, thread.id)

        # 7. Test Cascade Delete: Delete Thread, should delete Session, Reflection, Event, Artifact
        self.db.delete(thread)
        self.db.commit()

        # Assert all child items are cascade-deleted, leaving no orphans
        self.assertEqual(self.db.query(models.Thread).count(), 0)
        self.assertEqual(self.db.query(models.Session).count(), 0)
        self.assertEqual(self.db.query(models.MemoryEvent).count(), 0)
        self.assertEqual(self.db.query(models.Artifact).count(), 0)
        self.assertEqual(self.db.query(models.Reflection).count(), 0)


if __name__ == "__main__":
    unittest.main()
