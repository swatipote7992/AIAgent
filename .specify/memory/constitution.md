<!--
SYNC IMPACT REPORT (temporary scratch, remove before committing)
Version change: 1.0.0 -> 1.1.0
Modified principles: II. FastAPI Backend Conventions (added a gen_ai span-attribute
  instrumentation requirement; no renaming)
Added sections: none
Removed sections: none
Follow-up TODOs:
  - The repository has no automated tests yet. Principle I applies to new work from now on;
    a backlog item to add tests for the existing API and indexing code is recommended.
  - The shared API key is built into the frontend bundle (known limit, see Constraints).
    Replacing it with per-user sign-in is a deferred improvement, not a constitution matter.
  - The temporary failure drill (simulate_failure_drill in backend/api/ragapi.py) must be
    removed when the monitoring drills end (Principle IX).
-->
# AIAgent (insur-agent) Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)
Tests for new behaviour MUST be written before the implementation or together with it, and
MUST be seen to fail for the right reason before the code that makes them pass. A change is
NOT done until its tests pass, or, where no automated test is practical (for example a
deployed Azure setting), a real check has been run against the real system and its result
recorded. Bug fixes MUST include a test that reproduces the bug. Tests MUST NOT call paid
services (Azure OpenAI) unless the test is explicitly marked as an integration check.

### II. FastAPI Backend Conventions
The backend MUST follow these rules:
- Request and response bodies MUST be Pydantic models with validation (length limits,
  required fields).
- Authentication MUST be a FastAPI dependency (the `X-API-Key` header, compared with
  `secrets.compare_digest`), never inline in endpoint bodies.
- Endpoints MUST return explicit, correct HTTP status codes (401 for a bad key, 502 for an
  upstream failure, 503 when not ready) and MUST NOT leak internal error details beyond what
  the caller needs.
- `/health` (liveness, checks no other service) and `/ready` (readiness, checks the search
  index without calling Azure OpenAI and without creating anything) MUST exist, need no key,
  and return no sensitive data.
- Endpoints MUST stay thin. Retrieval, prompting and indexing logic lives in separate
  modules (`answering/`, `indexing/`, `vector_embedding/`) and MUST be importable and
  testable without starting the server.
- Logging MUST be structured and meaningful (duration, counts, source files, error reason)
  and MUST NOT contain secrets or question text.
- Every OpenTelemetry span that calls an Azure OpenAI (or other AI) service MUST set the
  `gen_ai.operation.name` and `gen_ai.provider.name` attributes, consistent with the existing
  instrumentation in the API and retrieval code.

### III. React and TypeScript Frontend Conventions
The frontend MUST use strict TypeScript with no implicit `any`. All calls to the backend
MUST go through the typed API layer (`frontend/src/api.ts`) with shared types in `types.ts`.
Components MUST be small and single-purpose. `npm run build` (type check plus build) MUST
pass before a frontend change is considered done. The frontend MUST NOT hold any secret
other than the shared API key described under Technology and Security Constraints.

### IV. Secrets Are Never Printed or Logged
API keys, deployment tokens, connection strings and passwords MUST NEVER be printed to a
terminal, written to logs, echoed in command output, pasted into the README or included in
error messages. Users' question text MUST NOT be logged (only its length). Secrets MUST live
only in the git-ignored `.env` file locally and in Azure secrets (container app secrets) when
deployed. Commands that handle secrets MUST read them into variables and mask or discard the
output. If a secret is exposed by accident, it MUST be reported to the owner immediately and
rotated.

### V. No Credentials in Git
`.env`, the API key and any other credential MUST NEVER be committed, and `.env` MUST stay
in `.gitignore`. `.env.example` MUST contain placeholders only. Before every commit, staged
changes MUST be checked for credentials. Agent folders that may hold credentials (`.claude/`)
MUST be reviewed before being committed.

