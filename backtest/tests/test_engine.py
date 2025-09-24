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


def test_engine_empty_data():
    df = pd.DataFrame(columns=["close"], dtype=float)
    result = run_backtest(df, Noop({}), starting_cash=5_000, mode="target")
    assert result.equity_curve.empty
    assert result.position_curve.empty


def test_engine_high_entropy_scenario():
    idx = pd.date_range("2024-01-02", periods=6, freq="B")
    df = pd.DataFrame(
        {
            "close": [100, 50, 125, 60, 140, 80],
        },
        index=idx,
    )
    result = run_backtest(df, Noop({}), starting_cash=1_000, mode="target")
    assert len(result.equity_curve) == len(df)
    assert (result.equity_curve == 1_000).all()
