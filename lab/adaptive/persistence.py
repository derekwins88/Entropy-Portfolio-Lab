"""Simple, safe persistence helpers for adaptive state."""
from __future__ import annotations

import io
import json
import os
import pickle
import tempfile
from dataclasses import asdict, is_dataclass
from typing import Any


def _atomic_write(path: str, data: bytes) -> None:
    """Write *data* to *path* atomically."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def save_pickle(path: str, obj: Any) -> None:
    """Persist *obj* to *path* using pickle with an atomic write."""
    buffer = io.BytesIO()
    pickle.dump(obj, buffer, protocol=pickle.HIGHEST_PROTOCOL)
    _atomic_write(path, buffer.getvalue())


def load_pickle(path: str) -> Any:
    """Load a pickled object from *path*."""
    with open(path, "rb") as handle:
        return pickle.load(handle)


def to_jsonable(obj: Any) -> Any:
    """Return a JSON-serialisable representation of *obj*."""
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return obj


def save_json(path: str, obj: Any, **kwargs: Any) -> None:
    """Persist *obj* as JSON to *path* using an atomic write."""
    data = json.dumps(to_jsonable(obj), indent=2, sort_keys=True, **kwargs).encode("utf-8")
    _atomic_write(path, data)


def load_json(path: str) -> Any:
    """Load JSON data from *path*."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
