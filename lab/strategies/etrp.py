"""Entropy-Tilted Risk Parity strategy implementation."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def _shannon_entropy(values: np.ndarray, bins: int = 20) -> float:
    """Approximate Shannon entropy (base e) using histogram density."""
    if values.size == 0 or np.all(np.isnan(values)):
        return float("nan")
    hist, _ = np.histogram(values[~np.isnan(values)], bins=bins, density=True)
    total = hist.sum()
    if total == 0:
        return float("nan")
    probs = hist / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log(probs)))


def rolling_entropy(returns: pd.Series, window: int, bins: int) -> pd.Series:
    """Rolling entropy for a return series."""
    return returns.rolling(window).apply(lambda window_vals: _shannon_entropy(window_vals.values, bins))


def realized_vol(returns: pd.Series, window: int) -> pd.Series:
    """Rolling realized volatility (daily std)."""
    return returns.rolling(window).std()


def to_month_end_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Map a daily index to month-end timestamps."""
    return df.index.to_period("M").to_timestamp("M")


def inverse_vol_weights(ret_df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Compute inverse-volatility weights."""
    vol = ret_df.rolling(window).std()
    weights = 1.0 / vol.replace(0, np.nan)
    weights = weights.div(weights.sum(axis=1), axis=0)
    return weights


def cap_and_renorm(weights: pd.DataFrame, cap: float) -> pd.DataFrame:
    """Apply a per-asset cap and renormalize weights to sum to 1."""
    capped = weights.clip(upper=cap)
    totals = capped.sum(axis=1).replace(0, np.nan)
    return capped.div(totals, axis=0)


def normalize_01(series: pd.Series, lookback: int) -> pd.Series:
    """Normalize a series to the [0, 1] range using a rolling min/max."""
    rolling_min = series.rolling(lookback).min()
    rolling_max = series.rolling(lookback).max()
    denom = (rolling_max - rolling_min).replace(0, np.nan)
    return (series - rolling_min) / denom


def target_vol_scalar(portfolio_returns: pd.Series, target_vol_ann: float) -> float:
    """Compute a leverage scalar to hit the target annualized volatility."""
    if len(portfolio_returns) < 252:
        return 1.0
    vol_ann = portfolio_returns[-252:].std() * np.sqrt(252)
    if pd.isna(vol_ann) or vol_ann == 0:
        return 1.0
    return float(np.clip(target_vol_ann / vol_ann, 0.2, 5.0))


def etrp_weights(
    prices: pd.DataFrame,
    window_days: int = 63,
    entropy_bins: int = 20,
    weight_cap: float = 0.30,
    target_vol_ann: float = 0.10,
    regime: Optional[Dict] = None,
) -> pd.DataFrame:
    """Compute monthly weights for the Entropy-Tilted Risk Parity strategy."""
    prices = prices.sort_index()
    returns = prices.pct_change().dropna(how="all")

    base_weights = inverse_vol_weights(returns, window_days)

    entropy = returns.apply(lambda col: rolling_entropy(col, window_days, entropy_bins))
    entropy_norm = entropy.apply(lambda col: normalize_01(col, 252 * 3))

    tilted_daily = (base_weights * (1.0 - entropy_norm))
    tilted_daily = tilted_daily.div(tilted_daily.sum(axis=1), axis=0)
    tilted_daily = cap_and_renorm(tilted_daily, weight_cap)

    month_ends = to_month_end_index(tilted_daily)
    weights_me = tilted_daily.groupby(month_ends).last()
    weights_me = weights_me.shift(1).dropna(how="all")

    if regime:
        vol_threshold = float(regime.get("vol_pctl", 0.95))
        entropy_threshold = float(regime.get("entropy_pctl", 0.80))
        defense_weights = regime.get("defense_weights", {"IEF": 0.35, "TLT": 0.35, "SHY": 0.30})

        daily_weights = tilted_daily.shift(1).reindex(returns.index).fillna(0)
        portfolio_daily = (daily_weights * returns).sum(axis=1)
        portfolio_vol = portfolio_daily.rolling(window_days).std()
        avg_entropy = entropy_norm.mean(axis=1)

        vol_cutoff = portfolio_vol.rolling(252 * 3, min_periods=60).quantile(vol_threshold)
        entropy_cutoff = avg_entropy.rolling(252 * 3, min_periods=60).quantile(entropy_threshold)
        stress = (portfolio_vol > vol_cutoff) | (avg_entropy > entropy_cutoff)
        stress_me = stress.groupby(month_ends).last()

        defense = pd.Series(0.0, index=weights_me.columns)
        for symbol, weight in defense_weights.items():
            if symbol in defense.index:
                defense[symbol] = float(weight)
        if defense.sum() > 0:
            defense = defense / defense.sum()

        idx = stress_me.index.intersection(weights_me.index)
        mask = stress_me.loc[idx].astype(float).values.reshape(-1, 1)
        weights_me.loc[idx] = (1 - 0.5 * mask) * weights_me.loc[idx].values + (0.5 * mask) * defense.values
        weights_me = weights_me.div(weights_me.sum(axis=1), axis=0)

    portfolio_monthly = portfolio_returns_monthly(returns, weights_me)
    leverage = target_vol_scalar(portfolio_monthly, target_vol_ann)
    weights_me = weights_me * leverage
    return weights_me


def portfolio_returns_monthly(ret_daily: pd.DataFrame, weights_me: pd.DataFrame) -> pd.Series:
    """Expand monthly weights to daily returns and aggregate back to month-end."""
    month_ends = ret_daily.index.to_period("M").to_timestamp("M")
    daily_weights = weights_me.reindex(ret_daily.index, method="ffill").fillna(0)
    portfolio_daily = (daily_weights.shift(1).fillna(0) * ret_daily).sum(axis=1)
    return portfolio_daily.groupby(month_ends).apply(lambda values: (1 + values).prod() - 1)


def run_etrp(prices: pd.DataFrame, config: Dict) -> Dict:
    """Run the ETRP pipeline and return weights, returns, equity curve, and metrics."""
    strategy_cfg = config["strategy"]
    weights = etrp_weights(
        prices=prices,
        window_days=strategy_cfg["window_days"],
        entropy_bins=strategy_cfg["entropy_bins"],
        weight_cap=strategy_cfg["weight_cap"],
        target_vol_ann=strategy_cfg["target_vol_ann"],
        regime=strategy_cfg.get("regime"),
    )

    returns = prices.pct_change().dropna(how="all")
    portfolio_monthly = portfolio_returns_monthly(returns, weights)
    equity = (1 + portfolio_monthly).cumprod()

    cagr = (1 + portfolio_monthly).prod() ** (12 / len(portfolio_monthly)) - 1
    vol_ann = portfolio_monthly.std() * np.sqrt(12)
    sharpe = 0.0 if vol_ann == 0 else cagr / vol_ann
    max_dd = (equity / equity.cummax() - 1).min()

    return {
        "weights_me": weights,
        "port_monthly": portfolio_monthly,
        "equity": equity,
        "metrics": {
            "CAGR": float(cagr),
            "VolAnn": float(vol_ann),
            "Sharpe": float(sharpe),
            "MaxDD": float(max_dd),
        },
    }


__all__ = [
    "etrp_weights",
    "portfolio_returns_monthly",
    "realized_vol",
    "rolling_entropy",
    "target_vol_scalar",
    "run_etrp",
]
