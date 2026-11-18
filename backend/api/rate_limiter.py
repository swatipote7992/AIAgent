import os

from fastapi import Request
from slowapi import Limiter

# Limits on /api/ask, because the app is public and every question costs Azure OpenAI money.
# Two limits apply to every question, and a question that is refused still counts:
#   - per visitor: RATE_LIMIT_PER_VISITOR, for example "6/minute;60/hour" (one visitor = one network address)
#   - all visitors together: RATE_LIMIT_ALL_VISITORS_PER_DAY, for example "1000/day" (a ceiling on the daily cost)
# The counters live in this process's memory. That is enough while the app runs as ONE replica (it does), but they
# restart from zero when the container restarts or scales to zero, so the daily ceiling is a safety net, not exact.


def visitor_key(request: Request) -> str:
    # The visitor's network address as the ingress proxy saw it: the LAST X-Forwarded-For entry, which the proxy
    # added itself. Earlier entries are written by the visitor and could be faked to dodge the limit.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def all_visitors_key(request: Request) -> str:
    return "all-visitors"


def per_visitor_limit() -> str:
    return os.environ.get("RATE_LIMIT_PER_VISITOR", "6/minute;60/hour")


def all_visitors_limit() -> str:
    return os.environ.get("RATE_LIMIT_ALL_VISITORS_PER_DAY", "1000/day")


limiter = Limiter(key_func=visitor_key, enabled=os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false")
