import os


# Fails at the top of a function, before any API call, naming every missing setting at once, instead of a confusing
# KeyError or Azure auth error deep inside an SDK call later that only reports one missing setting at a time.
def require_settings(*names: str) -> None:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings in .env: {', '.join(missing)}")
