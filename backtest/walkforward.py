"""Anchored walk-forward testing utilities."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .core.data import ensure_datetime_index, rolling_drawdown, standardize_columns
from .core.engine import run_backtest
from .core.metrics import summarize
from .core.strategy import BarStrategy

StrategyFactory = Callable[[Dict[str, Any]], BarStrategy]


@dataclass
class WalkForwardSplit:
    """Container for a single walk-forward split result."""

    split: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    params: Dict[str, Any]
    selection_metric: str
    insample_stats: Dict[str, float]
    oos_stats: Dict[str, float]
    equity_curve: pd.Series
    oos_equity: pd.Series


def _coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"none", "null"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if value.startswith("0") and value != "0" and not value.startswith("0."):
            raise ValueError
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_grid_spec(spec: Optional[Sequence[str]]) -> List[Dict[str, Any]]:
    """Parse a CLI-style grid specification into parameter dictionaries.

    The format mirrors the example from the user instructions::

        rsi_len=10,14,21 ema_len=20,50 rsi_buy=20,30

    Parameters are separated by whitespace. Each token is ``name=value1,value2``.
    ``value`` strings are coerced to ``int``/``float`` where possible.
    """

    if not spec:
        return [{}]

    values: Dict[str, List[Any]] = {}
    for token in spec:
        if "=" not in token:
            raise ValueError(f"Malformed grid token: {token}")
        name, raw_values = token.split("=", 1)
        choices = [_coerce_value(v.strip()) for v in raw_values.split(",") if v]
        if not choices:
            raise ValueError(f"No values supplied for grid parameter '{name}'")
        values[name] = choices

    keys = list(values)
    combos = [dict(zip(keys, prod)) for prod in itertools.product(*(values[k] for k in keys))]
    if not combos:
        return [{}]
    return combos


def _ensure_param_grid(grid: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if grid is None:
        return [{}]
    combos = [dict(params) for params in grid]
    return combos or [{}]


def _filter_fills(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    mask = (df.index >= start) & (df.index <= end)
    return df.loc[mask]


def _filter_trades(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for column in ("entry_time", "exit_time"):
        if column in out.columns:
            out[column] = pd.to_datetime(out[column])
    mask_start = pd.Series(True, index=out.index)
    if "exit_time" in out.columns:
        mask_start &= out["exit_time"].fillna(pd.Timestamp.max) >= start
    if "entry_time" in out.columns:
        mask_start &= out["entry_time"] <= end
    return out.loc[mask_start]


def anchored_walk_forward(
    data: pd.DataFrame,
    strategy_factory: StrategyFactory,
    param_grid: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    selection_metric: str = "Sharpe_annualized",
    min_train: int = 504,
    test_window: int = 252,
    starting_cash: float = 100_000.0,
    mode: str = "target",
    size: int = 1,
    size_notional: Optional[float] = None,
    risk_R: Optional[float] = None,
    atr_len: Optional[int] = None,
    risk_pct: float = 0.01,
    commission: float = 0.0,
    slippage_bps: float = 0.0,
    bench: Optional[pd.Series] = None,
) -> List[WalkForwardSplit]:
    """Run an anchored walk-forward search over *param_grid*.

    ``param_grid`` should be an iterable of dictionaries mapping parameter names to
    values. ``selection_metric`` determines the in-sample metric used to pick the
    best configuration for each split.
    """

    frame = standardize_columns(ensure_datetime_index(data))
    if "close" not in frame.columns:
        raise ValueError("Input data must contain a 'close' column for walk-forward")

    if len(frame) < max(min_train, 2):
        raise ValueError("Not enough rows for walk-forward evaluation")

    grid = _ensure_param_grid(param_grid)

    bench_series: Optional[pd.Series] = None
    if bench is not None:
        bench_series = pd.Series(bench).copy()
        bench_series.index = pd.to_datetime(bench_series.index)
        bench_series = bench_series.sort_index()

    results: List[WalkForwardSplit] = []
    split = 1
    n = len(frame)
    train_end = max(min_train, 1)

    while train_end < n:
        test_end = min(train_end + max(test_window, 1), n)
        train_slice = frame.iloc[:train_end]
        test_slice = frame.iloc[train_end:test_end]
        if test_slice.empty:
            break

        bench_train = None
        bench_test = None
        if bench_series is not None:
            bench_train = bench_series.reindex(train_slice.index).ffill().dropna()
            bench_test = bench_series.reindex(test_slice.index).ffill().dropna()

        best_params: Optional[Dict[str, Any]] = None
        best_stats: Optional[Dict[str, float]] = None
        best_metric = -math.inf

        for params in grid:
            strat = strategy_factory(dict(params))
            rr = run_backtest(
                train_slice,
                strat,
                starting_cash=starting_cash,
                mode=mode,
                size=size,
                size_notional=size_notional,
                risk_R=risk_R,
                atr_len=atr_len,
                risk_pct=risk_pct,
                commission=commission,
                slippage_bps=slippage_bps,
            )
            stats = summarize(rr.equity_curve, rr.fills, rr.trade_log, bench=bench_train)
            metric_value = stats.get(selection_metric)
            if metric_value is None or (isinstance(metric_value, float) and math.isnan(metric_value)):
                metric_value = -math.inf
            if metric_value > best_metric:
                best_metric = metric_value
                best_params = dict(params)
                best_stats = stats

        if best_params is None or best_stats is None or not np.isfinite(best_metric):
            raise ValueError(
                f"Failed to find a valid parameter set for split {split} using metric '{selection_metric}'"
            )

        strat_full = strategy_factory(dict(best_params))
        full_slice = frame.iloc[:test_end]
        rr_full = run_backtest(
            full_slice,
            strat_full,
            starting_cash=starting_cash,
            mode=mode,
            size=size,
            size_notional=size_notional,
            risk_R=risk_R,
            atr_len=atr_len,
            risk_pct=risk_pct,
            commission=commission,
            slippage_bps=slippage_bps,
        )

        equity_full = rr_full.equity_curve
        equity_oos = equity_full.loc[test_slice.index]
        fills_oos = _filter_fills(rr_full.fills, test_slice.index[0], test_slice.index[-1])
        trades_oos = _filter_trades(rr_full.trade_log, test_slice.index[0], test_slice.index[-1])
        stats_oos = summarize(equity_oos, fills_oos, trades_oos, bench=bench_test)

        results.append(
            WalkForwardSplit(
                split=split,
                train_start=train_slice.index[0],
                train_end=train_slice.index[-1],
                test_start=test_slice.index[0],
                test_end=test_slice.index[-1],
                params=best_params,
                selection_metric=selection_metric,
                insample_stats=best_stats,
                oos_stats=stats_oos,
                equity_curve=equity_full,
                oos_equity=equity_oos,
            )
        )

        train_end = test_end
        split += 1
        if test_end == n:
            break

    return results


def walkforward_drawdown(equity: pd.Series) -> pd.Series:
    """Helper to compute drawdown for walk-forward plots."""

    return rolling_drawdown(equity)


__all__ = [
    "WalkForwardSplit",
    "anchored_walk_forward",
    "parse_grid_spec",
    "walkforward_drawdown",
]
