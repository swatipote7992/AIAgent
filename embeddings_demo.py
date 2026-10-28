from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()  # reads OPENAI_API_KEY from the .env file

# Initialise the embedding model
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
)

# Create embeddings for document chunks
documents = [
    "Our insurance platform generates quotes and policies.",
    "Underwriters review referrals and assess insurance risks.",
]

document_vectors = embedding_model.embed_documents(documents)

# Create an embedding for a user query
query = "How are insurance referrals reviewed?"
query_vector = embedding_model.embed_query(query)

print(document_vectors[0])
print(len(query_vector))
