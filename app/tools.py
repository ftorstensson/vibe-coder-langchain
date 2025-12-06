import os
from typing import List, Optional
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from google.cloud import firestore

# Initialize DB for Tools
db = firestore.Client(project=os.environ.get("GCP_PROJECT", "vibe-agent-final"))

@tool
def list_files(path: str = ".") -> str:
    """List files in a directory."""
    try:
        return "\n".join(sorted(os.listdir(path)))
    except Exception as e:
        return f"Error: {e}"

@tool
def read_file(path: str) -> str:
    """Read a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content[:200_000] + ("\n...[truncated]" if len(content) > 200_000 else "")
    except Exception as e:
        return f"Error reading {path}: {e}"

@tool
def write_file(path: str, content: str, append: bool = False) -> str:
    """Write content to a file. Creates the directory if it doesn't exist."""
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"Error writing to {path}: {e}"

@tool
def update_board(thread_id: str, phase: str, tasks: List[str], status: str) -> str:
    """
    Updates the visual Project Board for the user.
    Args:
        thread_id: The ID of the current conversation (You MUST get this from your context).
        phase: The current phase (e.g., 'Discovery', 'Blueprint', 'Coding').
        tasks: A list of specific todo items (e.g., ['Create Repo', 'Design DB']).
        status: A brief status update (e.g., 'Architecting the solution...').
    """
    try:
        doc_ref = db.collection("project_boards").document(thread_id)
        doc_ref.set({
            "phase": phase,
            "tasks": tasks,
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP
        }, merge=True)
        return f"Successfully updated Board for thread {thread_id}."
    except Exception as e:
        return f"Error updating board: {e}"

# Export the tools list
inspector_tools = ToolNode([list_files, read_file, write_file, update_board])