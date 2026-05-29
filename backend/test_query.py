import os
import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Append parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vector_store import VectorStoreManager
import models
from database import SessionLocal

def run_db_query(query_text: str):
    print(f"Initializing VectorStoreManager...")
    v = VectorStoreManager()
    
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(email="default@recall.ai").first()
        user_id = user.id if user else "default-user"
        print(f"Using User ID: {user_id}")
        
        # Fetch allowed event IDs matching extracted articles/webpages
        allowed_events = db.query(models.MemoryEvent).filter(
            models.MemoryEvent.user_id == user_id,
            models.MemoryEvent.status == "extracted"
        ).all()
        allowed_ids = [e.id for e in allowed_events]
        print(f"Total extracted documents in DB: {len(allowed_ids)}")
        
        print(f"Running Hybrid Query: '{query_text}'...\n")
        results = v.query(
            query_text=query_text,
            user_id=user_id,
            allowed_event_ids=allowed_ids,
            n_results=15
        )
        
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        
        if not docs:
            print("No matching candidate chunks found.")
            return
            
        print("=== FINAL RETRIEVED CHUNKS IN TEST SCRIPT ===")
        for idx, (doc, meta) in enumerate(zip(docs, metas)):
            print(f"\n[{idx + 1}] Source: {meta.get('title')} ({meta.get('location')})")
            print(f"    URL: {meta.get('url')}")
            print(f"    Content: {doc}")
            print("-" * 50)
            
    finally:
        db.close()

if __name__ == "__main__":
    query = "what was that article about google drive engine"
    run_db_query(query)
