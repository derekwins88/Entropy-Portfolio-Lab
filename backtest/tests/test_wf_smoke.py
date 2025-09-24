import numpy as np
import pandas as pd

from backtest.core.engine import run_backtest
from backtest.strategies.trinity import factory as make_trinity
from backtest.walk_forward import walk_forward


def test_walk_forward_generates_oos_returns(tmp_path):
    rng = np.random.default_rng(7)
    index = pd.date_range("2021-01-04", periods=520, freq="B")
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, len(index))))
    frame = pd.DataFrame(
        {
            "close": prices,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "volume": np.full(len(index), 1_000_000),
        },
        index=index,
    )

    grid = [
        {
            "entropy_lookback": 20,
            "entry_entropy_threshold": 0.5,
            "breakout_period": 30,
            "ema_fast": 10,
            "ema_slow": 40,
            "vwap_len": 10,
        }
    ]

    oos = walk_forward(
        frame,
        make_trinity,
        grid,
        train_days=400,
        test_days=100,
        run_backtest=run_backtest,
        mode="target",
        sizing_kwargs={"size_notional": 10_000},
        out_csv=tmp_path / "wf_oos.csv",
    )

    assert len(oos) >= 90
    assert (tmp_path / "wf_oos.csv").exists()
