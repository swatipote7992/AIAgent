import os

from dotenv import load_dotenv
from retrieval.embeddings import get_embedding_model
from langchain_community.vectorstores.azuresearch import AzureSearch

load_dotenv()  # reads the Azure settings from the .env file

REQUIRED_SETTINGS = ("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_KEY")


def create_vector_store() -> AzureSearch:
    """Connect to the Azure AI Search index to answer a question: the search client gets a timeout and automatic
    retries, and the question is embedded with a timeout and retries too. LangChain creates the index if it does
    not exist, so only /ready (which must not do that) uses a plain SearchClient instead.
    The indexing-time version (library defaults, no query timeout) is indexing/vector_storing.py.
    """
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings in .env: {', '.join(missing)}")

    timeout = float(os.environ.get("SEARCH_TIMEOUT_SECONDS", "10"))
    # Options of the Azure SDK client: seconds to connect and to read, and how often it retries a failed call.
    options = {
        "additional_search_client_options": {
            "connection_timeout": timeout,
            "read_timeout": timeout,
            "retry_total": int(os.environ.get("SEARCH_MAX_RETRIES", "2")),
            "retry_backoff_factor": 0.5,
        }
    }

    return AzureSearch(
        azure_search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        azure_search_key=os.environ["AZURE_SEARCH_KEY"],
        index_name=os.environ.get("AZURE_SEARCH_INDEX", "insurance-policies-v2"),
        embedding_function=get_embedding_model(),
        **options,
    )
