import os

from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator, ResponseCompletenessEvaluator

# Model-graded checks from the Azure AI Evaluation SDK. Each asks a judge model for a score from 1 (worst) to 5 (best):
#   groundedness  is every claim of the answer supported by the chunks the model was given?
#   relevance     does the answer address the question?
#   completeness  does the answer contain what the reference answer in the golden dataset contains?
# Each judged answer is 3 calls to the judge model, so this is the part of an eval run that costs money.
# The judge is the same chat deployment as the app unless EVAL_JUDGE_DEPLOYMENT names another one; a judge that is the
# same model as the one being judged tends to be kind to it, so prefer a different (stronger) deployment if you have one.

SCORE_KEYS = {"groundedness": "groundedness", "relevance": "relevance", "completeness": "response_completeness"}


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


def judge_answer(judges: dict, case: dict, answer: str, context: str) -> dict:
    # Returns {name: {"score": float or None, "reason": str, "error": str or None}} for each judge.
    calls = {
        "groundedness": lambda: judges["groundedness"](query=case["question"], response=answer, context=context),
        "relevance": lambda: judges["relevance"](query=case["question"], response=answer),
        "completeness": lambda: judges["completeness"](ground_truth=case["expected_answer"], response=answer),
    }
    out = {}
    for name, call in calls.items():
        try:
            result = call()
            key = SCORE_KEYS[name]
            score = result.get(key)
            out[name] = {
                "score": float(score) if score is not None else None,
                "reason": str(result.get(f"{key}_reason", ""))[:300],
                "error": None,
            }
        except Exception as error:  # one failed judge call must not stop the run
            out[name] = {"score": None, "reason": "", "error": f"{type(error).__name__}: {str(error)[:150]}"}
    return out
