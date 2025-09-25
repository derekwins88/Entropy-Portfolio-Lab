#!/usr/bin/env python
"""
Walk-forward backtest runner for Entropy-Portfolio-Lab.
Splits history into rolling train/test folds, runs strategy, saves metrics per fold.

Usage:
    python scripts/run_walkforward.py --config configs/etrp.yml --train 5 --test 1
"""
from __future__ import annotations
import argparse, sys, yaml
from pathlib import Path
from copy import deepcopy
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import lab.strategies as lab_strategies
sys.modules.setdefault("strategies", lab_strategies)
from lab.run import load_prices
from lab.strategies.etrp import run_etrp

def rolling_windows(start: pd.Timestamp, end: pd.Timestamp, train_years: int, test_years: int):
    # month granularity
    idx = pd.date_range(start, end, freq="M")
    for i in range(0, len(idx) - (train_years + test_years)*12 + 1, test_years*12):
        train_start = idx[i]
        train_end   = idx[i + train_years*12 - 1]
        test_start  = idx[i + train_years*12]
        test_end    = idx[min(i + (train_years+test_years)*12 - 1, len(idx)-1)]
        yield (train_start, train_end, test_start, test_end)

def load_prices_resilient(cfg: dict):
    try:
        return load_prices(cfg)
    except Exception as exc:
        if cfg.get("data", {}).get("use_synth_if_missing", True):
            print(f"[run_fold] warning: {exc}. Falling back to synthetic data.")
            cfg2 = deepcopy(cfg)
            cfg2["data"]["data_dir"] = "__synthetic__"
            return load_prices(cfg2)
        raise


def run_fold(cfg: dict, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    cfg2 = deepcopy(cfg)
    cfg2["backtest"]["start"] = str(start.date())
    cfg2["backtest"]["end"]   = str(end.date())
    px = load_prices_resilient(cfg2)
    res = run_etrp(px, cfg2)
    m = {k: float(v) for k,v in res["metrics"].items()}
    m.update({"start": str(start.date()), "end": str(end.date())})
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/etrp.yml")
    ap.add_argument("--train", type=int, default=5, help="train years")
    ap.add_argument("--test", type=int, default=1, help="test years")
    ap.add_argument("--out", default="runs/walkforward.csv")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    start = pd.Timestamp(cfg["backtest"]["start"])
    end   = pd.Timestamp(cfg["backtest"]["end"])

    rows = []
    for tr_start, tr_end, te_start, te_end in rolling_windows(start, end, args.train, args.test):
        # in a true hyperparam search you'd tune on train here; we just run test
        print(f"[fold] train {tr_start.date()}→{tr_end.date()} | test {te_start.date()}→{te_end.date()}")
        m = run_fold(cfg, te_start, te_end)
        rows.append(m)

    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"[walkforward] saved metrics to {args.out}")
    print(df.describe().T)

if __name__ == "__main__":
    main()
