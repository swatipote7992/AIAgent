import os
import re
from collections import Counter

from dotenv import load_dotenv
from embeddings import get_embedding_model
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.documents import Document

load_dotenv()  # reads the Azure settings from the .env file

REQUIRED_SETTINGS = ("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_KEY")


def create_vector_store() -> AzureSearch:
    """Connect to the Azure AI Search index. LangChain creates the index if it does not exist.

    The index vector size comes from the embedding model, so if the model changes
    a new index is needed and everything must be re-embedded.
    """
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings in .env: {', '.join(missing)}")

    return AzureSearch(
        azure_search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        azure_search_key=os.environ["AZURE_SEARCH_KEY"],
        index_name=os.environ.get("AZURE_SEARCH_INDEX", "insurance-policies"),
        embedding_function=get_embedding_model(),
    )


def make_chunk_ids(chunks: list[Document]) -> list[str]:
    """Stable ID per chunk (product, version, page, chunk number) so re-running updates instead of duplicating."""
    per_page: Counter[str] = Counter()
    ids = []
    for chunk in chunks:
        meta = chunk.metadata
        prefix = f"{meta['product_id']}-v{meta['document_version']}-p{meta['page']}"
        ids.append(re.sub(r"[^A-Za-z0-9_\-=]", "-", f"{prefix}-c{per_page[prefix]}"))
        per_page[prefix] += 1
    return ids


def store_chunks(chunks: list[Document]) -> list[str]:
    """Embed every chunk and upload its text, vector and metadata to the index."""
    vector_store = create_vector_store()
    return vector_store.add_documents(documents=chunks, keys=make_chunk_ids(chunks))
