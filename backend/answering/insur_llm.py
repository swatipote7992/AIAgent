import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field
from answering.retrieval import get_retriever

load_dotenv(override=True)  # .env wins over variables already set in the shell


class Reply(BaseModel):
    """What the chat model returns: the answer plus questions the user could ask next."""

    answer: str = Field(description="The answer, with source and page for each fact.")
    followups: list[str] = Field(
        description="Up to 3 short follow-up questions, each complete on its own and answerable from the context."
    )


@lru_cache
def get_cached_retriever():
    return get_retriever()


def ask_llm(question: str) -> dict:
    """Retrieve the chunks relevant to the question and let the chat model answer from them."""
    chunks = get_cached_retriever().invoke(question)

    # Join the chunk texts into one context string, keeping source and page for citations
    context = "\n\n".join(
        f"[{c.metadata.get('source')}, page {c.metadata.get('page_label')}]\n{c.page_content}"
        for c in chunks
    )

    """Chat model and prompt, built once and reused for every question."""
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
            "Mention the source and page for each fact. "
            "Also suggest up to 3 follow-up questions the user could ask next. Each must be a short, "
            "complete question that makes sense on its own and can be answered from the context below. "
            "If you do not know the answer, suggest no follow-ups.\n\nContext:\n{context}"
        )),
        ("human", "{question}"),
    ])
    chain = prompt | llm.with_structured_output(Reply)
    reply = chain.invoke({"context": context, "question": question})

    return {
        "answer": reply.answer,
        "followups": reply.followups[:3],
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
