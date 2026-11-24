from langchain_core.callbacks import BaseCallbackHandler
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from opentelemetry import trace


def is_content_filter_error(error) -> bool:
    # The structured call raises openai's ContentFilterFinishReasonError. A plain call (the continuation rounds)
    # makes langchain-openai raise a ValueError whose message mentions the content filter instead.
    if isinstance(error, ContentFilterFinishReasonError):
        return True
    return isinstance(error, ValueError) and "content filter" in str(error).lower()


class FinishReasonHandler(BaseCallbackHandler):
    # Collects the finish reason of every model call of one question and puts the list on the current span.
    # "stop" is a normal end, "length" means the max_tokens cap cut the reply, "content_filter" means the
    # content filter stopped it. A call that raises does not reach on_llm_end, so on_llm_error records it:
    # a cut-off structured reply (LengthFinishReasonError) as "length", a filtered one as "content_filter",
    # and any other failure as "error:<exception class name>" (the class name only, never the message).
    def __init__(self):
        self.reasons: list[str] = []

    def record(self, reason) -> None:
        if reason:
            self.reasons.append(str(reason))
            trace.get_current_span().set_attribute("gen_ai.response.finish_reasons", list(self.reasons))

    def on_llm_error(self, error, **kwargs):
        if isinstance(error, LengthFinishReasonError):
            self.record("length")
        elif is_content_filter_error(error):
            self.record("content_filter")
        else:
            self.record(f"error:{type(error).__name__}")

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                info = generation.generation_info or {}
                message = getattr(generation, "message", None)
                meta = getattr(message, "response_metadata", None) or {}
                self.record(info.get("finish_reason") or meta.get("finish_reason"))
