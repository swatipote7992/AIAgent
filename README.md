# AIAgent

A RAG project over PDF insurance policy documents, built with LangChain, Azure OpenAI (`text-embedding-3-small` for embeddings, `gpt-4.1-mini` for answers) and Azure AI Search, managed with **pip** and `backend/requirements.txt`. The code lives in `backend/`. Commands are for Windows PowerShell; each block says which folder to run it from.

**Status:** the whole RAG flow works end to end for all three sample documents (the policy, the underwriting rules guide and the claims guide). Every PDF in `backend/data/` is loaded, cleaned, enriched with metadata, split into chunks, embedded and stored in an Azure AI Search index (27 chunks). A question then retrieves the most relevant chunks and `gpt-4.1-mini` answers from them with source and page citations.

## Project layout

```
AIAgent/
├── .env                 your settings and keys (not in git)
├── .env.example         template for .env
├── .gitignore           ignores .env, .venv, caches
├── README.md
├── frontend/            React + TypeScript + Vite web app
│   ├── package.json, vite.config.ts, tsconfig.json, index.html
│   └── src/             main.tsx, App.tsx, api.ts, types.ts, styles.css
└── backend/
    ├── .venv/           virtual environment (not in git)
    ├── .gitignore
    ├── requirements.txt
    ├── indexing/        the indexing phase (run when documents change)
    │   ├── ragindexing.py   entry point: PDF to chunks to index
    │   └── load_pdf.py, clean_text.py, metadata.py, chunking.py
    ├── vector_embedding/   shared by indexing and answering
    │   └── embeddings.py, vector_store.py
    ├── answering/       the answering phase (runs for every question)
    │   ├── retrieval.py     finds the chunks relevant to a question
    │   └── insur_llm.py     builds the prompt and calls the chat model
    ├── api/
    │   └── ragapi.py        FastAPI endpoint used by the frontend
    └── data/            the sample PDFs
```

| File | Purpose |
| --- | --- |
| [indexing/ragindexing.py](backend/indexing/ragindexing.py) | Entry point of the indexing phase: runs the five indexing stages |
| [load_pdf.py](backend/indexing/load_pdf.py) | Loads the PDF, one document per page |
| [clean_text.py](backend/indexing/clean_text.py) | Cleans the extracted text |
| [metadata.py](backend/indexing/metadata.py) | Adds source, page and policy metadata |
| [chunking.py](backend/indexing/chunking.py) | Splits pages into overlapping chunks |
| [embeddings.py](backend/vector_embedding/embeddings.py) | Creates the Azure OpenAI embedding model (used by indexing and by retrieval) |
| [vector_store.py](backend/vector_embedding/vector_store.py) | Connects to the Azure AI Search index; `store_chunks()` embeds and uploads the chunks (used by indexing and by retrieval) |
| [retrieval.py](backend/answering/retrieval.py) | Retrieves the chunks most relevant to a question |
| [api/ragapi.py](backend/api/ragapi.py) | FastAPI server with one endpoint, `POST /api/ask`, which passes the question to `insur_llm.py` |
| [insur_llm.py](backend/answering/insur_llm.py) | `ask_llm(question)`: retrieves the relevant chunks, builds the prompt and calls the chat model |
| [frontend/](frontend/) | React and TypeScript web app (dark console theme) |
| [insurance_policy.pdf](backend/data/insurance_policy.pdf) | Fictional sample policy used as input |
| [underwriting_rules.pdf](backend/data/underwriting_rules.pdf) | Fictional internal underwriting rules guide (6 pages). Indexed |
| [claims_handling.pdf](backend/data/claims_handling.pdf) | Fictional internal claims handling guide (7 pages). Indexed |
| [.env.example](.env.example) | Template for the settings in `.env` (project root) |
| [requirements.txt](backend/requirements.txt) | Pinned dependencies |
| [.gitignore](.gitignore), [backend/.gitignore](backend/.gitignore) | Keep `.venv`, `.env` and caches out of git |

## Setup

Do this once before running the indexing or the API. The virtual environment and the requirements file live in `backend/`.

### Create a virtual environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Install dependencies

