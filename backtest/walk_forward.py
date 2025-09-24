"""Anchored walk-forward pipeline that emits out-of-sample returns."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

StrategyFactory = Callable[[Dict[str, object]], object]
RunBacktestFn = Callable[..., object]


def _coerce(value: str) -> object:
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _parse_grid_token(token: str) -> tuple[str, List[object]]:
    if "=" not in token:
        raise ValueError(f"Malformed grid token: {token}")
    name, raw_values = token.split("=", 1)
    values = [segment.strip() for segment in raw_values.split(",") if segment.strip()]
    if not values:
        raise ValueError(f"No values supplied for grid parameter '{name}'")
    return name.strip(), [_coerce(value) for value in values]


def parse_grid(grid_str: str) -> List[Dict[str, object]]:
    """Parse a simple CLI grid specification into parameter dictionaries."""

    text = (grid_str or "").strip()
    if not text:
        return [{}]

    pairs = [_parse_grid_token(token) for token in text.split()]
    keys = [name for name, _ in pairs]
    values = [choices for _, choices in pairs]
    combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    return combos or [{}]


def _select_best_params(
    frame: pd.DataFrame,
    factory: StrategyFactory,
    params_grid: Iterable[Dict[str, object]],
    *,
    run_backtest: RunBacktestFn,
    mode: str,
    sizing_kwargs: Dict[str, object],
) -> Dict[str, object]:
    best_params: Dict[str, object] | None = None
    best_score = -np.inf
    for params in params_grid:
        strategy = factory(params)
        result = run_backtest(frame, strategy, mode=mode, **sizing_kwargs)
        equity_attr = getattr(result, "equity_curve", None)
        if equity_attr is None:
            raise AttributeError("run_backtest result must expose 'equity_curve'")
        equity = pd.Series(equity_attr, dtype=float)
        returns = equity.pct_change().dropna()
        std = float(returns.std(ddof=0))
        if std == 0:
            if best_params is None:
                best_params = dict(params)
            continue
        sharpe = float(returns.mean()) / std * np.sqrt(252.0)
        if sharpe > best_score:
            best_score = sharpe
            best_params = dict(params)
    if best_params is None:
        raise RuntimeError("walk_forward: unable to find viable parameters")
    return best_params


def walk_forward(
    data: pd.DataFrame,
    strategy_factory: StrategyFactory,
    param_grid: Sequence[Dict[str, object]],
    *,
    train_days: int = 500,
    test_days: int = 125,
    run_backtest: RunBacktestFn,
    mode: str = "target",
    sizing_kwargs: Dict[str, object] | None = None,
    out_csv: str | Path = "artifacts/wf_oos_returns.csv",
) -> pd.Series:
    """Run anchored walk-forward analysis and return concatenated OOS returns."""

    if train_days <= 0 or test_days <= 0:
        raise ValueError("train_days and test_days must be positive")

    frame = data.copy()
    frame.index = pd.DatetimeIndex(frame.index)
    grid = list(param_grid) or [{}]
    sizing_kwargs = dict(sizing_kwargs or {})

    oos_returns: list[pd.Series] = []
    start = 0
    while start + train_days + test_days <= len(frame):
        train_slice = frame.iloc[start : start + train_days]
        test_slice = frame.iloc[start + train_days : start + train_days + test_days]

        best_params = _select_best_params(
            train_slice,
            strategy_factory,
            grid,
            run_backtest=run_backtest,
            mode=mode,
            sizing_kwargs=sizing_kwargs,
        )

        strategy = strategy_factory(best_params)
        result = run_backtest(test_slice, strategy, mode=mode, **sizing_kwargs)
        equity_attr = getattr(result, "equity_curve", None)
        if equity_attr is None:
            raise AttributeError("run_backtest result must expose 'equity_curve'")
        equity = pd.Series(equity_attr, dtype=float)
        returns = equity.pct_change().fillna(0.0)
        returns.index.name = "date"
        oos_returns.append(returns.rename("ret_oos"))

        start += test_days

    if not oos_returns:
        raise RuntimeError("walk_forward: no folds were generated")

    oos = pd.concat(oos_returns)
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    oos.to_csv(out_path)
    return oos


def run_wf_from_cli(
    csv_path: str,
    grid: str,
    StrategyFactory: StrategyFactory,
    run_backtest: RunBacktestFn,
    *,
    mode: str = "target",
    train_days: int = 500,
    test_days: int = 125,
    out_csv: str = "artifacts/wf_oos_returns.csv",
    sizing_kwargs: Dict[str, object] | None = None,
) -> pd.Series:
    """Helper invoked by the CLI to run the walk-forward pipeline."""

    df = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
    df = df.rename(columns=lambda c: c.lower())
    param_grid = parse_grid(grid)
    return walk_forward(
        df,
        StrategyFactory,
        param_grid,
        train_days=train_days,
        test_days=test_days,
        run_backtest=run_backtest,
        mode=mode,
        sizing_kwargs=sizing_kwargs or {},
        out_csv=out_csv,
    )
