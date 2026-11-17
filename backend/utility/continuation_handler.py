from langchain_core.messages import AIMessage, HumanMessage
from opentelemetry import trace

from utility.timeout_handler import check_deadline
from utility.finish_reason_handler import is_content_filter_error

MAX_CONTINUATIONS = 3  # at most this many extra model calls to finish a reply cut by the token limit


class AnswerTruncatedError(RuntimeError):
    # The reply was still cut off after the last continuation, or the joined text is not a valid reply.
    pass


class AnswerBlockedError(RuntimeError):
    # The model ended the reply for a reason other than "stop" or "length", for example the content filter.
    pass


def blocked_message(reason) -> str:
    if reason == "content_filter":
        return "The answer was stopped by the content filter. Please rephrase the question."
    return f"The model ended the answer unexpectedly (finish reason: {reason})."


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
    # Returns (full_text, rounds_used) when a round ends with "stop". Raises AnswerTruncatedError if it is still cut
    # off after the last round, and AnswerBlockedError if a round ends for any other reason (content_filter and so on).
    text = partial
    span = trace.get_current_span()
    for rounds in range(1, max_rounds + 1):
        check_deadline()  # no new model call once the request has run out of time
        span.set_attribute("llm.continuations", rounds)
        try:
            piece = llm.invoke(
                messages + [AIMessage(content=text), HumanMessage(content=instruction)],
                config={"callbacks": [handler]},
            )
        except Exception as error:
            if is_content_filter_error(error):
                raise AnswerBlockedError(blocked_message("content_filter")) from error
            raise
        reason = (piece.response_metadata or {}).get("finish_reason")
        if reason not in ("stop", "length"):
            raise AnswerBlockedError(blocked_message(reason))
        text += _strip_fences(piece.content)
        if reason == "stop":
            return text, rounds
    raise AnswerTruncatedError(
        f"The answer was still cut off after {max_rounds} continuations. Please ask a narrower question."
    )
