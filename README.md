# AIAgent

A RAG project over PDF insurance policy documents, built with LangChain and OpenAI embeddings, managed with **pip** and `requirements.txt`. This file also logs how the project was set up. Commands are for Windows PowerShell, run from the project root.

**Current direction:** OpenAI embeddings (`text-embedding-3-large`). The original diagram used Azure OpenAI and Azure AI Search; Azure OpenAI can be swapped in later with `AzureOpenAIEmbeddings`. The vector store is not chosen yet.

## Project layout

| File | Purpose |
| --- | --- |
| [main.py](main.py) | Entry point that runs the whole pipeline |
| [load_pdf.py](load_pdf.py) | Loads the PDF, one document per page |
| [clean_text.py](clean_text.py) | Cleans the extracted text |
| [metadata.py](metadata.py) | Adds source, page and policy metadata |
| [chunking.py](chunking.py) | Splits pages into overlapping chunks |
| [embeddings.py](embeddings.py) | Turns chunks into embedding vectors |
| [embeddings_demo.py](embeddings_demo.py) | Small standalone demo of the embedding methods |
| [insurance_policy.pdf](insurance_policy.pdf) | Fictional sample policy used as input |
| [.env.example](.env.example) | Template for the API key |
| [requirements.txt](requirements.txt) | Pinned dependencies |

## Part 1: Setup

### Step 1: Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Step 2: Add a .gitignore

[.gitignore](.gitignore) keeps generated and sensitive files out of git:

- The virtual environment (`.venv/`).
- The `.env` file, which holds the API key.
- Python cache (`__pycache__/`, `*.pyc`).
- Tool caches (`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`).

Check what git will track:

```powershell
git status --short
```

### Step 3: Install dependencies

```powershell
pip install langchain langchain-community pypdf langchain-openai
pip freeze > requirements.txt
```

To recreate the environment elsewhere:

```powershell
pip install -r requirements.txt
```

### Step 4: Set the OpenAI API key

Put your key in a `.env` file (already ignored by git). Use [.env.example](.env.example) as the template.

Or set it for the current PowerShell session only:

```powershell
$env:OPENAI_API_KEY="your-key"
```

Without a key, `OpenAIEmbeddings` raises a "Missing credentials" error when it is created.

## Part 2: Input data

### Step 5: Sample insurance policy PDF

A fictional sample policy is at [insurance_policy.pdf](insurance_policy.pdf) so the pipeline has data to work with. It has 14 pages and covers:

- Definitions, scope of cover and the underwriting process (pages 1-4)
- Underwriting decision matrix by age, BMI and smoking (page 5)
- Outcomes for medical conditions such as hypertension, diabetes, asthma and cancer (page 6)
- Mental health, occupation and lifestyle underwriting (pages 7-8)
- General exclusions, waiting periods, premiums and loadings, claims (pages 9-12)
- Appeals and review of underwriting decisions (page 13) and contact details (page 14)

## Part 3: The ingestion pipeline

[main.py](main.py) runs the stages below in order and prints a summary after each one.

```powershell
python main.py
```

### Step 6: Load the PDF

`load_pdf()` in [load_pdf.py](load_pdf.py) uses `PyPDFLoader` to return one document per page. It only loads; it does nothing when imported.

### Step 7: Clean and prepare the extracted text

Poor extraction produces poor chunks, so pages are cleaned before splitting. The logic is in [clean_text.py](clean_text.py).

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

### Step 8: Preserve metadata

Each chunk must keep track of where it came from, so answers can cite the right policy section. The logic is in [metadata.py](metadata.py).

Every page, and therefore every chunk (the splitter copies page metadata onto its chunks), carries:

- `source`: the file name only, for example `insurance_policy.pdf` (not the local path).
- `page`: zero-based page index from the loader, and `page_label`: the human page number.
- `total_pages`.
- `policy_type`, `document_version`, `product_id` and `access_level` (the extra fields; `access_level` can later be used as a search filter for permissions).

The default values for the sample policy are set at the top of [metadata.py](metadata.py) and should be changed per document when ingesting real policies. Noisy PDF fields such as `producer` and `creationdate` are dropped to keep the stored index small.

### Step 9: Split the pages into chunks

`create_chunk()` in [chunking.py](chunking.py) uses LangChain's `RecursiveCharacterTextSplitter`.

- **Chunk size:** 500 characters.
- **Overlap:** 50 characters, so a clause cut at a chunk boundary still appears with its surrounding context in the next chunk.
- **Splitting order:** the splitter tries paragraph breaks first, then line breaks, then spaces, so chunks tend to end at natural boundaries.
- **Metadata:** every chunk keeps its page's metadata.

The two values are constants at the top of [chunking.py](chunking.py) and can be tuned.

Verified: 14 cleaned pages are split into 20 chunks, none longer than 500 characters, and every chunk has its metadata.

### Step 10: Embed the chunks

`embed_chunks()` in [embeddings.py](embeddings.py) turns each chunk into an embedding vector.

- It uses `OpenAIEmbeddings` with the `text-embedding-3-large` model and reads `OPENAI_API_KEY` from `.env`.
- It embeds the text of every chunk in one call to `embed_documents()`.
- The returned list is in the same order as the chunks: vector `i` belongs to chunk `i`. Metadata stays on the chunk, so vectors and metadata can be stored together in the vector store.
- It makes a real OpenAI API call each time `main.py` runs, so it uses a small amount of API credit.

Verified: 20 chunks produce 20 embeddings of length 3072.

## Part 4: Background on embeddings

- An embedding model turns text into a list of numbers (an embedding vector).
- `embed_documents()` converts a list of chunk texts into vectors.
- `embed_query()` converts the user's question into a vector for similarity search.
- Chunk vectors are stored in a vector store next to their text; at query time the question vector is compared with them to find relevant context.

[embeddings_demo.py](embeddings_demo.py) shows both methods on two sample sentences and one query. Run it:

```powershell
python embeddings_demo.py
```

## Next steps

- Store the chunks, vectors and metadata in a vector store (Azure AI Search, or a local store such as FAISS or Chroma).
- Build the retrieval and answer chain: retriever, `ChatPromptTemplate`, chat model, `create_retrieval_chain` with `create_stuff_documents_chain`.

## Superseded options (not used)

- **uv** (`uv init --bare`, `uv add`): replaced by pip. The leftover `pyproject.toml` and `uv.lock` were deleted.
- A `src/` + `tests/` layout and a single empty `main.py` were considered but not created.
