"""Smoke tests for the Cerberus Hyperion strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import run_backtest
from backtest.strategies.cerberus_hyperion import CerberusHyperion


def _synthetic_trend_frame(rows: int = 400) -> pd.DataFrame:
    index = pd.date_range("2022-01-03", periods=rows, freq="B")
    trend = 100.0 * np.exp(0.01 * np.arange(rows))
    close = trend
    open_ = close * 0.998
    high = close * 1.004
    low = close * 0.996
    volume = np.linspace(150_000, 450_000, rows)
    data = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )
    return data


def test_hyperion_smoke_generates_trades() -> None:
    frame = _synthetic_trend_frame()
    result = run_backtest(frame, CerberusHyperion({}), mode="delta", size_notional=10_000)
    assert len(result.trade_log) >= 1, "expected at least one trade in the smoke test"
