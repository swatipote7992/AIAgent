import openai
from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError

# HTTP status codes that may pass on their own: timeout, too many requests and server errors.
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


def is_transient(error: BaseException) -> bool:
    # True for a failure that may pass on its own: a timeout, a lost connection, a 429 or a 5xx.
    # False for errors that trying again cannot fix: a bad request, a wrong key, the content filter, a cut-off answer.
    #
    # This code does not retry anything itself. The OpenAI client and the Azure SDK already retry a failed call
    # (with backoff, jitter and Retry-After), and that is the only place a call is retried. This function only
    # decides whether a call that is still failing after those retries may go to the fallback deployment.
    for _ in range(3):  # also look at the error this one was raised from
        if isinstance(error, (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)):
            return True
        if isinstance(error, openai.APIStatusError):
            return error.status_code in TRANSIENT_STATUS
        if isinstance(error, (ServiceRequestError, ServiceResponseError)):
            return True
        if isinstance(error, HttpResponseError):
            return error.status_code in TRANSIENT_STATUS
        if error.__cause__ is None:
            return False
        error = error.__cause__
    return False
