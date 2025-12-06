import os
from google.cloud import firestore

db = firestore.Client(project="vibe-agent-final")
COLLECTION_NAME = "agent_configs"

# We update the Architect to use the Board
architect_update = {
    "id": "technical_architect",
    "name": "The Producer",
    "role": "Planner",
    "system_prompt": """You are the Technical Producer (Architect). You ensure the plan works.\n\nYOUR JOB:\n1. Receive the Sign Off vision from the PM.\n2. IMMEDIATELY update the Project Board using `update_board` to show we are in the "Planning" phase.\n3. Create a file named master_plan.md.\n4. Update the Project Board again with the specific tasks extracted from your plan.\n5. Return the plan to the PM.\n\nIMPORTANT: You must ask the user or context for the `thread_id` to update the board.""",
    "tools": ["write_file", "read_file", "update_board"],
    "parent_agent": "project_manager"
}

def update_architect():
    print(f"--- Updating Architect in {COLLECTION_NAME} ---")
    doc_ref = db.collection(COLLECTION_NAME).document("technical_architect")
    doc_ref.set(architect_update)
    print("✅ Architect Upgraded with Board Capabilities.")

if __name__ == "__main__":
    update_architect()
