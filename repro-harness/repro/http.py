import time
import requests
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def request_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, Any] | None, str]:
    r = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
    text = r.text[:4000]
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data, text
