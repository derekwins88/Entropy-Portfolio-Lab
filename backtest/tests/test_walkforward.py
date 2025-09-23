from __future__ import annotations

import pandas as pd

from backtest.walkforward import anchored_walk_forward
from backtest.strategies.flat import Flat


def test_walkforward_flat_strategy_has_flat_oos_returns():
    index = pd.date_range("2020-01-01", periods=60, freq="B")
    prices = pd.Series(100 + index.to_series().rank(method="first") * 0.1, index=index)
    df = prices.to_frame("close")

    results = anchored_walk_forward(
        df,
        lambda params: Flat(params),
        param_grid=[{}],
        min_train=20,
        test_window=10,
        starting_cash=10_000.0,
    )

    assert results, "Expected at least one walk-forward split"
    for split in results:
        assert abs(split.oos_stats.get("TotalReturn", 0.0)) < 1e-9
        assert abs(split.oos_stats.get("CAGR", 0.0)) < 1e-9
        assert split.oos_stats.get("Trades", 0.0) == 0.0
