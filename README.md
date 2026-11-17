# AIAgent

A RAG project over PDF insurance policy documents, built with LangChain, Azure OpenAI (`text-embedding-3-small` for embeddings, `gpt-4.1-mini` for answers) and Azure AI Search, managed with **pip** and `backend/requirements.txt`. The code lives in `backend/`. Commands are for Windows PowerShell; each block says which folder to run it from.

**Status:** the whole RAG flow works end to end for all three sample documents (the policy, the underwriting rules guide and the claims guide). Every PDF in `backend/data/` is loaded, cleaned, enriched with metadata, split into chunks, embedded and stored in an Azure AI Search index (27 chunks). A question then retrieves the most relevant chunks and `gpt-4.1-mini` answers from them with source and page citations. The app is also deployed to Azure (see "Deploying to Azure" below), and signing in and asking a question on the deployed site works.

## Project layout

```
AIAgent/
├── .env                 your settings and keys (not in git)
├── .env.example         template for .env
├── .gitignore           ignores .env, .venv, caches
├── README.md
├── deploy.ps1           deploys everything to Azure (see "Deploying to Azure")
├── frontend/            React + TypeScript + Vite web app
│   ├── package.json, vite.config.ts, tsconfig.json, index.html
│   ├── public/          staticwebapp.config.json (sign-in rule for Azure)
│   └── src/             main.tsx, App.tsx, api.ts, types.ts, styles.css
└── backend/
    ├── .venv/           virtual environment (not in git)
    ├── .gitignore
    ├── requirements.txt
    ├── Dockerfile       builds the backend image (used by deploy.ps1)
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
| [insurance_generic_v1.pdf](backend/data/insurance_generic_v1.pdf), [audi](backend/data/insurance_audi_v1.pdf), [bmw](backend/data/insurance_bmw_v1.pdf), [mercedes](backend/data/insurance_mercedes_v1.pdf) | Fictional mock car insurance policies used as input |
| [deploy.ps1](deploy.ps1) | Deploys the backend (Azure Container Apps) and the frontend (Azure Static Web Apps) |
| [backend/Dockerfile](backend/Dockerfile) | Builds the backend container image |
| [staticwebapp.config.json](frontend/public/staticwebapp.config.json) | Makes the deployed frontend require sign-in, invited users only |
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
| `AZURE_SEARCH_INDEX` | Index name | `insurance-policies-v2` |

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

[indexing/ragindexing.py](backend/indexing/ragindexing.py) is the entry point of the indexing phase. It indexes every PDF in `backend/data/` (the four `insurance_*_v1.pdf` files), one after the other, passes the result of each stage to the next, and prints a short summary after every stage. To add a document, put a PDF in `backend/data/` and run it again. Set the project up first (see [Setup](#setup)), then run it from inside `backend/` with the virtual environment active:

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

The input is any PDF placed in `backend/data/`, for example a policy, an underwriting guide or a claims guide. Each is loaded the same way. A document of this kind typically has:

- A title page and definitions.
- Sections on the rules that apply, such as what is covered, what is excluded and who can approve what.
- Tables, such as limits, loadings or decision matrices.
- Procedures, such as how to make a claim or appeal a decision.
- Contact details at the end.

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
- `document_type`: the file name without `.pdf` (for example `insurance_audi_v1`), so each chunk records which kind of document it is from.
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

- Index `insurance-policies-v2` (earlier: `insurance-policies`) with the fields `id`, `content`, `content_vector` and `metadata`.
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

Two protections were added for the deployed version:

- **CORS.** The frontend and the backend are on different addresses, so [ragapi.py](backend/api/ragapi.py) allows calls only from the frontend addresses listed in the `CORS_ORIGINS` setting (default `http://localhost:5173`), POST only.
- **API key.** `POST /api/ask` needs an `X-API-Key` header equal to the `API_KEY` setting. If `API_KEY` is not set (local development) the check is skipped. Without or with a wrong key the answer is 401.

The response is `{"answer": "...", "followups": ["...", ...], "chunks": [{"source", "page", "title", "text"}, ...]}`. `followups` holds up to 3 suggested next questions (empty when the model does not know the answer). The model returns them in the same call as the answer, using a structured output (`Reply` in [insur_llm.py](backend/answering/insur_llm.py)), and the prompt asks for questions that are complete on their own and answerable from the retrieved context.

The prompt lives only in [insur_llm.py](backend/answering/insur_llm.py). The API only answers questions from what is already in the index; it does not index anything (run `ragindexing.py` for that).

### Frontend ([frontend/](frontend/))

React with TypeScript, built with Vite, in the dark console theme (design 4 from the mockups). The screen has a chat column on the left and a "Retrieved chunks" panel on the right.

- [src/App.tsx](frontend/src/App.tsx): the page. Example questions on an empty chat, a transcript of questions and answers, and an input box (Enter sends, Shift+Enter adds a line). Click a question to see the chunks that were retrieved for it. Each chunk expands to show its text.
- Follow-up questions: under the latest answer, [App.tsx](frontend/src/App.tsx) shows the suggested follow-ups as buttons. Clicking one asks it like any other question. Typed follow-ups are still answered on their own, because the chat has no memory of earlier questions yet.
- [src/api.ts](frontend/src/api.ts): the call to `/api/ask`. When deployed it calls the backend address in `VITE_API_URL` and sends the key in `VITE_API_KEY`; both are empty in development.
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
- Per-user login on the API. Locally it has none, so only run it on your own machine. The deployed version is protected by the frontend sign-in plus the shared API key (see "Deploying to Azure").

## Deploying to Azure

The app runs as two parts in the resource group `insu_rag_rg`. The same group already holds the Azure OpenAI and AI Search resources.

| Part | Service | Name | Region |
| --- | --- | --- | --- |
| Backend (FastAPI, built from [backend/Dockerfile](backend/Dockerfile)) | Azure Container Apps | `insur-rag-api` | UK South |
| Image storage | Azure Container Registry (Basic) | `insurragacr` | UK South |
| Frontend (React build) | Azure Static Web Apps (Free) | `insur-rag-web` | East US 2 |

Live addresses:

- Frontend: https://white-dune-05b8e1a0f.8.azurestaticapps.net
- Backend: https://insur-rag-api.ashyhill-483ba230.uksouth.azurecontainerapps.io/docs

### Decisions

