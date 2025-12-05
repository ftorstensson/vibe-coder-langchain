"""
VIBE CODER - BACKEND BRAIN (v24.0 - Custom Engine)
Updated: 2025-12-05
Features:
- CustomFirestoreSaver (Bypasses buggy library completely)
- Hybrid Gemini 2.5
- Time-Sortable Checkpoint IDs
"""

import os
import uuid
import time
import asyncio
from google.cloud import firestore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any, Dict, AsyncIterator
from typing_extensions import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langserve import add_routes
from pydantic import BaseModel, Field
from app.tools import inspector_tools, list_files, read_file, write_file

# --- CUSTOM SAVER IMPORTS ---
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# --- 1. INITIALIZATION ---
db = firestore.Client(project=os.environ.get("GCP_PROJECT", "vibe-agent-final"))

def get_agent_config(agent_id: str):
    doc = db.collection("agent_configs").document(agent_id).get()
    if doc.exists: return doc.to_dict()
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

llm_flash = ChatVertexAI(
    model_name="gemini-2.5-flash",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location=REGION,
    temperature=0.1,
    safety_settings=safety_settings,
)

llm_pro = ChatVertexAI(
    model_name="gemini-2.5-pro",
    project=os.environ.get("GCP_PROJECT", "vibe-agent-final"),
    location=REGION,
    temperature=0.5,
    safety_settings=safety_settings,
)

# --- 3. AGENTS ---
architect_agent = create_react_agent(llm_flash, tools=[write_file, read_file], state_modifier=architect_config.get("system_prompt"))
frontend_agent = create_react_agent(llm_flash, tools=[write_file, read_file, list_files], state_modifier=frontend_config.get("system_prompt"))

# --- 4. SUPERVISOR ---
class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["supervisor", "technical_architect", "head_of_frontend", "__end__"]

class RoutingDecision(BaseModel):
    reasoning: str = Field(description="Brief thought process.")
    action: Literal["delegate_to_architect", "delegate_to_frontend", "respond_to_user"] = Field(description="Next step.")
    response_content: str = Field(description="Response text.")

supervisor_router = llm_pro.with_structured_output(RoutingDecision)
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", pm_config.get("system_prompt")),
    MessagesPlaceholder(variable_name="messages"),
])
supervisor = supervisor_prompt | supervisor_router

def supervisor_node(state: AgentState):
    print(f"--- SUPERVISOR NODE (History Length: {len(state['messages'])}) ---")
    
    safe_messages = []
    for msg in state["messages"]:
        if hasattr(msg, "content") and not isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            safe_messages.append(AIMessage(content=str(msg.content)))
        else:
            safe_messages.append(msg)
    
    decision: RoutingDecision = supervisor.invoke({"messages": safe_messages})
    print(f"--- DECISION: {decision.action} ---")
    
    if decision.action == "delegate_to_architect":
        return {"messages": [HumanMessage(content=decision.response_content, name="Supervisor")], "next": "technical_architect"}
    elif decision.action == "delegate_to_frontend":
        return {"messages": [HumanMessage(content=decision.response_content, name="Supervisor")], "next": "head_of_frontend"}
    else:
        return {"messages": [AIMessage(content=decision.response_content)], "next": "__end__"}

def architect_node(state: AgentState):
    return {"messages": architect_agent.invoke(state)["messages"]}

def frontend_node(state: AgentState):
    return {"messages": frontend_agent.invoke(state)["messages"]}

# --- 5. TOPOLOGY ---
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("technical_architect", architect_node)
workflow.add_node("head_of_frontend", frontend_node)
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", lambda s: s.get("next"), {"technical_architect": "technical_architect", "head_of_frontend": "head_of_frontend", "__end__": END})
workflow.add_edge("technical_architect", "supervisor")
workflow.add_edge("head_of_frontend", "supervisor")

# --- 6. THE CUSTOM ENGINE (Grok's Option 3 - Modified) ---
class CustomFirestoreSaver(BaseCheckpointSaver):
    def __init__(self, client: firestore.Client, collection: str = "checkpoints"):
        super().__init__(serde=JsonPlusSerializer())
        self.client = client
        self.collection = collection

    # Synchronous Get (Required by BaseCheckpointSaver)
    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        # Get the LATEST checkpoint by sorting descending
        query = (
            self.client.collection(self.collection)
            .where("thread_id", "==", thread_id)
            .order_by("checkpoint_id", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(query.stream())
        
        if not docs:
            return None
            
        data = docs[0].to_dict()
        checkpoint = self.serde.loads(data["checkpoint"])
        metadata = self.serde.loads(data["metadata"])
        # Reconstruct config
        final_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": data.get("checkpoint_ns", ""),
                "checkpoint_id": data["checkpoint_id"]
            }
        }
        return CheckpointTuple(final_config, checkpoint, metadata, None)

    # Async Get (Required)
    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    # List (Stubbed - Not strictly needed for basic flow)
    def list(self, config: Optional[Dict[str, Any]], *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        return [] # Placeholder

    async def alist(self, config: Optional[Dict[str, Any]], *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        return [] # Placeholder

    # Async Put
    async def aput(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        
        # ID GENERATION STRATEGY: Time-Sortable
        # If ID is missing, generate one that is alphabetically consistently increasing
        if config["configurable"].get("checkpoint_id"):
             checkpoint_id = config["configurable"]["checkpoint_id"]
        else:
             checkpoint_id = f"{int(time.time()*1000)}_{str(uuid.uuid4())[:8]}"
        
        # Serialize
        doc_data = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "checkpoint": self.serde.dumps(checkpoint),
            "metadata": self.serde.dumps(metadata),
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        # Write (Async via thread)
        doc_ref = self.client.collection(self.collection).document(f"{thread_id}_{checkpoint_id}")
        await asyncio.to_thread(doc_ref.set, doc_data)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id
            }
        }

    # Sync Put (Required)
    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        # Not used by async runner but good to have
        return {}

# COMPILE WITH CUSTOM ENGINE
checkpointer = CustomFirestoreSaver(db, "custom_checkpoints")
graph = workflow.compile(checkpointer=checkpointer)

app = FastAPI(title="Vibe Coder LangGraph Agency")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vibe-coder-frontend-534939227554.australia-southeast1.run.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_routes(app, graph, path="/agent")

@app.get("/health")
def health(): return {"status": "IT WORKS"}