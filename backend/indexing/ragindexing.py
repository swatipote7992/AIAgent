from pathlib import Path

from indexing.chunking import create_chunk
from indexing.clean_text import clean_documents
from indexing.load_pdf import load_pdf
from indexing.metadata import enrich_metadata
from vector_embedding.vector_store import store_chunks

PDF_PATH = Path(__file__).resolve().parent.parent / "data" / "insurance_policy.pdf"


def index_pipeline(pdf_path: Path):
    # Load the PDF and split it into pages
    documents = load_pdf(pdf_path)
    print(f"Loaded {len(documents)} pages")

    # Clean the text of each page
    documents = clean_documents(documents)
    print(f"{len(documents)} pages after cleaning")

    # Enrich the metadata of each page
    documents = enrich_metadata(documents)
    print(f"Metadata added to {len(documents)} pages")

    # Split the pages into smaller overlapping chunks
    chunks = create_chunk(documents)
    print(f"Split into {len(chunks)} chunks")

    # Embed each chunk and store text, vector and metadata in Azure AI Search
    ids = store_chunks(chunks)
    print(f"Stored {len(ids)} chunks in the Azure AI Search index")


if __name__ == "__main__":
    index_pipeline(PDF_PATH)
