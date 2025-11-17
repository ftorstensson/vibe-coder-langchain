# app/chain.py
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langserve import add_routes
from fastapi import FastAPI

# 1. Define our LLM (Language Model)
# This connects to Gemini in your Google Cloud project.
llm = ChatVertexAI(
    model_name="gemini-1.5-flash",
    project="vibe-agent-final",
    location="australia-southeast1",
    temperature=0
)

# 2. Define our Prompt Template
# This tells the LLM how to behave.
prompt = ChatPromptTemplate.from_template(
    "You are a helpful assistant. Answer the question: {input}"
)

# 3. Define our Agent Chain
# This chains the components together: Prompt -> LLM -> Output Parser
chain = prompt | llm | StrOutputParser()

# 4. Create the FastAPI Application
app = FastAPI(
    title="LangChain Vibe Coder",
    description="A simple, single-agent API server.",
    version="1.0.0"
)

# 5. Add the LangServe Routes
# This automatically creates the /invoke, /batch, etc. endpoints for our chain.
add_routes(app, chain, path="/agent")

# 6. Add a Health Check Endpoint
# This is critical for Cloud Run to know the server started correctly.
@app.get("/health")
def health():
    return {"status": "healthy"}