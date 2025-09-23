import numpy as np
import pandas as pd

from backtest.core.metrics import summarize


def test_summarize_benchmark_metrics():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    equity = pd.Series([100.0, 105.0, 100.0, 102.0, 101.0], index=idx)
    bench = equity.copy()

    stats = summarize(equity, bench=bench)

    assert stats["Beta"] == 1.0
    assert abs(stats["Alpha"]) < 1e-12
    assert stats["TrackingError"] == 0.0
    assert np.isnan(stats["InformationRatio"])
    assert stats["UpCapture"] == 1.0
    assert stats["DownCapture"] == 1.0
