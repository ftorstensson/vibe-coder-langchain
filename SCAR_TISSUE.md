# Scar Tissue Ledger (v2.0) - The LangGraph War

This document contains the hard-won, battle-tested lessons learned from catastrophic failures. These are not theories; they are unbreakable laws paid for with time and frustration. This document MUST be consulted before debugging any deployment issues.

---

### **Entry 015: The "Nested Agent" Recursion Loop**

*   **Symptom:** A Supervisor delegates to a Sub-Agent (e.g., Inspector). The graph enters an infinite loop until it hits `GraphRecursionError` (limit 25).
*   **Diagnosis:** The Sub-Agent was a `create_react_agent`, which has its own internal "Think-Act-Observe" loop. When it finished, it returned a final text response. The outer graph topology was `inspector -> tools -> supervisor`. The Supervisor saw the Inspector's final answer, treated it as new input, and re-delegated it, causing the loop.
*   **The Unbreakable Fix:** **Linear Delegation Topology.** If a Sub-Agent is autonomous (like a ReAct agent), it must route to `END`, not back to the Supervisor. The job is done when the Sub-Agent speaks.
*   **Golden Path Topology:**
    ```python
    workflow.add_conditional_edges("supervisor", lambda s: s.get("next"), {"inspector": "inspector", "__end__": END})
    workflow.add_edge("inspector", END) # Do NOT go back to Supervisor
    ```

---

### **Entry 014: The "Consecutive AI Message" Crash (Error 400)**

*   **Symptom:** The application crashes with `InvalidArgument: 400 Please ensure that the number of function response parts is equal to the number of function call parts`.
*   **Diagnosis:** The Supervisor output an `AIMessage` ("Delegating..."), and then the Inspector immediately ran and generated another `AIMessage` (Tool Call). This created a history sequence of `[Human, AI, AI]`. The Gemini API strictly forbids consecutive AI turns; there must be a User turn in between.
*   **The Unbreakable Fix:** **The "Human Injection" Pattern.** The Supervisor must NOT output an `AIMessage` when delegating. Instead, it should inject a `HumanMessage` into the state, acting as a proxy for the user's intent. This satisfies the `User -> Model -> User` requirement.
*   **Golden Path Code:**
    ```python
    if decision.action == "delegate":
        # Inject a directive as if it were a user speaking
        directive = HumanMessage(content="Execute this request...", name="Supervisor")
        return {"messages": [directive], "next": "inspector"}
    ```

---

### **Entry 013: The Gemini "Silent Refusal" (Zero-Token Output)**

*   **Symptom:** The LLM returns an empty string `content=''` with `usage_metadata={'output_tokens': 0}`. No error is raised, but the logic fails.
*   **Diagnosis:** This occurs with `gemini-2.0-flash` at `temperature=0` when using strict System Prompts (e.g., "Output only one word"). The model's safety/chat-tuning conflicts with the constraint, causing it to "refuse" by saying nothing.
*   **The Unbreakable Fix:** **Structured Output (JSON Mode).** Do not rely on string parsing for routing. Use `.with_structured_output(PydanticSchema)`. This forces the model into a validation mode that bypasses the "chatty" refusal triggers. Also, raise `temperature` slightly (e.g., `0.1`).
*   **Golden Path Code:**
    ```python
    class RoutingDecision(BaseModel):
        action: Literal["delegate", "respond"]
    
    router = llm.with_structured_output(RoutingDecision)
    ```

---

### **Entry 012: The `FixedFirestoreSaver` Bug and Patch**

*   **Symptom:** After resolving all dependency and code issues, the application crashes on the first invocation of a new thread with a `TypeError: sequence item 2: expected str instance, NoneType found`.
*   **Diagnosis:** This is a confirmed bug in the `langgraph-checkpoint-firestore==0.1.7` library. The `aput` method does not correctly handle the case where `checkpoint_id` is `None` on the initial write for a new thread.
*   **The Unbreakable Fix:** Implement a patched `FixedFirestoreSaver` class that inherits from the original. This class must override the `aput` method to check for and forcefully set a `checkpoint_id` (e.g., using `uuid.uuid4()`) if one does not exist, before calling the parent method with the corrected config.
*   **Golden Path Code:**
    ```python
    import uuid
    from langgraph_checkpoint_firestore import FirestoreSaver

    class FixedFirestoreSaver(FirestoreSaver):
        async def aput(self, config, checkpoint, metadata, new_versions=None):
            configurable = config.setdefault("configurable", {})
            if configurable.get("checkpoint_id") is None:
                configurable["checkpoint_id"] = str(uuid.uuid4())
            if configurable.get("checkpoint_ns") is None:
                configurable["checkpoint_ns"] = ""
            return await super().aput(config, checkpoint, metadata, new_versions)
    ```
