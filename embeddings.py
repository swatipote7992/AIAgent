import os

from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings

load_dotenv(override=True)  # .env wins over variables already set in the shell

REQUIRED_SETTINGS = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY")


def get_embedding_model() -> AzureOpenAIEmbeddings:
    """Create the Azure OpenAI embedding model (text-embedding-3-small by default).

    The deployment name, endpoint and API version must match what was created in Azure.
    """
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings in .env: {', '.join(missing)}")

    return AzureOpenAIEmbeddings(
        azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )
