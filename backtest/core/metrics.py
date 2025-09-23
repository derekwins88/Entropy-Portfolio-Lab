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
        raise ValueError(
            "Expected a Series or single-column DataFrame for equity curve"
        )
    return curve.astype(float)


def daily_returns(series: pd.Series) -> pd.Series:
    """Return percentage changes with a forward-filled, sorted index."""

    s = series.astype(float).copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index().ffill().dropna()
    if s.empty:
        return pd.Series(dtype=float)
    return s.pct_change().fillna(0.0)


def capture_ratios(equity: pd.Series, bench: pd.Series) -> dict:
    """Compute up/down capture ratios and tracking error on daily returns."""

    eq_ret = daily_returns(equity)
    bench_ret = daily_returns(bench)
    eq_ret, bench_ret = eq_ret.align(bench_ret, join="inner")
    df = pd.concat([eq_ret, bench_ret], axis=1).dropna()
    if df.empty:
        return {"UpCapture": 0.0, "DownCapture": 0.0, "TrackingError": 0.0}

    up = df[df.iloc[:, 1] > 0]
    down = df[df.iloc[:, 1] < 0]
    eps = 1e-12
    up_cap = (up.iloc[:, 0].mean() / (up.iloc[:, 1].mean() + eps)) if len(up) else 0.0
    down_cap = (
        down.iloc[:, 0].mean() / (down.iloc[:, 1].mean() + eps)
        if len(down)
        else 0.0
    )
    te = (df.iloc[:, 0] - df.iloc[:, 1]).std(ddof=0) * math.sqrt(252)
    return {
        "UpCapture": float(up_cap),
        "DownCapture": float(down_cap),
        "TrackingError": float(te if np.isfinite(te) else 0.0),
    }


def active_stats(equity: pd.Series, bench: pd.Series) -> Dict[str, float]:
    """Return active risk/return statistics relative to *bench*."""

    eq_ret = daily_returns(equity)
    bench_ret = daily_returns(bench)
    eq_ret, bench_ret = eq_ret.align(bench_ret, join="inner")
    eq_ret = eq_ret.dropna()
    bench_ret = bench_ret.dropna()

    if len(eq_ret) < 2 or len(bench_ret) < 2:
        return {
            "Alpha": np.nan,
            "Beta": np.nan,
            "InformationRatio": np.nan,
            "TrackingError": 0.0,
        }

    bench_var = float(bench_ret.var(ddof=0))
    if not np.isfinite(bench_var) or bench_var <= 0:
        return {
            "Alpha": np.nan,
            "Beta": np.nan,
            "InformationRatio": np.nan,
            "TrackingError": 0.0,
        }

    eq_arr = eq_ret.to_numpy()
    bench_arr = bench_ret.to_numpy()
    cov = float(np.cov(eq_arr, bench_arr, ddof=0)[0, 1])
    beta = cov / bench_var if bench_var else np.nan

    periods_per_year = max(infer_periods_per_year(eq_ret.index), 1)
    annual_scale = math.sqrt(periods_per_year)
    diff = eq_ret - bench_ret
    tracking_error = float(diff.std(ddof=0) * annual_scale)

    strat_mean = float(eq_ret.mean())
    bench_mean = float(bench_ret.mean())
    alpha = (strat_mean - beta * bench_mean) * periods_per_year if np.isfinite(beta) else np.nan

    info_ratio = np.nan
    if tracking_error > 0 and np.isfinite(tracking_error):
        info_ratio = (strat_mean - bench_mean) * periods_per_year / tracking_error

    return {
        "Alpha": float(alpha) if np.isfinite(alpha) else np.nan,
        "Beta": float(beta) if np.isfinite(beta) else np.nan,
        "InformationRatio": float(info_ratio) if np.isfinite(info_ratio) else np.nan,
        "TrackingError": tracking_error if tracking_error > 0 else 0.0,
    }


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
        "Volatility_annualized": (
            float(returns.std() * math.sqrt(periods_per_year))
            if not returns.empty
            else 0.0
        ),
    }

    sharpe = _sharpe_ratio(returns) if not returns.empty else 0.0
    stats["Sharpe_d"] = float(sharpe)
    stats["Sharpe_annualized"] = float(sharpe * math.sqrt(periods_per_year))

    sortino = _sortino_ratio(returns) if not returns.empty else np.inf
    stats["Sortino_annualized"] = float(
        sortino * math.sqrt(periods_per_year) if np.isfinite(sortino) else np.inf
    )

    dd = rolling_drawdown(equity)
    stats["MaxDrawdown"] = float(dd.min())
    stats["Calmar"] = float(
        stats["CAGR"] / abs(stats["MaxDrawdown"])
        if stats["MaxDrawdown"] < 0
        else np.nan
    )

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
    bench_series: Optional[pd.Series] = None
    if bench is not None:
        try:
            bench_series = _as_series(bench).dropna()
        except ValueError:
            bench_series = None

    if bench_series is not None and not bench_series.empty:
        stats.update(active_stats(equity, bench_series))
        stats.update(capture_ratios(equity, bench_series))

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
        stats["WinRate"] = (
            float(len(wins) / len(trades_df)) if len(trades_df) else np.nan
        )
        stats["AvgTrade"] = float(trades_df["pnl"].mean())
        stats["AvgWin"] = float(wins["pnl"].mean()) if not wins.empty else 0.0
        stats["AvgLoss"] = float(losses["pnl"].mean()) if not losses.empty else 0.0
        gross_win = wins["pnl"].sum()
        gross_loss = losses["pnl"].sum()
        stats["ProfitFactor"] = (
            float(gross_win / abs(gross_loss)) if gross_loss != 0 else np.inf
        )
    else:
        stats["Trades"] = 0.0
        stats["WinRate"] = np.nan
        stats["AvgTrade"] = 0.0
        stats["AvgWin"] = 0.0
        stats["AvgLoss"] = 0.0
        stats["ProfitFactor"] = np.nan

    return stats
