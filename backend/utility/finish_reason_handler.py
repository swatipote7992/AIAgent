from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry import trace


class FinishReasonHandler(BaseCallbackHandler):
    # Collects the finish reason of every model call of one question and puts the list on the current span.
    # "stop" is a normal end, "length" means the max_tokens cap cut the reply.
    # on_llm_end is not called when the call raises (a cut-off structured reply raises LengthFinishReasonError),
    # so the caller records that case itself with record("length").
    def __init__(self):
        self.reasons: list[str] = []

    def record(self, reason) -> None:
        if reason:
            self.reasons.append(str(reason))
            trace.get_current_span().set_attribute("gen_ai.response.finish_reasons", list(self.reasons))

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                info = generation.generation_info or {}
                message = getattr(generation, "message", None)
                meta = getattr(message, "response_metadata", None) or {}
                self.record(info.get("finish_reason") or meta.get("finish_reason"))
