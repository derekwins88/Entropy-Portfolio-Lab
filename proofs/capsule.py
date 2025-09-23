"""Proof capsule generator for optimization results."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_capsule(results_csv: str, sharpe_min: float, maxdd_max: float, out_prefix: str) -> bool:
    df = pd.read_csv(results_csv)
    sharpe_series = df.get("Sharpe_annualized", df.get("Sharpe_d", pd.Series([0.0])))
    maxdd_series = df.get("MaxDD", df.get("MaxDrawdown", pd.Series([0.0])))

    sharpe = float(pd.Series(sharpe_series).median())
    maxdd = float(pd.Series(maxdd_series).median())
    verdict = bool(sharpe >= sharpe_min and maxdd <= maxdd_max)

    manifest: dict[str, Any] = {
        "source": results_csv,
        "claims": {"Sharpe_annualized_min": sharpe_min, "MaxDD_max": maxdd_max},
        "observed": {"Sharpe_annualized": sharpe, "MaxDD": maxdd},
        "verdict": verdict,
    }

    out_json = Path(f"{out_prefix}.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(manifest, indent=2))

    lean_stub = f"""
-- Auto-generated capsule stub
-- Observed Sharpe = {sharpe:.4f}
-- Observed MaxDD = {maxdd:.4f}
-- Claim: Sharpe ≥ {sharpe_min}, MaxDD ≤ {maxdd_max}
-- sha256(manifest) = {sha256_text(json.dumps(manifest, sort_keys=True))}
"""
    out_lean = Path(f"{out_prefix}.lean")
    out_lean.write_text(lean_stub)

    print(json.dumps(manifest, indent=2))
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a proof capsule from results CSV")
    parser.add_argument("--results", required=True, help="CSV with grid or walk-forward results")
    parser.add_argument("--sharpe", type=float, required=True, help="Minimum acceptable Sharpe ratio")
    parser.add_argument("--maxdd", type=float, required=True, help="Maximum acceptable drawdown")
    parser.add_argument("--out", default="proofs/capsule", help="Output prefix for capsule files")
    args = parser.parse_args()

    ok = make_capsule(args.results, args.sharpe, args.maxdd, args.out)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
