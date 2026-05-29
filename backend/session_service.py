import datetime
import urllib.parse
import json
import re
import numpy as np
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import models

# Global Groq Setup
import os
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except:
        pass

class SessionService:
    @staticmethod
    def _get_domain(url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                return netloc[4:]
            return netloc
        except:
            return ""

    @staticmethod
    def calculate_closeness(
        event_a: models.MemoryEvent,
        event_b: models.MemoryEvent,
        vector_store
    ) -> float:
        """
        Closeness Score = 0.20 * T_prox + 0.05 * D_sim + 0.40 * S_match + 0.25 * V_sim + 0.10 * R_tab
        """
        # 1. Time Proximity (Max weight 20%)
        t_diff = abs((event_b.created_at - event_a.created_at).total_seconds())
        if t_diff <= 600: # 10 mins
            t_prox = 1.0
        elif t_diff >= 1800: # 30 mins
            t_prox = 0.0
        else:
            # Linear decay from 10 to 30 mins
            t_prox = 1.0 - ((t_diff - 600) / 1200.0)
            
        # 2. Domain Similarity (Max weight 5%)
        dom_a = SessionService._get_domain(event_a.url)
        dom_b = SessionService._get_domain(event_b.url)
        d_sim = 1.0 if (dom_a and dom_a == dom_b) else 0.0
        
        # 3. Search Intent Matching (Max weight 40%)
        s_match = 0.0
        meta_a = event_a.metadata_json or {}
        meta_b = event_b.metadata_json or {}
        
        q_a = meta_a.get("search_query")
        q_b = meta_b.get("search_query")
        
        # Check topic clusters similarity
        tc_a = meta_a.get("topic_cluster_id")
        tc_b = meta_b.get("topic_cluster_id")
        if tc_a and tc_b and tc_a == tc_b:
            s_match = 1.0
        elif q_a and q_b:
            # Query word overlap
            words_a = set(q_a.lower().split())
            words_b = set(q_b.lower().split())
            if words_a.intersection(words_b):
                s_match = 0.8
        elif q_a or q_b:
            # One is a search, check if keywords appear in the other's title
            query_term = q_a if q_a else q_b
            other_title = (event_b.title or "") if q_a else (event_a.title or "")
            if query_term and other_title:
                words = set(query_term.lower().split())
                title_words = set(other_title.lower().split())
                if words.intersection(title_words):
                    s_match = 0.9

        # 4. Semantic Similarity (Max weight 25%)
        v_sim = 0.0
        title_a = event_a.title or ""
        title_b = event_b.title or ""
        if title_a and title_b:
            try:
                embeds = vector_store._get_embeddings([title_a, title_b])
                if len(embeds) == 2:
                    sim = float(np.dot(embeds[0], embeds[1]))
                    v_sim = max(0.0, sim) # scale to [0,1] assuming normalized vectors
            except Exception as e:
                print(f"Sessionize: vector similarity calculation failed: {e}")
                
        # 5. Tab interaction (Max weight 10%)
        tab_a = meta_a.get("tab_id")
        tab_b = meta_b.get("tab_id")
        r_tab = 1.0 if (tab_a is not None and tab_a == tab_b) else 0.0
        
        closeness = (0.20 * t_prox) + (0.05 * d_sim) + (0.40 * s_match) + (0.25 * v_sim) + (0.10 * r_tab)
        return closeness

    @staticmethod
    def sessionize_events(db: Session, user_id: str, vector_store) -> int:
        """Groups all unclustered MemoryEvents into Sessions."""
        events = db.query(models.MemoryEvent).filter_by(
            user_id=user_id, session_id=None
        ).order_by(models.MemoryEvent.created_at.asc()).all()
        
        if not events:
            return 0
            
        # Group events by closeness threshold >= 0.5
        groups = []
        if events:
            current_group = [events[0]]
            for i in range(1, len(events)):
                prev = events[i-1]
                curr = events[i]
                closeness = SessionService.calculate_closeness(prev, curr, vector_store)
                if closeness >= 0.50:
                    current_group.append(curr)
                else:
                    groups.append(current_group)
                    current_group = [curr]
            groups.append(current_group)
            
        sessions_created = 0
        for grp in groups:
            # Spin up a Session row
            started_at = grp[0].created_at
            ended_at = grp[-1].created_at
            
            # Generate local dynamic heuristic title as a baseline
            primary_ev = grp[0]
            for ev in grp:
                if (ev.engagement_score or 0) > (primary_ev.engagement_score or 0):
                    primary_ev = ev
                    
            clean_title = re.split(r'\s+[-|—–]\s+', primary_ev.title or "Untitled Page")[0].strip()
            topic = "General Learning"
            if "youtube" in primary_ev.source_type.lower():
                topic = "Video Research"
            elif "github" in primary_ev.source_type.lower():
                topic = "Code Engineering"
            
            summary = f"Browsing session focusing on {clean_title} containing {len(grp)} event(s)."
            intent = f"Research related to {clean_title}."
            
            # Create session model
            session = models.Session(
                user_id=user_id,
                title=clean_title,
                summary=summary,
                intent=intent,
                started_at=started_at,
                ended_at=ended_at,
                status="closed"
            )
            db.add(session)
            db.flush()
            
            # Assign events
            for ev in grp:
                ev.session_id = session.id
                
            # Perform Groq summaries if client exists
            SessionService.summarize_session_llm(session, grp)
            
            # Trigger Thread linkage/clustering
            SessionService.link_session_to_thread(db, user_id, session, vector_store)
            
            sessions_created += 1
            
        db.commit()
        return sessions_created

    @staticmethod
    def summarize_session_llm(session: models.Session, events: List[models.MemoryEvent]):
        """Runs LLM Llama summaries using Groq API client."""
        if not groq_client:
            return
            
        # Compile list of URLs and titles visited
        pages_summary = ""
        for idx, ev in enumerate(events):
            pages_summary += f"- Title: {ev.title or 'Unknown'} | URL: {ev.url or ''}\n"
            
        system_prompt = """You are a cognitive workflow reconstruction assistant.
Analyze the browsing history segment of the user and output a JSON block with exactly these 4 fields:
{
  "title": "<Short, specific title representing the task context>",
  "intent": "<Clear statement describing user's goal or what they were trying to learn/build>",
  "summary": "<A 2-sentence summary of their search and browsing pattern>",
  "resources": ["<resource URL 1>", "<resource URL 2>", ...]
}

Return ONLY the raw JSON block without markdown fences or headers."""

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Browsing activities:\n{pages_summary}"}
                ],
                temperature=0.3,
                max_tokens=384
            )
            content = response.choices[0].message.content.strip()
            # Strip markdown formatting
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
            
            data = json.loads(content)
            
            session.title = data.get("title") or session.title
            session.intent = data.get("intent") or session.intent
            
            res_list = data.get("resources", [])
            resources_str = "\n".join(res_list) if res_list else ""
            session.summary = (data.get("summary") or session.summary) + f"\n\nKey Resources:\n{resources_str}"
            
        except Exception as e:
            print(f"Sessionize: Groq session summarization failed: {e}")

    @staticmethod
    def link_session_to_thread(
        db: Session,
        user_id: str,
        session: models.Session,
        vector_store
    ):
        """Task 7 & 8: Matches the session to an active or past thread, or creates a new Thread."""
        # Find active threads for the user
        active_threads = db.query(models.Thread).filter_by(user_id=user_id, status="active").all()
        best_thread = None
        best_similarity = -1.0
        
        session_intent = session.intent or session.title or ""
        
        # 1. semantic clustering lookup
        if active_threads and session_intent:
            try:
                thread_titles = [t.title or "" for t in active_threads]
                texts = [session_intent] + thread_titles
                embeds = vector_store._get_embeddings(texts)
                if len(embeds) > 1:
                    sess_vec = embeds[0]
                    for idx, thread in enumerate(active_threads):
                        th_vec = embeds[idx + 1]
                        sim = float(np.dot(sess_vec, th_vec))
                        if sim > best_similarity:
                            best_similarity = sim
                            best_thread = thread
            except Exception as e:
                print(f"Threading: Cosine match failed: {e}")
                
        # Link to thread if similarity >= 0.70
        if best_thread and best_similarity >= 0.70:
            session.thread_id = best_thread.id
            print(f"Threading: Assigned session '{session.title}' to Thread '{best_thread.title}' (sim: {best_similarity:.2f})")
            
            # Update thread title and summary using Groq if possible
            if groq_client:
                SessionService._update_thread_summary_llm(db, best_thread)
        else:
            # Create a brand new Thread
            # Get clean topic name for thread title
            thread_title = session.title or "New Research Thread"
            if len(thread_title) > 50:
                thread_title = thread_title[:47] + "..."
                
            new_thread = models.Thread(
                user_id=user_id,
                title=thread_title,
                summary=session.summary or "Long-term learning thread.",
                status="active"
            )
            db.add(new_thread)
            db.flush()
            session.thread_id = new_thread.id
            print(f"Threading: Spawned new thread: '{new_thread.title}'")

    @staticmethod
    def _update_thread_summary_llm(db: Session, thread: models.Thread):
        """Regenerates thread summary incorporating the newly linked session details."""
        linked_sessions = db.query(models.Session).filter_by(thread_id=thread.id).all()
        sessions_summary = ""
        for s in linked_sessions:
            sessions_summary += f"- Session: {s.title}\n  Intent: {s.intent}\n  Summary: {s.summary}\n"
            
        system_prompt = """You are a research summarizer.
Synthesize the titles and intents of multiple browsing sessions into a single Thread context.
Output a JSON block with exactly these two fields:
{
  "title": "<Consolidated learning thread title>",
  "summary": "<Overall summary of the ongoing research goal and progress>"
}
Keep it brief."""

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Sessions in Thread:\n{sessions_summary}"}
                ],
                temperature=0.3,
                max_tokens=256
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
            
            data = json.loads(content)
            thread.title = data.get("title") or thread.title
            thread.summary = data.get("summary") or thread.summary
        except Exception as e:
            print(f"Threading: Failed to regenerate summary: {e}")
