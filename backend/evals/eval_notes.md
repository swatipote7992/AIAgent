# How I built the eval pipeline — interview walkthrough

A step-by-step account of `backend/evals/`, in the order you'd explain it to an interviewer: what problem each step solves, and the code that backs it up. Use this as a script, not a reference doc.

**The one-line framing to open with:** "I needed a way to know if a change to the prompt or the retrieval made the RAG app's *answers* better or worse, not just whether the code still ran — so I built a small eval harness: a fixed question set, two kinds of checks (cheap deterministic ones and a model-graded judge), and a pass/fail gate."

---

## Step 1 — Build a fixed question set with known-good answers (the "golden dataset")

Without a fixed set of questions, every run is testing something different and results aren't comparable. So the first thing was a dataset of questions drafted from the real PDFs, each with the facts the answer must contain and where those facts live.

```python
# backend/data/golden_data/golden_dataset_v1.py
GOLDEN_DATASET = [
    {"id": "g001", "category": "direct", "answerable": True,
     "question": "Does the Audi policy cover a home wall charger, and up to what amount?",
     "expected_answer": "Yes. A home wall charger is covered up to GBP 1,000 if it is damaged or stolen.",
     "expected_facts": ["1000"], "sources": [{"file": "insurance_audi_v1.pdf", "page": "2"}]},
    ...
]
```

Six `category` values drive different checks later: `direct, comparison, partial, fallback, unanswerable, safety`. Loading is versioned on purpose — I never edit `golden_dataset_v1.py` once it exists, I add `golden_dataset_v2.py`, so an old run's results stay reproducible against the exact dataset that produced them:

```python
# backend/data/golden_data/__init__.py
def load_golden_dataset(version: str | None = None) -> tuple[list[dict], str]:
    version = (version or "").strip().lower() or versions[-1]   # no version given = latest
    module = importlib.import_module(f".golden_dataset_{version}", __package__)
    return module.GOLDEN_DATASET, version
```

## Step 2 — Run each question through the real app, not a mock

The eval calls the exact same function the API calls — no special test path, so the eval tests what actually ships.

```python
# backend/evals/run_evals.py
try:
    result = ask(case["question"])          # ask == retrieval.chain_llm.ask_llm
except Exception as error:                   # the app failing IS a result, not a reason to stop the run
    row["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    return row
answer, chunks = result["answer"], result["chunks"]
```

Catching the exception there matters: one bad question (a timeout, a content-filter block) shouldn't kill a 42-question run. It gets recorded as a failed row and the run continues.

## Step 3 — Check the answer without calling a model at all (cheap, deterministic, instant)

Before paying for a judge, I check things a model shouldn't be needed for: are the expected facts actually in the text, and did the model cite a page that doesn't exist.

```python
# backend/evals/answer_checks.py
def fact_found(answer: str, fact: str) -> bool:
    # "450|500" means either is fine; numbers must match whole (25 must not match inside 250)
    for option in fact.split("|"):
        pattern = re.escape(normalize(option))
        if option[0].isdigit():
            pattern = r"(?<![0-9.])" + pattern + r"(?![0-9])"
        if re.search(pattern, normalize(answer)):
            return True
    return False

def invalid_citations(answer: str) -> list[tuple[str, str]]:
    # citations() regex-extracts (file, page) pairs like "insurance_audi_v1.pdf, page 2"
    labels = pdf_page_labels()                              # real page labels, read once from the PDFs, @lru_cache'd
    return [(f, p) for f, p in citations(answer) if f not in labels or p not in labels[f]]
```

This is the part I'd call out as catching a *different class of bug* than an LLM judge: an invented citation or a wrong number is unambiguous and doesn't need a second opinion from another model.

## Step 4 — Check retrieval separately from the answer

An answer can be wrong for two different reasons — search didn't find the right page, or search found it but the model didn't use it well. Splitting the check tells you which one happened.

```python
# backend/evals/retrieval_checks.py
def check_retrieval(expected_sources: list[dict], chunks: list[dict]) -> tuple[int, int, list[str]]:
    got = {(str(c.get("source")), str(c.get("page"))) for c in chunks}
    missing = [f"{s['file']} page {s['page']}" for s in expected_sources if (s["file"], s["page"]) not in got]
    return len(expected_sources) - len(missing), len(expected_sources), missing
```

**Known limitation I'd mention if asked:** this checks at the page level, not the chunk level — it can say "found" even when the one specific chunk with the answer wasn't the chunk retrieved from that page.

## Step 5 — Add model-graded judges for the things regex can't catch

Facts-present and no-invented-citations don't tell you if the answer actually *reads well* or is *fully supported* by the context. For that I used the Azure AI Evaluation SDK's built-in judges.

```python
# backend/evals/judge_evaluators.py
from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator, ResponseCompletenessEvaluator

def build_judges(deployment: str | None = None) -> dict:
    model_config = {"azure_endpoint": ..., "api_key": ..., "azure_deployment": deployment or "gpt-4.1-mini", ...}
    return {
        "groundedness": GroundednessEvaluator(model_config),   # is every claim supported by the retrieved chunks?
        "relevance": RelevanceEvaluator(model_config),         # does it address the question?
        "completeness": ResponseCompletenessEvaluator(model_config),  # does it cover the reference answer?
    }

def judge_answer(judges: dict, case: dict, answer: str, context: str) -> dict:
    return {
        "groundedness": judges["groundedness"](query=case["question"], response=answer, context=context),
        ...
    }
```

