"""
Lightweight regime classifier:
- Inputs: rolling realized vol, avg entropy, momentum
- Outputs: regime label in {'calm','normal','turbo','panic'}
This is intentionally simple and interpretable.
"""
from __future__ import annotations
import pandas as pd

def classify_regime(
    returns: pd.DataFrame,
    entropy: pd.DataFrame | None = None,
    vol_window: int = 63,
    ent_window: int = 63,
    vol_pcts: tuple = (0.33, 0.66),
    ent_pcts: tuple = (0.33, 0.66),
) -> pd.Series:
    """
    Compute regime label per day using percentile thresholds over a trailing 3-year window when possible.
    Returns a pd.Series indexed like returns.index containing string labels.
    """
    idx = returns.index
    # realized vol (portfolio-level default: mean of asset vols)
    vol = returns.rolling(vol_window).std().mean(axis=1)
    # entropy fallback: if not provided, use per-asset rolling entropy mean (na-safe)
    if entropy is None:
        # crude: use histogram-based per-asset entropies approximated via returns distribution width
        entropy = returns.abs().rolling(ent_window).mean()
        avg_entropy = entropy.mean(axis=1)
    else:
        avg_entropy = entropy.mean(axis=1)

    # compute long-window percentiles (use expanding/multiyear)
    lookback = max(int(252*3), vol_window*2)
    vol_p1 = vol.rolling(lookback, min_periods=60).quantile(vol_pcts[0])
    vol_p2 = vol.rolling(lookback, min_periods=60).quantile(vol_pcts[1])
    ent_p1 = avg_entropy.rolling(lookback, min_periods=60).quantile(ent_pcts[0])
    ent_p2 = avg_entropy.rolling(lookback, min_periods=60).quantile(ent_pcts[1])

    labels = pd.Series(index=idx, dtype=object)
    for t in idx:
        v = vol.loc[t]
        e = avg_entropy.loc[t]
        # guard: if thresholds are NaN (start of history), use "normal"
        if pd.isna(v) or pd.isna(e) or pd.isna(vol_p1.loc[t]) or pd.isna(ent_p1.loc[t]):
            labels.loc[t] = "normal"
            continue
        # regime logic: simple grid of low/medium/high vol and low/med/high entropy
        v_level = 0 if v <= vol_p1.loc[t] else (1 if v <= vol_p2.loc[t] else 2)
        e_level = 0 if e <= ent_p1.loc[t] else (1 if e <= ent_p2.loc[t] else 2)
        # map to regime label
        if v_level == 0 and e_level <= 1:
            labels.loc[t] = "calm"
        elif v_level == 2 and e_level == 2:
            labels.loc[t] = "panic"
        elif v_level == 2:
            labels.loc[t] = "turbo"
        else:
            labels.loc[t] = "normal"
    return labels
