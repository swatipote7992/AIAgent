from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()  # reads OPENAI_API_KEY from the .env file

EMBEDDING_MODEL = "text-embedding-3-large"


def embed_chunks(chunks: list[Document]) -> list[list[float]]:
    """Convert each chunk's text into an embedding vector. Vector i belongs to chunks[i]."""
    embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return embedding_model.embed_documents([chunk.page_content for chunk in chunks])
