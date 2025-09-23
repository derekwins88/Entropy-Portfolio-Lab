import pandas as pd

from backtest.attribution import attribute_returns, percent_contributions, pivot_attribution


def test_attribution_sums_match():
    trades = [
        {"asset": "AAPL", "pnl": 10.0, "exit_time": "2024-01-03"},
        {"asset": "MSFT", "pnl": -5.0, "exit_time": "2024-01-04"},
        {"asset": "AAPL", "pnl": 2.0, "exit_time": "2024-01-05"},
    ]
    regimes = pd.Series(
        ["P", "NP", "P"],
        index=pd.to_datetime(["2024-01-02", "2024-01-04", "2024-01-05"]),
    )
    df = attribute_returns(trades, regimes)
    assert round(df["pnl"].sum(), 6) == 7.0

    pivot = pivot_attribution(df)
    assert set(pivot.index) == {"AAPL", "MSFT"}

    percent = percent_contributions(df)
    assert all(percent.sum(axis=0).round(6) == 100.0)
