import importlib
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Reads SYS_PROMPT_VERSION from the root .env, like the other modules (.env wins over the shell).
# In Azure there is no .env file and the container app's own setting is used.
load_dotenv(override=True)

# Each version of the system prompt is a module here named sys_prompt_v<number>.py
# with a SYSTEM_PROMPT string. To change the prompt, add a new version; do not edit an old one.
PROMPTS_DIR = Path(__file__).parent


def available_versions() -> list[str]:
    # e.g. ["v1", "v2"], sorted by number
    found = []
    for f in PROMPTS_DIR.glob("sys_prompt_v*.py"):
        m = re.fullmatch(r"sys_prompt_(v\d+)", f.stem)
        if m:
            found.append(m.group(1))
    return sorted(found, key=lambda v: int(v[1:]))


def load_system_prompt(version: str | None = None) -> tuple[str, str]:
    # Returns (text, version). Version order: argument, then SYS_PROMPT_VERSION from .env, then the latest file.
    versions = available_versions()
    if not versions:
        raise FileNotFoundError(f"No sys_prompt_v<N>.py files in {PROMPTS_DIR}")
    wanted = (version or os.environ.get("SYS_PROMPT_VERSION") or "").strip().lower()  # " V3 " counts as v3
    version = wanted or versions[-1]
    if version not in versions:
        raise ValueError(f"No system prompt version '{version}'. Available: {versions}")
    module = importlib.import_module(f".sys_prompt_{version}", __package__)
    return module.SYSTEM_PROMPT, version
