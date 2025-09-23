"""Portfolio utilities for combining strategy runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Union

import numpy as np
import pandas as pd

from .engine import RunResult, run_backtest
from .strategy import BarStrategy
from .data import ensure_datetime_index, standardize_columns


@dataclass
class PortfolioSpec:
    name: str
    csv: str
    strategy: str
    params: Dict
    weight: float = 1.0
    cash: Optional[float] = None


SpecInput = Union[Dict, PortfolioSpec]


def _data_ok(df: pd.DataFrame) -> bool:
    if not isinstance(df.index, pd.DatetimeIndex):
        return False
    if not df.index.is_monotonic_increasing:
        return False
    if df.index.duplicated().any():
        return False
    if "close" not in df.columns:
        return False
    if df["close"].isna().any():
        return False
    return True


def run_portfolio(
    specs: Iterable[SpecInput],
    factories: Dict[str, Callable[[dict], BarStrategy]],
    *,
    starting_cash: float = 100_000.0,
    mode: str = "target",
    size: int = 1,
    size_notional: Optional[float] = None,
    risk_R: Optional[float] = None,
    atr_len: Optional[int] = None,
    risk_pct: float = 0.01,
    commission: float = 0.0,
    slippage_bps: float = 0.0,
) -> pd.Series:
    """Run a set of strategies and aggregate their equity curves."""

    curves: List[pd.Series] = []
    weights: List[float] = []
    skipped: List[str] = []

    for spec in specs:
        if isinstance(spec, PortfolioSpec):
            csv_path = spec.csv
            strategy_key = spec.strategy
            params = spec.params or {}
            weight = float(spec.weight)
            cash = float(spec.cash if spec.cash is not None else starting_cash)
            name = spec.name
        else:
            csv_path = spec["csv"]
            strategy_key = spec["strategy"]
            params = spec.get("params", {}) or {}
            weight = float(spec.get("weight", 1.0))
            cash = float(spec.get("cash", starting_cash))
            name = spec.get("name", strategy_key)

        data = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
        data = ensure_datetime_index(data)
        data = standardize_columns(data)
        if not _data_ok(data):
            skipped.append(name)
            continue
        factory = factories[strategy_key]
        strategy = factory(params)
        result: RunResult = run_backtest(
            data,
            strategy,
            starting_cash=cash,
            mode=mode,
            size=size,
            size_notional=size_notional,
            risk_R=risk_R,
            atr_len=atr_len,
            risk_pct=risk_pct,
            commission=commission,
            slippage_bps=slippage_bps,
        )
        curves.append(result.equity_curve.rename(name))
        weights.append(weight)

    if not curves:
        empty = pd.Series(dtype=float, name="portfolio")
        empty.attrs["skipped"] = skipped
        return empty

    combined = pd.concat(curves, axis=1).sort_index()
    combined = combined.ffill().bfill()

    weights_arr = np.array(weights, dtype=float)
    if weights_arr.sum() == 0:
        weights_arr = np.ones_like(weights_arr)
    weights_arr = weights_arr / weights_arr.sum()

    portfolio_curve = (combined * weights_arr).sum(axis=1)
    portfolio_curve.name = "portfolio"
    portfolio_curve.attrs["skipped"] = skipped
    return portfolio_curve
