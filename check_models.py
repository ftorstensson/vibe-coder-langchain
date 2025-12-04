import os
from langchain_google_vertexai import ChatVertexAI

project_id = "vibe-agent-final"
location = "us-central1"

# The Grok Candidate List
candidates = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-pro-001",
    "gemini-2.5-flash-001",
    "gemini-2.0-flash-001" # Control group (known good)
]

print(f"--- Probing 2.5 Models in {location} ---")
for model in candidates:
    try:
        llm = ChatVertexAI(model_name=model, project=project_id, location=location, max_retries=0)
        llm.invoke("test")
        print(f"✅ AVAILABLE: {model}")
    except Exception as e:
        if "404" in str(e) or "NotFound" in str(e):
            print(f"❌ NOT FOUND: {model}")
        else:
            print(f"⚠️  ERROR ({model}): {str(e)[:100]}...")