---

### **Entry 011: The Supervisor's Infinite Loop (GraphRecursionError)**

*   **Symptom:** A multi-agent graph with a Supervisor -> Worker -> Supervisor loop executes perfectly but never finishes. The local server logs show the nodes repeating in a perfect cycle (`---SUPERVISOR NODE---`, `---INSPECTOR NODE---`, `---SUPERVISOR NODE---`...) until the application crashes with `langgraph.errors.GraphRecursionError: Recursion limit reached`.
*   **Diagnosis:** This is a critical failure of agent logic. The Supervisor's prompt is too simplistic. After the Worker agent (Inspector) successfully uses a tool and the graph returns to the Supervisor, the Supervisor sees the new `ToolMessage` in the history. Its simple logic ("if a tool is involved, delegate") fires again, causing it to re-delegate the same completed task in an infinite loop.
*   **The Unbreakable Fix:** The Supervisor's prompt **MUST** include an explicit "off-ramp." It needs to be instructed on what to do *after* a tool has been successfully used. The best practice is for it to summarize the tool's output for the user and then terminate the workflow.
*   **Golden Path Prompt Logic:**
    ```
    1. If the HUMAN asks for a tool-related task -> Delegate.
    2. If the last message is a TOOL response -> Summarize the response and FINISH.
    3. Otherwise -> Respond directly.
    ```
---

### **Entry 010: The Docker "Input/Output Error" Paradox**

*   **Symptom:** The `docker build` or `docker push` command fails with a cryptic, low-level error like `input/output error` or `failed to commit snapshot`. The deployed application in Cloud Run does not reflect the latest local code, creating a paradox where the cloud logs show errors that have already been fixed locally.
*   **Diagnosis:** This is a definitive sign of a **corrupted local Docker Desktop environment**. The Docker VM's internal filesystem is in a broken state, preventing new images from being built or pushed correctly.
*   **The Unbreakable Fix:** Do not waste time debugging the code. The environment is the problem. Apply the "Disposable Environment" principle:
    1.  **Quit Docker Desktop.**
    2.  **Reset to Factory Defaults:** Use the "Troubleshoot" menu in Docker Desktop to perform a full reset. This is the "nuke" option.
    3.  **Restart Docker Desktop.**
    4.  **Re-authenticate:** Run `gcloud auth configure-docker` to restore the connection to your Artifact Registry.
*   **Golden Path Command:** `gcloud auth configure-docker [REGION]-docker.pkg.dev`

---

### **Entry 009: The Gemini `BaseMessage` Rejection**

*   **Symptom:** A running LangGraph application crashes mid-execution with `ValueError: Unexpected message with type <class 'langchain_core.messages.base.BaseMessage'>`. This typically happens in a node that is being called for the *second* time in a loop (e.g., a Supervisor node after a Tool node has executed).
*   **Diagnosis:** The `langchain-google-vertexai` library for Gemini is extremely strict. It only accepts concrete `HumanMessage` or `AIMessage` types in its history. When a `ToolNode` executes, it adds a `ToolMessage` to the state. If this state is passed back to a simple LLM chain (like our Supervisor), the Gemini API rejects the history because it contains a `ToolMessage`.
*   **The Unbreakable Fix:** Before invoking any simple LLM chain, sanitize the message history. Create a "safe" list of messages where any non-standard message (like `ToolMessage`) is converted into a generic `AIMessage`.
*   **Golden Path Code:**
    ```python
    def supervisor_node(state: AgentState):
        safe_messages = []
        for msg in state["messages"]:
            if hasattr(msg, "content") and not isinstance(msg, (HumanMessage, AIMessage)):
                safe_messages.append(AIMessage(content=str(msg.content)))
            else:
                safe_messages.append(msg)
        response = supervisor.invoke({"messages": safe_messages})
        # ... rest of the node logic
    ```

