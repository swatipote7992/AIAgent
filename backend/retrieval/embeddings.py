import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from observability.tracing import traced
from opentelemetry import trace
from utility.require_settings import require_settings
from utility.transient_error_checker import is_transient

load_dotenv(override=True)  # .env wins over variables already set in the shell

log = logging.getLogger("embeddings")


def _client_options() -> dict:
    # A question is embedded while the user waits, so it gets a timeout and a retry count.
    # Indexing keeps the library defaults; see indexing/data_embedding.py.
    return {
        "timeout": float(os.environ.get("EMBEDDING_TIMEOUT_SECONDS", "10")),
        "max_retries": int(os.environ.get("EMBEDDING_MAX_RETRIES", "2")),
    }


@lru_cache
def _fallback_embeddings() -> AzureOpenAIEmbeddings | None:
    # A second deployment of the SAME model (for example in another region), used when the primary keeps failing.
    # A different model gives vectors that do not match the index, so never point this at another model.
    name = os.environ.get("AZURE_OPENAI_EMBEDDING_FALLBACK_DEPLOYMENT", "").strip()
    if not name:
        return None
    return AzureOpenAIEmbeddings(
        azure_deployment=name,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        **_client_options(),
    )


class TracedEmbeddings(AzureOpenAIEmbeddings):
    """Same embedding model, but embedding the user's question shows up as its own "embedding" span."""

    @traced("embedding")
    def embed_query(self, text: str) -> list[float]:
        # Only the kind of call and the model name go on the span, never the text being embedded.
        span = trace.get_current_span()
        span.set_attribute("gen_ai.operation.name", "embeddings")
        span.set_attribute("gen_ai.provider.name", "azure.ai.openai")
        span.set_attribute("gen_ai.request.model", self.deployment)
        try:
            return super().embed_query(text)
        except Exception as error:
            # The primary deployment keeps failing (after the client's own retries): try the fallback, if there is one.
            fallback = _fallback_embeddings()
            if fallback is None or not is_transient(error):
                raise
            log.warning("embedding failed (%s), using the fallback deployment", type(error).__name__)
            span.set_attribute("embedding.fallback_used", True)
            return fallback.embed_query(text)


def get_embedding_model() -> AzureOpenAIEmbeddings:
    """The embedding model used to embed a question at answer time: tracing and a fallback deployment.
    The indexing-time model (library defaults, no tracing) is indexing/data_embedding.py.
    """
    require_settings("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY")

    return TracedEmbeddings(
        azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        **_client_options(),
    )
