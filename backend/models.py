import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# Helper function to generate string UUIDs
def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, nullable=True)
    
    # Relationships
    threads = relationship("Thread", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("MemoryEvent", back_populates="user", cascade="all, delete-orphan")
    reflections = relationship("Reflection", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("RecallQuery", back_populates="user", cascade="all, delete-orphan")
    privacy_preferences = relationship("PrivacyPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    blocked_domains = relationship("BlockedDomain", back_populates="user", cascade="all, delete-orphan")
    category_permissions = relationship("CategoryPermission", back_populates="user", cascade="all, delete-orphan")
    deletion_requests = relationship("DeletionRequest", back_populates="user", cascade="all, delete-orphan")

class Thread(Base):
    __tablename__ = "threads"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String, default="active", index=True)  # active, completed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="threads")
    sessions = relationship("Session", back_populates="thread", cascade="all, delete-orphan")
    reflections = relationship("Reflection", back_populates="thread", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    thread_id = Column(String, ForeignKey("threads.id"), nullable=True, index=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    intent = Column(Text, nullable=True)
    status = Column(String, default="active", index=True)  # active, closed
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    thread = relationship("Thread", back_populates="sessions")
    memories = relationship("MemoryEvent", back_populates="session", cascade="all, delete-orphan")

class MemoryEvent(Base):
    __tablename__ = "memory_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True, index=True)
    event_type = Column(String, index=True)  # SEARCH, ARTICLE, VIDEO, GITHUB, PDF, DOCUMENTATION
    source_type = Column(String, index=True)  # youtube, github, pdf, web, search
    title = Column(String, nullable=True)
    url = Column(String, nullable=True)
    duration_seconds = Column(Integer, default=0)
    scroll_depth = Column(Integer, default=0)
    engagement_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_json = Column(JSON, nullable=True)
    
    status = Column(String, default="pending", index=True)  # pending, extracted, failed, ignored
    
    # Content Preview preserved for frontend timeline compatibility
    content_preview = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="memories")
    session = relationship("Session", back_populates="memories")
    artifacts = relationship("Artifact", back_populates="memory_event", cascade="all, delete-orphan")

class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    event_id = Column(String, ForeignKey("memory_events.id"), index=True)
    content = Column(Text, nullable=False)
    location = Column(String, nullable=True)  # e.g., Page 1, Timestamp 02:30
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    memory_event = relationship("MemoryEvent", back_populates="artifacts")

class Reflection(Base):
    __tablename__ = "reflections"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    thread_id = Column(String, ForeignKey("threads.id"), index=True)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="reflections")
    thread = relationship("Thread", back_populates="reflections")

class TopicCluster(Base):
    __tablename__ = "topic_clusters"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    topic_name = Column(String)
    embedding_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RecallQuery(Base):
    __tablename__ = "recall_queries"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    query = Column(Text)
    response_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="queries")

class PrivacyPreference(Base):
    __tablename__ = "privacy_preferences"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    privacy_mode = Column(String, default="balanced")  # balanced, strict, local
    cloud_sync_enabled = Column(Boolean, default=True)
    local_only_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="privacy_preferences")

class BlockedDomain(Base):
    __tablename__ = "blocked_domains"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    domain = Column(String, index=True)
    wildcard = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="blocked_domains")

class CategoryPermission(Base):
    __tablename__ = "category_permissions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    category = Column(String)  # articles, youtube, github, pdf, social_media, ai_chats, etc.
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="category_permissions")

class DeletionRequest(Base):
    __tablename__ = "deletion_requests"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    request_type = Column(String)  # delete_session, delete_all, delete_domain
    status = Column(String, default="pending")  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="deletion_requests")
