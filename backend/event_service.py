import urllib.parse
import json
import numpy as np
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
    def extract_search_query(url: str) -> Optional[str]:
        """Extracts the query terms from search engine URLs (Google, Bing, DuckDuckGo, Perplexity)."""
        if not url:
            return None
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        query_params = urllib.parse.parse_qs(parsed.query)

        # Google, Bing, DuckDuckGo usually use 'q'
        if any(engine in netloc for engine in ["google", "bing", "duckduckgo", "perplexity"]):
            q = query_params.get("q")
            if q:
                return q[0].strip()
        # Yahoo uses 'p'
        elif "yahoo" in netloc:
            p = query_params.get("p")
            if p:
                return p[0].strip()
                
        return None

    @staticmethod
    def calculate_engagement(duration: int, scroll_depth: int, revisits: int) -> float:
        """Calculates a weighted engagement score on a 0-100 scale."""
        # 1. Time duration points: up to 40% (maxes out at 120 seconds)
        time_points = min(duration / 120.0, 1.0) * 40.0
        
        # 2. Scroll depth points: up to 40%
        scroll_points = (min(scroll_depth, 100) / 100.0) * 40.0
        
        # 3. Revisit points: up to 20% (reaches max at 2 revisits)
        revisit_points = min(revisits * 10.0, 20.0)
        
        return round(time_points + scroll_points + revisit_points, 1)

    @staticmethod
    def assign_topic_cluster(
        db: Session,
        user_id: str,
        query_text: str,
        vector_store
    ) -> models.TopicCluster:
        """
        Embeds the query text and assigns it to a similar TopicCluster using cosine similarity.
        Creates a new TopicCluster if similarity < 0.75.
        """
        # Generate 384d vector embedding of the query
        embeddings = vector_store._get_embeddings([query_text])
        query_vec = embeddings[0] if len(embeddings) > 0 else np.zeros(384)
        
        # Fetch existing user topic clusters
        clusters = db.query(models.TopicCluster).filter_by(user_id=user_id).all()
        best_cluster = None
        best_similarity = -1.0
        
        for cluster in clusters:
            if not cluster.embedding_id:
                continue
            try:
                cluster_vec = np.array(json.loads(cluster.embedding_id)).astype('float32')
                # Calculate cosine similarity (normalized vectors dot product)
                sim = float(np.dot(query_vec, cluster_vec))
                if sim > best_similarity:
                    best_similarity = sim
                    best_cluster = cluster
            except Exception:
                continue
                
        # Link to best match if similarity threshold is met (e.g. 0.75)
        if best_cluster and best_similarity >= 0.75:
            print(f"TopicCluster: Grouped '{query_text}' into existing cluster: '{best_cluster.topic_name}' (sim: {best_similarity:.2f})")
            return best_cluster
            
        # Otherwise, create a new TopicCluster
        # Use first 3 words of query as the topic name
        words = query_text.split()
        topic_name = " ".join(words[:3]).capitalize() + " Research"
        
        new_cluster = models.TopicCluster(
            user_id=user_id,
            topic_name=topic_name,
            embedding_id=json.dumps(query_vec.tolist())
        )
        db.add(new_cluster)
        db.commit()
        db.refresh(new_cluster)
        print(f"TopicCluster: Created new cluster: '{topic_name}' for query: '{query_text}'")
        return new_cluster

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
            status="pending",
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
