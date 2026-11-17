from langchain_core.messages import AIMessage, HumanMessage
from opentelemetry import trace

MAX_CONTINUATIONS = 3  # at most this many extra model calls to finish a reply cut by the token limit


class AnswerTruncatedError(RuntimeError):
    # The reply was still cut off after the last continuation, or the joined text is not a valid reply.
    pass


def _strip_fences(text: str) -> str:
    # The model sometimes wraps the rest of the text in a code fence; drop it.
    text = text.strip("\n")
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text


def continue_reply(llm, messages: list, partial: str, instruction: str, handler, max_rounds: int = MAX_CONTINUATIONS):
    # Send the partial reply back as an AI message and ask the model to carry on, up to max_rounds times.
    # Returns (full_text, rounds_used). Raises AnswerTruncatedError if it is still cut off after the last round.
    text = partial
    span = trace.get_current_span()
    for rounds in range(1, max_rounds + 1):
        span.set_attribute("llm.continuations", rounds)
        piece = llm.invoke(
            messages + [AIMessage(content=text), HumanMessage(content=instruction)],
            config={"callbacks": [handler]},
        )
        text += _strip_fences(piece.content)
        if (piece.response_metadata or {}).get("finish_reason") != "length":
            return text, rounds
    raise AnswerTruncatedError(
        f"The answer was still cut off after {max_rounds} continuations. Please ask a narrower question."
    )
