from langchain_core.documents import Document
from vector_store import create_vector_store

DEFAULT_K = 4  # keep small (3 to 5): extra chunks add noise and cost tokens
DEFAULT_SEARCH_TYPE = "hybrid"  # "similarity", "hybrid" or "semantic_hybrid"


def get_retriever(k: int = DEFAULT_K, search_type: str = DEFAULT_SEARCH_TYPE, filters: str | None = None):
    """Connect to the existing index (same embedding model and index name as indexing) as a retriever.
    filters is an OData filter string, for example "search.ismatch('individual_health', 'metadata')".
    """
    search_kwargs = {"filters": filters} if filters else {}
    # k is an argument of the retriever itself; putting it in search_kwargs passes it twice and fails
    return create_vector_store().as_retriever(search_type=search_type, k=k, search_kwargs=search_kwargs)


def retrieve(question: str, k: int = DEFAULT_K, search_type: str = DEFAULT_SEARCH_TYPE) -> list[Document]:
    """Return the k chunks most relevant to the question."""
    return get_retriever(k=k, search_type=search_type).invoke(question)
