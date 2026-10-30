import os
from pathlib import Path
from pydantic import SecretStr

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

from chunking import create_chunk
from clean_text import clean_documents
from load_pdf import load_pdf
from metadata import enrich_metadata
from retrieval import get_retriever
from vector_store import store_chunks

load_dotenv(override=True)  # .env wins over variables already set in the shell


def index_pipeline(PDF_PATH: Path):
    #### Indexing Pipeline ####
    # Load the PDF and split it into pages
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

    # Embed each chunk and store text, vector and metadata in Azure AI Search
    ids = store_chunks(chunks)
    print(f"Stored {len(ids)} chunks in the Azure AI Search index")


def retrieve_pipeline(question: str):
    #### Retrieval and Generation ####
    print("----------------------------")
    QUESTION = "What underwriting decision applies to a smoker with a BMI of 32?"
    print(f"Question: {QUESTION}")

    # Find the chunks most relevant to the question
    retriever = get_retriever()
    retrieved_chunks = retriever.invoke(QUESTION)

    for chunk in retrieved_chunks:
        print(
            f"  retrieved: [{chunk.metadata.get('source')}, page {chunk.metadata.get('page_label')}] {chunk.page_content[:80]!r}"
        )

    # Join the chunk texts into one context string, keeping source and page for citations
    context = "\n\n".join(
        f"[{c.metadata.get('source')}, page {c.metadata.get('page_label')}]\n{c.page_content}"
        for c in retrieved_chunks
    )

    return context


def main():
    # data/ sits next to main.py, so this works from any working directory
    PDF_PATH = Path(__file__).parent / "data" / "insurance_policy.pdf"
    index_pipeline(PDF_PATH)

    QUESTION = "What underwriting decision applies to a smoker with a BMI of 32?"
    context = retrieve_pipeline(QUESTION)

    # Chat model: deployment name, endpoint and API version must match what was created in Azure
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=SecretStr(os.environ["AZURE_OPENAI_API_KEY"]),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        temperature=0,
    )

    # Prompt: the retrieved chunks go into {context}, the question into {question}
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Answer only from the context below. "
                    "If the answer is not in the context, say you don't know. "
                    "Mention the source and page for each fact.\n\nContext:\n{context}"
                ),
            ),
            ("human", "{question}"),
        ]
    )

    # Prompt -> model -> plain text answer
    chain = prompt | llm | StrOutputParser()

    # Ask the chat model to answer from the context only
    answer = chain.invoke({"context": context, "question": QUESTION})
    print(f"Answer: {answer}")


if __name__ == "__main__":
    main()
