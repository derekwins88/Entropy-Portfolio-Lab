import pytest
from repro.config import load_config
from repro.http import request_json
from repro.evidence import log_evidence


@pytest.mark.skipif(True, reason="Fill endpoint + tokens first")
def test_idor_read_forbidden():
    cfg = load_config()
    assert cfg.token_a and cfg.token_b, "Set TOKEN_A and TOKEN_B in .env"

    # TODO: create/choose a resource owned by A, then try to access from B
    resource_id_owned_by_a = "REPLACE_ME"

    url = f"{cfg.base_url}/api/resource/{resource_id_owned_by_a}"

    headers_a = {"Authorization": f"Bearer {cfg.token_a}"}
    headers_b = {"Authorization": f"Bearer {cfg.token_b}"}

    s_a, d_a, t_a = request_json("GET", url, headers=headers_a)
    s_b, d_b, t_b = request_json("GET", url, headers=headers_b)

    log_evidence({"test": "idor", "phase": "A_read", "url": url, "status": s_a, "preview": t_a[:250]})
    log_evidence({"test": "idor", "phase": "B_read", "url": url, "status": s_b, "preview": t_b[:250]})

    # Expected: B must be blocked
    assert s_a == 200
    assert s_b in (401, 403, 404)
