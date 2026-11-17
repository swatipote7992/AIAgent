import logging
import time

import openai
from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError

log = logging.getLogger("retry")

# HTTP status codes worth trying again: timeout, too many requests and server errors.
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def is_transient(error: BaseException) -> bool:
    # True for a failure that may pass on its own: a timeout, a lost connection, a 429 or a 5xx.
    # False for errors that trying again cannot fix: a bad request, a wrong key, the content filter, a cut-off answer.
    for _ in range(3):  # also look at the error this one was raised from
        if isinstance(error, (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)):
            return True
        if isinstance(error, openai.APIStatusError):
            return error.status_code in RETRY_STATUS
        if isinstance(error, (ServiceRequestError, ServiceResponseError)):
            return True
        if isinstance(error, HttpResponseError):
            return error.status_code in RETRY_STATUS
        if error.__cause__ is None:
            return False
        error = error.__cause__
    return False


def call_with_retry(fn, retries: int = 1, delay: float = 0.5, what: str = "call"):
    # Run fn(). If it fails with a transient error, wait (delay, then twice as long each time) and run it again,
    # up to `retries` more times. Any other error, or the last failure, is raised as it is.
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as error:
            if attempt == retries or not is_transient(error):
                raise
            log.warning("%s failed (%s), retry %d of %d", what, type(error).__name__, attempt + 1, retries)
            time.sleep(delay * 2**attempt)