### VI. Pinned pip Dependencies
The project uses pip with a pinned `backend/requirements.txt` and a virtual environment.
uv or other package managers MUST NOT be adopted for the project (using `uvx` to run an
external tool such as Spec Kit is allowed). Every new dependency MUST be added to
`requirements.txt` with an exact version, and `pip check` MUST report no conflicts.

### VII. Every Step Is Documented in the README
Every action taken on the project (including installs, failed attempts, Azure changes,
drills and decisions) MUST be recorded in `README.md` as numbered steps, in order. Source
code MUST NOT be pasted into the README; the file path is linked instead. Shell commands to
run are allowed. When the direction changes, the current direction MUST be updated and
abandoned approaches moved to a "Superseded options" section.

### VIII. Honest Reporting
Reports MUST state what was verified and what was not. A step MUST NOT be described as
working, deployed or fixed unless it was checked in the place it matters (for example, the
deployed Azure app, not only the local machine). Failures, skipped steps and unconfirmed
assumptions MUST be stated plainly.

### IX. Deployment Safety
Changes that affect the live Azure app MUST be made with the least disruption:
- A targeted update (rebuild the image, then update the container app) MUST be preferred
  over `deploy.ps1` when the API key must stay the same, because `deploy.ps1` recreates the
  backend and issues a new `API_KEY` on every run.
- Every `az` step MUST check its exit code, and a failed step MUST stop the script.
- Resources shared with other work (the resource group `insu_rag_rg`, the AI Search service,
  the Azure OpenAI resource) MUST NOT be deleted as part of deploying this app.
- Temporary code or settings (failure drills, `SIMULATE_FAILURE`, debug switches) MUST be
  switched off immediately after use and removed from the code when no longer needed.
- After a deploy, the live endpoints (`/health`, `/ready`) MUST be checked.

## Technology and Security Constraints

- **Stack:** Python and FastAPI backend, LangChain, Azure OpenAI (`text-embedding-3-small`,
  `gpt-4.1-mini`), Azure AI Search, React with TypeScript and Vite, deployed to Azure
  Container Apps (backend) and Static Web Apps (frontend, invited users only).
- **Known accepted limit:** the shared `API_KEY` is built into the frontend bundle. It keeps
  strangers out but not invited users. It MUST NOT be reused for anything else, and it MUST
  be rotated if it leaks outside the deployed bundle.
- **Index naming:** the search index name comes from `AZURE_SEARCH_INDEX` (default
  `insurance-policies-v2`). Code that only reads MUST NOT create the index.
- **Documents:** sample documents are fictional and named `insurance_<brand>_v1.pdf`. No
  real personal or policy data MUST be added to the repository.
- **Cost:** operations that call Azure OpenAI in bulk (re-indexing, load tests) MUST be
  mentioned to the owner before they are run.

## Development Workflow and Quality Gates

- Work happens on a feature branch and reaches `main` through a pull request.
- Before a change is considered done: tests pass (Principle I), `pip check` is clean, `npm
  run build` passes for frontend changes, no secret is in the diff (Principles IV and V), and
  the README is updated (Principle VII).
- Before a pull request is raised, the branch is validated against the branching strategy and
  quality gate (the `validate-pr` skill).
- Spec-driven changes SHOULD follow the Spec Kit flow: `/speckit-specify`, `/speckit-plan`,
  `/speckit-tasks`, `/speckit-implement`.
- `CLAUDE.md` holds working rules for the coding agent and MUST NOT contradict this
  constitution. Where they differ, this constitution wins.

## Governance

This constitution supersedes other practices and the working notes in `CLAUDE.md`.
Amendments MUST be made through `/speckit-constitution`, MUST be recorded in the README, and
MUST update the version below. Versioning follows semantic versioning: MAJOR for removing or
redefining a principle in a backward-incompatible way, MINOR for adding a principle or
materially expanding guidance, PATCH for clarifications and wording. Every plan, pull request
and review MUST check compliance with these principles, and any deviation MUST be justified
in writing in the plan or pull request. Runtime guidance for the coding agent is in
`CLAUDE.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-16 | **Last Amended**: 2026-11-24
