import urllib.parse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import models

class EventService:
    @staticmethod
    def map_event_type(url: str, source_type: str) -> str:
        """
        Maps source types and URL patterns to canonical Event Types:
        SEARCH, ARTICLE, VIDEO, GITHUB, PDF, DOCUMENTATION
        """
        s_lower = source_type.lower() if source_type else ""
        url_lower = url.lower() if url else ""
        
        if "youtube" in s_lower or "video" in s_lower:
            return "VIDEO"
        if "github" in s_lower or "code" in s_lower:
            return "GITHUB"
        if "pdf" in s_lower or url_lower.endswith(".pdf"):
            return "PDF"
        if "search" in s_lower or "google.com/search" in url_lower or "bing.com/search" in url_lower:
            return "SEARCH"
            
        # Check for standard reference/doc portals to categorize as DOCUMENTATION
        doc_indicators = [
            "docs.docker.com",
            "developer.mozilla.org",
            "react.dev/reference",
            "nextjs.org/docs",
            "python.org/doc",
            "stackoverflow.com",
            "wikipedia.org",
            "learn.microsoft.com",
            "cloud.google.com/docs",
            "aws.amazon.com"
        ]
        if any(indicator in url_lower for indicator in doc_indicators):
            return "DOCUMENTATION"
            
        return "ARTICLE"

    @staticmethod
    def create_event(
        db: Session,
        user_id: str,
        url: str,
        title: str,
        source_type: str,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> models.MemoryEvent:
        """Creates a structured MemoryEvent in the SQLite database."""
        event_type = EventService.map_event_type(url, source_type)
        
        event = models.MemoryEvent(
            user_id=user_id,
            source_type=source_type,
            event_type=event_type,
            title=title,
            url=url,
            duration_seconds=0,
            scroll_depth=0,
            engagement_score=0.0,
            metadata_json=metadata_json or {}
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def add_event_artifacts(
        db: Session,
        event_id: str,
        parsed_data: List[Dict[str, Any]]
    ) -> List[models.Artifact]:
        """Creates database Artifact records from parsed page segments and links them to the MemoryEvent."""
        artifacts = []
        for item in parsed_data:
            text = item.get("text", "").strip()
            if not text:
                continue
            location = item.get("metadata", {}).get("location", "General")
            
            artifact = models.Artifact(
                event_id=event_id,
                content=text,
                location=location
            )
            db.add(artifact)
            artifacts.append(artifact)
            
        db.commit()
        return artifacts
