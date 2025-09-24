"""Pattern recognition helpers."""

from __future__ import annotations

import pandas as pd


def nr7(high: pd.Series, low: pd.Series, lookback: int = 7) -> pd.Series:
    """Return a boolean series for the NR7 (narrowest range in ``lookback`` bars).

    Parameters
    ----------
    high, low:
        Series representing the high and low of each bar.
    lookback:
        Window length used to compare true ranges. The default mirrors the
        canonical "NR7" setup.
    """

    true_range = (high - low).abs()
    rolling_min = true_range.rolling(lookback, min_periods=lookback).min()
    return (true_range <= rolling_min).fillna(False)


__all__ = ["nr7"]
