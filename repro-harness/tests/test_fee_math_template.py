from repro.evidence import log_evidence


def fee_model(amount: int, fee_bps: int) -> int:
    # Example model; replace per target
    return (amount * fee_bps) // 10_000


def test_fee_rounding_sanity():
    # Replace with protocol-specific expected behavior
    fee_bps = 30  # 0.30%
    for amt in [1, 2, 3, 10, 100, 9999, 10_000, 10_001]:
        fee = fee_model(amt, fee_bps)
        log_evidence({"test": "fee_rounding", "amount": amt, "fee": fee})
        assert fee >= 0
        assert fee <= amt
