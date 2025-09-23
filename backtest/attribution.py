"""Performance attribution utilities for trade logs.

This module provides a lightweight approach for breaking down trade-level PnL by
asset and regime labels. It is intentionally opinionated yet flexible so it can
consume the JSON/CSV trade exports produced by the backtesting engine as well as
hand-crafted dictionaries during experimentation.

Two representations are exposed:

* :func:`attribute_returns` — produces a tidy dataframe with ``asset`` and
  ``regime`` columns alongside ``pnl``.
* :func:`pivot_attribution` — convenience wrapper that returns an
  ``asset × regime`` table aggregating PnL.

Additional helpers simplify reporting (percent contributions and quick
summaries). The functions are composable with pandas plotting utilities which
keeps downstream analysis ergonomic.
"""
from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

__all__ = [
    "attribute_returns",
    "pivot_attribution",
    "percent_contributions",
    "summarize_attribution",
    "plot_attribution",
]


def _as_series_regime(regimes: Optional[pd.Series]) -> Optional[pd.Series]:
    """Return a datetime-indexed, sorted copy of *regimes*."""

    if regimes is None:
        return None
    aligned = regimes.copy()
    aligned.index = pd.to_datetime(aligned.index)
    return aligned.sort_index()


def attribute_returns(
    trades: Iterable[dict],
    regimes: Optional[pd.Series] = None,
    *,
    asset_key: str = "asset",
    exit_time_key: str = "exit_time",
    pnl_key: str = "pnl",
) -> pd.DataFrame:
    """Compute attribution rows from an iterable of trade dictionaries."""

    regimes = _as_series_regime(regimes)
    rows = []
    for trade in trades or []:
        asset = str(trade.get(asset_key, "UNKNOWN"))
        pnl_raw = trade.get(pnl_key, 0.0)
        try:
            pnl = float(pnl_raw)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            pnl = 0.0
        exit_ts = trade.get(exit_time_key)
        timestamp = pd.Timestamp(exit_ts) if exit_ts is not None else None

        regime_value = None
        if regimes is not None and timestamp is not None:
            selection = regimes.loc[:timestamp]
            regime_value = None if selection.empty else selection.iloc[-1]

        rows.append({"asset": asset, "regime": regime_value, "pnl": pnl})

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["asset", "regime", "pnl"])

    if "regime" not in frame or frame["regime"].isna().all():
        frame["regime"] = "ALL"

    return frame


def pivot_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot the attribution table into ``asset × regime`` totals."""

    if df.empty:
        return df
    return (
        df.pivot_table(index="asset", columns="regime", values="pnl", aggfunc="sum")
        .fillna(0.0)
    )


def percent_contributions(df: pd.DataFrame) -> pd.DataFrame:
    """Return percentage contributions for each asset/regime combination."""

    if df.empty:
        return df
    pivot = pivot_attribution(df)
    col_sums = pivot.sum(axis=0)
    safe = col_sums.replace(0, 1e-12)
    return (pivot / safe).mul(100.0)


def summarize_attribution(df: pd.DataFrame) -> dict:
    """Produce a compact attribution summary."""

    if df.empty:
        return {"total": 0.0, "top_asset": None, "top_regime": None}

    total = float(df["pnl"].sum())
    by_asset = df.groupby("asset")["pnl"].sum().sort_values(ascending=False)
    by_regime = df.groupby("regime")["pnl"].sum().sort_values(ascending=False)
    return {
        "total": total,
        "top_asset": None if by_asset.empty else by_asset.index[0],
        "top_regime": None if by_regime.empty else by_regime.index[0],
    }


def plot_attribution(df: pd.DataFrame, ax=None):
    """Render a stacked bar chart of attribution by regime and asset."""

    if df.empty:
        raise ValueError("Attribution dataframe is empty")

    import matplotlib.pyplot as plt

    pivot = pivot_attribution(df)
    if pivot.empty:
        raise ValueError("Attribution pivot is empty")

    axis = ax or plt.gca()
    pivot.T.plot(kind="bar", stacked=True, ax=axis, title="PnL by Regime (stacked by asset)")
    axis.set_ylabel("PnL")
    axis.set_xlabel("Regime")
    return axis