- **Two hosts with CORS** instead of one container serving both. I first built a version where FastAPI served the built frontend (one container, no CORS). Direction changed to two hosts, so the static-file code was removed from [ragapi.py](backend/api/ragapi.py) and CORS was added.
- **Who can use it: you and a few invited people.** [staticwebapp.config.json](frontend/public/staticwebapp.config.json) lets only users with the `invited` role open the frontend, signing in with a Microsoft account.
- **The backend has its own protection.** The sign-in only covers the frontend page, so the backend also needs the shared `API_KEY`, otherwise anyone who found its address could run up Azure OpenAI costs.
- **Secrets stay out of git and out of the image.** [backend/.dockerignore](backend/.dockerignore) keeps `.env` out of the image. [deploy.ps1](deploy.ps1) reads `.env` at run time and stores each value as a Container Apps secret.

### How to deploy

1. Install the Azure CLI and sign in: `az login`.
2. Make sure `.env` in the project root holds your Azure settings (see [.env.example](.env.example)) and the search index is filled.
3. From the project root run `.\deploy.ps1`. It takes a few minutes. It does these steps:
   - Creates the resource group (if needed) and the registry.
   - Builds the backend image inside Azure, so local Docker is not needed.
   - Creates the Static Web App first, because its address must go into `CORS_ORIGINS`.
   - Creates the Container Apps environment and the backend app with all settings as secrets, plus a new random `API_KEY`.
   - Builds the frontend against the backend address and key, and uploads it.
4. Invite yourself (the frontend lets in invited users only). Use a Microsoft account email:

```powershell
az staticwebapp users invite --name insur-rag-web --resource-group insu_rag_rg --authentication-provider aad --user-details <your-microsoft-email> --domain white-dune-05b8e1a0f.8.azurestaticapps.net --roles invited --invitation-expiration-in-hours 24
```

5. Open the invitation link it prints, sign in, then open the frontend address and ask a question.

Running [deploy.ps1](deploy.ps1) again is safe. It deletes and recreates the backend app, which also generates a new `API_KEY`, and the rebuilt frontend gets the new key, so the two stay in sync.

### Problems met and how they were fixed

1. **PowerShell stopped on an `az` warning.** `az acr build` prints "Packing source code" on stderr, and Windows PowerShell treated that as a fatal error. Fix: `$ErrorActionPreference` is `Continue` and each step checks the exit code.
2. **`az acr build` crashed on special characters** in the streamed build log (a `charmap` encoding error), although the build itself succeeded in Azure. Fix: build with `--no-logs` and poll the build status until it is `Succeeded`.
3. **App Service refused the plan: the subscription's quota for B1 instances is 0.** Fix: switched the backend to Azure Container Apps, which needs no such quota and scales to zero when idle.
4. **Static Web Apps refused West Europe** ("region is currently not accepting new customers"), and UK South is not offered. Fix: East US 2. This only holds the static frontend files.

### Verified

- The backend `/docs` page returns 200.
- `POST /api/ask` without the key returns 401.
- The frontend address redirects to the Microsoft sign-in (302).
- The CORS preflight from `http://localhost:5173` that asks to send the key header returns 200 (tested locally).
- `npm run build` passes with the new [api.ts](frontend/src/api.ts).
- Inviting a user, signing in and getting an answer from the deployed site was done and confirmed by you. I did not check it myself, and I made no call with the correct key from here because it would call Azure OpenAI.

### Things to know

- **First question after idle is slow.** The backend scales to zero, so it can take 10 to 30 seconds to start.
- **The key is in the frontend code.** The `API_KEY` is built into the frontend JavaScript. Only invited, signed-in users can load it, but any of them could read it. It protects against strangers, not against invited users.
- **Cost.** The Basic registry costs a few pounds a month. Container Apps and Static Web Apps cost almost nothing at this size.
- **Do not delete the resource group `insu_rag_rg`.** It also contains `insuragservice` (AI Search) and `insuragopenai` (Azure OpenAI). To remove only this app, delete the container app, the Container Apps environment, the static web app and the registry one by one.
- **Different names.** Names must be unique across Azure. Anyone else using [deploy.ps1](deploy.ps1) has to change the names at the top.
- **The registry admin login is switched on** so the container can pull its image. A managed identity would be the more secure setup.

## Mock car insurance data

You asked for four mock car insurance documents: one generic and one each for Audi, BMW and Mercedes. They are fictional PDFs, saved in the same folder and format as the existing documents, so the indexing pipeline picks them up automatically.

- [insurance_generic_v1.pdf](backend/data/insurance_generic_v1.pdf): standard cover levels, exclusions, excesses by driver age, no claims discount, claims and cancellation.
- [insurance_audi_v1.pdf](backend/data/insurance_audi_v1.pdf): Audi-specific excesses, genuine parts rules, key and ADAS recalibration, tracker discount and example premiums.
- [insurance_bmw_v1.pdf](backend/data/insurance_bmw_v1.pdf): the same sections with BMW rules (carbon fibre repairs, Digital Key, M model excess).
- [insurance_mercedes_v1.pdf](backend/data/insurance_mercedes_v1.pdf): the same sections with Mercedes-Benz rules (approved repairer excess, air suspension, AMG excess).

The earlier documents (`insurance_policy.pdf`, `underwriting_rules.pdf` and `claims_handling.pdf`) were then deleted from `backend/data/` at your request; they are still in git history. Some later sections below still use them as worked examples. The file names become the document type in the metadata, so they show up as `insurance_audi_v1` and so on. The PDFs were generated with a throwaway script outside the project, and `reportlab` was not added to [requirements.txt](backend/requirements.txt). To make the chatbot answer from them, run the indexing again (see "Indexing"). I did not run it, because it calls Azure OpenAI.

## Changing the documents and re-indexing

The documents changed: the three earlier PDFs were replaced by four mock car insurance PDFs ([insurance_generic_v1.pdf](backend/data/insurance_generic_v1.pdf), [insurance_audi_v1.pdf](backend/data/insurance_audi_v1.pdf), [insurance_bmw_v1.pdf](backend/data/insurance_bmw_v1.pdf) and [insurance_mercedes_v1.pdf](backend/data/insurance_mercedes_v1.pdf)). Because the content is different, the index is rebuilt from scratch instead of updating the old one.

