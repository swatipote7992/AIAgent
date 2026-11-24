import re

from opentelemetry import trace

from data.prompts import load_system_prompt
from guardrails.exceptions import OutputBlockedError
from observability.tracing import traced

# Phrases that suggest the model is talking about its own instructions rather than answering from the policies.
LEAKAGE_PHRASES = re.compile(
    r"\b(my (system )?instructions?\b|system prompt|i('m| am) instructed to|i cannot (reveal|share) my instructions"
    r"|as an ai (language )?model)\b",
    re.IGNORECASE,
)

# Citations use the same "[source, page X]" shape the context is built with in build_prompt().
CITATION = re.compile(r"\[([^,\]]+),\s*page\s*([^\]]+)\]", re.IGNORECASE)


@traced("output_guardrails")
def check_prompt_leakage(answer: str) -> None:
    # Blocks an answer that quotes the system prompt back, whether verbatim or by naming it.
    span = trace.get_current_span()
    if LEAKAGE_PHRASES.search(answer):
        span.set_attribute("guardrail.output_blocked", "prompt_leakage")
        raise OutputBlockedError("prompt_leakage")
    system_text, _ = load_system_prompt()
    words = re.findall(r"\w+", system_text.lower())
    answer_lower = answer.lower()
    for i in range(len(words) - 7):
        if " ".join(words[i : i + 8]) in answer_lower:
            span.set_attribute("guardrail.output_blocked", "prompt_leakage")
            raise OutputBlockedError("prompt_leakage")


@traced("output_guardrails")
def check_citation_grounding(answer: str, chunks) -> None:
    # Blocks an answer that cites a source not among the chunks actually retrieved for this question.
    known_sources = {str(c.metadata.get("source", "")).lower() for c in chunks}
    span = trace.get_current_span()
    for source, _page in CITATION.findall(answer):
        source_name = source.strip().lower()
        if not any(source_name in known or known in source_name for known in known_sources):
            span.set_attribute("guardrail.output_blocked", "invented_citation")
            raise OutputBlockedError("invented_citation")


def output_guardrails(answer: str, chunks) -> None:
    check_prompt_leakage(answer)
    check_citation_grounding(answer, chunks)
