# A question blocked before it reached retrieval or the chat model. The message is a short category (for example
# "prompt_injection"), never the question text; blocked_input_message() turns it into what the user sees.
class InputBlockedError(RuntimeError):
    pass


def blocked_input_message(reason: str) -> str:
    if reason.startswith("pii:"):
        return "Please don't include personal details (such as a card, account or phone number) in your question."
    messages = {
        "prompt_injection": "This question can't be answered as written. Please ask about the insurance policies directly.",
        "urgent_emergency": "This looks like it may need urgent help. Please contact your insurer's claims line or emergency services, not this assistant.",
        "regulated_advice": "This assistant can only answer questions about what the policy documents say, not give financial or legal advice.",
        "abusive_language": "Please rephrase your question without that language.",
        "length_exceeded": "Your question is too long. Please reframe and ask a shorter question.",
        "content_filter": "This question violates content policy. Please ask about the insurance policies directly.",
    }
    return messages.get(reason, "This question could not be answered.")


# A generated answer blocked before it reached the user. The message is a short category, never the answer text;
# blocked_output_message() turns it into what the user sees.
class OutputBlockedError(RuntimeError):
    pass


def blocked_output_message(reason: str) -> str:
    messages = {
        "prompt_leakage": "I can't share that. Please ask about what the policy documents say instead.",
        "invented_citation": "That answer could not be verified against the policy documents. Please rephrase your question.",
    }
    return messages.get(reason, "This answer could not be returned.")
