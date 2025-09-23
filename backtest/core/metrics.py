"""Performance metrics for backtest runs."""
from __future__ import annotations

import math
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

from .data import infer_periods_per_year, rolling_drawdown

SeriesLike = Union[pd.Series, pd.DataFrame]


def _as_series(curve: SeriesLike) -> pd.Series:
    if isinstance(curve, pd.DataFrame):
        if curve.shape[1] == 1:
            return curve.iloc[:, 0]
        raise ValueError("Expected a Series or single-column DataFrame for equity curve")
    return curve.astype(float)


def _annualized_return(equity: pd.Series, periods_per_year: int) -> float:
    if equity.empty or equity.iloc[0] == 0:
        return 0.0
    total_return = equity.iloc[-1] / equity.iloc[0]
    periods = max(len(equity) - 1, 1)
    years = periods / periods_per_year
    if years <= 0:
        return total_return - 1.0
    return total_return ** (1.0 / years) - 1.0


def _sharpe_ratio(returns: pd.Series) -> float:
    std = returns.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return returns.mean() / std


def _sortino_ratio(returns: pd.Series) -> float:
    downside = returns[returns < 0]
    if downside.empty:
        return np.inf
    downside_std = downside.std()
    if downside_std == 0 or np.isnan(downside_std):
        return np.inf
    return returns.mean() / downside_std


def summarize(
    equity_curve: SeriesLike,
    fills: Optional[pd.DataFrame] = None,
    trade_log: Optional[Union[pd.DataFrame, list[dict]]] = None,
    bench: Optional[SeriesLike] = None,
) -> Dict[str, float]:
    equity = _as_series(equity_curve).dropna()
    if equity.empty:
        raise ValueError("Equity curve is empty")

    periods_per_year = infer_periods_per_year(equity.index)
    returns = equity.pct_change().dropna()

    stats: Dict[str, float] = {
        "Start": float(equity.iloc[0]),
        "End": float(equity.iloc[-1]),
        "TotalReturn": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
        "CAGR": float(_annualized_return(equity, periods_per_year)),
        "Volatility_annualized": float(returns.std() * math.sqrt(periods_per_year)) if not returns.empty else 0.0,
    }

    sharpe = _sharpe_ratio(returns) if not returns.empty else 0.0
    stats["Sharpe_d"] = float(sharpe)
    stats["Sharpe_annualized"] = float(sharpe * math.sqrt(periods_per_year))

    sortino = _sortino_ratio(returns) if not returns.empty else np.inf
    stats["Sortino_annualized"] = float(sortino * math.sqrt(periods_per_year) if np.isfinite(sortino) else np.inf)

    dd = rolling_drawdown(equity)
    stats["MaxDrawdown"] = float(dd.min())
    stats["Calmar"] = float(stats["CAGR"] / abs(stats["MaxDrawdown"]) if stats["MaxDrawdown"] < 0 else np.nan)

    if not returns.empty:
        threshold = 0.0
        positive = np.maximum(returns - threshold, 0.0).sum()
        negative = np.maximum(threshold - returns, 0.0).sum()
        stats["Omega"] = float(positive / negative) if negative > 0 else np.inf
        var_level = np.percentile(returns, 5)
        stats["VaR_5"] = float(var_level)
        tail = returns[returns <= var_level]
        stats["CVaR_5"] = float(tail.mean()) if not tail.empty else float(var_level)
    else:
        stats["Omega"] = np.nan
        stats["VaR_5"] = np.nan
        stats["CVaR_5"] = np.nan

    # Benchmarked stats -------------------------------------------------
    if bench is not None:
        bench_series = _as_series(bench).reindex(equity.index).ffill().dropna()
        bench_returns = bench_series.pct_change().dropna()
        aligned = returns.reindex(bench_returns.index).dropna()
        bench_aligned = bench_returns.reindex(aligned.index)
        if not aligned.empty and bench_aligned.var() > 0:
            covariance = np.cov(aligned, bench_aligned)[0, 1]
            beta = covariance / bench_aligned.var()
            stats["Beta"] = float(beta)

            strat_ann = _annualized_return((1 + aligned).cumprod(), periods_per_year)
            bench_ann = _annualized_return((1 + bench_aligned).cumprod(), periods_per_year)
            stats["Alpha"] = float(strat_ann - beta * bench_ann)

            diff = aligned - bench_aligned
            tracking_error = diff.std() * math.sqrt(periods_per_year)
            stats["InformationRatio"] = float((aligned.mean() - bench_aligned.mean()) * math.sqrt(periods_per_year) / tracking_error) if tracking_error > 0 else np.nan
        else:
            stats["Beta"] = np.nan
            stats["Alpha"] = np.nan
            stats["InformationRatio"] = np.nan

    # Trade diagnostics --------------------------------------------------
    trades_df: Optional[pd.DataFrame] = None
    if isinstance(trade_log, list):
        trades_df = pd.DataFrame(trade_log)
    elif isinstance(trade_log, pd.DataFrame):
        trades_df = trade_log

    if trades_df is not None and not trades_df.empty and "pnl" in trades_df.columns:
        wins = trades_df[trades_df["pnl"] > 0]
        losses = trades_df[trades_df["pnl"] < 0]
        stats["Trades"] = float(len(trades_df))
        stats["WinRate"] = float(len(wins) / len(trades_df)) if len(trades_df) else np.nan
        stats["AvgTrade"] = float(trades_df["pnl"].mean())
        stats["AvgWin"] = float(wins["pnl"].mean()) if not wins.empty else 0.0
        stats["AvgLoss"] = float(losses["pnl"].mean()) if not losses.empty else 0.0
        gross_win = wins["pnl"].sum()
        gross_loss = losses["pnl"].sum()
        stats["ProfitFactor"] = float(gross_win / abs(gross_loss)) if gross_loss != 0 else np.inf
    else:
        stats["Trades"] = 0.0
        stats["WinRate"] = np.nan
        stats["AvgTrade"] = 0.0
        stats["AvgWin"] = 0.0
        stats["AvgLoss"] = 0.0
        stats["ProfitFactor"] = np.nan

    return stats
