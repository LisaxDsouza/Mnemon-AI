import time
import requests
import json

BACKEND_URL = "http://localhost:8000"

def run_integration_test():
    print("="*60)
    print("RECALL AI BACKEND INTEGRATION TEST")
    print("="*60)
    
    # 1. Check health
    try:
        health = requests.get(f"{BACKEND_URL}/")
        print(f"[*] API Health Check: Status Code {health.status_code} - {health.json()}")
    except Exception as e:
        print(f"[!] API is offline. Make sure to run 'python backend/main.py' first. Error: {e}")
        return

    # 2. Simulate User Onboarding Signup
    signup_payload = {
        "email": "test_developer@recall.ai",
        "allowed_categories": ["articles", "youtube", "github", "pdf"],
        "blocked_domains": ["reddit.com", "facebook.com"],
        "privacy_mode": "balanced"
    }
    signup_res = requests.post(f"{BACKEND_URL}/auth/signup", json=signup_payload)
    print(f"[*] Onboarding Signup: {signup_res.json()}")
    user_id = signup_res.json().get("user_id")

    # 3. Simulate capture of a blocked domain
    blocked_payload = {
        "url": "https://www.facebook.com/messages",
        "title": "Facebook Messages",
        "tab_id": 999,
        "user_id": user_id
    }
    blocked_res = requests.post(f"{BACKEND_URL}/capture", json=blocked_payload)
    print(f"[*] Capture Blocked Domain Test: {blocked_res.json()}")

    # 4. Simulate capture of a valid page
    capture_payload = {
        "url": "https://en.wikipedia.org/wiki/Recall",
        "title": "Recall - Wikipedia",
        "tab_id": 1001,
        "user_id": user_id
    }
    capture_res = requests.post(f"{BACKEND_URL}/capture", json=capture_payload)
    capture_data = capture_res.json()
    print(f"[*] Capture Valid Domain Test: {capture_data}")
    event_id = capture_data.get("event_id")

    # 5. Simulate engagement under threshold
    engage_low = {
        "tab_id": 1001,
        "duration": 5,
        "scroll_depth": 10,
        "user_id": user_id
    }
    engage_low_res = requests.post(f"{BACKEND_URL}/engagement", json=engage_low)
    print(f"[*] Engagement (Low Metric): {engage_low_res.json()}")

    # 6. Simulate engagement crossing threshold (auto-extraction)
    engage_high = {
        "tab_id": 1001,
        "duration": 25,
        "scroll_depth": 50,
        "user_id": user_id
    }
    engage_high_res = requests.post(f"{BACKEND_URL}/engagement", json=engage_high)
    print(f"[*] Engagement (High Metric -> Auto Extract): {engage_high_res.json()}")

    # Wait for background extraction
    print("[*] Waiting 5 seconds for background document extraction & FAISS indexing...")
    time.sleep(5)

    # 7. Add second document to enable session clustering
    capture_payload2 = {
        "url": "https://en.wikipedia.org/wiki/Information_retrieval",
        "title": "Information Retrieval - Wikipedia",
        "tab_id": 1002,
        "user_id": user_id
    }
    capture_res2 = requests.post(f"{BACKEND_URL}/capture", json=capture_payload2)
    event_id2 = capture_res2.json().get("event_id")
    
    engage_high2 = {
        "tab_id": 1002,
        "duration": 25,
        "scroll_depth": 50,
        "user_id": user_id
    }
    requests.post(f"{BACKEND_URL}/engagement", json=engage_high2)
    print("[*] Logged second capture page and queued extraction.")
    
    print("[*] Waiting 5 seconds for second page extraction...")
    time.sleep(5)

    # 8. Trigger Session Clustering
    cluster_res = requests.post(f"{BACKEND_URL}/sessions/trigger-clustering?user_id={user_id}")
    print(f"[*] Session Clustering Agent Run: {cluster_res.json()}")

    # 9. List Sessions
    sessions_res = requests.get(f"{BACKEND_URL}/sessions?user_id={user_id}")
    sessions_list = sessions_res.json()
    print(f"[*] Clustered Sessions List (Count: {len(sessions_list)}):")
    for s in sessions_list:
        print(f"    - Session: {s['title']} | Topic: {s['topic']}")
        print(f"      Summary: {s['summary']}")

    # 10. Multi-Agent RAG Query
    query_payload = {
        "query": "What is recall in the context of information retrieval?",
        "user_id": user_id
    }
    query_res = requests.post(f"{BACKEND_URL}/query", json=query_payload)
    query_data = query_res.json()
    
    print(f"[*] Multi-Agent Retrieval Query: '{query_payload['query']}'")
    print(f"    Answer: {query_data.get('answer')}")
    if query_data.get('citation'):
        print(f"    Citation Quote: \"{query_data['citation']['quote']}\"")
        print(f"    Source URL: {query_data['citation']['url']}")

    # 11. Profile Reflection
    reflection_res = requests.get(f"{BACKEND_URL}/privacy/reflection?user_id={user_id}")
    print(f"[*] Learning Profile Reflection: {reflection_res.json()}")

    print("="*60)
    print("TEST SUITE COMPLETED SUCCESSFULLY")
    print("="*60)

if __name__ == "__main__":
    run_integration_test()
