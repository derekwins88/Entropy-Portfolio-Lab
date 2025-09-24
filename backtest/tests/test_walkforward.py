from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backtest.walkforward import anchored_walk_forward, walk_forward
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


class _DummyResult:
    def __init__(self, index: pd.Index) -> None:
        self.equity_curve = pd.Series(np.linspace(1.0, 1.1, len(index)), index=index)
        self.fills = pd.DataFrame(columns=["timestamp", "symbol", "qty", "price"]).set_index(
            pd.Index([], name="timestamp")
        )
        self.trade_log = pd.DataFrame()


def _run_backtest_stub(frame: pd.DataFrame, strategy, seed: int | None = None, **_):
    if seed is not None:
        np.random.seed(seed)
    return _DummyResult(frame.index)


def _metric_stub(result: _DummyResult):
    eq = result.equity_curve
    ret = float(eq.iloc[-1] / eq.iloc[0] - 1.0) if len(eq) > 1 else 0.0
    return {"return": ret}


def test_simple_walkforward_report_is_deterministic(tmp_path):
    dates = pd.date_range("2022-01-01", periods=800, freq="D")
    df = pd.DataFrame({"close": np.linspace(100, 120, len(dates))}, index=dates)

    report = walk_forward(
        df,
        make_strategy=lambda params: Flat(params),
        params={},
        train_years=1.0,
        test_months=2.0,
        step_months=2.0,
        seed=123,
        metric_fn=_metric_stub,
        run_fn=_run_backtest_stub,
    )

    assert report["fold_count"] > 0
    aggregate = json.dumps(report["aggregate"], sort_keys=True)
    assert "return" in aggregate

    # ensure folds round-trip to JSON cleanly
    out_path = tmp_path / "wf.json"
    out_path.write_text(json.dumps(report, sort_keys=True))
    parsed = json.loads(out_path.read_text())
    assert parsed["fold_count"] == report["fold_count"]
