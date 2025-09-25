"""
Adaptive vol targeter - maintains target volatility using trailing realized vol and decay.
Provides monthly scalar to scale portfolio exposure.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_target_scalar(port_returns_monthly: pd.Series, base_target_ann: float = 0.10, min_scalar: float = 0.2, max_scalar: float = 5.0):
    """
    Given monthly portfolio returns series, compute scaling factor to move to base_target_ann.
    Uses trailing 12-month vol estimate (if available).
    """
    if port_returns_monthly is None or len(port_returns_monthly.dropna()) < 6:
        return 1.0
    # convert monthly to annualized vol
    vol_m = port_returns_monthly.rolling(12).std()
    latest_vol_m = vol_m.dropna().iloc[-1] if not vol_m.dropna().empty else None
    if latest_vol_m is None or latest_vol_m == 0:
        return 1.0
    vol_ann = latest_vol_m * np.sqrt(12)
    scalar = float(base_target_ann / vol_ann) if vol_ann > 0 else 1.0
    scalar = float(np.clip(scalar, min_scalar, max_scalar))
    return scalar
