import importlib
import os
import re
from pathlib import Path

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
    # Returns (text, version). Version order: argument, then env SYS_PROMPT_VERSION, then the latest file.
    versions = available_versions()
    if not versions:
        raise FileNotFoundError(f"No sys_prompt_v<N>.py files in {PROMPTS_DIR}")
    version = version or os.environ.get("SYS_PROMPT_VERSION") or versions[-1]
    if version not in versions:
        raise ValueError(f"No system prompt version '{version}'. Available: {versions}")
    module = importlib.import_module(f".sys_prompt_{version}", __package__)
    return module.SYSTEM_PROMPT, version
