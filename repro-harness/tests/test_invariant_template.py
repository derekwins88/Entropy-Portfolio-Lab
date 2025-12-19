from repro.config import load_config
from repro.http import request_json
from repro.evidence import log_evidence


def test_invariant_placeholder():
    """
    Replace with your invariant.
    Example: 'A user must not read another user's resource.'
    """
    cfg = load_config()

    # TODO: set endpoint and headers
    url = f"{cfg.base_url}/api/health"

    status, data, text = request_json("GET", url)

    log_evidence({
        "test": "invariant_placeholder",
        "url": url,
        "status": status,
        "body_preview": text[:300],
    })

    # Placeholder assertion (make this meaningful per target)
    assert status in (200, 401, 403)
