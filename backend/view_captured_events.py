import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "recall_ai.db")
if not os.path.exists(db_path):
    print(f"Database file not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, url, title, event_type, source_type, created_at FROM memory_events ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    
    print("\n=== LATEST 10 EVENTS IN DATABASE ===")
    if not rows:
        print("Database is empty (no events captured yet).")
    for row in rows:
        print(f"ID: {row[0][:8]}... | Type: {row[3]} | Source: {row[4]} | Title: {row[2][:30]} | URL: {row[1][:40]} | Created: {row[5]}")
except Exception as e:
    print("Error querying database:", e)
finally:
    conn.close()
