---
name: "create-pr"
description: "Create a pull request for the current branch: checks status, drafts a title/summary from the commits, pushes, and opens the PR with gh."
argument-hint: "(optional) commit message / PR title, used verbatim — if omitted, you'll be asked for one"
user-invocable: true
disable-model-invocation: false
---

## What this skill does

Runs this project's quality gates against **only the currently staged files**, then drafts and opens a pull request scoped to exactly those files. Stack: Python/FastAPI backend (pytest, pip), React/TypeScript/Vite frontend (`tsc` + Vite build). Never push or open a PR if a gate fails — report the failure and stop. This skill never runs `git commit` — committing is always the user's own action.

## Steps

### 1. Determine the PR scope from staged files

- `git diff --staged --name-only` — this exact list is the scope of the PR. If it's empty, stop and ask the user to `git add` whatever they want included; do not fall back to unstaged or untracked changes.
- `git status --short` — note (don't include) any unstaged or untracked changes outside the staged list, so the user knows what's being left out.
- `git branch --show-current` and confirm it is not `main`.
- `git diff --staged --stat` — the actual content diff for everything in scope.

### 2. Naming standard (CLAUDE.md rule)

- For every **new** file in the staged list from step 1, check the snake_case rule: lowercase, underscores, no spaces, no vague names (`errors.py`, `utils.py`), no run-together words. Flag violations; do not rename files yourself — report them and ask whether to proceed or fix first.

### 3. Secrets check

- `git diff --staged` — scan for anything that looks like an API key, connection string, or token in the staged content. The repo's own hook ([.claude/hooks/block_secrets.py](.claude/hooks/block_secrets.py)) already blocks `git add` of `.claude/`/`.env`, but confirm nothing slipped through in a tracked file (e.g. a key pasted into a test or config).

### 4. Backend checks (only if a staged file is under `backend/`)

Run from `backend/` with the virtual environment active:
- `pip check` — no dependency conflicts.
- `python -m pytest` — all tests pass. If `requirements-dev.txt` isn't installed yet, install it first.
- If a backend lint tool is configured in `requirements-dev.txt` (none is, today — e.g. `ruff`/`flake8`), run it; otherwise skip this and say so rather than inventing a command.

### 5. Frontend checks (only if a staged file is under `frontend/`)

Run from `frontend/`:
- `npm run build` — this already runs `tsc --noEmit` (type check) then the Vite build, which is this project's standard in place of a separate lint step (no ESLint is configured in [frontend/package.json](frontend/package.json) today).

### 6. README check (CLAUDE.md working rule)

- Confirm `README.md` has a numbered step (or update) covering the staged work. If `README.md` itself isn't already staged with that update, stop and ask whether to add one before continuing — don't add it silently.

### 7. Report gate results

Before drafting anything, show a markdown table with one row per gate from steps 2–6 and columns `Gate | Status | Detail`. Status is one of `PASS`, `FAIL`, or `SKIPPED` (e.g. no backend/frontend files staged, or no lint tool configured) — never mark a gate `PASS` if it wasn't actually run. Example shape:

| Gate | Status | Detail |
| --- | --- | --- |
| Naming (snake_case) | PASS | 2 new files checked |
| Secrets | PASS | no matches in staged diff |
| Backend: pip check | SKIPPED | no backend files staged |
| Backend: pytest | SKIPPED | no backend files staged |
| Frontend: npm run build | FAIL | tsc error in src/App.tsx:42 |
| README updated | PASS | step 48 added |

If any row is `FAIL`, stop here — do not draft the PR, push, or ask for a commit. State the failure plainly and wait for the user to fix it and re-run the skill.

### 8. Use the user's text verbatim — do not draft anything

Only if every gate in step 7 is green:
- Take the text the user passed as the skill argument (`/create-pr <text>`). If none was given, **ask the user for it** — do not invent, expand, or auto-draft a message.
- Use that exact text as **both** the commit message and the PR title/body, with no additions. Do not reword it, add a summary, add a `## Summary`/`## Test plan` body, or append any attribution line or footer — this skill's commits and PRs carry no Claude/Claude Code attribution.

### 9. Get approval, then commit, push and open the PR

Show the gate table (step 7) and the exact text from step 8, and ask for explicit approval before doing anything irreversible. Only on approval:
1. `git commit -m "<user's text>"` — no attribution line, no additions. Commits exactly the staged files from step 1, nothing more.
2. `git push -u origin HEAD` (or a plain `git push` if the branch already tracks a remote).
3. `gh pr create --base main --title "<user's text>" --body "<user's text>"` — no attribution footer, body passed via a heredoc if the text spans multiple lines.
4. Run `git status` after the commit to confirm it succeeded, and return the PR URL.

If the user does not approve, stop — do not commit, push, or open anything. This is the one explicit case where this skill commits on the user's behalf; every other git workflow in this project stays commit-by-hand.

**`.claude/` exception:** if the staged scope from step 1 includes any file under `.claude/` or `.env`, the repo's own hook ([.claude/hooks/block_secrets.py](.claude/hooks/block_secrets.py)) will refuse the `git commit` in step 9 no matter what — it exists specifically so `.claude/` changes are reviewed and committed from the user's own terminal, not by an agent. Don't retry or try to work around it. Tell the user plainly that this commit needs to be run by them, give them the exact commit message, and stop — then offer to push and open the PR once they confirm it's committed.

