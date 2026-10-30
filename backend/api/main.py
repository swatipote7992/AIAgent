import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field
from retrieval import get_retriever

load_dotenv(override=True)  # .env wins over variables already set in the shell

app = FastAPI(title="Policy RAG API")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@lru_cache
def get_chain():
    """Same model and prompt as main.py, built once and reused for every question."""
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Answer only from the context below. "
            "If the answer is not in the context, say you don't know. "
            "Mention the source and page for each fact.\n\nContext:\n{context}"
        )),
        ("human", "{question}"),
    ])
    return prompt | llm | StrOutputParser()


@lru_cache
def get_cached_retriever():
    return get_retriever()


@app.post("/api/ask")
def ask(request: AskRequest):
    question = request.question.strip()
    try:
        chunks = get_cached_retriever().invoke(question)
        context = "\n\n".join(
            f"[{c.metadata.get('source')}, page {c.metadata.get('page_label')}]\n{c.page_content}"
            for c in chunks
        )
        answer = get_chain().invoke({"context": context, "question": question})
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {error}")

    return {
        "answer": answer,
        "chunks": [
            {
                "source": c.metadata.get("source"),
                "page": c.metadata.get("page_label"),
                "title": c.page_content.splitlines()[0] if c.page_content else "",
                "text": c.page_content,
            }
            for c in chunks
        ],
    }
