import logging
import os
import secrets
import time

from answering.insur_llm import ask_llm
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ragapi")

# Send traces, metrics and logs to Azure Monitor (Application Insights) when its connection string is set.
# Locally the variable is not set, so nothing is sent. This must run before the FastAPI app is created.
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()

app = FastAPI(title="Policy RAG API")

# Frontend addresses allowed to call this API, comma separated (set CORS_ORIGINS on Azure).
origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(x_api_key: str = Header(default="")):
    """Reject calls without the shared key. Skipped when API_KEY is not set (local development)."""
    expected = os.environ.get("API_KEY")
    if expected and not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or wrong API key")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health():
    """Liveness check for monitoring (no key needed, returns no data)."""
    return {"status": "ok"}


@app.post("/api/ask", dependencies=[Depends(require_api_key)])
def ask(request: AskRequest):
    """Take the user's question and return the answer with the chunks it was based on."""
    question = request.question.strip()
    started = time.perf_counter()
    try:
        result = ask_llm(question)
    except Exception as error:
        ms = round((time.perf_counter() - started) * 1000)
        log.error("ask failed after %d ms, question_chars=%d, error=%s", ms, len(question), error)
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {error}")
    ms = round((time.perf_counter() - started) * 1000)
    sources = sorted({str(c.get("source")) for c in result.get("chunks", [])})
    log.info("ask ok in %d ms, question_chars=%d, chunks=%d, sources=%s", ms, len(question), len(result.get("chunks", [])), sources)
    return result