---

### **Entry 008: The `ModuleNotFoundError` Cascade (Dependency Hell)**

*   **Symptom:** The container crashes on startup with `ModuleNotFoundError` for a module that appears to be part of an installed library (e.g., `langgraph.checkpoint.firestore` or `langgraph.graph.message`).
*   **Diagnosis:** This indicates a severe "Version Congruence Failure." The root cause is a set of incompatible dependencies in `requirements.txt`. A silent `pip install` failure or a mismatch between library versions (e.g., `langserve` requiring an older `sse-starlette`, or a library expecting a different version of `langchain-core`) is preventing the required modules from being correctly installed or accessed.
*   **The Unbreakable Fix:** Do not attempt to fix dependencies one by one. Use a known-good, fully pinned `requirements.txt` file that has been battle-tested. Verify all dependencies locally with `pip install -r requirements.txt` in a clean virtual environment (`.venv`) *before* attempting a Docker build.
*   **Golden Path Command:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

---

### **Entry 007: The LangServe `config_keys` Paradox (CRITICAL)**

*   **Symptom:** A perfectly deployed LangGraph application with a Firestore checkpointer crashes on every invocation with `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id...`. This happens even when the `curl` command correctly provides a `thread_id` in the `config` block.
*   **Diagnosis:** This is a catastrophic, silent bug in the interaction between LangServe and LangGraph. The `config_keys=["configurable"]` argument in the `add_routes` function **incorrectly modifies the structure of the config object** before passing it to the graph. It strips the `"configurable"` wrapper that the checkpointer is hardcoded to expect, causing the checkpointer to see an empty config and fail.
*   **The Unbreakable Fix:** **NEVER** use the `config_keys` argument in `add_routes` when serving a stateful LangGraph with a checkpointer.
*   **Golden Path Code:**
    ```python
    add_routes(
        app,
        compiled_graph,
        path="/agent",
        # DO NOT ADD config_keys HERE
        playground_type="default",
    )
    ```
---

### **Entry 006: The Environmental Parity Failure (Local vs. Cloud Build)**

*   **Symptom:** A `Dockerfile` and `requirements.txt` that build and run perfectly on a local machine (e.g., macOS) fail catastrophically during the `pip install` phase when deployed with `gcloud run deploy --source .`. The error is often a long, complex compilation failure (e.g., for `protobuf` or `grpcio`) that times out after 10 minutes.
*   **Diagnosis:** This is a fundamental **Environmental Parity Failure**. The local machine often downloads pre-compiled binary packages ("wheels") that are specific to its architecture (e.g., macOS, ARM64). The clean Linux environment used by Google Cloud Build may not have a pre-compiled wheel available for that specific combination of library, Python version, and architecture. It therefore falls back to compiling the package from source, which can fail due to missing system-level C++ compilers or other dependencies not present in the base `python:slim` image.
*   **The Unbreakable Fix (The "Local Push" Workflow):** Do not fight the cloud build environment. Trust the environment that works. The immediate and authoritative solution is to bypass Cloud Build entirely.
    1.  **Build the container on the local machine**, where it is proven to work: `docker build -t [image_name] .`
    2.  **Tag that proven artifact** for your cloud registry: `docker tag [image_name] [gcr_path]`
    3.  **Push the finished artifact:** `docker push [gcr_path]`
    4.  **Deploy the pre-built artifact:** `gcloud run deploy --image [gcr_path]`
*   **Codified Law:** This workflow is now enshrined in the Foundation Document as the primary method for establishing a Stable Bedrock when dependency compilation issues arise. The `gcloud run deploy --source .` command is now considered high-risk.

---

### **Entry 005: The LangChain Golden Path**