Each judged answer is 3 extra model calls — the expensive part of a run. One deliberate choice: the judge deployment can be overridden with `EVAL_JUDGE_DEPLOYMENT`, because a model judging its own answers tends to be lenient on itself.

## Step 6 — Tie it together behind one CLI, with a cheap dry-run first

Everything above is driven by one entry point so a run is reproducible from a single command, and so you can see the cost *before* spending it.

```python
# backend/evals/run_evals.py
parser.add_argument("--versions", nargs="+", help="system prompt versions to compare")
parser.add_argument("--gate", action="store_true", help="exit 1 when a pass mark is missed")
parser.add_argument("--dry-run", action="store_true", help="show the plan and call nothing")
...
print_plan(cases, versions, args)
if args.dry_run:
    return 0                       # stops here — no Azure credentials even imported yet

from retrieval.chain_llm import ask_llm   # imported late on purpose, so --dry-run never needs them
```

```powershell
python -m evals.run_evals --dry-run                 # plan only
python -m evals.run_evals --limit 3 --versions v3    # small real run
python -m evals.run_evals --versions v1 v2 v3 --gate # full comparison, fail the build if a pass mark is missed
```

## Step 7 — Turn per-case rows into one number per metric, and a CI gate

Forty-two pass/fail rows aren't useful on their own — I needed one table to compare prompt versions, and one gate a pipeline could act on.

```python
# backend/evals/eval_report.py
def summarize(rows: list[dict]) -> dict:
    return {
        "pass_rate": rate(sum(1 for r in rows if r.get("passed")), len(rows)),
        "safety_pass_rate": rate(sum(1 for r in safety if r["passed"]), len(safety)),
        "groundedness": average([(r.get("judges") or {}).get("groundedness", {}).get("score") for r in answered]),
        ...
    }

# backend/evals/gate_thresholds.py
GATE_THRESHOLDS = {"pass_rate": 0.70, "safety_pass_rate": 1.00, "groundedness": 3.5, ...}

def check_gate(summary: dict) -> list[str]:
    return [f"{k} {summary[k]:.2f} is below {v:.2f}" for k, v in GATE_THRESHOLDS.items()
            if summary.get(k) is not None and summary[k] < v]
```

One rule I'd highlight: a safety case (prompt injection, personal data) that causes the *app itself* to error still counts as **not passed** in the summary — a safety check must not fail open just because something broke.

## Step 8 — The bug I found and fixed: eval runs weren't showing up in Azure AI Foundry

This is the best "debugging story" from the project, worth telling in full.

**Symptom:** the judge scores worked fine locally, but nothing ever appeared on the project's Evaluation page in the Foundry portal.

**Root cause, found by reading the SDK, not guessing:** calling an evaluator directly — `judges["groundedness"](query=..., response=..., context=...)` — only ever computes a score locally. It never talks to Azure at all. The *only* thing that uploads a run is the SDK's own batch function, `evaluate()`, called with a specific keyword:

```python
# backend/evals/judge_evaluators.py
# Judges every row through evaluate() instead of calling the judges directly, so the run also shows up in Foundry.
def run_foundry_evaluation(rows, azure_ai_project, evaluation_name, deployment=None):
    judges = build_judges(deployment)
    data_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")  # one JSONL file
    result = evaluate(
        data=str(data_path),
        evaluators=judges,
        azure_ai_project=azure_ai_project,     # <- this one keyword is what uploads the run
        evaluation_name=evaluation_name,
    )
    # scores come back as result["rows"][i]["outputs.<evaluator>.<key>"], matched back to our case by inputs.id
```

`azure_ai_project` had to be the *project endpoint*, not the plain Azure OpenAI endpoint:
`https://<resource>.services.ai.azure.com/api/projects/<project>` — I confirmed that shape by reading the installed SDK's own source for how it decides which upload path to use (`is_onedp_project()` just checks `isinstance(azure_ai_project, str)`), instead of trusting the docstring alone.

**Fix wired in:** `run_evals.py` now checks one setting (`AZURE_AI_PROJECT_ENDPOINT`) and, if it's set, batches a whole prompt version's answers through `run_foundry_evaluation()` in one call instead of judging case-by-case — same judge cost (still 3 calls per answer), but now the run is visible in the portal too.

**Verified, not just assumed:** ran it for real on 2 cases, got back a Foundry run URL, and confirmed in the portal — status "Completed", 100% / 2 of 2 passed on all three metrics, under evaluation name `v1_v3_20261119_173523`.

---

## If asked "why two kinds of checks instead of just the judge?"

| | Deterministic (`answer_checks.py`) | Judge (`judge_evaluators.py`) |
|---|---|---|
| Cost | free, instant | 3 model calls per answer |
| Good at | exact facts, invented citations | "does this actually address the question" |
| Consistency | identical input → identical result | a same-model judge can be lenient on itself |
| Blind spot | can't rate "almost right" | a fluent wrong answer can still score well |

The short version: the deterministic checks are the regression test you can run constantly for free; the judge is the closer-to-human-review check you run when you actually need the nuance.
