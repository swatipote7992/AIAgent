import os

import httpx
from opentelemetry import trace

from guardrails.exceptions import InputBlockedError
from observability.tracing import traced

API_VERSION = "2024-09-01"


# Calls Azure AI Content Safety's Prompt Shields: a real jailbreak/prompt-injection classifier, not a regex guess.
# Same account as AZURE_OPENAI_ENDPOINT (a multi-service AIServices resource), so the same key works here too.
# If the call itself fails (timeout, outage), the question is let through rather than blocking everyone on an
# Azure incident; the deterministic checks in input_guardrails.py still run either way.
@traced("prompt_shields")
def check_prompt_shields(question: str) -> None:
    endpoint = os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT", "").strip().rstrip("/")
    if not endpoint:
        return
    span = trace.get_current_span()
    span.set_attribute("gen_ai.operation.name", "content_safety")
    span.set_attribute("gen_ai.provider.name", "azure.ai.content_safety")
    url = f"{endpoint}/contentsafety/text:shieldPrompt?api-version={API_VERSION}"
    headers = {"Ocp-Apim-Subscription-Key": os.environ["AZURE_OPENAI_API_KEY"], "Content-Type": "application/json"}
    timeout = float(os.environ.get("PROMPT_SHIELDS_TIMEOUT_SECONDS", "5"))
    try:
        response = httpx.post(url, headers=headers, json={"userPrompt": question, "documents": []}, timeout=timeout)
        response.raise_for_status()
        attack_detected = response.json().get("userPromptAnalysis", {}).get("attackDetected", False)
    except Exception as error:
        span.set_attribute("prompt_shields.error", type(error).__name__)
        return  # fail open: a broken safety check must not take the whole app down
    span.set_attribute("prompt_shields.attack_detected", attack_detected)
    if attack_detected:
        raise InputBlockedError("prompt_injection")
