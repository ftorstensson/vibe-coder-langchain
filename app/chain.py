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
    ("system", "You are the Project Manager for The Everything Agency. Your role is to collaborate with the Creative Director (the user) to brainstorm and refine ideas. You are the user's single point of contact. Begin the conversation by introducing yourself and stating your purpose."),
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

app = FastAPI(title="Vibe Coder — The Everything Agency PM")

add_routes(
    app,
    chain_with_history,
    path="/agent",
    config_keys=["configurable"],
    playground_type="default"
)

@app.get("/health")
def health():
    return {"status": "EVERYTHING AGENCY PM IS ALIVE AND WELL"}

@app.post("/reset")
def reset():
    store.clear()
    return {"status": "memory cleared"}