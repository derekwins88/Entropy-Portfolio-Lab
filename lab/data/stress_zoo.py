"""
Stress Zoo dataset generator for Entropy-Portfolio-Lab.

Usage:
    >>> from lab.data.stress_zoo import generate_stress_zoo
    >>> generate_stress_zoo(outdir="data/stress_zoo", universe=["SPY","QQQ","IWM","TLT"], n_days=252*5, seed=42)

Output:
    data/stress_zoo/<scenario>/<SYMBOL>.csv  (Date, Close)
    data/stress_zoo/<scenario>/prices.csv   (Date, SPY, QQQ, ...)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Sequence, Dict, Any

DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "LQD", "GLD", "SHY"]

def _gbm_prices(seed, mu, sigma, start_price, idx):
    rng = np.random.default_rng(seed)
    dt = 1/252
    eps = rng.normal(loc=(mu*dt), scale=(sigma*np.sqrt(dt)), size=len(idx))
    logret = eps
    price = start_price * np.exp(np.cumsum(logret))
    return pd.Series(price, index=idx)

def _mean_reverting_prices(seed, mu, sigma, theta, start_price, idx):
    # Ornstein-Uhlenbeck discretization on log-price
    rng = np.random.default_rng(seed)
    dt = 1/252
    x = np.log(start_price)
    out = []
    for _ in range(len(idx)):
        dx = theta*(mu - x)*dt + sigma*np.sqrt(dt)*rng.normal()
        x = x + dx
        out.append(np.exp(x))
    return pd.Series(out, index=idx)

def _regime_switch_prices(seed, regimes, trans_mat, start_price, idx):
    rng = np.random.default_rng(seed)
    n = len(idx)
    k = len(regimes)
    states = np.zeros(n, dtype=int)
    # initial state
    states[0] = rng.integers(0, k)
    for t in range(1, n):
        states[t] = rng.choice(k, p=trans_mat[states[t-1]])
    price = np.empty(n)
    logp = np.log(start_price)
    dt = 1/252
    for t in range(n):
        r = rng.normal(loc=regimes[states[t]]["mu"] * dt, scale=regimes[states[t]]["sigma"] * np.sqrt(dt))
        logp = logp + r
        price[t] = np.exp(logp)
    return pd.Series(price, index=idx)

def _jumps_prices(seed, mu, sigma, jump_prob, jump_mu, jump_sigma, start_price, idx):
    rng = np.random.default_rng(seed)
    dt = 1/252
    logp = np.log(start_price)
    out = []
    for _ in range(len(idx)):
        jump = rng.random() < jump_prob
        j = rng.normal(jump_mu, jump_sigma) if jump else 0.0
        r = rng.normal(mu*dt, sigma*np.sqrt(dt))
        logp = logp + r + j
        out.append(np.exp(logp))
    return pd.Series(out, index=idx)

def _correlated_basket(seed, mus, sigmas, corr, start_prices, idx):
    rng = np.random.default_rng(seed)
    dt = 1/252
    n = len(idx)
    k = len(mus)
    cov = np.outer(sigmas, sigmas) * corr
    L = np.linalg.cholesky(cov)
    logp = np.log(np.array(start_prices))
    out = np.zeros((n, k))
    for t in range(n):
        z = rng.normal(size=k)
        eps = L @ z
        logp = logp + (np.array(mus)*dt) + eps * np.sqrt(dt)
        out[t] = np.exp(logp)
    df = pd.DataFrame(out, index=idx, columns=[f"S{i}" for i in range(k)])
    return df

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def generate_stress_zoo(
    outdir: str = "data/stress_zoo",
    universe: Sequence[str] | None = None,
    n_days: int = 252*5,
    start_date: str = "2015-01-01",
    seed: int = 42,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Generate a set of synthetic market scenarios.

    Parameters
    ----------
    outdir : str
        Root folder to write scenario CSVs.
    universe : sequence[str]
        Ticker list. Defaults to DEFAULT_UNIVERSE.
    n_days : int
        Number of business days to simulate (default ~5 years).
    start_date : str
        Start date for the index.
    seed : int
        RNG seed (reproducible).
    verbose : bool
        If True print progress.

    Returns
    -------
    dict
        Metadata about generated scenarios and file paths.
    """
    universe = list(universe or DEFAULT_UNIVERSE)
    idx = pd.date_range(start=start_date, periods=n_days, freq="B")
    out_root = Path(outdir)
    _ensure_dir(out_root)

    start_prices = {s: float(80 + 40 * (i % 5)) for i, s in enumerate(universe)}

    scenarios = {}

    # 1) trend_up (orangutan swinging up)
    if verbose: print("[zoo] generating trend_up")
    trend_up = {}
    for i, sym in enumerate(universe):
        mu = 0.12 + 0.02 * (i % 3)    # modest positive drift
        sigma = 0.12
        trend_up[sym] = _gbm_prices(seed + i, mu, sigma, start_prices[sym], idx)
    scenarios["trend_up"] = pd.DataFrame(trend_up)

    # 2) trend_down (giraffe bending down slowly)
    if verbose: print("[zoo] generating trend_down")
    trend_down = {}
    for i, sym in enumerate(universe):
        mu = -0.08 - 0.01 * (i % 2)
        sigma = 0.12
        trend_down[sym] = _gbm_prices(seed + 100 + i, mu, sigma, start_prices[sym], idx)
    scenarios["trend_down"] = pd.DataFrame(trend_down)

    # 3) mean_revert
    if verbose: print("[zoo] generating mean_revert")
    mean_rev = {}
    for i, sym in enumerate(universe):
        mu = np.log(start_prices[sym])  # mean log-price
        sigma = 0.06
        theta = 1.2  # stronger pull
        mean_rev[sym] = _mean_reverting_prices(seed + 200 + i, mu, sigma, theta, start_prices[sym], idx)
    scenarios["mean_revert"] = pd.DataFrame(mean_rev)

    # 4) regime_switch (cheeky rhino)
    if verbose: print("[zoo] generating regime_switch")
    regimes = [
        {"mu": 0.15, "sigma": 0.18},   # bull
        {"mu": -0.12, "sigma": 0.25},  # bear
        {"mu": 0.0, "sigma": 0.40},    # panic
    ]
    trans_mat = np.array([
        [0.90, 0.08, 0.02],
        [0.05, 0.90, 0.05],
        [0.10, 0.10, 0.80],
    ])
    rs = {}
    for i, sym in enumerate(universe):
        rs[sym] = _regime_switch_prices(seed + 400 + i, regimes, trans_mat, start_prices[sym], idx)
    scenarios["regime_switch"] = pd.DataFrame(rs)

    # 5) vol_spike (sudden volatility; short spikes)
    if verbose: print("[zoo] generating vol_spike")
    vs = {}
    for i, sym in enumerate(universe):
        base_mu, base_sigma = 0.02, 0.10
        # create base series and then inject a few spike windows
        p = _gbm_prices(seed + 500 + i, base_mu, base_sigma, start_prices[sym], idx).copy()
        rng_local = np.random.default_rng(seed + 600 + i)
        for spike_start in rng_local.choice(range(30, len(idx)-30), size=5, replace=False):
            span = rng_local.integers(3, 15)
            jdx = slice(spike_start, spike_start+span)
            # multiply local volatility by factor
            window = _gbm_prices(seed + 700 + i + spike_start, 0.0, base_sigma*3.5, p.iloc[jdx].iloc[0], idx[jdx])
            p.iloc[jdx] = window.values
        vs[sym] = p
    scenarios["vol_spike"] = pd.DataFrame(vs)

    # 6) jumps (black rhino)
    if verbose: print("[zoo] generating jumps")
    jumps = {}
    for i, sym in enumerate(universe):
        jumps[sym] = _jumps_prices(seed + 800 + i, mu=0.02, sigma=0.1, jump_prob=0.01, jump_mu=-0.05, jump_sigma=0.08, start_price=start_prices[sym], idx=idx)
    scenarios["jumps"] = pd.DataFrame(jumps)

    # 7) diversification_failure: many assets highly correlated (everything moves together)
    if verbose: print("[zoo] generating diversification_failure")
    df = {}
    k = len(universe)
    mus = [0.05]*k
    sigs = [0.18]*k
    # correlation near 0.95
    corr = np.full((k, k), 0.95)
    np.fill_diagonal(corr, 1.0)
    basket = _correlated_basket(seed + 1000, mus, sigs, corr, [start_prices[s] for s in universe], idx)
    basket.columns = universe
    scenarios["diversification_failure"] = basket

    # 8) black_swan: long calm then single catastrophic month
    if verbose: print("[zoo] generating black_swan")
    bs = {}
    for i, sym in enumerate(universe):
        p = _gbm_prices(seed + 1200 + i, mu=0.06, sigma=0.08, start_price=start_prices[sym], idx=idx).copy()
        # pick one month to crash
        rng_local = np.random.default_rng(seed + 1300 + i)
        crash_start = rng_local.integers(low=100, high=len(idx)-20)
        crash_len = rng_local.integers(5, 15)
        # mul by a steep drop path
        drop = np.linspace(1.0, 0.45 - 0.1*(i%3), crash_len)
        p.iloc[crash_start:crash_start+crash_len] = p.iloc[crash_start] * drop
        bs[sym] = p
    scenarios["black_swan"] = pd.DataFrame(bs)

    # Write outputs
    meta = {}
    for scen, df in scenarios.items():
        scen_dir = out_root / scen
        _ensure_dir(scen_dir)
        # per-symbol csvs
        for col in df.columns:
            s = pd.DataFrame({"Date": df.index, "Close": df[col].values})
            s.to_csv(scen_dir / f"{col}.csv", index=False)
        # combined prices csv
        df_out = df.copy()
        df_out.index.name = "Date"
        df_out.to_csv(scen_dir / "prices.csv")
        meta[scen] = {"path": str(scen_dir), "shape": df.shape}
        if verbose: print(f"[zoo] wrote scenario {scen} -> {scen_dir}  shape={df.shape}")

    return {"outdir": str(out_root), "scenarios": meta}
