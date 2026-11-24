import openai
from opentelemetry import trace

from guardrails.exceptions import InputBlockedError
from observability.tracing import traced

# Azure's content filter runs on every chat call automatically; it cannot be called ahead of time like Prompt
# Shields, only found out by making the call and seeing how it fails. Two different failures, two different
# places: a GENERATED answer that gets filtered raises ContentFilterFinishReasonError (handled in chain_llm.py,
# an AnswerBlockedError); the PROMPT itself being blocked, before any tokens are generated, raises this one.


# Call from an `except Exception` around the model invocation. Raises InputBlockedError("content_filter") when the
# question itself was blocked; otherwise returns, so the caller's own handling of every other error still applies.
@traced("content_filter_middleware")
def check_content_filter_error(error: BaseException) -> None:
    if not (isinstance(error, openai.BadRequestError) and getattr(error, "code", None) == "content_filter"):
        return
    span = trace.get_current_span()
    # Standard OpenTelemetry GenAI attribute names, same as the chat span, so this still shows as an AI call.
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.provider.name", "azure.ai.openai")
    categories = ((error.body or {}).get("innererror") or {}).get("content_filter_result") or {}
    flagged = sorted(name for name, result in categories.items() if result.get("filtered") or result.get("detected"))
    span.set_attribute("content_filter.categories", flagged)
    raise InputBlockedError("content_filter") from error
