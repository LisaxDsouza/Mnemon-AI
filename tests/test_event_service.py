import unittest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Append parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from database import Base
import models
from event_service import EventService

class TestEventService(unittest.TestCase):

    def setUp(self):
        # Create an in-memory SQLite database specifically for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        # Create a mock default user
        self.user = models.User(email="test@mnemon.ai")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_map_event_type(self):
        """Verifies mapping of source types/URLs to canonical Event Types."""
        # youtube video -> VIDEO
        self.assertEqual(EventService.map_event_type("https://youtube.com/watch?v=123", "youtube"), "VIDEO")
        
        # github -> GITHUB
        self.assertEqual(EventService.map_event_type("https://github.com/my/repo", "github"), "GITHUB")
        
        # pdf -> PDF
        self.assertEqual(EventService.map_event_type("https://example.com/paper.pdf", "pdf"), "PDF")
        
        # search -> SEARCH
        self.assertEqual(EventService.map_event_type("https://www.google.com/search?q=docker", "search"), "SEARCH")
        
        # docs.docker.com -> DOCUMENTATION (even if general web source type)
        self.assertEqual(EventService.map_event_type("https://docs.docker.com/network/bridge/", "web"), "DOCUMENTATION")
        
        # stackoverflow -> DOCUMENTATION
        self.assertEqual(EventService.map_event_type("https://stackoverflow.com/questions/123", "web"), "DOCUMENTATION")
        
        # general news -> ARTICLE
        self.assertEqual(EventService.map_event_type("https://news.ycombinator.com/item?id=45", "articles"), "ARTICLE")

    def test_create_event_and_artifacts(self):
        """Verifies event creation and linking artifacts."""
        # 1. Create a documentation event
        event = EventService.create_event(
            db=self.db,
            user_id=self.user.id,
            url="https://docs.docker.com/network/bridge/",
            title="Docker Bridge Networking",
            source_type="web"
        )
        self.assertIsNotNone(event.id)
        self.assertEqual(event.event_type, "DOCUMENTATION")
        self.assertEqual(event.status, "pending")

        # 2. Add artifacts
        parsed_data = [
            {"text": "Bridge networks apply to containers running on the same daemon host.", "metadata": {"location": "Overview"}},
            {"text": "A bridge network is a Link Layer device which forwards traffic.", "metadata": {"location": "Technical Details"}}
        ]
        artifacts = EventService.add_event_artifacts(self.db, event.id, parsed_data)
        
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(self.db.query(models.Artifact).count(), 2)
        
        # Check parent-child relation
        db_artifacts = self.db.query(models.Artifact).filter_by(event_id=event.id).all()
        self.assertEqual(len(db_artifacts), 2)
        self.assertEqual(db_artifacts[0].content, "Bridge networks apply to containers running on the same daemon host.")
        self.assertEqual(db_artifacts[0].location, "Overview")

    def test_extract_search_query(self):
        """Verifies extracting queries from search engines."""
        google_url = "https://www.google.com/search?q=docker+container+ports&oq=docker"
        self.assertEqual(EventService.extract_search_query(google_url), "docker container ports")
        
        yahoo_url = "https://search.yahoo.com/search?p=kubernetes+pods"
        self.assertEqual(EventService.extract_search_query(yahoo_url), "kubernetes pods")
        
        invalid_url = "https://example.com/item"
        self.assertIsNone(EventService.extract_search_query(invalid_url))

    def test_calculate_engagement(self):
        """Verifies 0-100 engagement scaling calculations."""
        # 1. Zero values
        self.assertEqual(EventService.calculate_engagement(0, 0, 0), 0.0)
        
        # 2. Maximum values (120s time, 100% scroll, 2 revisits)
        self.assertEqual(EventService.calculate_engagement(120, 100, 2), 100.0)
        
        # 3. Overshoot values (should cap at 100)
        self.assertEqual(EventService.calculate_engagement(300, 150, 5), 100.0)
        
        # 4. Partial values (60s duration -> 20pts, 50% scroll -> 20pts, 1 revisit -> 10pts)
        self.assertEqual(EventService.calculate_engagement(60, 50, 1), 50.0)

    def test_assign_topic_cluster(self):
        """Verifies that similar search queries map to the same cluster while distinct ones create new clusters."""
        import numpy as np
        
        # Mock VectorStoreManager._get_embeddings
        class MockVectorStore:
            def _get_embeddings(self, texts):
                # Simple mock mapping text similarity
                # "docker bridge" -> [1, 0, 0]
                # "docker setup" -> [0.8, 0.6, 0]
                # "cooking recipes" -> [0, 0, 1]
                t = texts[0].lower()
                if "docker bridge" in t:
                    vec = np.array([1.0, 0.0, 0.0], dtype='float32')
                elif "docker setup" in t:
                    vec = np.array([0.9, 0.1, 0.0], dtype='float32')
                else:
                    vec = np.array([0.0, 0.0, 1.0], dtype='float32')
                # Pad to 384 dimensions
                padded = np.zeros(384, dtype='float32')
                padded[:3] = vec
                # Normalize L2
                padded = padded / np.linalg.norm(padded)
                return [padded]

        mock_vs = MockVectorStore()

        # 1. Create first cluster for Docker Bridge
        c1 = EventService.assign_topic_cluster(self.db, self.user.id, "docker bridge network", mock_vs)
        self.assertIsNotNone(c1.id)
        self.assertIn("Docker", c1.topic_name)

        # 2. Create similar query, should match c1
        c2 = EventService.assign_topic_cluster(self.db, self.user.id, "docker setup bridge config", mock_vs)
        self.assertEqual(c1.id, c2.id)

        # 3. Create unrelated query, should generate a new cluster
        c3 = EventService.assign_topic_cluster(self.db, self.user.id, "cooking recipes for chicken pasta", mock_vs)
        self.assertNotEqual(c1.id, c3.id)
        self.assertIn("Cooking", c3.topic_name)

if __name__ == "__main__":
    unittest.main()
