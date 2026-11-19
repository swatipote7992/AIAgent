import logging
import os
import secrets
import time

from retrieval.insur_llm import ask_llm
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from api.exception_handler import register_exception_handlers
from api.rate_limiter import all_visitors_key, all_visitors_limit, limiter, per_visitor_limit, visitor_key
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from utility.continuation_handler import AnswerBlockedError, AnswerTruncatedError
from utility.timeout_handler import RequestTimeoutError, run_with_deadline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ragapi")
# The Azure SDK logs every HTTP request with all headers at INFO; with health probes that would flood the logs.
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

# Send traces, metrics and logs to Azure Monitor (Application Insights) when its connection string is set.
# Locally the variable is not set, so nothing is sent. This must run before the FastAPI app is created.
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()

# FastAPI's own extra spans and exception logs are off: our stage spans (see observability/tracing.py)
# already give the timing, and the exception logs can carry error text.
app = FastAPI(title="Policy RAG API", telemetry={"operation_spans": False, "logs": False})

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
    """Liveness check: the process is up. It checks no other service, so an outage elsewhere never restarts the container."""
    return {"status": "ok"}


_ready_cache = {"at": 0.0, "documents": 0}


@app.get("/ready")
def ready():
    """Readiness check: the AI Search index can be reached and has documents. Azure OpenAI is not called (cost and rate limits).

    It uses a plain search client, not create_vector_store(), because that would create a missing index.
    The result is cached for 10 seconds so frequent probes do not hammer AI Search.
    """
    if time.monotonic() - _ready_cache["at"] > 10:
        try:
            client = SearchClient(
                endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
                index_name=os.environ.get("AZURE_SEARCH_INDEX", "insurance-policies-v2"),
                credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
            )
            _ready_cache["documents"] = client.get_document_count()
        except Exception as error:
            log.error("not ready: cannot read the search index: %s", error)
            raise HTTPException(status_code=503, detail="Search index is not reachable")
        _ready_cache["at"] = time.monotonic()
    if _ready_cache["documents"] == 0:
        raise HTTPException(status_code=503, detail="Search index is empty")
    return {"status": "ready", "documents": _ready_cache["documents"]}


def simulate_failure_drill():
    """TEMPORARY: failure drill for testing monitoring and alerts. Does nothing unless SIMULATE_FAILURE is set.

    "error" fails every question and "slow" adds 8 seconds. Remove this function and its call in ask() after the drill.
    """
    drill = os.environ.get("SIMULATE_FAILURE", "")
    if drill == "slow":
        time.sleep(8)
    elif drill == "error":
        raise RuntimeError("Simulated failure for the monitoring drill (SIMULATE_FAILURE=error)")


def answer(question: str) -> dict:
    simulate_failure_drill()
    return ask_llm(question)


register_exception_handlers(app)  # 504, 422 and 502 for our own errors, see api/exception_handler.py


app.state.limiter = limiter  # the rate limiter looks itself up here (see api/rate_limiter.py)


@app.post("/api/ask", dependencies=[Depends(require_api_key)])
@limiter.limit(per_visitor_limit, key_func=visitor_key)  # how often one visitor may ask
@limiter.limit(all_visitors_limit, key_func=all_visitors_key)  # how many questions per day in total
async def ask(request: Request, body: AskRequest):
    """Take the user's question and return the answer with the chunks it was based on.

    The whole request has one time budget (REQUEST_TIMEOUT_SECONDS, see utility/timeout_handler.py). Calls to Azure are
    retried only inside their own SDK clients; nothing here retries the request.
    A visitor who asks too often gets a 429 (see api/rate_limiter.py); the key check runs first, so calls with a wrong
    key are refused without using up anyone's allowance.
    """
    question = body.question.strip()
    started = time.perf_counter()
    try:
        result = await run_with_deadline(answer, question)
    except (RequestTimeoutError, AnswerBlockedError, AnswerTruncatedError):
        raise  # turned into 504, 422 and 502 by the handlers in api/exception_handler.py
    except Exception as error:  # anything else: a clear 502 (raised here so the response gets the CORS headers)
        ms = round((time.perf_counter() - started) * 1000)
        log.error("ask failed after %d ms, question_chars=%d, error=%s", ms, len(question), error)
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {error}")
    ms = round((time.perf_counter() - started) * 1000)
    sources = sorted({str(c.get("source")) for c in result.get("chunks", [])})
    log.info("ask ok in %d ms, question_chars=%d, chunks=%d, sources=%s", ms, len(question), len(result.get("chunks", [])), sources)
    return result
