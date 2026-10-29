from pathlib import Path

from clean_text import clean_documents
from load_pdf import load_pdf
from metadata import enrich_metadata
from chunking import create_chunk
from embeddings import embed_chunks

PDF_PATH = Path(__file__).parent / "insurance_policy.pdf"


def main():
    #Load the PDF and split it into pages
    documents = load_pdf(PDF_PATH)
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
    print("----------------------------")
    print(f"Tenth Chunk: {chunks[9]}")
    print("----------------------------")

    # Convert each chunk into an embedding vector
    vectors = embed_chunks(chunks)
    print(f"Created {len(vectors)} embeddings of length {len(vectors[0])}")


if __name__ == "__main__":
    main()
