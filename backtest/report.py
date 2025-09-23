"""Reporting helpers for walk-forward and equity analytics."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .walkforward import WalkForwardSplit, walkforward_drawdown


# ---------------------------------------------------------------------------
# Daily equity utilities
# ---------------------------------------------------------------------------

def rolling_sharpe(returns: pd.Series, window: int = 60) -> pd.Series:
    """Compute a rolling Sharpe ratio scaled to daily frequency."""

    win = max(int(window), 1)
    rolling = returns.rolling(win)
    mean = rolling.mean()
    std = rolling.std(ddof=0).replace(0, np.nan)
    return (mean / std) * np.sqrt(252)


def drawdown(equity: pd.Series) -> pd.Series:
    """Return the percentage drawdown of an equity curve."""

    equity = equity.astype(float)
    peak = equity.cummax().replace(0, np.nan)
    return equity.divide(peak).subtract(1.0)


def daily_equity_report(equity: pd.Series, window: int = 60) -> pd.DataFrame:
    """Return a dataframe with equity, returns, drawdown and rolling Sharpe."""

    equity = equity.rename("equity")
    returns = equity.pct_change().fillna(0.0).rename("ret")
    dd = drawdown(equity).rename("dd")
    roll = rolling_sharpe(returns, window).rename(f"roll_sharpe_{window}")
    return pd.concat([equity, returns, dd, roll], axis=1)


def attach_regimes(df: pd.DataFrame, regimes: pd.Series) -> pd.DataFrame:
    """Pad/forward-fill *regimes* to match *df*'s index."""

    aligned = regimes.rename("regime")
    aligned.index = pd.to_datetime(aligned.index)
    aligned = aligned.sort_index()
    joined = aligned.reindex(df.index, method="pad")
    return pd.concat([df, joined], axis=1)


# ---------------------------------------------------------------------------
# Walk-forward helpers (existing functionality)
# ---------------------------------------------------------------------------

def _format_params(params: dict) -> str:
    if not params:
        return "{}"
    return ", ".join(f"{k}={v}" for k, v in sorted(params.items()))


def walkforward_table(results: Sequence[WalkForwardSplit]) -> pd.DataFrame:
    """Convert walk-forward split results into a tidy ``DataFrame``."""

    rows = []
    include_bench = any("Alpha" in split.oos_stats for split in results)
    for split in results:
        oos = split.oos_stats
        row = {
            "split": split.split,
            "train_start": split.train_start,
            "train_end": split.train_end,
            "test_start": split.test_start,
            "test_end": split.test_end,
            "params": _format_params(split.params),
            f"IS_{split.selection_metric}": split.insample_stats.get(split.selection_metric, float("nan")),
            "CAGR": oos.get("CAGR", float("nan")),
            "Sharpe": oos.get("Sharpe_annualized", oos.get("Sharpe_d", float("nan"))),
            "MaxDD": oos.get("MaxDrawdown", float("nan")),
            "ProfitFactor": oos.get("ProfitFactor", float("nan")),
        }
        if include_bench:
            row["Alpha"] = oos.get("Alpha", float("nan"))
            row["Beta"] = oos.get("Beta", float("nan"))
            row["InformationRatio"] = oos.get("InformationRatio", float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def save_table(table: pd.DataFrame, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(p, index=False)


def print_table(table: pd.DataFrame) -> None:
    if table.empty:
        print("No walk-forward splits produced output")
        return
    with pd.option_context("display.max_rows", None, "display.width", None):
        print(table.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


def plot_walkforward(results: Sequence[WalkForwardSplit], path: str | Path) -> Path:
    """Render an equity + drawdown plot for walk-forward splits."""

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Matplotlib is required for plotting walk-forward results") from exc

    if not results:
        raise ValueError("No walk-forward results to plot")

    equity = results[-1].equity_curve
    dd = walkforward_drawdown(equity)

    fig, (ax_eq, ax_dd) = plt.subplots(2, 1, sharex=True, figsize=(10, 8))
    equity.plot(ax=ax_eq, color="black", label="Equity")
    ax_eq.set_ylabel("Equity")
    ax_eq.legend(loc="upper left")

    for split in results:
        ax_eq.axvspan(split.train_start, split.train_end, color="#4c72b0", alpha=0.05)
        ax_eq.axvspan(split.test_start, split.test_end, color="#dd8452", alpha=0.18)

    dd.plot(ax=ax_dd, color="#c44e52", label="Drawdown")
    ax_dd.axhline(0.0, color="black", linewidth=0.8)
    ax_dd.set_ylabel("Drawdown")
    ax_dd.set_xlabel("Date")
    ax_dd.legend(loc="lower left")

    fig.suptitle("Walk-Forward Equity & Drawdown")
    fig.tight_layout()

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


__all__ = [
    "rolling_sharpe",
    "drawdown",
    "daily_equity_report",
    "attach_regimes",
    "walkforward_table",
    "save_table",
    "print_table",
    "plot_walkforward",
]
