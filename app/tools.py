import os
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

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

# This is the ToolNode for the graph
inspector_tools = ToolNode([list_files, read_file])