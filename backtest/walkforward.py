"""Anchored walk-forward testing utilities."""

from __future__ import annotations

import itertools
import math
import inspect
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .core.data import ensure_datetime_index, rolling_drawdown, standardize_columns
from .core.engine import RunResult, run_backtest
from .core.metrics import summarize
from .core.strategy import BarStrategy

StrategyFactory = Callable[[Dict[str, Any]], BarStrategy]


@dataclass
class SimpleFoldResult:
    """Serializable container for the lightweight walk-forward report."""

    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: Dict[str, Any]


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


def _expand_param_grid_map(
    grid: Optional[Mapping[str, Sequence[Any]]]
) -> List[Dict[str, Any]]:
    if not grid:
        return [{}]

    keys: List[str] = []
    values: List[List[Any]] = []
    for key, raw_values in grid.items():
        if isinstance(raw_values, (str, bytes)):
            choices = [raw_values]
        else:
            choices = list(raw_values)
        if not choices:
            raise ValueError(f"No values supplied for grid parameter '{key}'")
        keys.append(str(key))
        values.append([choice for choice in choices])

    combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
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


def _coerce_metric_values(metrics: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (np.integer, np.floating, int, float)):
            num = float(value)
            out[key] = num if np.isfinite(num) else None
        else:
            out[key] = value
    return out


def _metric_as_float(value: Any) -> float:
    if value is None or isinstance(value, bool):
        return float("-inf")
    if isinstance(value, (np.integer, np.floating, int, float)):
        num = float(value)
        return num if np.isfinite(num) else float("-inf")
    try:
        num = float(value)
    except (TypeError, ValueError):
        return float("-inf")
    return num if np.isfinite(num) else float("-inf")


def _rolling_windows(
    index: pd.DatetimeIndex,
    train_window: pd.Timedelta,
    test_window: pd.Timedelta,
    step: pd.Timedelta,
) -> List[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    if index.empty:
        return []

    start = index.min()
    end = index.max()
    windows: List[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]] = []

    current_train_end = start + train_window
    while True:
        test_start = current_train_end
        test_end = test_start + test_window
        if test_end > end:
            break
        windows.append((start, current_train_end, test_start, test_end))
        current_train_end = current_train_end + step
    return windows


def _accepts_seed(fn: Callable[..., Any]) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return False
    return "seed" in params


def _metrics_from_result(
    result: RunResult,
    metric_fn: Optional[Callable[[Any], Dict[str, Any]]],
) -> Dict[str, Any]:
    if metric_fn is None:
        metrics = summarize(result.equity_curve, result.fills, result.trade_log)
    else:
        try:
            metrics = metric_fn(result)
        except TypeError:
            metrics = metric_fn(getattr(result, "equity_curve", pd.Series(dtype=float)))
    return _coerce_metric_values(dict(metrics))


