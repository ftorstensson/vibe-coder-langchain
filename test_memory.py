import requests, uuid

LOCAL_URL = "http://localhost:8000/agent/invoke"
CLOUD_URL = "https://vibe-coder-langchain-534939227554.australia-southeast1.run.app/agent/invoke"

def test(url, name):
    tid = f"test-{uuid.uuid4().hex[:6]}"
    secret = f"KEY-{uuid.uuid4().hex[:4]}"
    print(f"\n--- {name} ({tid}) ---")
    try:
        print(f"1. Telling secret: {secret}")
        requests.post(url, json={"input": {"messages": [{"type": "human", "content": f"My secret code is {secret}. Remember it."}]}, "config": {"configurable": {"thread_id": tid}}})
        print(f"2. Asking for secret...")
        res = requests.post(url, json={"input": {"messages": [{"type": "human", "content": "What is my secret code?"}]}, "config": {"configurable": {"thread_id": tid}}})
        ans = res.json().get("output", {}).get("messages", [])[-1]["content"]
        print(f"3. Agent said: {ans}")
        if secret in ans: print("✅ SUCCESS: Memory works.")
        else: print("❌ FAILURE: Amnesia detected.")
    except Exception as e: print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    test(LOCAL_URL, "Local")
    test(CLOUD_URL, "Cloud")
