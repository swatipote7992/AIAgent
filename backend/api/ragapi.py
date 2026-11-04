from answering.insur_llm import ask_llm
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Policy RAG API")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@app.post("/api/ask")
def ask(request: AskRequest):
    """Take the user's question and return the answer with the chunks it was based on."""
    try:
        return ask_llm(request.question.strip())
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {error}")