From `backend/` with the virtual environment active:

```powershell
pip install langchain langchain-community pypdf langchain-openai azure-search-documents python-dotenv fastapi uvicorn
pip freeze > requirements.txt
```

To recreate the environment elsewhere (from `backend/`):

```powershell
pip install -r requirements.txt
```

If the virtual environment was moved from another folder and misbehaves (for example "No module named langchain_core"), delete `backend/.venv` and recreate it with the commands above. Activation scripts and launchers keep the old path of a moved venv.

### Create the Azure resources and set the settings

1. Create an Azure AI Search service and note its endpoint and admin key.
2. In Azure OpenAI, deploy the `text-embedding-3-small` embedding model and a chat model (`gpt-4.1-mini`), and note the endpoint, key, deployment names and API version.
3. Copy [.env.example](.env.example) to `.env` **in the project root** (next to `.env.example`, not inside `backend/`) and fill in the values. The code finds it by searching upward from `backend/`:

| Setting | Meaning | Default if omitted |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | required |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | required |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Name of your embedding deployment | `text-embedding-3-small` |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version | `2024-10-21` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Name of your chat model deployment | `gpt-4.1-mini` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint | required |
| `AZURE_SEARCH_KEY` | Azure AI Search admin key | required |
| `AZURE_SEARCH_INDEX` | Index name | `insurance-policies` |

The deployment name, endpoint and API version must match what you created in Azure. If a required setting is missing, the program stops with a "Missing settings in .env" message naming it.

`OPENAI_API_KEY` appears in [.env.example](.env.example) but nothing in the project uses it any more.

### Git ignore

[.gitignore](.gitignore) (project root) and [backend/.gitignore](backend/.gitignore) keep generated and sensitive files out of git:

- The virtual environment (`.venv/`).
- The `.env` file, which holds the keys.
- Python cache (`__pycache__/`, `*.pyc`).
- Tool caches (`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`).

The root `.gitignore` is the one that protects `.env`, because `.env` sits in the project root. A `.gitignore` inside `backend/` does not cover it. When the code was first moved into `backend/` the old `.gitignore` moved with it, `.env` was no longer ignored and got committed by accident (caught before pushing). Check what git will track before committing:

```powershell
git status --short
```

## Indexing: ragindexing.py

