from pathlib import Path

from langchain_core.documents import Document

# Values for the sample policy; change them per document when ingesting real policies.
DEFAULT_POLICY_INFO = {
    "policy_type": "individual_health",
    "document_version": "3.2",
    "product_id": "NH-2026-01",
    "access_level": "internal",  # e.g. public / internal / underwriters_only, usable as a search filter
}

KEPT_LOADER_FIELDS = ("page", "page_label", "total_pages")  # drops noisy PDF fields such as producer


def enrich_metadata(documents: list[Document], policy_info: dict | None = None) -> list[Document]:
    """Give every page a small, consistent metadata set. The text splitter copies it to each chunk."""
    policy_info = policy_info or DEFAULT_POLICY_INFO
    enriched = []
    for doc in documents:
        metadata = {k: doc.metadata[k] for k in KEPT_LOADER_FIELDS if k in doc.metadata}
        metadata["source"] = Path(doc.metadata["source"]).name  # filename only, not the local path
        metadata.update(policy_info)
        enriched.append(Document(page_content=doc.page_content, metadata=metadata))
    return enriched
