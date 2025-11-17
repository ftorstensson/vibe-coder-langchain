# Scar Tissue Ledger (v1.0) - Mission: "The Golden Path"

This document contains the hard-won, battle-tested lessons learned from catastrophic failures. These are not theories; they are unbreakable laws paid for with time and frustration. This document MUST be consulted before debugging any deployment issues.

---

### **Entry 001: The Gunicorn/FastAPI Language Mismatch**

*   **Symptom:** A successfully deployed Cloud Run service returns a `500 Internal Server Error`. The logs show a `TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'`.
*   **Diagnosis:** This is a fundamental incompatibility between a WSGI server (Gunicorn's default) and an ASGI application (FastAPI). The server is speaking the wrong language to the application, causing an immediate crash on request.
*   **The Unbreakable Fix:** The `Dockerfile`'s `CMD` line for Gunicorn **MUST** specify the `uvicorn.workers.UvicornWorker` class using the `-k` flag. This forces Gunicorn to speak ASGI.
*   **Golden Path Command:** `CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]`

---

### **Entry 002: The `gcloud logs` Command Hallucination**

*   **Symptom:** Repeated attempts to view Cloud Run logs fail with `Invalid choice: 'tail'` or `unrecognized arguments: --stream`.
*   **Diagnosis:** The AI's internal knowledge of the `gcloud` CLI was catastrophically wrong and outdated. It was hallucinating commands (`tail`) and flags (`--stream`) that do not exist in the `gcloud run services logs` command group.
*   **The Unbreakable Fix:** The only source of truth for a CLI command is the tool's own help flag. The command `gcloud run services logs --help` revealed that `read` is the only valid command. Never trust an AI's memory of a CLI command; always verify with `--help` when in doubt.
*   **Golden Path Command:** `gcloud run services logs read [SERVICE_NAME] --region [REGION]`

---

### **Entry 003: The Local Docker Environment**

*   **Symptom A:** `docker: command not found` when running a local build script.
*   **Diagnosis A:** Docker Desktop is not installed or not running.
*   **Fix A:** Install and run the Docker Desktop application.

*   **Symptom B:** `error from registry: Unauthenticated request` when pushing an image.
*   **Diagnosis B:** The local Docker engine is not authenticated with Google Cloud's Artifact Registry.
*   **Fix B:** Run the one-time setup command: `gcloud auth configure-docker [REGION]-docker.pkg.dev`.

---



### **Entry 004: The `pip install git+` Dependency Chain**

*   **Symptom A:** The `docker build` process fails during `RUN pip install` with the error `Cannot find command 'git'`.
*   **Diagnosis A:** The base `python:slim` Docker image does not include the `git` client. `pip` requires `git` to be installed in the container's environment to fetch packages from a GitHub URL.
*   **The Unbreakable Fix A:** Add a `RUN apt-get update && apt-get install -y git` layer to the `Dockerfile` *before* the `pip install` command.

*   **Symptom B:** The `pip install` command fails with a `ResolutionImpossible` error due to conflicting dependencies between `fastapi` and a git-installed package (`google-adk`).
*   **Diagnosis B:** Pinning specific versions of high-level application frameworks (`fastapi==x.y.z`) can create conflicts with the dependencies of other libraries.
*   **The Unbreakable Fix B:** In `requirements.txt`, pin the version of the most critical or sensitive library (in our case, `google-adk`). For general-purpose frameworks like `fastapi`, `uvicorn`, and `gunicorn`, remove the version pins to allow `pip`'s dependency resolver the flexibility to find a compatible set of versions that satisfies all requirements.
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
