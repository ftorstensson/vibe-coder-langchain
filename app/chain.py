# app/chain.py
import os
import uuid
from fastapi import FastAPI
from typing_extensions import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, END
from langgraph_checkpoint_firestore import FirestoreSaver
from langgraph.prebuilt import ToolNode, create_react_agent
from langserve import add_routes
from google.cloud.firestore_v1 import Client

from app.tools import inspector_tools, list_files, read_file

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["supervisor", "inspector", "__end__"]

llm = ChatVertexAI(
    model_name="gemini-1.5-flash",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location="australia-southeast1",
    temperature=0,
)

inspector_agent = create_react_agent(llm, tools=[list_files, read_file])

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Project Manager. If the user wants to list files, read files, or inspect code -> respond with exactly one word: inspector. Otherwise, answer directly and finish."""),
    ("placeholder", "{messages}")
])
supervisor = supervisor_prompt | llm

def sanitize_messages(messages):
    safe = []
    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            safe.append(msg)
        else:
            safe.append(AIMessage(content=str(msg.content)))
    return safe

def supervisor_node(state: AgentState):
    print("---SUPERVISOR NODE---")
    safe_msgs = sanitize_messages(state["messages"])
    response = supervisor.invoke({"messages": safe_msgs})
    if response.content.strip().lower() == "inspector":
        return {"next": "inspector"}
    else:
        return {"messages": [response], "next": "__end__"}

def inspector_node(state: AgentState):
    print("---INSPECTOR NODE---")
    safe_msgs = sanitize_messages(state["messages"])
    result = inspector_agent.invoke({"messages": safe_msgs})
    return {"messages": result["messages"]}

workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("inspector", inspector_node)
workflow.add_node("tools", inspector_tools)
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", lambda s: s.get("next", "__end__"), {"inspector": "inspector", "__end__": END})
workflow.add_edge("inspector", "tools")
workflow.add_edge("tools", "supervisor")

# THE FINAL FIX: Patched FirestoreSaver to handle the NoneType bug
class FixedFirestoreSaver(FirestoreSaver):
    async def aput(self, config, checkpoint, metadata, new_versions=None):
        configurable = config.setdefault("configurable", {})
        if configurable.get("checkpoint_id") is None:
            configurable["checkpoint_id"] = str(uuid.uuid4())
        if configurable.get("checkpoint_ns") is None:
            configurable["checkpoint_ns"] = ""
        return await super().aput(config, checkpoint, metadata, new_versions)

checkpointer = FixedFirestoreSaver(
    project_id="vibe-agent-final",
    checkpoints_collection="checkpoints"
)
graph = workflow.compile(checkpointer=checkpointer)

app = FastAPI(title="Vibe Coder LangGraph Agency")
add_routes(app, graph, path="/agent")

@app.get("/health")
def health():
    return {"status": "IT WORKS"}