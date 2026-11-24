# AIAgent (insur-agent)

A RAG app over fictional car insurance policy PDFs: LangChain, Azure OpenAI (`text-embedding-3-small` for embeddings, `gpt-4.1-mini` for answers) and Azure AI Search. The backend is FastAPI in `backend/`, the frontend is React + TypeScript + Vite in `frontend/`, and both are deployed to Azure. The README is the long-form documentation: [README.md](README.md).

## Working rules (from the owner, always follow)

- **Log everything in [README.md](README.md), step by step.** After every action or answer in this project (including installs, failed attempts, Azure changes and drills), add or update a numbered step in the README. When the direction changes, update the current direction and move abandoned approaches to a "Superseded options" section.
- **No source code in the README.** Link the file path instead, for example `[ragapi.py](backend/api/ragapi.py)`. Shell commands to run are fine.
- **Never deploy or change the live Azure app unless the owner says so.** Always ask first, every time, even for a small targeted rebuild. Re-indexing needs a yes too.
- **Never commit, push, or open a PR on your own.** The one exception is the `/create-pr` skill ([SKILL.md](.claude/skills/create-pr/SKILL.md)): it may commit, push, and open a PR, but only after showing its pass/fail gate table and getting explicit approval for that specific run. Even then, if the staged scope includes anything under `.claude/` or `.env`, stop and leave that commit to the owner's own terminal — the secrets hook enforces this and will not be worked around.
- **Name every new file in snake_case with a specific name** (`exception_handler.py`, not `errors.py`; no spaces, no run-together words).
- **Keep README entries short:** say what was done and why, not how it was tested or deployed.
- Package management is **pip + `backend/requirements.txt`** (pinned). uv was dropped for the project; `uvx` is only used to run Spec Kit.
- Be honest in reports: say what was verified and what was not. Do not claim something works in Azure unless it was checked there.

## Constitution (always applies, even without Spec Kit)

@.specify/memory/constitution.md

This import makes the project constitution load automatically every session, not only when a Spec Kit skill runs. It is the source of truth for project principles; amend it with `/speckit-constitution`, never by editing it directly.

## Commands

Windows, PowerShell. Run backend commands from `backend/` with the virtual environment active.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m indexing.ragindexing          # index every PDF in backend/data/ (calls Azure OpenAI, costs money)
uvicorn api.ragapi:app --port 8000      # run the API, docs at http://localhost:8000/docs
```

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # type check + production build
```

Tests use pytest (dev-only, pinned in [backend/requirements-dev.txt](backend/requirements-dev.txt), not in the Azure image). Run them from `backend/` with the virtual environment active: `pip install -r requirements-dev.txt`, then `python -m pytest`. Today the tests cover the secrets hook ([backend/tests/test_block_secrets.py](backend/tests/test_block_secrets.py)) and the prompt versions ([backend/tests/test_prompts.py](backend/tests/test_prompts.py)); the API, indexing and answering code have none yet.

Evals (AI quality checks against `backend/data/golden_data/`, they call Azure OpenAI and cost money): `python -m evals.run_evals --dry-run` shows the plan, `--retrieval-only` checks only the search, `--versions v1 v2 v3` compares prompt versions, `--gate` fails below the pass marks in `backend/evals/gate_thresholds.py`. Ask before a real run.

Deploy everything to Azure from the repo root: `./deploy.ps1` (needs `az login`).

## Architecture

- **Indexing** ([backend/indexing/](backend/indexing/)): load PDF, clean, add metadata, chunk, embed ([data_embedding.py](backend/indexing/data_embedding.py)) and store ([vector_storing.py](backend/indexing/vector_storing.py)) in Azure AI Search. Run it when documents change. Entry point is `ragindexing.py`; run it as a module (`-m`), never as a file.
- **Retrieval** ([backend/retrieval/](backend/retrieval/)): `retrieval.py` and `vector_store.py` find chunks (with a query-time timeout, retries and a fallback embedding deployment), `chain_llm.py` builds the prompt and calls the chat model.
- **API** ([backend/api/ragapi.py](backend/api/ragapi.py)): `POST /api/ask` (needs the `X-API-Key` header), `GET /health` (liveness) and `GET /ready` (checks the search index). Logging and Azure Monitor (OpenTelemetry) are configured here.
- **Frontend** ([frontend/src/](frontend/src/)): talks to the API using `VITE_API_URL` and `VITE_API_KEY`.
- **Documents** ([backend/data/](backend/data/)): mock car policies named `insurance_<brand>_v1.pdf`. The file name without `.pdf` becomes the chunk's `document_type`.

## Azure setup

Resource group `insu_rag_rg`. Backend on Container Apps (`insur-rag-api`, environment `insur-rag-env`, scales to zero), image from the registry `insurragacr`. Frontend on Static Web Apps (`insur-rag-web`). AI Search service `insuragservice`, Azure OpenAI deployments on the Azure AI Foundry account `technopanda92-5275-resource` (chat `gpt-4.1-mini`, embeddings `text-embedding-3-small`; the `insuragopenai` account also exists in the resource group but has no deployments and is unused), Application Insights `insur-rag-insights`. Secrets come from the root `.env` (git-ignored; template in [.env.example](.env.example)).

## Things that will bite you

- **The index name is `insurance-policies-v2`** (default in `vector_store.py`, overridable with `AZURE_SEARCH_INDEX`). The old `insurance-policies` index is unused.
- `create_vector_store()` **creates the index if it is missing**. Anything that only needs to read (like `/ready`) must use a plain `SearchClient` instead.
- Re-indexing replaces a file's old chunks by file name; files deleted from `backend/data/` stay in the index until removed by hand. A new index is only needed for a different embedding model/vector size or new metadata fields.
- **`deploy.ps1` deletes and recreates the backend and issues a new `API_KEY` every run**, and rebuilds the frontend with it. Prefer a targeted rebuild (`az acr build`, then `az containerapp update`) for small backend changes, so the key stays the same. Check the exit code of every `az` step.
- The `API_KEY` is built into the frontend JavaScript. It keeps strangers out, not invited users.
- In Git Bash, paths starting with `/subscriptions/...` get rewritten. Use `MSYS_NO_PATHCONV=1` or PowerShell for `az` commands that take resource IDs.
- `az containerapp update --yaml` needs compact JSON without a byte-order mark.
- The Azure SDK and the Azure Monitor exporter log at INFO and can flood the logs (and feed back into telemetry). Keep their loggers at WARNING.
- `SIMULATE_FAILURE` (`error` or `slow`) in `simulate_failure_drill()` is a **temporary** failure drill. It does nothing when the variable is unset. Never leave it set on the live app, and remove the function once the monitoring drills are finished.
- Never print secrets (API keys, deployment tokens, connection strings) in output or in the README. A hook enforces this ([.claude/hooks/block_secrets.py](.claude/hooks/block_secrets.py), registered in [.claude/settings.json](.claude/settings.json)); it also blocks `git add` of `.claude/` and `.env`, so review `.claude/` and add it from your own terminal.

## Spec Kit

Spec Kit skills are installed in `.claude/skills/` (`/speckit-constitution`, `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`) with their files in `.specify/`. Project principles are written in full in the constitution, imported above so they load every session; amend it with `/speckit-constitution`, not by editing this file.
