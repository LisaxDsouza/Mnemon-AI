import datetime
import re
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models

load_dotenv()

class SessionClusterer:
    def __init__(self):
        # Removed Groq client completely to avoid credit dependency
        pass

    def _clean_title(self, title: str) -> str:
        """Strips common browser title suffixes (e.g. - Google Search, - GitHub, | Medium)."""
        if not title:
            return "Untitled Page"
        # Split by typical title dividers: ' - ', ' | ', ' — ', ' – ' and take the first segment
        cleaned = re.split(r'\s+[-|—–]\s+', title)[0]
        return cleaned.strip()

    def _determine_topic(self, title: str, source_type: str) -> str:
        """Determines the session topic category based on keywords in the cleaned title."""
        if not title:
            return "General Browsing"
            
        title_lower = title.lower()
        
        # Local keyword-to-topic dictionary mapping
        keyword_map = {
            "Software Engineering": [
                "react", "vue", "js", "ts", "javascript", "typescript", "python", 
                "next.js", "rust", "html", "css", "api", "code", "programming", 
                "github", "git", "web dev", "developer", "hooks", "components"
            ],
            "DevOps & Databases": [
                "docker", "kubernetes", "aws", "nginx", "db", "postgres", "sqlite", 
                "mysql", "redis", "devops", "cloud", "server", "hosting", "sql", "migration"
            ],
            "Query Research": [
                "google", "search", "query", "bing", "yahoo", "wikipedia", "lookup"
            ]
        }
        
        for topic, keywords in keyword_map.items():
            for kw in keywords:
                if kw in title_lower:
                    return topic
                    
        # Fallback category
        if source_type:
            if source_type == "web" or source_type == "articles":
                return "General Web"
            return source_type.capitalize()
            
        return "General Browsing"

    def run_clustering(self, db: Session, user_id: str) -> int:
        """Finds unclustered memory events and groups them chronologically and semantically using local heuristics."""
        # Fetch unclustered events
        events = db.query(models.MemoryEvent).filter_by(
            user_id=user_id, session_id=None
        ).order_by(models.MemoryEvent.created_at.asc()).all()
        
        if len(events) < 2:
            return 0  # Need at least two events to cluster
            
        # Group chronologically (within 30 minutes threshold)
        clusters = []
        current_cluster = [events[0]]
        
        for i in range(1, len(events)):
            prev_event = events[i-1]
            curr_event = events[i]
            
            time_diff = (curr_event.created_at - prev_event.created_at).total_seconds()
            
            # If time gap is less than 30 minutes (1800s), group together
            if time_diff < 1800:
                current_cluster.append(curr_event)
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [curr_event]
                
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)
            
        sessions_created = 0
        
        # Local heuristic processing of each cluster (Zero LLM/Zero Credit)
        for cluster in clusters:
            # 1. Find the primary event (highest engagement_score, tiebreak with duration)
            primary_event = cluster[0]
            max_score = -1.0
            
            for ev in cluster:
                score = ev.engagement_score or 0.0
                if score > max_score:
                    max_score = score
                    primary_event = ev
                elif score == max_score:
                    # Tie breaker: choose longest duration
                    if (ev.duration_seconds or 0) > (primary_event.duration_seconds or 0):
                        primary_event = ev
            
            # 2. Extract clean title
            cleaned_title = self._clean_title(primary_event.title)
            
            # 3. Dynamic Title Generation
            if len(cluster) > 1:
                session_title = f"{cleaned_title} & {len(cluster) - 1} other tabs"
            else:
                session_title = cleaned_title
                
            # 4. Dynamic Topic Mapping
            session_topic = self._determine_topic(cleaned_title, primary_event.source_type)
            
            # 5. Local Summary Formatting
            started_at = cluster[0].created_at
            ended_at = cluster[-1].created_at
            duration_mins = max(1, int((ended_at - started_at).total_seconds() / 60))
            
            if len(cluster) > 1:
                session_summary = (
                    f"Local browsing workflow focused on '{cleaned_title}' ({primary_event.url}) "
                    f"with {len(cluster) - 1} other related pages spanning {duration_mins} minutes."
                )
            else:
                session_summary = f"Local browsing workflow focused on '{cleaned_title}' ({primary_event.url})."
                
            try:
                # Create new Session
                session = models.Session(
                    user_id=user_id,
                    title=session_title,
                    topic=session_topic,
                    summary=session_summary,
                    started_at=started_at,
                    ended_at=ended_at
                )
                db.add(session)
                db.flush()  # Generates session.id
                
                # Link events to the session
                for ev in cluster:
                    ev.session_id = session.id
                    
                sessions_created += 1
                print(f"Clustering (Local Heuristic): Created session '{session_title}' in '{session_topic}' category.")
            except Exception as e:
                print(f"Clustering: Failed to create session: {e}")
                
        db.commit()
        return sessions_created