1. **New index.** A new index named `insurance-policies-v2` is used, in the same Azure AI Search service (`insuragservice`). The old index `insurance-policies` is left untouched. The name is the default in [vector_store.py](backend/vector_embedding/vector_store.py) and is listed in [.env.example](.env.example). It can be overridden with `AZURE_SEARCH_INDEX`.
2. **Run the indexing pipeline again** from inside `backend/` with the virtual environment active:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m indexing.ragindexing
```

The module name is `indexing.ragindexing` (the file is [ragindexing.py](backend/indexing/ragindexing.py)). Typing `indexing.rank indexing` or `python m ...` does not work: the flag is `-m` with a dash, and the module name must match the file name.

**Output of the run:**

```text
python -m indexing.ragindexing
=== insurance_audi_v1.pdf
Loaded 3 pages
3 pages after cleaning
Metadata added to 3 pages
Split into 6 chunks
Removed 0 old entries for insurance_audi_v1.pdf
Stored 6 chunks in the Azure AI Search index
=== insurance_bmw_v1.pdf
Loaded 3 pages
Skipped empty/short page 3
2 pages after cleaning
Metadata added to 2 pages
Split into 5 chunks
Removed 0 old entries for insurance_bmw_v1.pdf
Stored 5 chunks in the Azure AI Search index
=== insurance_generic_v1.pdf
Loaded 2 pages
2 pages after cleaning
Metadata added to 2 pages
Split into 4 chunks
Removed 0 old entries for insurance_generic_v1.pdf
Stored 4 chunks in the Azure AI Search index
=== insurance_mercedes_v1.pdf
Loaded 3 pages
Skipped empty/short page 3
2 pages after cleaning
Metadata added to 2 pages
Split into 5 chunks
Removed 0 old entries for insurance_mercedes_v1.pdf
Stored 5 chunks in the Azure AI Search index
```

What it shows:

- All four files were indexed, 20 chunks in total (6 + 5 + 4 + 5), so the document count in `insurance-policies-v2` should be 20.
- "Removed 0 old entries" for every file is expected on a first run into a new index. On a re-run it would show the old chunks of that file being replaced.
- Page 3 of the BMW and Mercedes PDFs was skipped as empty or too short, so only the first two pages of those two files were indexed. The page 3 text is probably a short leftover of the last table, so check that nothing needed was dropped. The generic file has 2 pages and the Audi file has 3 pages that all passed.

3. **Check it.** In the Azure portal, open `insuragservice`, then Indexes, then `insurance-policies-v2`, and check that the document count is above 0. The deployed backend uses the new index after it is redeployed with [deploy.ps1](deploy.ps1).

### Adding more documents later

Question: if more documents are added, is a new index needed? No. Put the new PDF in `backend/data/` and run `python -m indexing.ragindexing` again against the same index. Before storing, [vector_store.py](backend/vector_embedding/vector_store.py) removes the old entries of each file being indexed (the "Removed N old entries" line), so unchanged files are simply refreshed and new files are added. A new index is only needed when the structure changes: a different embedding model or vector size, or new metadata fields in the index.

### Five more brands added

Five more mock policies were added to `backend/data/`, in the same format and sections as the first brand policies: [insurance_ford_v1.pdf](backend/data/insurance_ford_v1.pdf), [insurance_peugeot_v1.pdf](backend/data/insurance_peugeot_v1.pdf), [insurance_volvo_v1.pdf](backend/data/insurance_volvo_v1.pdf), [insurance_toyota_v1.pdf](backend/data/insurance_toyota_v1.pdf) and [insurance_tesla_v1.pdf](backend/data/insurance_tesla_v1.pdf). Toyota and Tesla were added on top of the brands you named. The four earlier PDFs were regenerated with the same content. To put them in the index, run `python -m indexing.ragindexing` again; the index stays `insurance-policies-v2`, and the existing files are replaced, not duplicated.

### Updating the example questions

The three example questions on the frontend start screen still asked about the old documents (smoker BMI, flood damage, claim time). They now ask about the car insurance data: BMW excess for a 22-year-old, Tesla battery damage cover and the Volvo courtesy car period. They are set in [App.tsx](frontend/src/App.tsx). The start screen text now says "car insurance policy documents".

### Monitoring built into the API

[ragapi.py](backend/api/ragapi.py) now writes one log line for every question: how long it took in milliseconds, the length of the question (the question text itself is not logged), how many chunks were found and which source files they came from. Failures are logged as errors with the reason. A new `GET /health` address returns `{"status": "ok"}` for uptime checks and needs no key. On Azure the lines show up in the container app log stream and in Log Analytics (see below for how to read them). It only takes effect after the backend is redeployed with [deploy.ps1](deploy.ps1).

Read the logs from the terminal:

```powershell
az containerapp logs show --name insur-rag-api --resource-group insu_rag_rg --follow
```

Other places to look in the portal: the container app's Metrics (requests, replicas, restarts), the Azure OpenAI resource `insuragopenai` (tokens and throttling), the AI Search service `insuragservice` (document count and queries) and Cost Management.

### Azure Monitor and OpenTelemetry

The API is connected to Azure Monitor through OpenTelemetry:

1. **Resource.** An Application Insights resource `insur-rag-insights` was created in `insu_rag_rg` (UK South). It is workspace-based and uses the same Log Analytics workspace as the Container Apps environment, so the container logs and the telemetry are in one place. [deploy.ps1](deploy.ps1) creates it if it is missing and reuses it otherwise.
2. **Package.** `azure-monitor-opentelemetry` was added to [requirements.txt](backend/requirements.txt).
3. **Startup.** [ragapi.py](backend/api/ragapi.py) starts the Azure Monitor exporter before the app is created, but only when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set. Locally it is not set, so nothing is sent.
4. **Deploy.** [deploy.ps1](deploy.ps1) reads the connection string from the resource and passes it to the container app as a secret.

This gives request traces for `/api/ask`, the log lines described above, and calls made to other services. Look at it in the portal under `insur-rag-insights`: Live metrics, Transaction search, Failures, Performance and Application map.

### Health and readiness checks

Two checks were added to [ragapi.py](backend/api/ragapi.py), neither needs the API key:

- `GET /health` (liveness): the process is up. It checks no other service, so an Azure outage never makes Azure restart a healthy container.
- `GET /ready` (readiness): the AI Search index can be reached and has documents. It returns `{"status": "ready", "documents": N}`, or 503 if the index is unreachable or empty. It does not call Azure OpenAI (cost and rate limits), it never creates a missing index, and it caches the result for 10 seconds. Checked locally against `insurance-policies-v2`: 200 with 46 documents.

[deploy.ps1](deploy.ps1) now sets Container Apps probes: liveness on `/health` every 30 seconds, readiness on `/ready` every 15 seconds, and a startup probe on `/ready` (up to about 2.5 minutes), so a cold replica gets no traffic until it can answer. The Azure SDK's per-request INFO logging is turned down so the probes do not flood the logs.

Applied to the live backend (revision `insur-rag-api--0000001`): `/health` returns `{"status": "ok"}` and `/ready` returns 200 with 46 documents. The first attempt to apply the probes failed because the `az` YAML reader rejects pretty-printed JSON; the fix is compact JSON without a byte-order mark, now in [deploy.ps1](deploy.ps1).

To change the probes on the live app without a full deploy (which would also issue a new `API_KEY`), rebuild the image and update the container app only.

### Failure drill and alert (temporary)

To see what a failing service looks like in the logs and in Azure Monitor, [ragapi.py](backend/api/ragapi.py) has a temporary switch that does nothing unless the environment variable `SIMULATE_FAILURE` is set on the container app: `error` makes every question fail with a 502 (logged as an error, with the exception in Application Insights) and `slow` adds 8 seconds to every answer. The switch is the function `simulate_failure_drill()`, called at the start of `ask()`. Remove the function and its call when the drill is over.

An alert rule `insur-rag-api-5xx-errors` was created on the container app: it fires when the app returns any HTTP 5xx response within 5 minutes, checked every minute, severity 2. It has no action group yet, so it only appears in Monitor, Alerts and sends no email.

Turn the failure on (this makes a new revision, about a minute):

```powershell
az containerapp update --name insur-rag-api --resource-group insu_rag_rg --set-env-vars SIMULATE_FAILURE=error
```

Turn it off again:

```powershell
az containerapp update --name insur-rag-api --resource-group insu_rag_rg --remove-env-vars SIMULATE_FAILURE
```

While it is on, ask questions on the site, then look at the container app Log stream (error lines), the Application Insights Failures page, and Monitor, Alerts (the alert fires after a minute or two).

### Failure drill results

Steps taken during the drills, in order:

1. **Alert state checked.** The alert `insur-rag-api-5xx-errors` had fired at 14:55 UTC (about 2 minutes after the failed requests) and then resolved itself. Alerts clear automatically when the failures stop, so it can show as Resolved when you look later. A second rule, `System Latency Alert`, had fired at 13:16 UTC during the slow drill. Neither rule has an action group, so no notification was sent.
2. **Slow drill.** `SIMULATE_FAILURE=slow` was set on the container app and 8 questions were sent to `/api/ask`. All returned 200, taking 9.2 to 10.3 seconds each.
3. **Error drill.** `SIMULATE_FAILURE=error` was set (new revision `insur-rag-api--0000003`) and 20 questions were sent. All 20 returned 502, and the container app metric Requests recorded 20 responses in the 5xx category in one minute.
4. **Problem found: telemetry feedback loop.** The Azure Monitor exporter logs every upload ("Transmission succeeded") and those log lines are sent as telemetry too, about one item per second even when idle. They bury the real log lines and add ingestion cost. Planned fix: set the exporter's logger to WARNING in [ragapi.py](backend/api/ragapi.py). Not applied yet.
5. **Still to do.** Create an action group (email) and attach it to both alert rules, switch the drill off with `--remove-env-vars SIMULATE_FAILURE`, and remove the drill function.

## Spec Kit setup

Steps taken to add GitHub Spec Kit (spec-driven development skills for Claude Code) to this project:

1. **Tried the command you gave.** `uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude`. It failed at once because `uvx` was not installed (it was not found in Git Bash or PowerShell).
2. **Installed uv.** `pip install uv` installed uv 0.13.8, which includes `uvx`, in the Python Scripts folder that is already on the PATH. A terminal opened before this may need to be reopened.
3. **Ran the command again.** `uvx` downloaded and built Spec Kit, but `specify init` rejected `--ai`: "No such option: --ai". This version of Spec Kit replaced `--ai` with `--integration`.
4. **Checked the options.** `specify init --help` showed the new options, and that `--here` asks for confirmation when the folder is not empty unless `--force` is given. Before forcing, I checked that `.claude/`, `.specify/` and `CLAUDE.md` did not exist and that the git working tree was clean, so nothing of yours could be overwritten.
5. **Ran the working command.**

```powershell
uvx --from git+https://github.com/github/spec-kit.git specify init --here --force --non-interactive --integration claude --script ps
```

   `--integration claude` replaces `--ai claude`, `--force` skips the confirmation, `--non-interactive` stops it asking questions, and `--script ps` picks the PowerShell scripts for Windows. It finished with exit code 0.
6. **What it added** (both folders are new and not committed): `.claude/skills/` with the skills `speckit-constitution`, `speckit-specify`, `speckit-plan`, `speckit-tasks`, `speckit-implement`, `speckit-converge` and the optional `speckit-clarify`, `speckit-analyze` and `speckit-checklist`; and `.specify/` with templates, scripts, workflows and a constitution file (`.specify/memory/`). Nothing in the existing code or README was changed.
7. **Next, in Claude Code from this folder:** run `/speckit-constitution` to set project principles, then `/speckit-specify`, `/speckit-plan`, `/speckit-tasks` and `/speckit-implement`. Spec Kit warns that `.claude/` can hold credentials for some agents, so consider adding it to `.gitignore`. I did not change `.gitignore`.

8. **Added a CLAUDE.md.** The project had none. [CLAUDE.md](CLAUDE.md) in the project root is read by Claude Code at the start of every session. It holds: your working rules (log every step in the README, no code in the README, pip only, report honestly), the commands to run the project, a short architecture map, the Azure resource names, the traps found so far (index name `insurance-policies-v2`, `deploy.ps1` rotating the API key, Git Bash rewriting Azure resource paths, noisy SDK logging, the temporary `SIMULATE_FAILURE` drill, never printing secrets) and a pointer to Spec Kit. It does not repeat the README or hold project principles, which belong in the Spec Kit constitution. Update it when a rule or trap changes, and remove the drill note when the drill is removed.

9. **Ran `/speckit-constitution`.** The constitution at [.specify/memory/constitution.md](.specify/memory/constitution.md) was still the empty template, so it was filled in as version 1.0.0 (ratified 2026-11-16) from the principles you listed. It has nine principles: test-first, FastAPI conventions, React and TypeScript conventions, secrets never printed or logged, no credentials in git, pinned pip dependencies, every step documented in the README, honest reporting and deployment safety. It also has sections for technology and security constraints (including the known limit that the shared API key sits in the frontend bundle) and for the development workflow and quality gates, plus governance with the amendment and versioning rules. No extension hooks were registered, so none ran. The file starts with a temporary "Sync Impact Report" comment to remove before committing. Open items it records: there are no automated tests yet, and the temporary failure drill must be removed after the monitoring drills.

## Secrets hook (Claude Code)

Steps taken to add a hook that stops Claude Code from committing, printing or writing secrets. It enforces constitution principles IV (secrets never printed or logged) and V (no credentials in git). A hook is run by Claude Code itself before a tool call, so it cannot be skipped the way a written rule can.

1. **Checked what existed.** The project had no agents, rules or hooks, only the Spec Kit skills in `.claude/skills/`, and the user settings had no hooks either.
2. **Decided what to block.** A PreToolUse hook on the shell tools (Bash and PowerShell) and on the file tools (Write, Edit, MultiEdit). The reason is that a deployment token was printed once in command output earlier in this project.
3. **Wrote the hook script** [block_secrets.py](.claude/hooks/block_secrets.py). Claude Code passes the tool call to it as JSON; an exit code of 2 blocks the call and shows the reason to Claude. It never prints the secret, only which rule was hit. It blocks:
   - `git add` of `.env` or anything under `.claude/`, and a bulk `git add` (`.`, `-A`, `--all`) while untracked `.env` or `.claude/` files exist;
   - `git commit` when the staged files include `.env` or `.claude/`, or when the staged changes add something that looks like a secret;
   - commands that print secrets: reading `.env`, listing environment variables, echoing a variable that holds a key or token, `az` commands that return keys (`list-keys`, `secret show` or `secret list`, `staticwebapp secrets list`) and `--show-secrets`;
   - file writes that contain a connection string, a private key, a known token format, or a long value assigned to a name such as key, token, secret or password. For `README.md` the check is stricter and also catches any long hex or base64-like string.
   - Allowed on purpose: writing `.env`, writing `.env.example`, reading `.env.example`, and values with placeholders such as `<your key>`.
4. **Registered it** in [settings.json](.claude/settings.json), which lists the hook under PreToolUse for the five tools above. It runs with Python from the PATH.
5. **Tested it.** A test script in the session scratchpad (not part of the project) fed the hook 23 made-up inputs, with the fake secrets built at run time. All 23 gave the expected result: 15 blocked and 8 allowed. This was a test of the script only; no real `git commit` has been run through it yet.
6. **Seen working live.** The hook was already active in the same session and blocked Claude's own first test file, because it contained a fake connection string. The file was rewritten to build the fake values at run time.
7. **Known limits.**
   - The hook cannot see commands you type in your own terminal, only Claude's.
   - It is a safety net, not a guarantee: a secret printed by a route the hook does not list is not caught.
   - A legitimate command can be blocked by mistake (for example `az containerapp secret list` with a `--query` that returns only names). If that happens, loosen the matching rule in the script.
   - `.claude/` is untracked and the hook blocks `git add` of it, including the hook's own files. Review `.claude/` first (principle V), then add the files from your own terminal.
8. **Not done.** The second hook (asking before commands that change the live app, such as `deploy.ps1`) and the optional rule files were not created.

### Tests for the secrets hook (pytest)

Steps taken to add the project's first automated tests, for the hook above. Choosing pytest over the built-in `unittest` was your decision: it is the usual runner for FastAPI, and the backend tests that principle I requires will use it too.

1. **Installed pytest** into the backend virtual environment: `pip install pytest` gave version 9.2.0, and `pip check` reported no broken requirements.
2. **Pinned it, kept out of the Azure image.** [requirements-dev.txt](backend/requirements-dev.txt) includes `requirements.txt` and adds the exact pytest version. The `Dockerfile` installs only `requirements.txt`, so pytest is not in the deployed image. [.dockerignore](backend/.dockerignore) now also leaves out `tests`, `.pytest_cache`, `requirements-dev.txt` and `pytest.ini`, so the tests are not copied into the image either. `.pytest_cache/` was already in [backend/.gitignore](backend/.gitignore).
3. **Configured pytest** in [pytest.ini](backend/pytest.ini): tests live in `backend/tests/`. Checked the configuration before writing any test: running pytest with an empty `tests/` folder read the config and exited with code 5, which means "no tests collected".
4. **Wrote the tests** in [test_block_secrets.py](backend/tests/test_block_secrets.py): 34 test cases (parametrized) that send made-up tool calls to the hook and check the exit code (2 = blocked, 0 = allowed). They cover commands that print secrets, file writes with secrets (including the stricter README check), `git add` and `git commit` in a temporary git repository (so the result does not depend on your working folder), and bad input. They also check that a block message never repeats the secret. The fake secrets are built when the tests run, so the test file contains nothing the hook itself would block.
5. **Ran them.** From `backend/` with the virtual environment active: all 34 passed.
6. **Checked that the tests can fail.** The same tests were run against a dummy hook that allows everything: 19 failed and the 15 "allowed" cases passed. With the real hook again all 34 passed. This was done after the hook was written, not before, so it is a check of the tests, not true test-first.
7. **How to run them:**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

8. **Not covered.** The tests call the hook script directly. They do not prove that Claude Code itself runs the hook with the settings in [settings.json](.claude/settings.json); that was only seen live once (secrets hook step 6). There are still no tests for the API, indexing or answering code.

## Distributed tracing

Steps taken to see where the time goes for one question. Before this, the API wrote one log line per question with the total time. Now each question is one trace with a timed span for every stage, so a slow answer can be traced to retrieval, the prompt or the model. You made the first code change (the helper file) yourself; the rest was made one edit at a time with your approval.

1. **Goal.** One trace per question with a child span per stage, attributes that help to find a slow or expensive question, and later percentile times (p50, p95, p99) per stage plus alerts. Spans never hold question text, answer text, chunk text or secrets.
2. **Wrote the helper** [tracing.py](backend/observability/tracing.py). It has one decorator, `traced("name")`, which runs a function inside a span with that name; the span's duration is the time of the function. If the function fails, the span is marked as an error and keeps only the exception's type name, not its message, because a message could contain a secret. The folder [backend/observability/](backend/observability/) also has leftover compiled files from the earlier logging feature that was reverted; they are not used.
3. **Split the answering code into stages** in [insur_llm.py](backend/answering/insur_llm.py). `ask_llm` used to do everything in one function. It now calls three small functions in order, each with its own span: `retrieval` (search in Azure AI Search), `prompt` (join the chunks into the context and build the prompt) and `llm_generation` (create the chat model and get the answer). `ask_llm` itself is also a span and is the parent of the three. The answer returned to the API did not change.
4. **Added attributes** (numbers and names only):
   - on `retrieval`: `rag.chunks`, the number of chunks found;
   - on `llm_generation`: the model name and the input and output token counts, counted with LangChain's usage callback. They were first named `llm.model`, `llm.input_tokens` and `llm.output_tokens`; step 19 replaced them with the standard `gen_ai.*` names and step 21 removed the old ones.
5. **Added a span for embedding the question** in [embeddings.py](backend/vector_embedding/embeddings.py). A small subclass of the embedding model wraps only the query embedding in an `embedding` span, so it shows up under `retrieval`. Indexing is not affected because it embeds documents, not queries.
6. **Expected shape of one trace:** `ask_llm` containing `retrieval` (which contains `embedding`), `prompt` and `llm_generation`.
7. **Checked offline.** The helper returns the wrapped function's result. The embedding subclass is the model that `get_embedding_model()` returns, and with a fake parent call it produces an `embedding` span whose parent is the surrounding span. The model's deployment name is available for the attribute. `insur_llm.py` imports and has all four functions.
8. **Deployed with a targeted update, not `deploy.ps1`.** `az acr build` of `backend/` as image `insur-rag-api` with a new tag (`trace-20261117112051`) succeeded, then `az containerapp update` on `insur-rag-api` to that image succeeded (exit code 0, revision `insur-rag-api--0000005`). The API key was not changed, and `SIMULATE_FAILURE` is not among the app's settings. Afterwards `/health` returned ok and `/ready` returned ready with 46 documents.
9. **Asked questions from the frontend.** Sending a question from Claude's shell needs the API key, and the secrets hook blocked reading it, so the questions were asked from the frontend instead.
10. **Looked at the traces in Application Insights** (`insur-rag-insights`): queried the `requests` and `dependencies` tables with `az monitor app-insights query` to check that each question is one trace with the expected parent and child spans and that the attributes are present.
11. **How to look at it in the portal:** Application Insights, Transaction search, open a `POST /api/ask` request for the end-to-end view; Application map for the whole app; Logs for a query on the `dependencies` table grouped by span name.
12. **Switched off FastAPI's own telemetry** in [ragapi.py](backend/api/ragapi.py) (extra spans and exception logs), because our stage spans already give the timing and exception text could carry secrets. It was first tested offline with a failing request carrying a fake marker in the error message, and no span held the marker. The change was deployed with the same targeted build and update as before (a new revision), then `/health` and `/ready` were checked.
13. **Sampling.** Read the Azure Monitor package's code: with no sampler setting it uses a rate limit of about 5 traces per second, far above this app's traffic. No change was made and it was not tested under heavy load.
14. **Percentiles.** Ran the p50, p95 and p99 query per span name. It works, but with so few questions the numbers are not meaningful yet.
15. **Created a p95 alert** on `insur-rag-insights` from an ARM template: it fires when the p95 of the `llm_generation` span is above 5 seconds over 15 minutes, checked every 5 minutes. It has no action group, so it only shows in Azure Monitor, Alerts and sends no message. You chose not to create a new action group or install a CLI extension, so the template is deployed with the built-in `az deployment group create`.
16. **Created a workbook** named `insur-rag-latency` on `insur-rag-insights` from an ARM template: a percentile table per stage, a p95-over-time chart and a tokens table. Deployment succeeded; it was not opened in the portal.
17. **Saved the commands and templates** in [scripts.md](scripts.md): the targeted deploy, the KQL queries, the alert and workbook templates and the offline failing-request check.
18. **Tried to see the traces in Microsoft Foundry.** The Foundry project's Traces page was empty. Findings: the project already had an Application Insights connection to a different resource (`inu_rag_insights`, which has had no telemetry), and the app sends its traces to `insur-rag-insights`; the app also calls its own Azure OpenAI resource, not the Foundry project. Replacing the Foundry connection was suggested as the safe option (it removes only the connection, not the resource); whether it was done is not recorded here. The spans also had none of the standard GenAI attributes (`gen_ai.*`), which Foundry's Traces page is expected to read.
19. **Added the standard GenAI attributes** to the `llm_generation` span in [insur_llm.py](backend/answering/insur_llm.py): operation name, provider name, request model and the input and output token counts, next to the existing `llm.*` ones. Names and numbers only. The file imports; it was deployed with the targeted build and update (a new revision) and `/health` and `/ready` were checked. Whether Foundry now shows the traces has not been verified.
20. **Moved the token queries to the new names.** The tokens table in the `insur-rag-latency` workbook and the token query in [scripts.md](scripts.md) now read `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`, falling back to the old names so spans recorded before the change still count. Checked on live data: both kinds of spans returned token counts. The workbook was redeployed from the updated template (same ID, so it was updated, not duplicated).
21. **Removed the old `llm.*` attributes** from [insur_llm.py](backend/answering/insur_llm.py), keeping only the `gen_ai.*` ones, and deployed with the targeted build and update (a new revision). `/health` and `/ready` were checked. The removal was not yet confirmed on a new question in Application Insights.
22. **Added three more attributes** (names, counts and lengths only): `question.chars` on `ask_llm` (the length of the question, never its text), `rag.sources` on `retrieval` (the policy file names found, reduced to the file name because the stored source can be a full local path), and on the `embedding` span the operation name, provider and embedding model name. Files: [insur_llm.py](backend/answering/insur_llm.py) and [embeddings.py](backend/vector_embedding/embeddings.py). Checked offline with fake data, including a fake Windows path with a user name: only file names came out, and no question, chunk or answer text appeared on any span. Deployed with the targeted build and update and `/health` and `/ready` were checked. Not yet confirmed on a new question in Application Insights.
23. **Still to do.** An action group with a receiver so alerts send a message (the existing 5xx and latency alerts also have none), check the alert and workbook in the portal, and re-run the percentiles once there are enough questions. Not applicable to this app: cache hit or miss and time to first token (no cache, no streaming).

24. **Question: how to track token usage, model costs and overall spend?** Answered in words only, nothing was changed or run. What exists already: the chat token counts are on the `llm_generation` span as `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` (see step 19), and the `insur-rag-latency` workbook has a tokens table. Gaps found: the `embedding` span has no token count, indexing runs are not measured, and nothing turns tokens into money. Proposed order: (a) Azure Cost Management on `insu_rag_rg` for the real bill, with a budget and an alert; (b) Azure OpenAI metrics (processed tokens per deployment) as the source that does not depend on our code; (c) a KQL query in the workbook that multiplies the span token counts by the current price per model, with the prices kept in the query and checked against the Azure price list; (d) a token count on the `embedding` span; (e) a daily token cap or alert. Not verified in Azure.
25. **Moved the system prompt into a versioned file.** It used to be a string inside `build_prompt` in [insur_llm.py](backend/answering/insur_llm.py). It now lives in [sys_prompt_v1.py](backend/prompts/sys_prompt_v1.py), with the same wording as before. First I made it a text file (`prompts/rag_answer/v1.txt`); you asked for a file named `sys_prompt_v1.py`, so I replaced that with the Python module and deleted the text file.
    - **Loader:** [prompts/__init__.py](backend/prompts/__init__.py) finds all `sys_prompt_v<N>.py` files. It uses the version in the environment variable `SYS_PROMPT_VERSION` if set, otherwise the highest number. An unknown version raises an error.
    - **Tracing:** the `prompt` span now has a `prompt.version` attribute (a name only, never the text), so answers and token counts can be compared per version.
    - **How to change the prompt:** add `sys_prompt_v2.py` next to v1 and leave v1 untouched. To go back, set `SYS_PROMPT_VERSION=v1`.
    - **Checked offline:** the loader returns v1 with the `{context}` placeholder, the template has the inputs `context` and `question`, an unknown version fails clearly, and the existing pytest tests still pass. **Not done:** no real question was asked and nothing was deployed, so the Azure app still runs the old inline prompt. The Dockerfile copies the whole `backend/` folder, so the new folder will be included in the next targeted build.
26. **Moved the prompts folder into `backend/data/`** at your request, so the prompt is now [sys_prompt_v1.py](backend/data/prompts/sys_prompt_v1.py) and the loader is [prompts/__init__.py](backend/data/prompts/__init__.py). [insur_llm.py](backend/answering/insur_llm.py) imports it from `data.prompts`, and the loader imports the versions with a relative import. Everything in step 25 about versions, `SYS_PROMPT_VERSION` and `prompt.version` still applies; the old `backend/prompts/` folder is gone, so the links in step 25 are out of date.
    - **Indexing is not affected:** [ragindexing.py](backend/indexing/ragindexing.py) only reads `*.pdf` directly inside `backend/data/`, and the 9 PDFs are still found.
    - **Mistake and fix:** my move command did not move anything (`git mv -k` skips untracked files but reports success) and the next command deleted the original folder. I rewrote both files with the same content. They are untracked, so git could not have restored them.
    - **Checked offline:** the loader returns v1, the template has `context` and `question`, an unknown version fails clearly, 34 pytest tests pass. Not deployed.
27. **Question: do we use few-shot prompting?** No. [sys_prompt_v1.py](backend/data/prompts/sys_prompt_v1.py) is zero-shot (instructions only, no example question and answer pairs). The `Reply` schema in [insur_llm.py](backend/answering/insur_llm.py) only fixes the output shape, and the retrieved chunks are source material, not examples. Possible gain from a few short fictional examples (citation format, "I don't know" with no follow-ups, follow-up quality) against a cost of extra input tokens on every question. Suggested way to try it: a `sys_prompt_v2.py` and a comparison by `prompt.version` on the same questions. Nothing was changed.
28. **Implemented few-shot prompting as version 2.** New file [sys_prompt_v2.py](backend/data/prompts/sys_prompt_v2.py): the same rules as v1 plus three short made-up examples with a fictional insurer and file name (answer found with a citation; answer only partly found; answer not found, so "I don't know" and no follow-ups). [sys_prompt_v1.py](backend/data/prompts/sys_prompt_v1.py) is unchanged.
    - **v2 is now the default**, because the loader picks the highest version. To go back to zero-shot without a code change, set `SYS_PROMPT_VERSION=v1` on the container app.
    - **Cost:** the prompt text grows from about 390 to about 1,770 characters (very roughly 100 to 440 tokens), added to the input of every question. This is an estimate from character counts, not a measured token count.
    - **Tests:** new [test_prompts.py](backend/tests/test_prompts.py) checks that every version has only the `context` placeholder (so the example text cannot break the template), that the latest version is the default, that the environment variable selects a version, that an unknown version fails, and that v2 has examples and v1 does not. All 40 pytest tests pass (34 old, 6 new).
    - **Not verified:** no real question was asked, so I do not know yet whether the answers or follow-ups are better, or whether the model copies example wording. Nothing was deployed; the Azure app still runs the old inline prompt. To compare, deploy with the targeted build and update, ask the same questions with `SYS_PROMPT_VERSION=v1` and without it, and compare by `prompt.version` and the tokens table.
29. **(The made-up examples below were replaced in step 30.) Added 59 examples and an underwriter and broker persona as version 3.** You asked for at least 50 to 60 relevant examples, then for the persona. New file [sys_prompt_v3.py](backend/data/prompts/sys_prompt_v3.py); [sys_prompt_v1.py](backend/data/prompts/sys_prompt_v1.py) and [sys_prompt_v2.py](backend/data/prompts/sys_prompt_v2.py) (3 examples) are kept so the three can be compared.
    - **Persona:** the prompt opens with "an experienced car insurance underwriter and broker": it reads the wording like an underwriter (cover, limits, excesses, exclusions) and explains it like a broker (plain language, practical consequence, neutral tone). It still must not quote prices, promise a claim will be paid, or give legal or financial advice.
    - **The 59 examples** use two fictional insurers (ExampleCo and SampleCo) and made-up facts, so real policy facts cannot be copied. Mix: 27 answers found in the context, 8 partly found, 8 not found, 5 comparing several chunks or insurers, 2 conflicting contexts, 3 about the user's own situation, 6 about wording, instruction override, guessing, personal data, advice and false claims. 10 have no follow-ups.
    - **v3 is now the default** (highest version). `SYS_PROMPT_VERSION=v1` or `v2` goes back with no code change.
    - **Cost:** about 27,000 characters, very roughly 6,800 tokens added to the input of every question, against about 100 for v1 (estimate from character counts, not measured). That is large for this app, and the examples take a share of the model's attention, so more is not automatically better.
    - **Tests:** [test_prompts.py](backend/tests/test_prompts.py) now also checks at least 50 examples, only the `{context}` placeholder in the text, and the persona. 43 tests pass.
    - **Not verified:** no real question was asked, so answer quality and whether the model copies example wording are unknown. The examples were written by me, not reviewed against the real policy PDFs, so some may not match how the real policies read. Nothing was deployed.
30. **Rewrote the v3 examples from your real PDFs (edited v3, no new version).** You said the made-up examples were wrong. I read all 9 PDFs in `backend/data/` (about 35,000 characters, 2 to 3 pages each) and rewrote the examples in [sys_prompt_v3.py](backend/data/prompts/sys_prompt_v3.py) from their wording. The two fictional insurers are gone; every example now uses the real file names, page numbers and figures of the insurer Northgate Mutual (mock data).
    - **What the PDFs turned out to contain:** per-brand excesses by driver age, theft and model add-ons, courtesy car limits, parts rules, keys and battery cover, telematics discounts, illustrative premiums, optional extras and the claims steps, plus the standard wording ([insurance_generic_v1.pdf](backend/data/insurance_generic_v1.pdf)) for windscreen, EU cover, exclusions, NCD, claims and cancelling. The brand wordings say the standard wording applies where they are silent.
    - **Persona changed to match:** "an experienced car insurance underwriter and broker working with the Northgate Mutual wording". The earlier rule "do not quote prices" was wrong for these documents, which contain illustrative premiums. It now says: no personal quote, but an illustrative premium from a document may be repeated and labelled illustrative.
    - **60 examples:** 15 on the standard wording, 11 to 12 each on Audi and BMW, 10 on Tesla, 8 on Ford and a few each on Mercedes, Volvo, Peugeot and Toyota. They cover excesses (with sums only where I added the numbers myself and said so), courtesy cars, parts, keys and batteries, telematics, business use and eligibility, standard-wording fallback, cross-brand comparisons, partly answered and unanswered questions, a conflict inside one page, and safety cases (instruction override, guessing, personal data, fraud, promises of payment). I first wrote 75 and trimmed to 60 because of the token cost.
    - **Real conflicts found in the PDFs:** on page 2 of each brand the text and the table disagree on the key replacement limit (for example Toyota text GBP 700, table GBP 1,500; also Ford, Peugeot, Volvo and Tesla). One example teaches the model to report both figures. Worth fixing in the PDFs.
    - **Checked:** a script confirmed that every cited file exists, every cited page is within that PDF's page count and every GBP figure in an answer appears in the PDF text (my own sums excepted, checked by hand). 43 pytest tests pass.
    - **Cost:** about 37,000 characters, very roughly 9,200 tokens added to the input of every question (estimate, not measured), against about 100 for v1.
    - **Not verified:** no real question was asked, so I do not know yet whether answers improve. The excerpts in the examples are shortened and flattened from the PDF text; the real chunks are bigger. Some follow-up questions point at nearby topics that the short excerpt does not show. Nothing was deployed.
31. **Fixed the key replacement mismatch in the PDFs.** On page 2 of five brand documents the text and the table gave different key limits. The table row was the same boilerplate ("Up to GBP 1,500 per claim, including programming") in every brand, while the text of each brand gave its own figure. I treated the brand text as correct and changed only that table row, so step 30's "real conflicts" item is now resolved:
    - [Toyota](backend/data/insurance_toyota_v1.pdf): GBP 700 (the words "including programming" were dropped, because the text does not say it).
    - [Ford](backend/data/insurance_ford_v1.pdf): GBP 1,000 including programming.
    - [Peugeot](backend/data/insurance_peugeot_v1.pdf): GBP 800 including programming (the text says a dealer must code the key).
    - [Volvo](backend/data/insurance_volvo_v1.pdf): GBP 1,200 including programming.
    - [Tesla](backend/data/insurance_tesla_v1.pdf): GBP 500 (words dropped for the same reason as Toyota).
    - Audi, BMW and Mercedes were not changed: their text gives no key figure, so their table value of GBP 1,500 does not conflict with anything.
    - **How:** the PDFs were made with ReportLab and no generator script is in the repo, so I patched the one text string in the page content with pypdf and kept the layout and fonts. Compared page by page before and after: the only text difference is that one table row per file, the page counts are unchanged, and the files still load with the PDF loader. I did not view them as rendered pages.
    - **Assumption you should check:** the brand text is right and the table was wrong. If you would rather have GBP 1,500 everywhere, the originals are in git (`git checkout -- backend/data/<file>`).
    - **Example updated:** the Toyota key example in [sys_prompt_v3.py](backend/data/prompts/sys_prompt_v3.py) no longer shows a conflict (it now answers GBP 700). The rule about reporting two conflicting figures stays, worded as "if the context ever gives two different figures".
    - **Not done:** the index `insurance-policies-v2` in Azure AI Search still holds the old chunks with GBP 1,500, so the app will keep giving the old table figure until the five files are re-indexed with `python -m indexing.ragindexing` (replaces each file's chunks by name; calls Azure OpenAI and costs a little). I did not run it. Nothing was committed.
32. **Added a `max_tokens` cap** (1,000 by default, changeable with `LLM_MAX_TOKENS`) to the chat model in [insur_llm.py](backend/answering/insur_llm.py). Before this nothing limited the reply, or set a timeout or retries. A cap that is too low cuts the structured reply and makes the call fail, so keep it above a full answer plus follow-ups.

## Next steps

To do, one by one (delete each item when it is done):

- Set an explicit timeout and retry count on the chat model.
- Record the cap and the finish reason (normal stop or cut by the limit) on the `llm_generation` span, so truncated answers show up in Application Insights.

Other open items:

- Failure has no action group yet, so it only appears in Monitor, Alerts and sends no email.
- code review agent
- Replace the shared API key with per-user sign-in on the backend.
- Replace the registry admin login with a managed identity.
- Run the deploy from a CI pipeline instead of by hand.
- From your list, three things your app doesn't have
- No reranking step.
- No cache, so cache.hit would always read the same.
- No streaming, so no time to first token.
