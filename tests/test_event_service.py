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

if __name__ == "__main__":
    unittest.main()
