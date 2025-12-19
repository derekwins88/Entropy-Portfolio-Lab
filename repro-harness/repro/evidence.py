import json
import os
import time
from typing import Any

ART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")
EVID_PATH = os.path.join(ART_DIR, "evidence.jsonl")


def ensure_artifacts_dir() -> None:
    os.makedirs(ART_DIR, exist_ok=True)


def log_evidence(entry: dict[str, Any]) -> None:
    ensure_artifacts_dir()
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **entry,
    }
    with open(EVID_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
