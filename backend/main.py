import os
import sys
import uuid
import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uvicorn
import urllib.parse

# Import local modules
sys.path.append(os.path.dirname(__file__))
from database import get_db, init_db
import models
from vector_store import VectorStoreManager
from parsers import get_parser_for_url
from agents import AgenticRetrievalSystem
from clustering import SessionClusterer

# Initialize DB on start
init_db()

app = FastAPI(title="Recall AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n[ROUTE ERROR] {request.method} {request.url.path}")
    print(tb)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": str(exc),
            "type": type(exc).__name__,
            "traceback": tb
        }
    )

# Initialize Managers
vector_store = VectorStoreManager()
agent_system = AgenticRetrievalSystem(vector_store)
clusterer = SessionClusterer()

# Default Pause State (in-memory pause tracking)
PAUSE_REGISTRY: Dict[str, datetime.datetime] = {}

# Default Blocked Domain Keywords
DEFAULT_BLOCKED_KEYWORDS = [
    "paypal.com",
    "stripe.com",
    "bank",
    "auth",
    "signin",
    "login",
    "1password.com",
    "lastpass.com",
    "checkout",
    "portal",
    "identity",
    "security"
]

# --- Schema Definitions ---

class SignupRequest(BaseModel):
    email: str
    allowed_categories: List[str]  # e.g., ["articles", "youtube", "github", "pdf"]
    blocked_domains: List[str]      # e.g., ["reddit.com", "facebook.com"]
    privacy_mode: Optional[str] = "balanced"

class CaptureRequest(BaseModel):
    url: str
    title: str
    tab_id: int
    user_id: Optional[str] = "default-user"

class EngagementRequest(BaseModel):
    tab_id: int
    duration: int  # in seconds
    scroll_depth: int  # percentage (0-100)
    user_id: Optional[str] = "default-user"

class PauseRequest(BaseModel):
    duration_minutes: int
    user_id: Optional[str] = "default-user"

class BlockedDomainCreate(BaseModel):
    domain: str
    wildcard: Optional[bool] = False
    user_id: Optional[str] = "default-user"

class PrivacyPreferenceUpdate(BaseModel):
    privacy_mode: str  # balanced, strict, local
    cloud_sync_enabled: bool
    user_id: Optional[str] = "default-user"

class CategoryToggleRequest(BaseModel):
    category: str
    enabled: bool
    user_id: Optional[str] = "default-user"

class AgentQueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = "default-user"

