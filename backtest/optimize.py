"""Parameter search and robustness utilities.

This module adds ergonomic helpers for common quantitative research workflows:

* :func:`grid_search` — brute-force grid evaluation that records summary metrics.
* :func:`walk_forward` — anchored walk-forward validation with rolling windows.
* :func:`monte_carlo` — block bootstrap Monte Carlo to stress a chosen parameter
  configuration.
* :func:`log_results` — optional CSV/JSON persistence for downstream analysis.

All helpers expect ``strategy_factory`` callables that accept a parameter
dictionary and return a :class:`~backtest.core.strategy.BarStrategy`
implementation.  This mirrors the factory objects created inside the CLI and the
existing walk-forward module which keeps the public API consistent.
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .core.engine import run_backtest
from .core.metrics import summarize

__all__ = [
    "grid_search",
    "walk_forward",
    "monte_carlo",
    "log_results",
]


def _param_product(grid: Dict[str, Iterable]) -> List[Dict]:
    keys = list(grid.keys())
    values = [list(v) for v in grid.values()]
    if not keys:
        return [dict()]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _coerce_score(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (float, int)):
        if value != value:  # NaN check without importing math
            return 0.0
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return 0.0


def grid_search(
    data: pd.DataFrame,
    strategy_factory: Callable[[Dict], object],
    grid: Dict[str, Iterable],
    *,
    run_kwargs: Optional[Dict] = None,
    score_key: str = "Sharpe_annualized",
    bench: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Evaluate a parameter grid and rank by *score_key*."""

    frame = data.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    run_kwargs = dict(run_kwargs or {})
    bench_series: Optional[pd.Series] = None
    if bench is not None:
        bench_series = pd.Series(bench).copy()
        bench_series.index = pd.to_datetime(bench_series.index)
        bench_series = bench_series.sort_index()
    rows = []
    for params in _param_product(grid):
        strategy = strategy_factory(dict(params))
        result = run_backtest(frame, strategy, **run_kwargs)
        bench_slice = None
        if bench_series is not None:
            bench_slice = bench_series.reindex(result.equity_curve.index).ffill()
        stats = summarize(
            result.equity_curve,
            result.fills,
            result.trade_log,
            bench=bench_slice,
        )
        score = _coerce_score(stats.get(score_key))
        rows.append({"params": params, "score": score, **stats})

    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values("score", ascending=False).reset_index(drop=True)


def walk_forward(
    data: pd.DataFrame,
    strategy_factory: Callable[[Dict], object],
    grid: Dict[str, Iterable],
    *,
    train_years: int = 2,
    test_years: int = 1,
    step_years: int = 1,
    run_kwargs: Optional[Dict] = None,
    score_key: str = "Sharpe_annualized",
    bench: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Anchored walk-forward validation over yearly windows."""

    frame = data.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    run_kwargs = dict(run_kwargs or {})
    bench_series: Optional[pd.Series] = None
    if bench is not None:
        bench_series = pd.Series(bench).copy()
        bench_series.index = pd.to_datetime(bench_series.index)
        bench_series = bench_series.sort_index()
    start = frame.index.min()
    end = frame.index.max()
    if pd.isna(start) or pd.isna(end):
        return pd.DataFrame()

    splits: List[Dict] = []
    current_start = start
    while current_start < end:
        train_end = current_start + pd.DateOffset(years=train_years)
        test_end = train_end + pd.DateOffset(years=test_years)

        train_slice = frame.loc[(frame.index >= current_start) & (frame.index < train_end)]
        test_slice = frame.loc[(frame.index >= train_end) & (frame.index < test_end)]

        if len(train_slice) < 60 or len(test_slice) < 20:
            break

        best_params: Optional[Dict] = None
        best_score = float("-inf")
        for params in _param_product(grid):
            result = run_backtest(train_slice, strategy_factory(dict(params)), **run_kwargs)
            bench_train = None
            if bench_series is not None:
                bench_train = bench_series.reindex(result.equity_curve.index).ffill()
            stats = summarize(
                result.equity_curve,
                result.fills,
                result.trade_log,
                bench=bench_train,
            )
            score = _coerce_score(stats.get(score_key))
            if score > best_score:
                best_score = score
                best_params = dict(params)

        if best_params is None:
            break

        evaluation = run_backtest(test_slice, strategy_factory(dict(best_params)), **run_kwargs)
        bench_oos = None
        if bench_series is not None:
            bench_oos = bench_series.reindex(evaluation.equity_curve.index).ffill()
        oos_stats = summarize(
            evaluation.equity_curve,
            evaluation.fills,
            evaluation.trade_log,
            bench=bench_oos,
        )
        splits.append(
            {
                "train_start": train_slice.index[0],
                "train_end": train_slice.index[-1],
                "test_start": test_slice.index[0],
                "test_end": test_slice.index[-1],
                "params": best_params,
                "score": _coerce_score(oos_stats.get(score_key)),
                **oos_stats,
            }
        )

        current_start = current_start + pd.DateOffset(years=step_years)

    return pd.DataFrame(splits)


def _block_bootstrap_prices(
    prices: pd.Series,
    *,
    block: int,
    seed: int,
) -> pd.Series:
    rng = random.Random(seed)
    returns = prices.pct_change().dropna().to_numpy()
    length = len(returns)
    blocks = []
    if length == 0:
        return prices.copy()
    while len(blocks) * block < length:
        start = rng.randrange(0, max(1, length - block))
        blocks.append(returns[start : start + block])
    bootstrap = np.concatenate(blocks, axis=0)[:length]
    boot_prices = [float(prices.iloc[0])]
    for ret in bootstrap:
        boot_prices.append(boot_prices[-1] * (1.0 + float(ret)))
    index = prices.index
    series = pd.Series(boot_prices[1:], index=index[1:])
    series = series.reindex(index).ffill()
    return series.fillna(float(prices.iloc[0]))


def monte_carlo(
    data: pd.DataFrame,
    strategy_factory: Callable[[Dict], object],
    params: Dict,
    *,
    trials: int = 50,
    block: int = 10,
    run_kwargs: Optional[Dict] = None,
    score_key: str = "Sharpe_annualized",
) -> pd.DataFrame:
    """Monte Carlo block bootstrap validation."""

    frame = data.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    run_kwargs = dict(run_kwargs or {})
    if "close" not in frame.columns:
        raise ValueError("Data must contain a 'close' column for Monte Carlo simulation")

    close = frame["close"].astype(float)
    rows = []
    for trial in range(trials):
        simulated = frame.copy()
        simulated["close"] = _block_bootstrap_prices(close, block=block, seed=41 + trial)
        result = run_backtest(simulated, strategy_factory(dict(params)), **run_kwargs)
        stats = summarize(result.equity_curve, result.fills, result.trade_log)
        rows.append({"trial": trial, "score": _coerce_score(stats.get(score_key)), **stats})
    return pd.DataFrame(rows)


def log_results(
    df: pd.DataFrame,
    out_csv: Optional[str] = None,
    out_json: Optional[str] = None,
) -> pd.DataFrame:
    """Persist *df* to CSV/JSON if the corresponding paths are supplied."""

    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv, index=False)
    if out_json:
        payload = json.loads(df.to_json(orient="records")) if not df.empty else []
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    return df
