from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 500  # max characters per chunk
CHUNK_OVERLAP = 50  # characters shared between neighbouring chunks so context is not cut mid-clause


def create_chunk(documents: list[Document]) -> list[Document]:
    """Split pages into smaller overlapping chunks. Each chunk keeps its page's metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(documents)
