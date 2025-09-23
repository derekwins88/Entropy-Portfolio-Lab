"""Data utilities used across the backtest package."""
from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd


def ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *df* with a monotonically increasing datetime index."""

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=False)
    out = out.sort_index()
    return out


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case column names and strip whitespace.

    Many CSV files contain capitalised OHLC columns. Lower-casing makes the
    downstream engine logic agnostic to the input naming convention.
    """

    mapping = {col: col.strip().lower() for col in df.columns}
    return df.rename(columns=mapping)


def require_columns(df: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")


def infer_periods_per_year(index: pd.Index) -> int:
    """Heuristic to infer the annualisation factor for a datetime index."""

    if isinstance(index, pd.DatetimeIndex) and len(index) > 1:
        freq = pd.infer_freq(index)
        if freq:
            freq = freq.upper()
            if freq in {"B", "D"}:
                return 252
            if freq in {"W", "W-MON", "W-FRI"}:
                return 52
            if freq.startswith("M"):
                return 12
            if freq.startswith("Q"):
                return 4
            if freq.startswith("A") or freq.startswith("Y"):
                return 1
        deltas = index.to_series().diff().dropna().dt.total_seconds()
        if not deltas.empty:
            avg_days = deltas.mean() / 86400.0
            if avg_days != 0:
                return int(round(365.0 / avg_days))
    return 252


def rolling_drawdown(equity: pd.Series) -> pd.Series:
    """Compute the running drawdown series."""

    running_max = equity.cummax()
    return equity / running_max - 1.0


def cumulative_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.fillna(0.0)).cumprod()


def align_curves(curves: Iterable[pd.Series]) -> pd.DataFrame:
    """Align a collection of equity curves on a shared index."""

    curves = list(curves)
    if not curves:
        return pd.DataFrame()
    df = pd.concat(curves, axis=1).sort_index()
    df = df.ffill().bfill()
    return df
