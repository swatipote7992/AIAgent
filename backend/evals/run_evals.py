"""Run the evals against the golden dataset. Run it from backend/ with the virtual environment active:

    python -m evals.run_evals --dry-run                      show the plan and a rough size, call nothing
    python -m evals.run_evals --retrieval-only               only the search step (cheap, no chat model)
    python -m evals.run_evals --limit 3 --versions v3        a small first run on the 3 first cases
    python -m evals.run_evals --versions v1 v2 v3            compare the system prompt versions side by side
    python -m evals.run_evals --versions v3 --gate           exit code 1 when a pass mark in gate_thresholds.py is missed

This calls Azure OpenAI and Azure AI Search for real and costs money (the judge makes 3 calls per answer).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from data.golden_data import available_versions as dataset_versions
from data.golden_data import load_golden_dataset
from data.prompts import available_versions as prompt_versions
from data.prompts import load_system_prompt
from evals.answer_checks import admits_not_knowing, check_facts, invalid_citations, leaked
from evals.eval_report import check_gate, format_table, summarize
from evals.retrieval_checks import check_retrieval, retrieve_only

RESULTS_DIR = Path(__file__).parent / "results"  # git-ignored: answers and scores of each run
# Categories where "I don't know" is a wrong answer (the documents do contain it).
MUST_ANSWER = {"direct", "comparison", "fallback"}


def evaluate_case(case: dict, ask, judges: dict | None, judge_answer) -> dict:
    # Run one question through the app and apply every check. `ask`, `judges` and `judge_answer` are passed in so the
    # checks can be tested without calling Azure.
    row = {"id": case["id"], "category": case["category"], "answerable": case["answerable"], "question": case["question"],
           "error": None, "answer": "", "retrieval": None, "facts": None, "invalid_citations": [],
           "admits_not_knowing": False, "wrongly_refused": False, "leaked": [], "judges": None, "passed": False}
    started = time.perf_counter()
    try:
        result = ask(case["question"])
    except Exception as error:  # the app failing is a result too, not a reason to stop the run
        row["error"] = f"{type(error).__name__}: {str(error)[:200]}"
        row["seconds"] = round(time.perf_counter() - started, 1)
        return row
    row["seconds"] = round(time.perf_counter() - started, 1)
    answer, chunks = result["answer"], result["chunks"]
    row["answer"] = answer

    if case["sources"]:
        found, total, missing = check_retrieval(case["sources"], chunks)
        row["retrieval"] = {"found": found, "total": total, "missing": missing}
    found, total, missing = check_facts(answer, case["expected_facts"])
    row["facts"] = {"found": found, "total": total, "missing": missing}
    row["invalid_citations"] = invalid_citations(answer)
    row["admits_not_knowing"] = admits_not_knowing(answer)
    row["wrongly_refused"] = case["category"] in MUST_ANSWER and row["admits_not_knowing"] and bool(missing)
    row["leaked"] = leaked(answer, case.get("must_not_contain", []))

    if case["category"] == "safety":
        # injection: the system prompt must not leak; personal data: the model must decline
        row["passed"] = not row["leaked"] if case.get("must_not_contain") else row["admits_not_knowing"]
    elif not case["answerable"]:
        row["passed"] = row["admits_not_knowing"] and not row["invalid_citations"]
    else:
        row["passed"] = not missing and not row["invalid_citations"] and not row["wrongly_refused"]

    if judges:
        context = "\n\n".join(f"[{c['source']}, page {c['page']}]\n{c['text']}" for c in chunks)
        row["judges"] = judge_answer(judges, case, answer, context)
    return row


def select_cases(cases: list[dict], args) -> list[dict]:
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    if args.categories:
        cases = [c for c in cases if c["category"] in args.categories]
    return cases[: args.limit] if args.limit else cases


def print_plan(cases: list[dict], versions: list[str], args) -> None:
    answers = len(cases) * len(versions)
    print(f"Plan: {len(cases)} cases x {len(versions)} prompt version(s) {versions}")
    if args.retrieval_only:
        print(f"  {len(cases)} searches (one embedding call each); no chat model, no judge.")
        return
    prompt_tokens = {v: len(load_system_prompt(v)[0]) // 4 for v in versions}
    # rough: system prompt + about 1,500 tokens of retrieved chunks and question, per answer; judges ~2,500 tokens per call
    input_tokens = sum((prompt_tokens[v] + 1500) * len(cases) for v in versions)
    judge_calls = 0 if args.no_judge else 3 * answers
    print(f"  {answers} answers from the chat model, about {input_tokens:,} input tokens (a rough estimate).")
    print(f"  {judge_calls} judge calls, about {judge_calls * 2500:,} input tokens (a rough estimate)." if judge_calls else "  no judge calls (--no-judge).")
    print("  Prices are not looked up here: check the Azure OpenAI price of your deployment before a full run.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG app on the golden dataset.")
    parser.add_argument("--dataset", help=f"golden dataset version, one of {dataset_versions()} (default: latest)")
    parser.add_argument("--versions", nargs="+", help=f"system prompt versions to compare, from {prompt_versions()} or 'all' (default: the current one)")
    parser.add_argument("--ids", nargs="+", help="only these case ids, for example g001 g012")
    parser.add_argument("--categories", nargs="+", help="only these categories, for example direct comparison")
    parser.add_argument("--limit", type=int, help="only the first N cases after the filters")
    parser.add_argument("--retrieval-only", action="store_true", help="only check the search step")
    parser.add_argument("--no-judge", action="store_true", help="skip the model-graded scores (cheaper)")
    parser.add_argument("--judge-deployment", help="chat deployment that grades the answers (default: EVAL_JUDGE_DEPLOYMENT or the app's)")
    parser.add_argument("--gate", action="store_true", help="exit with code 1 when a pass mark in gate_thresholds.py is missed")
    parser.add_argument("--dry-run", action="store_true", help="show the plan and call nothing")
    args = parser.parse_args(argv)

    cases, dataset_version = load_golden_dataset(args.dataset)
    cases = select_cases(cases, args)
    if not cases:
        print("No cases match the filters.")
        return 2
    if args.versions == ["all"]:
        versions = prompt_versions()
    else:
        versions = [v.lower() for v in args.versions] if args.versions else [load_system_prompt()[1]]
    print(f"Golden dataset {dataset_version}, {len(cases)} cases.")
    print_plan(cases, versions, args)
    if args.dry_run:
        return 0

    from answering.insur_llm import ask_llm  # imported here so --dry-run needs no Azure settings

    judges, judge_answer = None, None
    if not args.retrieval_only and not args.no_judge:
        from evals.judge_evaluators import build_judges, judge_answer

        judges = build_judges(args.judge_deployment)

    all_rows: dict[str, list[dict]] = {}
    if args.retrieval_only:
        rows = []
        for case in cases:
            row = {"id": case["id"], "category": case["category"], "answerable": case["answerable"], "question": case["question"],
                   "error": None, "retrieval": None, "facts": None, "invalid_citations": [], "admits_not_knowing": False,
                   "wrongly_refused": False, "passed": False}
            try:
                if case["sources"]:
                    found, total, missing = check_retrieval(case["sources"], retrieve_only(case["question"]))
                    row["retrieval"] = {"found": found, "total": total, "missing": missing}
                    row["passed"] = not missing
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {str(error)[:200]}"
            rows.append(row)
            print(f"  {row['id']} {row['category']:<13} retrieval {_show(row)}")
        all_rows["search"] = [r for r in rows if r["retrieval"] or r["error"]]
    else:
        for version in versions:
            os.environ["SYS_PROMPT_VERSION"] = version  # the app reads it for every question
            print(f"\n--- system prompt {version} ---")
            rows = []
            for case in cases:
                row = evaluate_case(case, ask_llm, judges, judge_answer)
                rows.append(row)
                scores = " ".join(f"{k[:5]}={v['score']:.0f}" for k, v in (row["judges"] or {}).items() if v["score"] is not None)
                status = "ERROR " + row["error"] if row["error"] else ("pass" if row["passed"] else "FAIL")
                print(f"  {row['id']} {row['category']:<13} {status:<5} retrieval {_show(row)} {scores} ({row.get('seconds')}s)")
            all_rows[version] = rows

    summaries = {name: summarize(rows) for name, rows in all_rows.items()}
    print("\n" + format_table(summaries))
    for name, rows in all_rows.items():
        failed = [r["id"] for r in rows if not r.get("passed")]
        print(f"\nnot passed with {name}: {', '.join(failed) if failed else 'none'}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"dataset": dataset_version, "summaries": summaries, "rows": all_rows}, indent=2, default=str), encoding="utf-8")
    print(f"\nFull results (answers, scores, reasons): {out}")

    if args.gate:
        failures = [f"{name}: {line}" for name, s in summaries.items() for line in check_gate(s)]
        print("\nGATE: " + ("FAILED" if failures else "passed"))
        for line in failures:
            print("  - " + line)
        return 1 if failures else 0
    return 0


def _show(row: dict) -> str:
    r = row["retrieval"]
    return "n/a" if not r else f"{r['found']}/{r['total']}" + (f" missing {', '.join(r['missing'])}" if r["missing"] else "")


if __name__ == "__main__":
    sys.exit(main())
