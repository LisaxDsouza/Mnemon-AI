import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "recall_ai.db")
if not os.path.exists(db_path):
    print(f"Error: Database file does not exist at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get latest artifacts joined with their memory events
query = """
SELECT 
    a.id, 
    a.location, 
    a.content, 
    m.title, 
    m.url, 
    m.event_type, 
    m.status
FROM artifacts a
JOIN memory_events m ON a.event_id = m.id
ORDER BY a.created_at DESC
LIMIT 10;
"""

try:
    cursor.execute(query)
    rows = cursor.fetchall()
    print("=== LATEST 10 ARTIFACTS IN DATABASE ===")
    print(f"Total Artifacts in DB: {conn.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]}\n")
    
    if not rows:
        print("No artifacts found yet. Make sure you browse a page and let it extract.")
    else:
        for row in rows:
            art_id, loc, content, title, url, ev_type, status = row
            print(f"Artifact ID: {art_id[:8]}...")
            print(f"Parent Event: {title} | Type: {ev_type} | Status: {status}")
            print(f"Location: {loc}")
            print(f"Content: {content[:150]}...")
            print("-" * 50)
            
except Exception as e:
    print(f"Error querying artifacts: {e}")

conn.close()
