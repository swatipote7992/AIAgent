from evals.gate_thresholds import GATE_THRESHOLDS, MAX_ERROR_RATE

# Turns the per-case rows of one run into numbers per prompt version, a table to read, and the pass/fail of the gate.


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def average(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    answered = [r for r in rows if not r.get("error")]
    answerable = [r for r in answered if r["answerable"]]
    with_sources = [r for r in answered if r["retrieval"] and r["retrieval"]["total"]]
    unanswerable = [r for r in answered if not r["answerable"] and r["category"] != "safety"]
    safety = [r for r in rows if r["category"] == "safety"]  # a safety case where the app raised an error counts as not passed
    with_facts = [r for r in answerable if r["facts"] and r["facts"]["total"]]
    summary = {
        "cases": len(rows),
        "errors": len(rows) - len(answered),
        "error_rate": rate(len(rows) - len(answered), len(rows)),
        "pass_rate": rate(sum(1 for r in rows if r.get("passed")), len(rows)),
        "retrieval_full_hit_rate": rate(sum(1 for r in with_sources if not r["retrieval"]["missing"]), len(with_sources)),
        "retrieval_recall": rate(sum(r["retrieval"]["found"] for r in with_sources), sum(r["retrieval"]["total"] for r in with_sources)),
        "facts_pass_rate": rate(sum(1 for r in with_facts if not r["facts"]["missing"]), len(with_facts)),
        "citation_ok_rate": rate(sum(1 for r in answerable if not r["invalid_citations"]), len(answerable)),
        "idk_rate": rate(sum(1 for r in unanswerable if r["admits_not_knowing"]), len(unanswerable)),
        "safety_pass_rate": rate(sum(1 for r in safety if r["passed"]), len(safety)),
        "wrongly_refused": sum(1 for r in answered if r["wrongly_refused"]),
    }
    for name in ("groundedness", "relevance", "completeness"):
        summary[name] = average([(r.get("judges") or {}).get(name, {}).get("score") for r in answered])
    categories = {}
    for r in rows:
        done, total = categories.get(r["category"], (0, 0))
        categories[r["category"]] = (done + (1 if r.get("passed") else 0), total + 1)
    summary["by_category"] = categories
    return summary


ROWS = [  # (label, key, kind)
    ("cases run", "cases", "int"),
    ("app errors", "errors", "int"),
    ("pass rate (all checks)", "pass_rate", "pct"),
    ("retrieval: found every page", "retrieval_full_hit_rate", "pct"),
    ("retrieval: pages found / expected", "retrieval_recall", "pct"),
    ("facts: all present", "facts_pass_rate", "pct"),
    ("citations: none invented", "citation_ok_rate", "pct"),
    ("says 'I don't know' when it should", "idk_rate", "pct"),
    ("safety cases passed", "safety_pass_rate", "pct"),
    ("wrongly refused to answer", "wrongly_refused", "int"),
    ("judge: groundedness (1-5)", "groundedness", "score"),
    ("judge: relevance (1-5)", "relevance", "score"),
    ("judge: completeness (1-5)", "completeness", "score"),
]


def _format(value, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value * 100:.0f}%"
    if kind == "score":
        return f"{value:.2f}"
    return str(value)


def format_table(summaries: dict[str, dict]) -> str:
    versions = list(summaries)
    width = max(len(label) for label, _, _ in ROWS) + 2
    lines = ["".ljust(width) + "".join(v.rjust(9) for v in versions)]
    for label, key, kind in ROWS:
        lines.append(label.ljust(width) + "".join(_format(summaries[v][key], kind).rjust(9) for v in versions))
    categories = sorted({c for s in summaries.values() for c in s["by_category"]})
    lines.append("")
    lines.append("passed / cases by category")
    for category in categories:
        cells = []
        for v in versions:
            done, total = summaries[v]["by_category"].get(category, (0, 0))
            cells.append(f"{done}/{total}".rjust(9))
        lines.append(category.ljust(width) + "".join(cells))
    return "\n".join(lines)


def check_gate(summary: dict) -> list[str]:
    # Returns one line for each pass mark that was missed. A metric that was not measured is skipped.
    failures = []
    for key, minimum in GATE_THRESHOLDS.items():
        value = summary.get(key)
        if value is not None and value < minimum:
            failures.append(f"{key} {value:.2f} is below the pass mark {minimum:.2f}")
    if summary["error_rate"] is not None and summary["error_rate"] > MAX_ERROR_RATE:
        failures.append(f"error_rate {summary['error_rate']:.2f} is above the limit {MAX_ERROR_RATE:.2f}")
    return failures
