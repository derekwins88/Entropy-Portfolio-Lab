"""Unit tests for the Entropy-Tilted Risk Parity strategy."""

import numpy as np
import pandas as pd

from lab.strategies.etrp import portfolio_returns_monthly, rolling_entropy, etrp_weights


def test_entropy_orders_series() -> None:
    """Higher-noise series should produce higher entropy."""
    index = pd.date_range("2020-01-01", periods=500, freq="B")
    rng = np.random.default_rng(0)
    low_noise = pd.Series(rng.normal(0, 0.005, len(index)), index=index, name="low")
    high_noise = pd.Series(rng.normal(0, 0.03, len(index)), index=index, name="high")

    entropy_low = rolling_entropy(low_noise, 63, 20).iloc[-1]
    entropy_high = rolling_entropy(high_noise, 63, 20).iloc[-1]

    assert entropy_high > entropy_low


def test_weights_shape_and_sum() -> None:
    """Monthly weights should sum to unity and produce finite returns."""
    index = pd.date_range("2020-01-01", periods=600, freq="B")
    rng = np.random.default_rng(1)
    prices = {}
    for symbol in ["A", "B", "C", "D"]:
        ret = 0.0002 + rng.normal(0, 0.01, len(index))
        prices[symbol] = 100 * (1 + pd.Series(ret, index=index)).cumprod()
    price_df = pd.DataFrame(prices)

    weights = etrp_weights(price_df, window_days=63, entropy_bins=20, weight_cap=0.5, target_vol_ann=0.1)
    assert np.allclose(weights.sum(axis=1), 1.0)

    returns = price_df.pct_change().dropna()
    portfolio_monthly = portfolio_returns_monthly(returns, weights)
    assert portfolio_monthly.notna().sum() > 0
    assert np.isfinite(portfolio_monthly).all()
