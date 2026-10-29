# AIAgent

A RAG project over PDF insurance policy documents, built with LangChain, Azure OpenAI embeddings (`text-embedding-3-small`) and Azure AI Search, managed with **pip** and `requirements.txt`. Commands are for Windows PowerShell, run from the project root.

**Status:** the indexing pipeline works end to end. The sample policy is loaded, cleaned, enriched with metadata, split into chunks, embedded and stored in an Azure AI Search index. Querying the index and generating answers is not built yet (see [Next steps](#next-steps)).

## Project layout

| File | Purpose |
| --- | --- |
| [main.py](main.py) | Entry point that runs the whole indexing pipeline |
| [load_pdf.py](load_pdf.py) | Loads the PDF, one document per page |
| [clean_text.py](clean_text.py) | Cleans the extracted text |
| [metadata.py](metadata.py) | Adds source, page and policy metadata |
| [chunking.py](chunking.py) | Splits pages into overlapping chunks |
| [embeddings.py](embeddings.py) | Creates the Azure OpenAI embedding model |
| [vector_store.py](vector_store.py) | Embeds the chunks and stores them in Azure AI Search |
| [insurance_policy.pdf](insurance_policy.pdf) | Fictional sample policy used as input |
| [.env.example](.env.example) | Template for the settings in `.env` |
| [requirements.txt](requirements.txt) | Pinned dependencies |
| [.gitignore](.gitignore) | Keeps `.venv`, `.env` and caches out of git |

## Setup

Do this once before running `main.py`.

### Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Install dependencies

```powershell
pip install langchain langchain-community pypdf langchain-openai azure-search-documents python-dotenv
pip freeze > requirements.txt
```

To recreate the environment elsewhere:

```powershell
pip install -r requirements.txt
```

### Create the Azure resources and set the settings

1. Create an Azure AI Search service and note its endpoint and admin key.
2. In Azure OpenAI, deploy the `text-embedding-3-small` embedding model and note the endpoint, key, deployment name and API version.
3. Copy [.env.example](.env.example) to `.env` and fill in the values:

| Setting | Meaning | Default if omitted |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | required |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | required |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Name of your embedding deployment | `text-embedding-3-small` |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version | `2024-10-21` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint | required |
| `AZURE_SEARCH_KEY` | Azure AI Search admin key | required |
| `AZURE_SEARCH_INDEX` | Index name | `insurance-policies` |

The deployment name, endpoint and API version must match what you created in Azure. If a required setting is missing, `main.py` stops with a "Missing settings in .env" message naming it.

`OPENAI_API_KEY` appears in [.env.example](.env.example) but nothing in the project uses it any more.

### Git ignore

[.gitignore](.gitignore) keeps generated and sensitive files out of git:

- The virtual environment (`.venv/`).
- The `.env` file, which holds the keys.
- Python cache (`__pycache__/`, `*.pyc`).
- Tool caches (`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`).

Check what git will track:

```powershell
git status --short
```

## main.py: the entry point

[main.py](main.py) runs the whole indexing pipeline. It reads [insurance_policy.pdf](insurance_policy.pdf), passes the result of each stage to the next, and prints a short summary after every stage. It also prints the tenth chunk as a quick check. Set the project up first (see [Setup](#setup)), then run:

```powershell
python main.py
```

### Indexing pipeline

| # | Stage | File | Function | Output |
| --- | --- | --- | --- | --- |
| 1 | Load the PDF | [load_pdf.py](load_pdf.py) | `load_pdf()` | one document per page |
| 2 | Clean the text | [clean_text.py](clean_text.py) | `clean_documents()` | cleaned pages |
| 3 | Add metadata | [metadata.py](metadata.py) | `enrich_metadata()` | pages with source, page and policy metadata |
| 4 | Split into chunks | [chunking.py](chunking.py) | `create_chunk()` | overlapping chunks, each with metadata |
| 5 | Embed and store the chunks | [vector_store.py](vector_store.py) (uses the model from [embeddings.py](embeddings.py)) | `store_chunks()` | chunks, vectors and metadata in the Azure AI Search index |

Each stage is described below in the same order.

## Stage 1: Load the PDF ([load_pdf.py](load_pdf.py))

`load_pdf()` uses `PyPDFLoader` to return one document per page. It only loads; it does nothing when imported.

The input is the fictional sample policy [insurance_policy.pdf](insurance_policy.pdf). It has 14 pages and covers:

- Definitions, scope of cover and the underwriting process (pages 1-4)
- Underwriting decision matrix by age, BMI and smoking (page 5)
- Outcomes for medical conditions such as hypertension, diabetes, asthma and cancer (page 6)
- Mental health, occupation and lifestyle underwriting (pages 7-8)
- General exclusions, waiting periods, premiums and loadings, claims (pages 9-12)
- Appeals and review of underwriting decisions (page 13) and contact details (page 14)

## Stage 2: Clean and prepare the extracted text ([clean_text.py](clean_text.py))

Poor extraction produces poor chunks, so pages are cleaned before splitting.

What it does:

- Collapses repeated spaces and repeated blank lines, keeping paragraph breaks.
- Removes bare page numbers ("Page 3 of 14") and short lines repeated at the top or bottom of many pages (headers and footers).
- Skips empty or near-empty pages (extraction errors) and prints which pages were skipped.

What it deliberately does not touch, so policy accuracy is protected:

- Wording, capitalisation, numbers and punctuation.
- Headings and section numbers (for example "4. Underwriting Decision Matrix").
- Long lines (over 80 characters), which are treated as policy wording, never as headers or footers.
- Very short pages, which are never stripped of lines.

Verified: the sample PDF still has 14 pages after cleaning (it has no headers or footers). A synthetic test with fake headers, footers and an empty page removed only those and kept every numbered clause.

## Stage 3: Preserve metadata ([metadata.py](metadata.py))

Each chunk must keep track of where it came from, so answers can cite the right policy section.

Every page, and therefore every chunk (the splitter copies page metadata onto its chunks), carries:

- `source`: the file name only, for example `insurance_policy.pdf` (not the local path).
- `page`: zero-based page index from the loader, and `page_label`: the human page number.
- `total_pages`.
- `policy_type`, `document_version`, `product_id` and `access_level` (the extra fields; `access_level` can later be used as a search filter for permissions).

The default values for the sample policy are set at the top of [metadata.py](metadata.py) and should be changed per document when ingesting real policies. Noisy PDF fields such as `producer` and `creationdate` are dropped to keep the stored index small.

## Stage 4: Split the pages into chunks ([chunking.py](chunking.py))

`create_chunk()` uses LangChain's `RecursiveCharacterTextSplitter`.

- **Chunk size:** 500 characters.
- **Overlap:** 50 characters, so a clause cut at a chunk boundary still appears with its surrounding context in the next chunk.
- **Splitting order:** the splitter tries paragraph breaks first, then line breaks, then spaces, so chunks tend to end at natural boundaries.
- **Metadata:** every chunk keeps its page's metadata.

The two values are constants at the top of [chunking.py](chunking.py) and can be tuned.

Verified: 14 cleaned pages are split into 20 chunks, none longer than 500 characters, and every chunk has its metadata.

## Stage 5: Embed and store the chunks ([vector_store.py](vector_store.py), [embeddings.py](embeddings.py))

### How it works

`get_embedding_model()` in [embeddings.py](embeddings.py) creates the Azure OpenAI embedding model from the `.env` settings. `store_chunks()` in [vector_store.py](vector_store.py) creates an `AzureSearch` vector store pointing at the Azure AI Search index and calls `add_documents()`. LangChain embeds each chunk and uploads its text, vector and metadata, so there is no separate embedding step in `main.py`.

Background on embeddings:

- An embedding model turns text into a list of numbers (an embedding vector).
- `embed_documents()` converts a list of chunk texts into vectors. This is what happens during indexing.
- `embed_query()` converts the user's question into a vector for similarity search. This will be used when querying.
- At query time the question vector is compared with the stored chunk vectors to find the relevant context.

### What is stored for each chunk

- `id`: a stable ID (see below).
- `content`: the chunk text.
- `content_vector`: the embedding (1,536 numbers for `text-embedding-3-small`).
- `metadata`: source, page and the policy fields from Stage 3, stored together as one JSON field.

### Design choices

- **Stable IDs:** each chunk gets an ID built from product, version, page and chunk number (for example `NH-2026-01-v3-2-p0-c0`). Running again updates the same entries instead of creating duplicates (verified, see Known limitations).
- **Index creation:** if the index does not exist, LangChain creates it using the embedding size. The index vector size must match the embedding model, so if you change the model, delete the index (or use a new index name) and re-embed everything.
- **Batching:** LangChain uploads in batches internally.

### Verified results

Running `python main.py` against Azure stored 20 chunks. Querying the index afterwards showed:

- Index `insurance-policies` with the fields `id`, `content`, `content_vector` and `metadata`.
- Document count: 20.
- `content_vector` size: 1536 dimensions, matching `text-embedding-3-small`.
- A sample entry with ID `NH-2026-01-v3-2-p0-c0` and its metadata JSON (source, page, policy type, document version, product ID).

You can check the same things in the Azure portal: the document count, and the vector field with its dimensions.

### Known limitations

- Re-running `main.py` with the same document updates the same entries: after a second run the index still had 20 documents with 20 unique IDs. IDs are built from product, version, page and chunk number, so they only stay stable while the text and chunk settings are unchanged. If an edited page produces fewer chunks than before, the extra old entries stay in the index until the index is rebuilt or they are deleted.
- Metadata is stored as one field, so it cannot be used for filtering. To filter on `access_level` or `document_version`, the index fields have to be defined explicitly.
- `langchain-community` prints a deprecation warning saying it is being sunset. It does not affect the pipeline today.

## Next steps

- Delete stale entries when a document is edited and produces fewer chunks (or rebuild the index).
- Define the index fields explicitly so `access_level` and `document_version` can be used as filters.
- Add retrieval: search the index with a question, using hybrid search and semantic ranking.
- Build the answer chain: retriever, `ChatPromptTemplate`, `AzureChatOpenAI`, `create_retrieval_chain` with `create_stuff_documents_chain`.
- Add a script to rebuild the index when the documents or the embedding model change.
