import importlib
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Reads SYS_PROMPT_VERSION and CONTINUE_PROMPT_VERSION from the root .env, like the other modules
# (.env wins over the shell). In Azure there is no .env file and the container app's own settings are used.
load_dotenv(override=True)

# Each prompt kind is a set of modules here named <kind>_v<number>.py with one text constant:
#   sys_prompt_v<N>.py      SYSTEM_PROMPT    the system prompt for answering (setting SYS_PROMPT_VERSION)
#   continue_prompt_v<N>.py CONTINUE_PROMPT  the instruction sent to continue a cut-off reply (setting CONTINUE_PROMPT_VERSION)
# To change a prompt, add a new version; do not edit an old one. An empty setting means the latest version.
PROMPTS_DIR = Path(__file__).parent


def available_versions(kind: str = "sys_prompt") -> list[str]:
    # e.g. ["v1", "v2"], sorted by number
    found = []
    for f in PROMPTS_DIR.glob(f"{kind}_v*.py"):
        m = re.fullmatch(rf"{kind}_(v\d+)", f.stem)
        if m:
            found.append(m.group(1))
    return sorted(found, key=lambda v: int(v[1:]))


def _load(kind: str, constant: str, setting: str, version: str | None) -> tuple[str, str]:
    # Returns (text, version). Version order: argument, then the setting from .env, then the latest file.
    versions = available_versions(kind)
    if not versions:
        raise FileNotFoundError(f"No {kind}_v<N>.py files in {PROMPTS_DIR}")
    wanted = (version or os.environ.get(setting) or "").strip().lower()  # " V3 " counts as v3
    version = wanted or versions[-1]
    if version not in versions:
        raise ValueError(f"No {kind} version '{version}'. Available: {versions}")
    module = importlib.import_module(f".{kind}_{version}", __package__)
    return getattr(module, constant), version


def load_system_prompt(version: str | None = None) -> tuple[str, str]:
    return _load("sys_prompt", "SYSTEM_PROMPT", "SYS_PROMPT_VERSION", version)


def load_continue_prompt(version: str | None = None) -> tuple[str, str]:
    return _load("continue_prompt", "CONTINUE_PROMPT", "CONTINUE_PROMPT_VERSION", version)
