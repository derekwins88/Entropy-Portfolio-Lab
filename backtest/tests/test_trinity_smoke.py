import numpy as np
import pandas as pd

from backtest.core.engine import run_backtest
from backtest.strategies.trinity import factory as make_trinity


def test_trinity_generates_trades():
    idx = pd.date_range("2022-01-03", periods=220, freq="B")
    trend = np.linspace(100.0, 120.0, len(idx))
    noise = np.random.default_rng(42).normal(0.0, 0.01, len(idx))
    close = trend + noise
    high = close * 1.001
    low = close * 0.999
    volume = np.full(len(idx), 1_500_000)

    frame = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=idx
    )

    params = {
        "entropy_lookback": 20,
        "entry_entropy_threshold": 0.05,
        "breakout_period": 30,
        "ema_fast": 8,
        "ema_slow": 34,
        "vwap_len": 5,
        "signal_mode": "delta",
    }

    strategy = make_trinity(params)
    result = run_backtest(frame, strategy, mode="delta")

    assert len(result.fills) >= 1