*   **Symptom:** All attempts to deploy a Google ADK agent to Cloud Run result in a catastrophic loop of `TypeError`, `ModuleNotFoundError`, and other startup failures.
*   **Diagnosis:** The Google ADK library (as of late 2025, `v1.17.0` - `v1.18.0`) is an experimental, unstable framework not yet suitable for production deployment. Its API changes rapidly and without clear documentation, and its tooling is unreliable.
*   **The Unbreakable Fix (Strategic Pivot):** Abandon the ADK entirely. Rebuild the foundation on a mature, battle-tested framework: **LangChain**.
*   **Golden Path Lessons:**
    *   **The `requirements.txt` is ground truth:** The only reliable source for package versions is the PyPI registry. The final working `requirements.txt` was built using flexible, stable version ranges (e.g., `langchain>=1.0.0,<2.0.0`).
    *   **The Error is the Manual:** LangServe requires the `sse-starlette` package for streaming, a fact only revealed by the `ImportError` in the logs. Trust the error message.
    *   **The Schema is the Law:** The `langserve` `/invoke` endpoint requires a specific nested JSON object: `{"input": {"chain_input_key": "value"}}`. The server's own validation errors are the final source of truth for the correct request structure.

---

### **Entry 004: The `pip install git+` Dependency Chain**

*   **Symptom A:** The `docker build` process fails during `RUN pip install` with the error `Cannot find command 'git'`.
*   **Diagnosis A:** The base `python:slim` Docker image does not include the `git` client. `pip` requires `git` to be installed in the container's environment to fetch packages from a GitHub URL.
*   **The Unbreakable Fix A:** Add a `RUN apt-get update && apt-get install -y git` layer to the `Dockerfile` *before* the `pip install` command.

*   **Symptom B:** The `pip install` command fails with a `ResolutionImpossible` error due to conflicting dependencies between `fastapi` and a git-installed package (`google-adk`).
*   **Diagnosis B:** Pinning specific versions of high-level application frameworks (`fastapi==x.y.z`) can create conflicts with the dependencies of other libraries.
*   **The Unbreakable Fix B:** In `requirements.txt`, pin the version of the most critical or sensitive library (in our case, `google-adk`). For general-purpose frameworks like `fastapi`, `uvicorn`, and `gunicorn`, remove the version pins to allow `pip`'s dependency resolver the flexibility to find a compatible set of versions that satisfies all requirements.

---

### **Entry 003: The Local Docker Environment**

*   **Symptom A:** `docker: command not found` when running a local build script.
*   **Diagnosis A:** Docker Desktop is not installed or not running.
*   **Fix A:** Install and run the Docker Desktop application.

*   **Symptom B:** `error from registry: Unauthenticated request` when pushing an image.
*   **Diagnosis B:** The local Docker engine is not authenticated with Google Cloud's Artifact Registry.
*   **Fix B:** Run the one-time setup command: `gcloud auth configure-docker [REGION]-docker.pkg.dev`.

---

### **Entry 002: The `gcloud logs` Command Hallucination**

*   **Symptom:** Repeated attempts to view Cloud Run logs fail with `Invalid choice: 'tail'` or `unrecognized arguments: --stream`.
*   **Diagnosis:** The AI's internal knowledge of the `gcloud` CLI was catastrophically wrong and outdated. It was hallucinating commands (`tail`) and flags (`--stream`) that do not exist in the `gcloud run services logs` command group.
*   **The Unbreakable Fix:** The only source of truth for a CLI command is the tool's own help flag. The command `gcloud run services logs --help` revealed that `read` is the only valid command. Never trust an AI's memory of a CLI command; always verify with `--help` when in doubt.
*   **Golden Path Command:** `gcloud run services logs read [SERVICE_NAME] --region [REGION]`

---

### **Entry 001: The Gunicorn/FastAPI Language Mismatch**

*   **Symptom:** A successfully deployed Cloud Run service returns a `500 Internal Server Error`. The logs show a `TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'`.
*   **Diagnosis:** This is a fundamental incompatibility between a WSGI server (Gunicorn's default) and an ASGI application (FastAPI). The server is speaking the wrong language to the application, causing an immediate crash on request.
*   **The Unbreakable Fix:** The `Dockerfile`'s `CMD` line for Gunicorn **MUST** specify the `uvicorn.workers.UvicornWorker` class using the `-k` flag. This forces Gunicorn to speak ASGI.
*   **Golden Path Command:** `CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]`

---