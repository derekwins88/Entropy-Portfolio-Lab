import numpy as np
import pandas as pd

from backtest.engines.multi_asset_backtest import run_backtest
from backtest.strategies.praetorian import factory


def test_praetorian_runs_and_closes_trades():
    idx = pd.date_range("2022-01-03", periods=320, freq="B")
    base = np.cumsum(np.random.normal(0, 0.8, len(idx)))
    price = 100 + base
    df = pd.DataFrame(
        {
            "close": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "volume": 1_000_000,
        },
        index=idx,
    )
    strat = factory(dict(entry_entropy_threshold=0.02))
    result = run_backtest(
        df,
        strat,
        mode="target",
        size_notional=10_000,
        risk_R=1.0,
        atr_len=14,
        risk_pct=0.01,
    )
    assert len(result.equity_curve) == len(df)
