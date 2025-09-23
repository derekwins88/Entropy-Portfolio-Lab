import pandas as pd

from backtest.core.engine import run_backtest
from backtest.core.strategy import BarStrategy


class Noop(BarStrategy):
    def on_bar(self, t, row, i, broker):
        return 0


def test_noop_equity_constant():
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    df = pd.DataFrame({"close": 100.0}, index=idx)
    rr = run_backtest(df, Noop({}), starting_cash=10_000, mode="target")
    assert rr.equity_curve.iloc[0] == rr.equity_curve.iloc[-1]
