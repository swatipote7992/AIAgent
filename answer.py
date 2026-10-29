import os

from dotenv import load_dotenv
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import AzureChatOpenAI
from retrieval import get_retriever

load_dotenv(override=True)  # .env wins over variables already set in the shell

REQUIRED_SETTINGS = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY")

SYSTEM_PROMPT = (
    "You answer questions about an insurance policy using only the policy context below.\n"
    "- If the context does not contain the answer, say that the policy provided does not cover it. "
    "Do not guess or use outside knowledge.\n"
    "- Quote loadings, limits and decisions exactly as written.\n"
    "- Cite the source and page for each fact, in the form [source, page N].\n\n"
    "Policy context:\n{context}"
)

# How each retrieved chunk is shown to the model, so it can cite the page
DOCUMENT_PROMPT = PromptTemplate.from_template("[{source}, page {page_label}]\n{page_content}")


def get_chat_model() -> AzureChatOpenAI:
    """Create the Azure OpenAI chat model (gpt-4.1-mini by default).
    The deployment name, endpoint and API version must match what was created in Azure.
    """
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings in .env: {', '.join(missing)}")

    return AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_CHAT_API_VERSION", os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")),
        temperature=0,  # same question, same answer
    )


def create_rag_chain():
    """Retriever -> prompt with the retrieved chunks -> chat model."""
    prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{input}")])
    answer_chain = create_stuff_documents_chain(get_chat_model(), prompt, document_prompt=DOCUMENT_PROMPT)
    return create_retrieval_chain(get_retriever(), answer_chain)


def answer_question(question: str) -> dict:
    """Return {"answer": str, "context": [retrieved chunks]} for the question."""
    return create_rag_chain().invoke({"input": question})
