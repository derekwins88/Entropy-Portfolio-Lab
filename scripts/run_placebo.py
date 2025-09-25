#!/usr/bin/env python
"""
Placebo test runner: scrambles returns to check strategy robustness.
If strategy still prints god-mode Sharpe under placebo, you know it's lying.

Usage:
    python scripts/run_placebo.py --config configs/etrp.yml --mode shuffle_months
"""
from __future__ import annotations
import argparse, sys, yaml
from pathlib import Path
import pandas as pd, numpy as np
from copy import deepcopy
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import lab.strategies as lab_strategies
sys.modules.setdefault("strategies", lab_strategies)
from lab.run import load_prices
from lab.strategies.etrp import run_etrp

def shuffle_months(px: pd.DataFrame, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # group by month, shuffle the order
    g = list(px.groupby(px.index.to_period("M")))
    rng.shuffle(g)
    df = pd.concat([grp for _, grp in g])
    df.index = pd.date_range(start=px.index[0], periods=len(df), freq="B")
    return df

def permute_within_blocks(px: pd.DataFrame, block_days=21, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = px.index
    arr = px.values.copy()
    n = len(idx)
    for start in range(0, n, block_days):
        block = arr[start:start+block_days]
        rng.shuffle(block)
        arr[start:start+block_days] = block
    df = pd.DataFrame(arr, index=idx, columns=px.columns)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/etrp.yml")
    ap.add_argument("--mode", choices=["shuffle_months","permute_blocks"], default="shuffle_months")
    ap.add_argument("--out", default="runs/placebo.csv")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))

    def load_prices_resilient(cfg: dict) -> pd.DataFrame:
        try:
            return load_prices(cfg)
        except Exception as exc:
            if cfg.get("data", {}).get("use_synth_if_missing", True):
                print(f"[placebo] warning: {exc}. Falling back to synthetic data.")
                cfg2 = deepcopy(cfg)
                cfg2["data"]["data_dir"] = "__synthetic__"
                return load_prices(cfg2)
            raise

    px = load_prices_resilient(cfg)

    if args.mode == "shuffle_months":
        px2 = shuffle_months(px)
    else:
        px2 = permute_within_blocks(px)

    res = run_etrp(px2, cfg)
    m = {k: float(v) for k,v in res["metrics"].items()}
    df = pd.DataFrame([m])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"[placebo] saved {args.out}")
    print(df)

if __name__ == "__main__":
    main()
