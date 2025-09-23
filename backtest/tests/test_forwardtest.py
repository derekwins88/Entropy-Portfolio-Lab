from __future__ import annotations

import json
import pandas as pd

from forwardtest.runner import run_once


def test_forward_run_smoke(tmp_path):
    df = pd.DataFrame(
        {
            "open": [100, 101, 102, 101, 102],
            "high": [101, 102, 103, 102, 103],
            "low": [99, 100, 101, 100, 101],
            "close": [100, 101, 102, 101, 102],
        },
        index=pd.date_range("2024-01-01", periods=5, freq="B"),
    )
    csv_path = tmp_path / "X.csv"
    df.to_csv(csv_path)

    spec = {
        "name": "X",
        "csv": str(csv_path),
        "strategy": "backtest.strategies.flat:Flat",
        "params": {},
        "mode": "target",
        "size": 1,
        "expect_ohlc": True,
    }

    root = tmp_path / "forward"
    line = run_once(spec, root=root)
    assert "EndEq" in line

    state = json.loads((root / "state.json").read_text())
    assert state["X"] == df.index[-1].isoformat()

    trades_file = root / "logs" / "X_Flat.trades.csv"
    equity_file = root / "logs" / "X_Flat.equity.csv"
    assert trades_file.exists()
    assert equity_file.exists()

    # Second run with no new rows should be a noop
    assert run_once(spec, root=root) == "noop"
