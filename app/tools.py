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

@tool
def write_file(path: str, content: str, append: bool = False) -> str:
    """Write content to a file. Creates the directory if it doesn't exist. Use append=True to add to the end of the file."""
    try:
        # Ensure the directory exists
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        # Determine the mode
        mode = 'a' if append else 'w'
        
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"Error writing to {path}: {e}"

# This is the ToolNode for the graph, now including the new tool
inspector_tools = ToolNode([list_files, read_file, write_file])