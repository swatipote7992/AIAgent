from functools import wraps

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("insur-rag")

#tracer is the thing that creates spans.
#The name insur-rag is just a label.
#traced("retrieval") makes a span named retrieval start when the function starts
#and end when it ends. The time between is its duration.
#python -c "from tracing import traced; f = traced('demo')(lambda: 5); print(f())

def traced(name):
    """Run the function inside a span called `name`, so its time shows up as one step of the question's trace."""

    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            # record_exception=False: the exception message could hold a secret, so keep only its type name
            with tracer.start_as_current_span(
                name, record_exception=False, set_status_on_exception=False
            ) as span:
                try:
                    return fn(*args, **kwargs)
                except Exception as error:
                    span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                    raise

        return inner

    return decorator
