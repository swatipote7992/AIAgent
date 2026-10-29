from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf(pdf_path: Path) -> list[Document]:
    """Load a PDF and return one Document per page."""
    return PyPDFLoader(str(pdf_path)).load()
