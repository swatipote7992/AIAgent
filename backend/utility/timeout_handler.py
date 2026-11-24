import asyncio
import contextvars
import os
import time

from fastapi.concurrency import run_in_threadpool

# One end-to-end deadline for a request (REQUEST_TIMEOUT_SECONDS). It is a time on the monotonic clock, kept in a
# context variable so every function the request calls can see it, including the worker thread that FastAPI runs
# the blocking work in (the thread gets a copy of the context). Without a request (a script) there is no deadline.
_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar("deadline", default=None)


class RequestTimeoutError(Exception):
    # The request used up its time budget.
    def __init__(self, budget: float | None = None):
        self.budget = budget
        limit = f"{budget:.0f} seconds" if budget else "the time limit"
        super().__init__(f"The answer took longer than {limit}. Please try again.")


def remaining() -> float | None:
    # Seconds left, or None when there is no deadline.
    deadline = _deadline.get()
    return None if deadline is None else deadline - time.monotonic()


def check_deadline() -> None:
    # Call before starting new work, so nothing new starts (and costs money) after the request has timed out.
    left = remaining()
    if left is not None and left <= 0:
        raise RequestTimeoutError()


def clamp_timeout(seconds: float) -> float:
    # A per-call timeout must never be longer than what is left of the request.
    check_deadline()
    left = remaining()
    return seconds if left is None else min(seconds, left)


async def run_with_deadline(fn, *args):
    # Run the blocking function fn in FastAPI's worker thread under one deadline.
    # Python cannot stop a running thread, so when the time is up we stop waiting and answer the client, and the
    # thread ends on its own: it starts no new call (check_deadline) and its calls have timeouts (clamp_timeout).
    budget = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "60"))
    token = _deadline.set(time.monotonic() + budget)
    try:
        async with asyncio.timeout(budget) as scope:
            return await run_in_threadpool(fn, *args)
    except TimeoutError as error:
        # a TimeoutError raised inside fn is an ordinary failure; only the budget running out is a RequestTimeoutError
        if scope.expired():
            raise RequestTimeoutError(budget) from error
        raise
    finally:
        _deadline.reset(token)
