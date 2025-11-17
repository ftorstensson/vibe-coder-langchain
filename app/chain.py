from fastapi import FastAPI
from langserve import add_routes
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.memory import ChatMessageHistory

# One global store per process (perfect for Cloud Run demo)
store: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

llm = ChatVertexAI(
    model_name="gemini-1.5-flash",
    project="vibe-agent-final",
    location="australia-southeast1",
    temperature=0
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are Vibe Coder — a super helpful assistant with perfect memory."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
])

chain = prompt | llm

chain_with_history = RunnableWithMessageHistory(
    runnable=chain,
    get_session_history=get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

app = FastAPI(title="Vibe Coder — FINAL & 100% WORKING")

add_routes(
    app,
    chain_with_history,
    path="/agent",
    config_keys=["configurable"],
    playground_type="chat"
)

@app.get("/health")
def health():
    return {"status": "VIBE CODER IS ALIVE AND WELL"}

@app.post("/reset")
def reset():
    store.clear()
    return {"status": "memory cleared"}