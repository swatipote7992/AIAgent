import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

    @app.exception_handler(AnswerBlockedError)
    async def answer_blocked(request: Request, error: AnswerBlockedError):
        log.error("answer blocked: %s", error)
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(AnswerTruncatedError)
    async def answer_truncated(request: Request, error: AnswerTruncatedError):
        log.error("answer truncated: %s", error)
        return JSONResponse(status_code=502, content={"detail": str(error)})
