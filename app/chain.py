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
from langgraph.prebuilt import create_react_agent
from langserve import add_routes
from google.cloud.firestore_v1 import Client

from app.tools import inspector_tools, list_files, read_file, write_file

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["supervisor", "inspector", "__end__"]

# THE FINAL, STRATEGIC UPGRADE: Change region to access the superior model
llm = ChatVertexAI(
    model_name="gemini-2.0-flash",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location="us-central1", # Using a region where the model is available
    temperature=0,
)

inspector_agent = create_react_agent(llm, tools=[list_files, read_file, write_file])

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Project Manager for The Everything Agency. Your job is to delegate tasks or summarize results.

CRITICAL RULES:
1. Review the most recent message in the conversation.
2. If the most recent message is from a HUMAN asking to READ, WRITE, LIST, or MODIFY files, you MUST delegate to the Inspector. To do this, respond with only the single word: inspector
3. If the most recent message is a TOOL response, your job is to summarize this result for the human user. Provide a concise, helpful summary of what was done, and then you are finished.
4. For any other general conversation, respond directly to the human.
"""),
    ("placeholder", "{messages}")
])
supervisor = supervisor_prompt | llm

def supervisor_node(state: AgentState):
    print("---SUPERVISOR NODE---")
    safe_messages = []
    for msg in state["messages"]:
        if hasattr(msg, "content") and not isinstance(msg, (HumanMessage, AIMessage)):
            safe_messages.append(AIMessage(content=str(msg.content)))
        else:
            safe_messages.append(msg)
    
    response = supervisor.invoke({"messages": safe_messages})
    if response.content.strip().lower() == "inspector":
        return {"next": "inspector"}
    else:
        return {"messages": [response], "next": "__end__"}

def inspector_node(state: AgentState):
    print("---INSPECTOR NODE---")
    safe_messages = []
    for msg in state["messages"]:
        if hasattr(msg, "content") and not isinstance(msg, (HumanMessage, AIMessage)):
            safe_messages.append(AIMessage(content=str(msg.content)))
        else:
            safe_messages.append(msg)
            
    result = inspector_agent.invoke({"messages": safe_messages})
    return {"messages": result["messages"]}

workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("inspector", inspector_node)
workflow.add_node("tools", inspector_tools)
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", lambda s: s.get("next"), {"inspector": "inspector", "__end__": END})
workflow.add_edge("inspector", "tools")
workflow.add_edge("tools", "supervisor")

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