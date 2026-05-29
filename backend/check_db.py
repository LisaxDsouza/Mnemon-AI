import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "recall_ai.db")
if not os.path.exists(db_path):
    print(f"Error: Database file does not exist at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print("Tables currently in SQLite database:")
print("-" * 40)
for t in sorted(tables):
    print(f"- {t}")
conn.close()
