def test_same_bar_flip_records_two_trades():
    import pandas as pd

    from backtest.core.engine import run_backtest
    from backtest.core.strategy import BarStrategy

    class FlipOnce(BarStrategy):
        def __init__(self, params):
            super().__init__(params)
            self.fired = False

        def warmup(self):
            return 0

        def on_bar(self, t, row, i, broker):
            if i == 1 and not self.fired:
                self.fired = True
                return +1
            if i == 2:
                return -2
            return 0

    idx = pd.date_range("2024-01-02", periods=4, freq="B")
    df = pd.DataFrame({"close": [100, 101, 100, 99]}, index=idx)
    rr = run_backtest(df, FlipOnce({}), starting_cash=1000, size=1, mode="delta")
    assert len(rr.trade_log) == 2
