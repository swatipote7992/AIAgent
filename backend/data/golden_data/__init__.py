import importlib
import re
from pathlib import Path

# Each version of the golden dataset is a module here named golden_dataset_v<number>.py with a GOLDEN_DATASET list.
# To change the questions, add a new version; do not edit an old one.
DATASET_DIR = Path(__file__).parent


def available_versions() -> list[str]:
    found = []
    for f in DATASET_DIR.glob("golden_dataset_v*.py"):
        m = re.fullmatch(r"golden_dataset_(v\d+)", f.stem)
        if m:
            found.append(m.group(1))
    return sorted(found, key=lambda v: int(v[1:]))


def load_golden_dataset(version: str | None = None) -> tuple[list[dict], str]:
    # Returns (cases, version). No version means the latest.
    versions = available_versions()
    if not versions:
        raise FileNotFoundError(f"No golden_dataset_v<N>.py files in {DATASET_DIR}")
    version = (version or "").strip().lower() or versions[-1]
    if version not in versions:
        raise ValueError(f"No golden dataset version '{version}'. Available: {versions}")
    module = importlib.import_module(f".golden_dataset_{version}", __package__)
    return module.GOLDEN_DATASET, version
