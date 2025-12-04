"""
VIBE CODER - BACKEND BRAIN (v21.0 - Gemini 2.5 Hybrid)
Updated: 2025-12-05
Features:
- PM Model: Gemini 2.5 Pro (High Reasoning, confirmed available)
- Worker Models: Gemini 2.5 Flash (High Speed, confirmed available)
- Region: us-central1
- Architecture: Database-Driven Personas + Linear Delegation
"""

import os
import uuid
from google.cloud import firestore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing_extensions import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory
from langgraph.graph import StateGraph, END
from langgraph_checkpoint_firestore import FirestoreSaver
from langgraph.prebuilt import create_react_agent
from langserve import add_routes
from pydantic import BaseModel, Field
from app.tools import inspector_tools, list_files, read_file, write_file

# --- 1. INITIALIZATION ---
db = firestore.Client(project=os.environ.get("GCP_PROJECT", "vibe-agent-final"))

def get_agent_config(agent_id: str):
    print(f"--- FETCHING CONFIG FOR: {agent_id} ---")
    doc = db.collection("agent_configs").document(agent_id).get()
    if doc.exists:
        return doc.to_dict()
    else:
        return {"system_prompt": "You are a helpful AI assistant."}

pm_config = get_agent_config("project_manager")
architect_config = get_agent_config("technical_architect")
frontend_config = get_agent_config("head_of_frontend")

# --- 2. MODEL SETUP ---
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
}

REGION = "us-central1"

# WORKER MODEL: Gemini 2.5 Flash (Confirmed Available)
llm_flash = ChatVertexAI(
    model_name="gemini-2.5-flash",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location=REGION,
    temperature=0.1,
    safety_settings=safety_settings,
)

# PM MODEL: Gemini 2.5 Pro (Confirmed Available)
llm_pro = ChatVertexAI(
    model_name="gemini-2.5-pro",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location=REGION,
    temperature=0.5, # Warm Vibe
    safety_settings=safety_settings,
)

# --- 3. AGENTS (Powered by Flash) ---
architect_agent = create_react_agent(
    llm_flash, 
    tools=[write_file, read_file],
    state_modifier=architect_config.get("system_prompt")
)

frontend_agent = create_react_agent(
    llm_flash, 
    tools=[write_file, read_file, list_files],
    state_modifier=frontend_config.get("system_prompt")
)

# --- 4. SUPERVISOR (Powered by Pro) ---
class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["supervisor", "technical_architect", "head_of_frontend", "__end__"]

class RoutingDecision(BaseModel):
    reasoning: str = Field(description="Brief thought process.")
    action: Literal["delegate_to_architect", "delegate_to_frontend", "respond_to_user"] = Field(
        description="Select 'delegate_to_architect' for planning. Select 'delegate_to_frontend' for coding. Select 'respond_to_user' to brainstorm, ask clarifying questions, or present results."
    )
    response_content: str = Field(
        description="If responding, the text. If delegating, the specific instruction for the agent."
    )

supervisor_router = llm_pro.with_structured_output(RoutingDecision)

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", pm_config.get("system_prompt")),
    MessagesPlaceholder(variable_name="messages"),
])
supervisor = supervisor_prompt | supervisor_router

def supervisor_node(state: AgentState):
    print("---SUPERVISOR NODE (Gemini 2.5 Pro)---")
    safe_messages = []
    for msg in state["messages"]:
        if hasattr(msg, "content") and not isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            safe_messages.append(AIMessage(content=str(msg.content)))
        else:
            safe_messages.append(msg)
    
    decision: RoutingDecision = supervisor.invoke({"messages": safe_messages})
    print(f"---DECISION: {decision.action}---")
    
    if decision.action == "delegate_to_architect":
        directive = HumanMessage(content=decision.response_content, name="Supervisor")
        return {"messages": [directive], "next": "technical_architect"}
    elif decision.action == "delegate_to_frontend":
        directive = HumanMessage(content=decision.response_content, name="Supervisor")
        return {"messages": [directive], "next": "head_of_frontend"}
    else:
        ai_msg = AIMessage(content=decision.response_content)
        return {"messages": [ai_msg], "next": "__end__"}

def architect_node(state: AgentState):
    print("---ARCHITECT NODE (2.5 Flash)---")
    result = architect_agent.invoke(state)
    return {"messages": result["messages"]}

def frontend_node(state: AgentState):
    print("---FRONTEND NODE (2.5 Flash)---")
    result = frontend_agent.invoke(state)
    return {"messages": result["messages"]}

# --- 5. TOPOLOGY ---
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("technical_architect", architect_node)
workflow.add_node("head_of_frontend", frontend_node)

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor", 
    lambda s: s.get("next"), 
    {
        "technical_architect": "technical_architect",
        "head_of_frontend": "head_of_frontend", 
        "__end__": END
    }
)

workflow.add_edge("technical_architect", "supervisor")
workflow.add_edge("head_of_frontend", "supervisor")

# --- 6. APP ---
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://vibe-coder-frontend-534939227554.australia-southeast1.run.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_routes(app, graph, path="/agent")

@app.get("/health")
def health():
    return {"status": "IT WORKS"}