def walk_forward(
    data: pd.DataFrame,
    make_strategy: Callable[[Dict[str, Any]], BarStrategy],
    params: Dict[str, Any],
    *,
    train_years: float = 2.0,
    test_months: float = 3.0,
    step_months: float = 3.0,
    seed: int = 42,
    metric_fn: Optional[Callable[[Any], Dict[str, Any]]] = None,
    run_fn: Optional[Callable[..., RunResult]] = None,
    run_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Minimal expanding walk-forward helper used by the CLI."""

    if seed is not None:
        try:  # pragma: no cover - guard for environments without numpy/random
            import random

            random.seed(seed)
            np.random.seed(seed)
        except Exception:  # pragma: no cover - deterministic best effort
            pass

    if run_fn is None:
        from .core.engine import run_backtest as run_fn

    run_kwargs = dict(run_kwargs or {})

    df = data.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        datetime_column = None
        for candidate in ("datetime", "date", "DATE", "Date"):
            if candidate in df.columns:
                datetime_column = candidate
                break
        if datetime_column is not None:
            df = df.copy()
            df[datetime_column] = pd.to_datetime(df[datetime_column])
            df = df.set_index(datetime_column)
        else:
            df = ensure_datetime_index(df)
    else:
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    train_window = pd.Timedelta(days=max(int(train_years * 365.25), 1))
    test_window = pd.Timedelta(days=max(int(test_months * 30.4375), 1))
    step_window = pd.Timedelta(days=max(int(step_months * 30.4375), 1))

    windows = _rolling_windows(df.index, train_window, test_window, step_window)
    fold_results: List[SimpleFoldResult] = []

    for idx, (train_start, train_end, test_start, test_end) in enumerate(windows, start=1):
        train_slice = df.loc[train_start:train_end]
        test_slice = df.loc[test_start:test_end]
        if train_slice.empty or test_slice.empty:
            continue

        strategy = make_strategy(dict(params))

        call_kwargs = dict(run_kwargs)
        if _accepts_seed(run_fn):
            call_kwargs.setdefault("seed", seed)

        result = run_fn(test_slice, strategy, **call_kwargs)

        if metric_fn is None:
            metrics = summarize(result.equity_curve, result.fills, result.trade_log)
        else:
            try:
                metrics = metric_fn(result)
            except TypeError:
                metrics = metric_fn(getattr(result, "equity_curve", pd.Series(dtype=float)))

        metrics = _coerce_metric_values(dict(metrics))

        fold_results.append(
            SimpleFoldResult(
                fold_id=idx,
                train_start=str(train_slice.index[0].date()),
                train_end=str(train_slice.index[-1].date()),
                test_start=str(test_slice.index[0].date()),
                test_end=str(test_slice.index[-1].date()),
                metrics=metrics,
            )
        )

    aggregate: Dict[str, Any] = {}
    if fold_results:
        keys = sorted({key for fold in fold_results for key in fold.metrics})
        for key in keys:
            values = [fold.metrics.get(key) for fold in fold_results]
            numeric = [
                float(v)
                for v in values
                if isinstance(v, (int, float))
                and not isinstance(v, bool)
                and np.isfinite(float(v))
            ]
            if numeric:
                aggregate[key] = float(np.mean(numeric))

    return {
        "folds": [asdict(fold) for fold in fold_results],
        "aggregate": aggregate,
        "fold_count": len(fold_results),
    }


def walk_forward_opt(
    data: pd.DataFrame,
    make_strategy: Callable[[Dict[str, Any]], BarStrategy],
    param_grid: Optional[Mapping[str, Sequence[Any]]],
    *,
    metric_key: str = "Sharpe_annualized",
    train_years: float = 2.0,
    test_months: float = 6.0,
    step_months: float = 6.0,
    seed: int = 42,
    metric_fn: Optional[Callable[[Any], Dict[str, Any]]] = None,
    run_fn: Optional[Callable[..., RunResult]] = None,
    run_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Walk-forward evaluation with in-sample parameter tuning per fold."""

    if seed is not None:
        try:  # pragma: no cover - guard for environments without numpy/random
            import random

            random.seed(seed)
            np.random.seed(seed)
        except Exception:  # pragma: no cover - deterministic best effort
            pass

    if run_fn is None:
        from .core.engine import run_backtest as run_fn

    run_kwargs = dict(run_kwargs or {})

    df = data.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        datetime_column = None
        for candidate in ("datetime", "date", "DATE", "Date"):
            if candidate in df.columns:
                datetime_column = candidate
                break
        if datetime_column is not None:
            df = df.copy()
            df[datetime_column] = pd.to_datetime(df[datetime_column])
            df = df.set_index(datetime_column)
        else:
            df = ensure_datetime_index(df)
    else:
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    train_window = pd.Timedelta(days=max(int(train_years * 365.25), 1))
    test_window = pd.Timedelta(days=max(int(test_months * 30.4375), 1))
    step_window = pd.Timedelta(days=max(int(step_months * 30.4375), 1))

    windows = _rolling_windows(df.index, train_window, test_window, step_window)
    combos = _expand_param_grid_map(param_grid)

    folds: List[Dict[str, Any]] = []

    for idx, (train_start, train_end, test_start, test_end) in enumerate(windows, start=1):
        train_slice = df.loc[train_start:train_end]
        test_slice = df.loc[test_start:test_end]
        if train_slice.empty or test_slice.empty:
            continue

        best_params: Optional[Dict[str, Any]] = None
        best_metric = float("-inf")

        for params in combos:
            strategy = make_strategy(dict(params))
            call_kwargs = dict(run_kwargs)
            if _accepts_seed(run_fn):
                call_kwargs.setdefault("seed", seed)
            train_result = run_fn(train_slice, strategy, **call_kwargs)
            metrics_train = _metrics_from_result(train_result, metric_fn)
            metric_value = _metric_as_float(metrics_train.get(metric_key))
            if metric_value > best_metric:
                best_metric = metric_value
                best_params = dict(params)

        if best_params is None or not np.isfinite(best_metric):
            raise ValueError(
                f"Failed to find a valid parameter set for fold {idx} using metric '{metric_key}'"
            )

        strategy_test = make_strategy(dict(best_params))
        call_kwargs = dict(run_kwargs)
        if _accepts_seed(run_fn):
            call_kwargs.setdefault("seed", seed)
        test_result = run_fn(test_slice, strategy_test, **call_kwargs)
        metrics_test = _metrics_from_result(test_result, metric_fn)

        folds.append(
            {
                "fold_id": idx,
                "train_start": str(train_slice.index[0].date()),
                "train_end": str(train_slice.index[-1].date()),
                "test_start": str(test_slice.index[0].date()),
                "test_end": str(test_slice.index[-1].date()),
                "best_params": best_params,
                "metrics": metrics_test,
            }
        )

    aggregate: Dict[str, Any] = {}
    if folds:
        keys = sorted({key for fold in folds for key in fold["metrics"]})
        for key in keys:
            values = [fold["metrics"].get(key) for fold in folds]
            numeric = [
                float(v)
                for v in values
                if isinstance(v, (int, float, np.integer, np.floating))
                and not isinstance(v, bool)
                and np.isfinite(float(v))
            ]
            if numeric:
                aggregate[key] = float(np.mean(numeric))

    return {"folds": folds, "aggregate": aggregate, "fold_count": len(folds)}


__all__ = [
    "SimpleFoldResult",
    "WalkForwardSplit",
    "anchored_walk_forward",
    "parse_grid_spec",
    "walk_forward",
    "walk_forward_opt",
    "walkforward_drawdown",
]
