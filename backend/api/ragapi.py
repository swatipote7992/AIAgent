import os
import secrets

from answering.insur_llm import ask_llm
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


@app.post("/api/ask", dependencies=[Depends(require_api_key)])
def ask(request: AskRequest):
    """Take the user's question and return the answer with the chunks it was based on."""
    try:
        return ask_llm(request.question.strip())
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {error}")

