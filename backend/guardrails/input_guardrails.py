import re

from guardrails.exceptions import InputBlockedError
from observability.tracing import traced
from opentelemetry import trace

# Deterministic (regex only, no model call) checks on the user's question, before it reaches retrieval or the chat
# model. Free and instant, but can only catch what a pattern can catch; see backend/evals/interview_notes.md for
# why this is only half of a guardrail strategy (the model-graded output checks are the other half).

LENGTH = re.compile(
    r"\b(?:.{1000,}|.{200,}\s+){3,}.*\b", re.DOTALL
)  # 3+ lines of 200+ chars each or 1000+ chars total

INJECTION = re.compile(
    r"\b(ignore|disregard|forget)\b(?:\s+\w+){0,4}\s+\b(previous|above|prior|all)\b(?:\s+\w+){0,4}\s+\b(instructions?|rules?|prompt)\b"
    r"|\breveal\b.{0,20}\bsystem prompt\b"
    r"|\bprint\b.{0,20}\b(system prompt|instructions)\b"
    r"|\byou are now\b"
    r"|\bact as\b.{0,20}\b(dan|jailbreak)\b",
    re.IGNORECASE,
)

URGENT = re.compile(
    # Combined with a sign of real distress, not the bare word "emergency" (a normal policy term, e.g.
    # "emergency roadside assistance") or "accident" on its own (a normal word for a claim already settled).
    r"\b(accident|crash|collision)\b.{0,30}\b(injur\w*|hurt|ambulance|bleeding|unconscious)\b"
    r"|\bsomeone(?:'s| is) (?:hurt|injured)\b"
    r"|\bi(?:'m| am) (?:injured|bleeding|unconscious)\b",
    re.IGNORECASE,
)

ADVICE = re.compile(
    r"\bshould i (?:sue|claim against|fire|complain about|invest)\b"
    r"|\blegal advice\b"
    r"|\bfinancial advice\b"
    r"|\bis it worth investing\b",
    re.IGNORECASE,
)

PROFANITY = re.compile(r"\b(fuck\w*|shit\w*|bastard|asshole)\b", re.IGNORECASE)  # small, deliberately short list

PII = {
    "email address": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "UK National Insurance number": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b", re.IGNORECASE),
    # 9+ digits in a row (ignoring spaces/dashes): a card, account or phone number, not a claim amount or year.
    "long number": re.compile(r"\b(?:\d[ -]?){9,}\b"),
}


# Check deterministic input guardrails on the question
# against every rule above and raises InputBlockedError(reason) on the first match.
@traced("input_guardrails")
def deterministic_guardrail(question: str) -> None:
    span = trace.get_current_span()
    reason = None
    if LENGTH.search(question):
        reason = "length_exceeded"
    elif INJECTION.search(question):
        reason = "prompt_injection"
    elif URGENT.search(question):
        reason = "urgent_emergency"
    elif ADVICE.search(question):
        reason = "regulated_advice"
    elif PROFANITY.search(question):
        reason = "abusive_language"
    else:
        for name, pattern in PII.items():
            if pattern.search(question):
                reason = f"pii:{name}"
                break
    if reason:
        span.set_attribute("guardrail.input_blocked", reason)
        raise InputBlockedError(reason)


@traced("input_guardrails")
def input_guardrails(question: str) -> None:
    deterministic_guardrail(question)