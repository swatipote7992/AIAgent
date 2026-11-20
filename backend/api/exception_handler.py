import logging

from api.rate_limiter import all_visitors_key
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from guardrails.exceptions import InputBlockedError, OutputBlockedError, blocked_input_message, blocked_output_message
from slowapi.errors import RateLimitExceeded
from utility.continuation_handler import AnswerBlockedError, AnswerTruncatedError
from utility.timeout_handler import RequestTimeoutError

log = logging.getLogger("api.exception_handler")


def register_exception_handlers(app: FastAPI) -> None:
    # The body has the same shape as FastAPI's own errors: {"detail": "..."}.
    # These handlers run inside the CORS middleware,
    # so the browser can read the error message of the frontend's calls.

    @app.exception_handler(RequestTimeoutError)
    async def request_timeout(request: Request, error: RequestTimeoutError):
        log.error("request ran out of time (budget %s s)", error.budget)
        return JSONResponse(status_code=504, content={"detail": str(error)})

    @app.exception_handler(InputBlockedError)
    async def input_blocked(request: Request, error: InputBlockedError):
        log.warning("question blocked by input guardrail: %s", error)  # the reason category only, never the question
        return JSONResponse(status_code=422, content={"detail": blocked_input_message(str(error))})

    @app.exception_handler(OutputBlockedError)
    async def output_blocked(request: Request, error: OutputBlockedError):
        log.warning("answer blocked by output guardrail: %s", error)  # the reason category only, never the answer
        return JSONResponse(status_code=422, content={"detail": blocked_output_message(str(error))})

    @app.exception_handler(AnswerBlockedError)
    async def answer_blocked(request: Request, error: AnswerBlockedError):
        log.error("answer blocked: %s", error)
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(AnswerTruncatedError)
    async def answer_truncated(request: Request, error: AnswerTruncatedError):
        log.error("answer truncated: %s", error)
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(request: Request, error: RateLimitExceeded):
        # No address is logged, only which of the two limits was hit.
        daily_ceiling = error.limit.key_func is all_visitors_key
        log.warning("question refused: %s limit reached", "daily all-visitors" if daily_ceiling else "per-visitor")
        detail = (
            "The service has reached today's question limit. Please try again tomorrow."
            if daily_ceiling
            else "You are asking too fast. Please wait a moment and try again."
        )
        try:
            retry_after = int(error.limit.limit.get_expiry())  # length of the window that was used up, in seconds
        except Exception:
            retry_after = 60
        return JSONResponse(status_code=429, content={"detail": detail}, headers={"Retry-After": str(retry_after)})
