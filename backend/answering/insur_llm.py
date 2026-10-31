import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from answering.retrieval import get_retriever

load_dotenv(override=True)  # .env wins over variables already set in the shell


@lru_cache
def get_chain():
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
            "Mention the source and page for each fact.\n\nContext:\n{context}"
        )),
        ("human", "{question}"),
    ])
    return prompt | llm | StrOutputParser()


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

    answer = get_chain().invoke({"context": context, "question": question})

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