class DeletionRequestSchema(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = "default-user"

# --- Helper Methods ---

def get_or_create_default_user(db: Session) -> models.User:
    """Ensures a default user exists for quick setup and testing."""
    user = db.query(models.User).filter_by(email="default@recall.ai").first()
    if not user:
        user = models.User(id="default-user", email="default@recall.ai")
        db.add(user)
        db.flush()
        
        privacy = models.PrivacyPreference(
            user_id=user.id,
            privacy_mode="balanced",
            cloud_sync_enabled=True,
            local_only_mode=False
        )
        db.add(privacy)
        
        default_categories = ["articles", "youtube", "github", "pdf"]
        for cat in default_categories:
            db.add(models.CategoryPermission(user_id=user.id, category=cat, enabled=True))
            
        disabled_categories = ["social_media", "ai_chats", "workspaces", "messaging"]
        for cat in disabled_categories:
            db.add(models.CategoryPermission(user_id=user.id, category=cat, enabled=False))
            
        db.commit()
    return user

def is_domain_blocked(url: str, user_id: str, db: Session) -> bool:
    """Evaluates system blocklists and custom user domains."""
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    
    for keyword in DEFAULT_BLOCKED_KEYWORDS:
        if keyword in domain or keyword in parsed_url.path.lower():
            return True
            
    user_blocks = db.query(models.BlockedDomain).filter_by(user_id=user_id).all()
    for block in user_blocks:
        block_domain = block.domain.lower()
        if block.wildcard:
            if block_domain in domain:
                return True
        else:
            if domain == block_domain or domain.endswith("." + block_domain):
                return True
                
    return False

def get_source_category(url: str) -> str:
    parsed_url = urllib.parse.urlparse(url)
    netloc = parsed_url.netloc.lower()
    
    if "youtube.com" in netloc or "youtu.be" in netloc:
        return "youtube"
    elif "github.com" in netloc:
        return "github"
    elif url.lower().endswith('.pdf'):
        return "pdf"
    elif "google.com" in netloc and "/search" in parsed_url.path:
        return "search"
    return "articles"

def is_category_allowed(url: str, user_id: str, db: Session) -> bool:
    category = get_source_category(url)
    if category == "search":
        return True
    perm = db.query(models.CategoryPermission).filter_by(user_id=user_id, category=category).first()
    return perm.enabled if perm else True

def split_text_chunks(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

# --- Background Task Ingestion & Extraction ---

def execute_deep_extraction(event_id: str, user_id: str, url: str):
    db = next(get_db())
    try:
        event = db.query(models.MemoryEvent).filter_by(id=event_id).first()
        if not event or event.status == "extracted":
            return
            
        parser = get_parser_for_url(url)
        if not parser:
            event.status = "ignored"
            db.commit()
            return
            
        parsed_data = parser(url)
        if not parsed_data:
            event.status = "failed"
            db.commit()
            return
            
        # Task 2: Create Artifact records in database
        from event_service import EventService
        EventService.add_event_artifacts(db, event_id, parsed_data)
        
        all_chunks = []
        all_metadatas = []
        full_text_list = []
        
        for idx, item in enumerate(parsed_data):
            text = item["text"]
            location = item["metadata"].get("location", f"Section {idx+1}")
            full_text_list.append(text)
            
            chunks = split_text_chunks(text, chunk_size=800, overlap=100)
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({
                    "memory_event_id": event_id,
                    "user_id": user_id,
                    "url": url,
                    "title": event.title,
                    "source_type": event.source_type,
                    "location": location
                })
                
        if not all_chunks:
            event.status = "failed"
            db.commit()
            return
            
        vector_store.add_documents(all_chunks, all_metadatas)
        
        event.status = "extracted"
        event.content_preview = " ".join(full_text_list)[:300] + "..."
        db.commit()
        print(f"Ingestion: Indexed memory {event_id} ({url}) - {len(all_chunks)} chunks.")
    except Exception as e:
        print(f"Ingestion: Extraction failed: {e}")
        try:
            event = db.query(models.MemoryEvent).filter_by(id=event_id).first()
            if event:
                event.status = "failed"
                db.commit()
        except:
            pass

# --- API Routes ---

@app.post("/auth/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter_by(email=request.email).first()
    if existing:
        return {"status": "user_exists", "user_id": existing.id}
        
    user_id = str(uuid.uuid4())
    user = models.User(id=user_id, email=request.email)
    db.add(user)
    db.flush()
    
    privacy = models.PrivacyPreference(
        user_id=user_id,
        privacy_mode=request.privacy_mode,
        cloud_sync_enabled=True,
        local_only_mode=(request.privacy_mode == "local")
    )
    db.add(privacy)
    
    categories = ["articles", "youtube", "github", "pdf", "social_media", "ai_chats", "workspaces", "messaging"]
    for cat in categories:
        enabled = cat in request.allowed_categories
        db.add(models.CategoryPermission(user_id=user_id, category=cat, enabled=enabled))
        
    for domain in request.blocked_domains:
        if domain.strip():
            db.add(models.BlockedDomain(user_id=user_id, domain=domain.strip(), wildcard=True))
            
    db.commit()
    return {"status": "created", "user_id": user_id}

@app.post("/capture")
async def capture(request: CaptureRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    user_id = user.id if request.user_id == "default-user" else request.user_id
    
    if user_id in PAUSE_REGISTRY:
        if datetime.datetime.utcnow() < PAUSE_REGISTRY[user_id]:
            return {"status": "paused", "reason": "Tracking is temporarily paused by the user."}
            
    if is_domain_blocked(request.url, user_id, db):
        return {"status": "blocked", "reason": "Domain lies in exclusion blocklist."}
        
    if not is_category_allowed(request.url, user_id, db):
        return {"status": "disabled", "reason": "Capture is disabled for this media category."}
        
    source_type = get_source_category(request.url)
    
    existing = db.query(models.MemoryEvent).filter_by(
        user_id=user_id, url=request.url, status="pending"
    ).order_by(models.MemoryEvent.created_at.desc()).first()
    
    if existing:
        return {"status": "accepted", "event_id": existing.id, "message": "Resumed existing candidate."}
        
    from event_service import EventService
    
    # 1. Parse search query terms if it's a search URL
    search_query = EventService.extract_search_query(request.url)
    
    event = EventService.create_event(
        db=db,
        user_id=user_id,
        url=request.url,
        title=request.title,
        source_type=source_type,
        metadata_json={"tab_id": request.tab_id}
    )
    
    if event.event_type == "SEARCH" and search_query:
        # Override title to use search query term
        event.title = f"Search: {search_query}"
        
        # 2. Topic Clustering Assignment
        cluster = EventService.assign_topic_cluster(db, user_id, search_query, vector_store)
        event.metadata_json = {
            **event.metadata_json,
            "search_query": search_query,
            "topic_cluster_id": cluster.id if cluster else None,
            "topic_name": cluster.topic_name if cluster else None
        }
        
        # 3. Save directly to vector store (skips re-scraping Google DOM)
        vector_store.add_documents(
            [f"User executed a search query: '{search_query}'"],
            [{
                "memory_event_id": event.id,
                "user_id": user_id,
                "url": request.url,
                "title": event.title,
                "source_type": "search",
                "location": "Search Engine"
            }]
        )
        
        # 4. Mark status as completed
        event.status = "extracted"
        event.content_preview = f"Search Query: {search_query}"
        db.commit()
    else:
        # Enqueue deep extraction immediately
        background_tasks.add_task(execute_deep_extraction, event.id, user_id, request.url)
    
    return {"status": "accepted", "event_id": event.id}

@app.post("/engagement")
async def engagement(request: EngagementRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    user_id = user.id if request.user_id == "default-user" else request.user_id
    
    event = db.query(models.MemoryEvent).filter(
        models.MemoryEvent.user_id == user_id
    ).filter(models.MemoryEvent.metadata_json["tab_id"].as_integer() == request.tab_id).order_by(
        models.MemoryEvent.created_at.desc()
    ).first()
    
    if not event:
        return {"status": "not_found", "message": "No active capture candidate exists for this tab."}
        
    meta = event.metadata_json or {}
    revisits = meta.get("revisits", 0)
    
    # Increment revisits if user has loaded a page again in same tab
    if request.duration < event.duration_seconds:
        revisits += 1
        
    event.duration_seconds = max(event.duration_seconds, request.duration)
    event.scroll_depth = max(event.scroll_depth, request.scroll_depth)
    
    # Save revisits
    event.metadata_json = {
        **meta,
        "revisits": revisits
    }
    
    from event_service import EventService
    event.engagement_score = EventService.calculate_engagement(
        event.duration_seconds,
        event.scroll_depth,
        revisits
    )
    
    db.commit()
    return {"status": "tracking", "event_id": event.id, "score": event.engagement_score}

@app.post("/extract")
async def force_extract(event_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    event = db.query(models.MemoryEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Memory candidate not found.")
        
    background_tasks.add_task(execute_deep_extraction, event.id, event.user_id, event.url)
    return {"status": "extraction_queued"}

@app.get("/timeline")
async def get_timeline(user_id: str = "default-user", db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    memories = db.query(models.MemoryEvent).filter_by(user_id=uid).order_by(
        models.MemoryEvent.created_at.desc()
    ).all()
    
    output = []
    for m in memories:
        output.append({
            "id": m.id,
            "url": m.url,
            "title": m.title,
            "source_type": m.source_type,
            "event_type": m.event_type,
            "status": m.status,
            "duration": m.duration_seconds,
            "scroll_depth": m.scroll_depth,
            "engagement_score": m.engagement_score,
            "created_at": m.created_at.isoformat(),
            "content_preview": m.content_preview
        })
    return output

# --- Session Clustering Routes ---

from session_service import SessionService

@app.get("/sessions")
async def get_sessions(user_id: str = "default-user", db: Session = Depends(get_db)):
    """Retrieves all sessions clustered for the user, with linked memory items."""
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    sessions = db.query(models.Session).filter_by(user_id=uid).order_by(
        models.Session.started_at.desc()
    ).all()
    
    output = []
    for s in sessions:
        linked_memories = db.query(models.MemoryEvent).filter_by(session_id=s.id).all()
        mem_list = [{
            "id": m.id,
            "title": m.title,
            "url": m.url,
            "source_type": m.source_type,
            "created_at": m.created_at.isoformat()
        } for m in linked_memories]
        
        output.append({
            "id": s.id,
            "title": s.title,
            "summary": s.summary,
            "intent": s.intent,
            "started_at": s.started_at.isoformat(),
            "ended_at": s.ended_at.isoformat(),
            "thread_id": s.thread_id,
            "memories": mem_list
        })
    return output

@app.post("/sessions/trigger-clustering")
async def trigger_clustering(user_id: str = "default-user", db: Session = Depends(get_db)):
    """Manually forces semantic clustering on ungrouped memory events."""
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    created = SessionService.sessionize_events(db, uid, vector_store)
    return {"status": "success", "sessions_created": created}

@app.get("/threads")
async def get_threads(user_id: str = "default-user", db: Session = Depends(get_db)):
    """Retrieves all learning/research threads for the user with nested sessions."""
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    threads = db.query(models.Thread).filter_by(user_id=uid).order_by(
        models.Thread.created_at.desc()
    ).all()
    
    output = []
    for t in threads:
        linked_sessions = db.query(models.Session).filter_by(thread_id=t.id).all()
        sess_list = []
        for s in linked_sessions:
            linked_memories = db.query(models.MemoryEvent).filter_by(session_id=s.id).all()
            mem_list = [{
                "id": m.id,
                "title": m.title,
                "url": m.url,
                "created_at": m.created_at.isoformat()
            } for m in linked_memories]
            
            sess_list.append({
                "id": s.id,
                "title": s.title,
                "intent": s.intent,
                "summary": s.summary,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat(),
                "memories": mem_list
            })
            
        output.append({
            "id": t.id,
            "title": t.title,
            "summary": t.summary,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "sessions": sess_list
        })
    return output


# --- Agentic Search Route ---

@app.post("/query")
async def handle_agentic_query(request: AgentQueryRequest, db: Session = Depends(get_db)):
    """Executes the multi-agent search pipeline using Planner, Retriever, Timeline, and Summarizer agents."""
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    answer_res, agent_logs = agent_system.search_memories(request.query, uid, db)
    return {
        "answer": answer_res.get("answer") or answer_res.get("error"),
        "citation": answer_res.get("citation"),
        "agent_logs": agent_logs
    }

@app.get("/privacy/local-stats")
async def get_local_stats(user_id: str = "default-user", db: Session = Depends(get_db)):
    """Computes zero-credit horizontal domain statistics locally using Python Counter."""
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    events = db.query(models.MemoryEvent.url).filter_by(user_id=uid).all()
    
    from collections import Counter
    domain_counter = Counter()
    for event in events:
        if event.url:
            try:
                parsed = urllib.parse.urlparse(event.url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain:
                    domain_counter[domain] += 1
            except:
                continue
                
    top_domains = [{"domain": d, "count": c} for d, c in domain_counter.most_common(8)]
    return {"top_domains": top_domains}

@app.get("/privacy/reflection")
async def get_reflection(user_id: str = "default-user", db: Session = Depends(get_db)):
    """Zero-credit local reflection fallback mapping top domains to learning topics for the frontend."""
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    events = db.query(models.MemoryEvent.url).filter_by(user_id=uid).all()
    
    from collections import Counter
    domain_counter = Counter()
    for event in events:
        if event.url:
            try:
                parsed = urllib.parse.urlparse(event.url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain:
                    domain_counter[domain] += 1
            except:
                continue
                
    top_domains = domain_counter.most_common(3)
    total_count = sum(c for d, c in top_domains)
    
    reflections = []
    for domain, count in top_domains:
        weight = round(count / max(1, total_count), 2)
        # Derive human-friendly name (e.g. stackoverflow.com -> Stackoverflow Research)
        topic = domain.split('.')[0].capitalize() + " Learning"
        reflections.append({
            "topic": topic,
            "weight": weight,
            "rationale": f"Analyzed {count} browser learning events captured on {domain}."
        })
    return {"reflection": reflections}

# --- Deletion & Privacy Management Endpoints ---

@app.post("/privacy/delete-session")
async def delete_session(request: DeletionRequestSchema, db: Session = Depends(get_db)):
    """Deletes all events and vector embeddings associated with a single clustered session."""
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    if not request.session_id:
        raise HTTPException(status_code=400, detail="Missing session_id parameter.")
        
    session = db.query(models.Session).filter_by(id=request.session_id, user_id=uid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    # Get all linked events
    events = db.query(models.MemoryEvent).filter_by(session_id=request.session_id).all()
    for ev in events:
        # Delete from FAISS vector store
        vector_store.delete_documents(ev.id)
        # Delete from DB
        db.delete(ev)
        
    db.delete(session)
    db.commit()
    return {"status": "deleted"}

@app.post("/privacy/delete-all")
async def delete_all_memories(request: DeletionRequestSchema, db: Session = Depends(get_db)):
    """Permanently purges all user memories, sessions, and vector databases."""
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    # Delete database events
    db.query(models.MemoryEvent).filter_by(user_id=uid).delete()
    db.query(models.Session).filter_by(user_id=uid).delete()
    db.query(models.RecallQuery).filter_by(user_id=uid).delete()
    
    # Wipe vector indices
    vector_store.delete_all_documents()
    db.commit()
    return {"status": "cleared", "message": "All database and vector store content deleted."}

@app.get("/runtime-config")
async def get_runtime_config(user_id: str = "default-user", db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    
    pref = db.query(models.PrivacyPreference).filter_by(user_id=uid).first()
    cats = db.query(models.CategoryPermission).filter_by(user_id=uid).all()
    blocks = db.query(models.BlockedDomain).filter_by(user_id=uid).all()
    
    pause_active = False
    if uid in PAUSE_REGISTRY:
        pause_active = datetime.datetime.utcnow() < PAUSE_REGISTRY[uid]
        
    return {
        "privacy_mode": pref.privacy_mode if pref else "balanced",
        "capture_enabled": not pause_active,
        "blocked_domains": [b.domain for b in blocks],
        "allowed_categories": {c.category: c.enabled for c in cats},
        "capture_thresholds": {
            "min_time_seconds": 20,
            "min_scroll_depth": 40
        }
    }

@app.get("/privacy/preferences")
async def get_privacy_preferences(user_id: str = "default-user", db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    pref = db.query(models.PrivacyPreference).filter_by(user_id=uid).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Privacy settings not found.")
    return {
        "privacy_mode": pref.privacy_mode,
        "cloud_sync_enabled": pref.cloud_sync_enabled,
        "local_only_mode": pref.local_only_mode
    }

@app.post("/privacy/preferences")
async def update_privacy_preferences(request: PrivacyPreferenceUpdate, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    pref = db.query(models.PrivacyPreference).filter_by(user_id=uid).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not found.")
        
    pref.privacy_mode = request.privacy_mode
    pref.cloud_sync_enabled = request.cloud_sync_enabled
    pref.local_only_mode = (request.privacy_mode == "local")
    db.commit()
    return {"status": "updated"}

@app.get("/privacy/blocked-domains")
async def get_blocked_domains(user_id: str = "default-user", db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if user_id == "default-user" else user_id
    blocks = db.query(models.BlockedDomain).filter_by(user_id=uid).all()
    return [{"id": b.id, "domain": b.domain, "wildcard": b.wildcard} for b in blocks]

@app.post("/privacy/blocked-domains")
async def add_blocked_domain(request: BlockedDomainCreate, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    existing = db.query(models.BlockedDomain).filter_by(user_id=uid, domain=request.domain).first()
    if existing:
        return {"status": "exists", "id": existing.id}
        
    block = models.BlockedDomain(
        user_id=uid,
        domain=request.domain,
        wildcard=request.wildcard
    )
    db.add(block)
    db.commit()
    return {"status": "added", "id": block.id}

@app.delete("/privacy/blocked-domains/{block_id}")
async def delete_blocked_domain(block_id: str, db: Session = Depends(get_db)):
    block = db.query(models.BlockedDomain).filter_by(id=block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Blocked domain entry not found.")
    db.delete(block)
    db.commit()
    return {"status": "deleted"}

@app.post("/privacy/category-toggle")
async def toggle_category(request: CategoryToggleRequest, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    uid = user.id if request.user_id == "default-user" else request.user_id
    
    perm = db.query(models.CategoryPermission).filter_by(user_id=uid, category=request.category).first()
    if not perm:
        perm = models.CategoryPermission(user_id=uid, category=request.category, enabled=request.enabled)
        db.add(perm)
    else:
        perm.enabled = request.enabled
    db.commit()
    return {"status": "updated"}

@app.post("/privacy/pause")
async def pause_capture(request: PauseRequest):
    uid = "default-user" if request.user_id == "default-user" else request.user_id
    until = datetime.datetime.utcnow() + datetime.timedelta(minutes=request.duration_minutes)
    PAUSE_REGISTRY[uid] = until
    return {"status": "paused", "until": until.isoformat()}

@app.get("/")
async def root():
    return {"message": "Recall AI API is online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
