import os

from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from utility.require_settings import require_settings

load_dotenv(override=True)  # .env wins over variables already set in the shell


def get_embedding_model() -> AzureOpenAIEmbeddings:
    """The embedding model used while indexing: whole documents, library defaults for timeout and retries, nobody
    waiting on it. The query-time model (with tracing and a fallback deployment) is retrieval/embeddings.py.
    """
    require_settings("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY")

    return AzureOpenAIEmbeddings(
        azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )
