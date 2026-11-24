import json
import os
import tempfile
from pathlib import Path

from azure.ai.evaluation import (
    GroundednessEvaluator,
    RelevanceEvaluator,
    ResponseCompletenessEvaluator,
    evaluate,
)

# Model-graded checks from the Azure AI Evaluation SDK. Each asks a judge model for a score from 1 (worst) to 5 (best):
#   groundedness  is every claim of the answer supported by the chunks the model was given?
#   relevance     does the answer address the question?
#   completeness  does the answer contain what the reference answer in the golden dataset contains?
# Each judged answer is 3 calls to the judge model, so this is the part of an eval run that costs money.
# The judge is the same chat deployment as the app unless EVAL_JUDGE_DEPLOYMENT names another one; a judge that is the
# same model as the one being judged tends to be kind to it, so prefer a different (stronger) deployment if you have one.

SCORE_KEYS = {
    "groundedness": "groundedness",
    "relevance": "relevance",
    "completeness": "response_completeness",
}


# Builds the three judge evaluators, all pointed at one chat deployment (the app's own unless overridden).
def build_judges(deployment: str | None = None) -> dict:
    model_config = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": deployment
        or os.environ.get("EVAL_JUDGE_DEPLOYMENT")
        or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini"),
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    }
    return {
        "groundedness": GroundednessEvaluator(model_config),
        "relevance": RelevanceEvaluator(model_config),
        "completeness": ResponseCompletenessEvaluator(model_config),
    }


# Shared shape for one judge's result, used by both ways of judging an answer below.
def _score_entry(score, reason: str = "", error: str | None = None) -> dict:
    return {
        "score": float(score) if score is not None else None,
        "reason": reason[:300],
        "error": error,
    }


# Judges every row through evaluate() instead of calling the judges directly, so the run also shows up in Foundry.
def run_foundry_evaluation(
    rows: list[dict], azure_ai_project: str, deployment: str | None = None
) -> tuple[dict, str | None]:
    judges = build_judges(deployment)
    with tempfile.TemporaryDirectory() as tmp:
        data_path = Path(tmp) / "eval_data.jsonl"
        data_path.write_text(
            "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
        )
        result = evaluate(
            data=str(data_path),
            evaluators=judges,
            azure_ai_project=azure_ai_project,
            evaluation_name="rag-eval-v1",
        )
    by_id = {
        row.get("inputs.id"): {
            name: _score_entry(
                row.get(f"outputs.{name}.{key}"),
                str(row.get(f"outputs.{name}.{key}_reason", "")),
            )
            for name, key in SCORE_KEYS.items()
        }
        for row in result["rows"]
    }
    return by_id, result.get("studio_url")


# Returns {name: {"score", "reason", "error"}} for each judge; one failed call must not stop the run.
def judge_answer(judges: dict, case: dict, answer: str, context: str) -> dict:
    calls = {
        "groundedness": lambda: judges["groundedness"](
            query=case["question"], response=answer, context=context
        ),
        "relevance": lambda: judges["relevance"](
            query=case["question"], response=answer
        ),
        "completeness": lambda: judges["completeness"](
            ground_truth=case["expected_answer"], response=answer
        ),
    }
    out = {}
    for name, call in calls.items():
        try:
            result = call()
            key = SCORE_KEYS[name]
            out[name] = _score_entry(
                result.get(key), str(result.get(f"{key}_reason", ""))
            )
        except Exception as error:
            out[name] = _score_entry(
                None, error=f"{type(error).__name__}: {str(error)[:150]}"
            )
    return out
