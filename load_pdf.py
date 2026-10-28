from pathlib import Path

from clean_text import clean_documents
from langchain_community.document_loaders import PyPDFLoader
from metadata import enrich_metadata

pdf_path = Path(__file__).parent / "insurance_policy.pdf"

loader = PyPDFLoader(str(pdf_path))
documents = loader.load()  # one doc per page
print(f"Loaded {len(documents)} pages")

documents = clean_documents(documents)
print(f"{len(documents)} pages after cleaning")

documents = enrich_metadata(documents)

print(documents[12])