The project has two phases. **Indexing** reads the PDF and fills the Azure AI Search index; run it when the documents change. **Answering** (the API and the frontend, see [Web app](#web-app-api-and-frontend)) reads from that index for every question. They are separate, so asking questions does not re-embed the PDF.

[indexing/ragindexing.py](backend/indexing/ragindexing.py) is the entry point of the indexing phase. It indexes every PDF in `backend/data/` ([insurance_policy.pdf](backend/data/insurance_policy.pdf), [underwriting_rules.pdf](backend/data/underwriting_rules.pdf) and [claims_handling.pdf](backend/data/claims_handling.pdf)), one after the other, passes the result of each stage to the next, and prints a short summary after every stage. To add a document, put a PDF in `backend/data/` and run it again. Set the project up first (see [Setup](#setup)), then run it from inside `backend/` with the virtual environment active:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m indexing.ragindexing
```

Run it as a module (`-m`) from `backend/`. Running the file directly (`python indexing/ragindexing.py`) fails with "No module named indexing", because the files in `indexing/` import each other as `indexing.x` and the shared files (`vector_store.py`, `embeddings.py`) by plain name. The PDF path is built from the location of the file, so it does not depend on the folder you run from. Each run re-embeds the PDF's chunks (a small API cost) and updates the same entries in the index.

### Indexing pipeline

| # | Stage | File | Function | Output |
| --- | --- | --- | --- | --- |
| 1 | Load the PDF | [load_pdf.py](backend/indexing/load_pdf.py) | `load_pdf()` | one document per page |
| 2 | Clean the text | [clean_text.py](backend/indexing/clean_text.py) | `clean_documents()` | cleaned pages |
| 3 | Add metadata | [metadata.py](backend/indexing/metadata.py) | `enrich_metadata()` | pages with source, page and policy metadata |
| 4 | Split into chunks | [chunking.py](backend/indexing/chunking.py) | `create_chunk()` | overlapping chunks, each with metadata |
| 5 | Embed and store the chunks | [vector_store.py](backend/vector_embedding/vector_store.py) (uses the model from [embeddings.py](backend/vector_embedding/embeddings.py)) | `store_chunks()` | chunks, vectors and metadata in the Azure AI Search index |

Answering then runs on the stored index, for every question:

| # | Stage | File | Function | Output |
| --- | --- | --- | --- | --- |
| 6 | Retrieve relevant chunks | [retrieval.py](backend/answering/retrieval.py), called by [insur_llm.py](backend/answering/insur_llm.py) | `get_retriever()` | the 4 chunks most relevant to the question |
| 7 | Generate the answer | [insur_llm.py](backend/answering/insur_llm.py) | `ask_llm()` | the answer, with sources |

Each stage is described below in the same order.

## Stage 1: Load the PDF ([load_pdf.py](backend/indexing/load_pdf.py))

`load_pdf()` uses `PyPDFLoader` to return one document per page. It only loads; it does nothing when imported.

The input is the fictional sample policy [insurance_policy.pdf](backend/data/insurance_policy.pdf). It has 14 pages and covers:

- Definitions, scope of cover and the underwriting process (pages 1-4)
- Underwriting decision matrix by age, BMI and smoking (page 5)
- Outcomes for medical conditions such as hypertension, diabetes, asthma and cancer (page 6)
- Mental health, occupation and lifestyle underwriting (pages 7-8)
- General exclusions, waiting periods, premiums and loadings, claims (pages 9-12)
- Appeals and review of underwriting decisions (page 13) and contact details (page 14)

## Stage 2: Clean and prepare the extracted text ([clean_text.py](backend/indexing/clean_text.py))

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

## Stage 3: Preserve metadata ([metadata.py](backend/indexing/metadata.py))

Each chunk must keep track of where it came from, so answers can cite the right policy section.

Every page, and therefore every chunk (the splitter copies page metadata onto its chunks), carries:

- `source`: the file name only, for example `insurance_policy.pdf` (not the local path).
- `page`: zero-based page index from the loader, and `page_label`: the human page number.
- `total_pages`.
- `document_type`: the file name without `.pdf` (`insurance_policy`, `underwriting_rules` or `claims_handling`), so each chunk records which kind of document it is from.
- `policy_type`, `document_version`, `product_id` and `access_level` (the extra fields; `access_level` can later be used as a search filter for permissions).

The default values for all three sample documents (they are for the same product and version) are set at the top of [metadata.py](backend/indexing/metadata.py) and should be changed per document when ingesting real policies. Noisy PDF fields such as `producer` and `creationdate` are dropped to keep the stored index small.

## Stage 4: Split the pages into chunks ([chunking.py](backend/indexing/chunking.py))

`create_chunk()` uses LangChain's `RecursiveCharacterTextSplitter`.

- **Chunk size:** 1000 characters. The sample pages are 500 to 900 characters, so each page becomes one chunk and a table is never cut in half.
- **Overlap:** 100 characters, so a clause cut at a chunk boundary still appears with its surrounding context in the next chunk.
- **Splitting order:** the splitter tries paragraph breaks first, then line breaks, then spaces, so chunks tend to end at natural boundaries.
- **Metadata:** every chunk keeps its page's metadata.

The two values are constants at the top of [chunking.py](backend/indexing/chunking.py) and can be tuned.

Verified: the 27 pages of the three documents (14 + 6 + 7) become 27 chunks, the longest 875 characters, and every chunk has its metadata.

Why 1000 and not 500: with 500 characters the authority table in `underwriting_rules.pdf` was split between two chunks, with the "Senior underwriter" row label at the end of one and its values at the start of the next. Search returned only the second chunk, and the question "Who can approve a total loading of +60%?" got a hedging answer. With one chunk per page the same question is answered correctly (a senior underwriter, page 2). Longer pages than these would still be split, so check the chunk size again if you add documents with long pages or large tables.

## Stage 5: Embed and store the chunks ([vector_store.py](backend/vector_embedding/vector_store.py), [embeddings.py](backend/vector_embedding/embeddings.py))

### How it works

`get_embedding_model()` in [embeddings.py](backend/vector_embedding/embeddings.py) creates the Azure OpenAI embedding model from the `.env` settings. `store_chunks()` in [vector_store.py](backend/vector_embedding/vector_store.py) creates an `AzureSearch` vector store pointing at the Azure AI Search index and calls `add_documents()`. LangChain embeds each chunk and uploads its text, vector and metadata, so there is no separate embedding step in `ragindexing.py`.

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

- **Stable IDs:** each chunk gets an ID built from product, file name, version, page and chunk number (for example `NH-2026-01-insurance_policy-v3-2-p0-c0`). The file name is part of the ID so documents of the same product and version do not overwrite each other.
- **Replacing a file's entries:** before a file's chunks are uploaded, its existing entries in the index are deleted. Running again replaces them instead of adding duplicates, and an edited file that now produces fewer chunks leaves no stale entries behind. The delete matches the stored source name exactly before removing anything.
- **Index creation:** if the index does not exist, LangChain creates it using the embedding size. The index vector size must match the embedding model, so if you change the model, delete the index (or use a new index name) and re-embed everything.
- **Batching:** LangChain uploads in batches internally.

### Verified results

Running `python -m indexing.ragindexing` (from `backend/`) against Azure stored 27 chunks (7 from the claims guide, 14 from the policy, 6 from the underwriting guide). Querying the index afterwards showed:

- Index `insurance-policies` with the fields `id`, `content`, `content_vector` and `metadata`.
- Document count: 27, all IDs unique, none left over from the earlier single-document index.
- `content_vector` size: 1536 dimensions, matching `text-embedding-3-small`.
- A sample entry with ID `NH-2026-01-insurance_policy-v3-2-p0-c0` and its metadata JSON (source, document type, page, policy type, document version, product ID).

You can check the same things in the Azure portal: the document count, and the vector field with its dimensions.

### Known limitations

- Re-running the indexing replaces each file's entries (old ones are deleted, new ones uploaded). Only the PDFs that are currently in `backend/data/` are touched, so deleting a PDF from that folder does not remove its entries from the index.
- Metadata is stored as one field, so it cannot be used for filtering. To filter on `access_level` or `document_version`, the index fields have to be defined explicitly.
- `langchain-community` prints a deprecation warning saying it is being sunset. It does not affect the pipeline today.

## Stage 6: Retrieve relevant chunks ([retrieval.py](backend/answering/retrieval.py))

### How it works

`get_retriever()` connects to the existing index through `create_vector_store()` in [vector_store.py](backend/vector_embedding/vector_store.py), so retrieval automatically uses the same embedding model and index name as indexing. It turns the store into a retriever with `as_retriever`, and `retrieve(question)` calls `retriever.invoke(question)` and returns the chunks. Each chunk has `page_content` and `metadata`, so answers can cite the source and page.

[insur_llm.py](backend/answering/insur_llm.py) calls `get_retriever()` and then `retriever.invoke(question)` to get the chunks. `retrieve(question)` in [retrieval.py](backend/answering/retrieval.py) does the same in one call.

### Search types

| Type | What it does | Status |
| --- | --- | --- |
| `similarity` | vector search only | works |
| `hybrid` (default) | vector plus keyword search, merged into one ranking | works |
| `semantic_hybrid` | hybrid plus Azure's semantic reranker | fails: the index has no semantic configuration |

`k` (default 4) is the number of chunks returned. Keep it small (3 to 5), because extra chunks add noise and cost tokens. `k` is passed to `as_retriever` directly; putting it inside `search_kwargs`, as many examples do, fails in this LangChain version with "got multiple values for keyword argument 'k'".

### Filters

`get_retriever(filters=...)` accepts an OData filter string for when only some documents should be searched. Metadata is stored as one JSON text field, so for now a filter can only match inside that text, for example `search.ismatch('individual_health', 'metadata')`. The filter was accepted by Azure, but with a single policy in the index it cannot yet show documents being excluded. Proper filters on `access_level` or `document_version` need explicit index fields (see Next steps).

### Verified results

- Question: "What underwriting decision applies to a smoker with a BMI of 32?" The top chunks were the underwriting decision matrix (page 5), the premium example with exactly a smoker at BMI 32 (page 11), the underwriting process (page 4) and the medical conditions table (page 6). With `hybrid` the premium example ranked first; with `similarity` the matrix did.
- Question: "Am I covered for flood damage?" The policy says nothing about floods, but retrieval still returned 4 chunks (General Exclusions, Definitions, and others). Retrieval always returns `k` chunks, even when none is relevant, so the answer step must be told to say "I don't know" when the context does not contain the answer.

### Known limitations

- `semantic_hybrid` needs a semantic configuration on the index, and semantic ranking enabled on the search service. The index was created without one, so it must be recreated (delete the index and re-run `python -m indexing.ragindexing`) with the configuration defined.

## Stage 7: Generate the answer ([insur_llm.py](backend/answering/insur_llm.py))

### How it works

[insur_llm.py](backend/answering/insur_llm.py) answers one question in `ask_llm(question)`. It is called by the API for every request. It builds three plain objects once and reuses them:

1. `llm`: `AzureChatOpenAI` with your chat deployment (`gpt-4.1-mini` by default). Temperature is 0, so the same question gives the same answer.
2. `prompt`: a `ChatPromptTemplate` with two inputs, `{context}` (the chunks) and `{question}`.
3. `chain`: `prompt | llm | StrOutputParser()`, which fills the prompt, calls the model and returns the answer as plain text.

Then, for each question, it does the steps one by one:

1. Get the retriever and call `retriever.invoke(question)` to get the chunks.
2. Join the chunk texts into one `context` string. Each chunk is prefixed with `[source, page N]` so the model can cite it.
3. Call `chain.invoke({"context": context, "question": question})` and return the answer together with the chunks.

### The system prompt rules

- Answer only from the context.
- If the answer is not in the context, say "I don't know". This matters because retrieval always returns 4 chunks, even for questions the policy never mentions.
- Mention the source and page for each fact.

### Page numbers

The context uses `page_label`, the number a reader sees in a PDF viewer (the 13th page is "page 13"). The loader's `page` field is zero-based, so using it would label that page "12".

### Verified results

- "What underwriting decision applies to a smoker with a BMI of 32?" The answer gave smoker: Accept with Loading +20% and BMI 30 to 34.9: Accept with Loading +15%, added them to a combined 35%, and cited pages 5 and 11. These match the policy.
- "Am I covered for flood damage?" The answer said the context does not mention flood damage and that it does not know whether it is covered, instead of inventing an answer.

### Known limitations

- The flood answer still listed pages 2, 8, 9 and 10 as sources, which do not mention floods. The cited pages can be ones that were merely retrieved, not ones that support the statement.
- The model only sees the 4 retrieved chunks, so a question whose answer spans more pages may be answered incompletely. Raising `k` helps at a token cost.

## Web app: API and frontend

A simple web app on top of the same pipeline. It is deliberately minimal for now: ask a question, read the answer, see which chunks were retrieved. More features can be added later.

### API ([api/ragapi.py](backend/api/ragapi.py) and [insur_llm.py](backend/answering/insur_llm.py))

The API is split in two files:

- [api/ragapi.py](backend/api/ragapi.py) is the web layer. It defines one endpoint, `POST /api/ask`, checks the request (`{"question": "..."}`, 1 to 1000 characters) and passes the question to `ask_llm()`. An empty question gets a 422 response, and any failure while answering (for example Azure not reachable) gets a 502 with the error message.
- [insur_llm.py](backend/answering/insur_llm.py) does the work in `ask_llm(question)`: it retrieves the relevant chunks with [retrieval.py](backend/answering/retrieval.py), joins them into a context string with source and page, and calls the chat model. The model and retriever are created once and reused for every question.

The response is `{"answer": "...", "chunks": [{"source", "page", "title", "text"}, ...]}`.

The prompt lives only in [insur_llm.py](backend/answering/insur_llm.py). The API only answers questions from what is already in the index; it does not index anything (run `ragindexing.py` for that).

### Frontend ([frontend/](frontend/))

React with TypeScript, built with Vite, in the dark console theme (design 4 from the mockups). The screen has a chat column on the left and a "Retrieved chunks" panel on the right.

- [src/App.tsx](frontend/src/App.tsx): the page. Example questions on an empty chat, a transcript of questions and answers, and an input box (Enter sends, Shift+Enter adds a line). Click a question to see the chunks that were retrieved for it. Each chunk expands to show its text.
- [src/api.ts](frontend/src/api.ts): the call to `/api/ask`.
- [src/types.ts](frontend/src/types.ts): the TypeScript types for the API response.
- [src/styles.css](frontend/src/styles.css): the dark theme. On narrow screens the chunks panel moves below the chat.
- [vite.config.ts](frontend/vite.config.ts): in development, Vite forwards `/api` to the FastAPI server on port 8000, so no CORS setup is needed.

### Running it

The index must already be filled (run `python -m indexing.ragindexing` once, see above). Then start both servers, each in its own terminal.

Terminal 1, the API:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn api.ragapi:app --port 8000
```

Terminal 2, the frontend (the first time, run `npm install`):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To check types and make a production build: `npm run build` (output in `frontend/dist/`, ignored by git).

### Verified

- The API returned the right answer and 4 chunks for the smoker and BMI 32 question, and the "I don't know" answer for the flood question.
- `npm run build` passes the TypeScript check and builds.
- In a browser, clicking the smoker example showed the answer and the four chunks (pages 11, 5, 4 and 6). I did not test it with the API stopped, so the error message display is untested.

### Not included yet

- Document list, upload and index status.
- Saved conversation history (the chat resets on reload).
- Highlighting which chunks the answer actually cited.
- Streaming the answer as it is written.
- Login. The API has none, so only run it on your own machine.

## More sample documents: underwriting rules and claims

Two separate fictional internal guides sit next to the policy in `data/`. Both are for the same product (`NH-2026-01`, version 3.2) and are consistent with the policy document (same loadings and limits), adding detail the policy does not have.

**[underwriting_rules.pdf](backend/data/underwriting_rules.pdf)** (6 pages: a title page and five sections):

- Authority levels by role, with loading limits.
- Evidence requirements (age 50 or over, cardiac conditions, diabetes, hypertension, and others).
- Referral rules, decline reasons, and postponements and exclusions.

**[claims_handling.pdf](backend/data/claims_handling.pdf)** (7 pages: a title page and six sections):

- Pre-authorisation (valid for 90 days) and emergency treatment.
- Annual limits and excess by benefit.
- Required documents, and the 6-month time limit.
- Reasons a claim is declined, fraud checks, and claim appeals.

Example questions: who can approve a +60% loading (underwriting rules), what evidence is needed for diabetes (underwriting rules), and what the excess is on an MRI (claims handling).

Both are **indexed** together with the policy by `python -m indexing.ragindexing`. Because they share the product and version with the policy, two things were added so the documents do not collide: the file name is part of every chunk ID, and every chunk has a `document_type` field (see Stage 3 and Stage 5).

Verified answers (each cites the right document and page):

- "Who can approve a total loading of +60%?" A senior underwriter, up to +75% (underwriting rules, page 2).
- "What is the excess on an MRI scan?" GBP 50 per scan (claims handling, page 3).
- "What evidence is needed for type 2 diabetes?" The latest HbA1c result and a GP report, within 21 days (underwriting rules, page 3).
- "What is the waiting period for inpatient treatment?" 14 days (policy, page 10).
- "Am I covered for flood damage?" "I don't know": none of the three documents mentions floods.

## Next steps

- Remove the index entries of a PDF that is deleted from `backend/data/`.
- Use `document_type` to search only one kind of document (needs explicit index fields, see below).
- Define the index fields explicitly so `access_level` and `document_version` can be used as filters.
- Enable semantic ranking: define a semantic configuration when the index is created, then use `semantic_hybrid`.
- Tighten the prompt so it cites only the pages that support a statement.
- Add a script to rebuild the index when the documents or the embedding model change.
