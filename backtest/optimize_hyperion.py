"""Grid search helper for Cerberus Hyperion."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from backtest import run_backtest, summarize
from backtest.strategies.cerberus_hyperion import CerberusHyperion


def _standardize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "close" in frame.columns:
        close = frame["close"].astype(float)
        result = pd.DataFrame(index=frame.index.copy())
        result["close"] = close
        result["open"] = frame.get("open", close).astype(float)
        result["high"] = frame.get("high", close).astype(float)
        result["low"] = frame.get("low", close).astype(float)
        if "volume" in frame:
            result["volume"] = frame["volume"].astype(float)
        return result

    close_candidates = [col for col in frame.columns if col.lower().endswith("_close")]
    if not close_candidates:
        raise ValueError("Input CSV must contain a 'close' column or *_Close columns")

    close_col = close_candidates[0]
    base = close_col[: -len("_Close")]
    base_lower = base.lower()

    def _match(suffix: str) -> Optional[pd.Series]:
        target = f"{base_lower}_{suffix.lower()}"
        for col in frame.columns:
            if col.lower() == target:
                return frame[col].astype(float)
        return None

    close = frame[close_col].astype(float)
    result = pd.DataFrame(index=frame.index.copy())
    result["close"] = close
    result["open"] = _match("Open") or close
    result["high"] = _match("High") or close
    result["low"] = _match("Low") or close
    volume = _match("Volume")
    if volume is not None:
        result["volume"] = volume
    return result


def _grid(param_spec: Dict[str, Iterable[object]]) -> Iterable[Dict[str, object]]:
    keys = sorted(param_spec.keys())
    values = [list(param_spec[key]) for key in keys]
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))


def run(csv_path: str, out_csv: str = "hyperion_grid.csv", seed: int = 42) -> pd.DataFrame:
    """Run a deterministic grid search and emit ADR/Sharpe/MDD."""

    np.random.seed(seed)
    raw = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
    frame = _standardize_frame(raw)
    frame = frame.dropna(subset=["close"]).copy()

    param_grid: Dict[str, Iterable[object]] = {
        "entry_entropy_threshold": [0.018, 0.025, 0.035, 0.042],
        "hyper_min": [0.70, 0.75, 0.80],
        "hyper_tier2": [0.85, 0.90],
        "breakout_period": [40, 55, 70],
        "ema_fast": [13, 21],
        "ema_slow": [89, 100, 144],
        "stop_atr_mult": [1.0, 1.2],
        "target_atr_mult": [3.0, 3.5, 4.0],
    }

    rows: list[dict[str, object]] = []
    for params in _grid(param_grid):
        strategy = CerberusHyperion(params)
        result = run_backtest(
            frame,
            strategy,
            starting_cash=100_000,
            mode="delta",
            size_notional=10_000,
            commission=0.0,
            slippage_bps=0.0,
        )
        stats = summarize(result.equity_curve, result.fills, result.trade_log)
        returns = result.equity_curve.pct_change().dropna()
        adr = 100.0 * float(returns.mean())
        total_return = 100.0 * (
            (float(result.equity_curve.iloc[-1]) / float(result.equity_curve.iloc[0])) - 1.0
        )
        rows.append(
            {
                "params": json.dumps(params),
                "Sharpe": stats.get("Sharpe_annualized", stats.get("Sharpe_d", 0.0)),
                "MDD": stats.get("MaxDD", stats.get("MaxDrawdown", 0.0)),
                "ADR_pct": adr,
                "TotalReturn_pct": total_return,
                "Trades": int(len(result.trade_log)),
            }
        )

    output = pd.DataFrame(rows).sort_values(["Sharpe", "ADR_pct"], ascending=[False, False])
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_path, index=False)

    top = output.iloc[0]
    print("Best config:")
    print(top.to_string())
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize Cerberus Hyperion via grid search")
    parser.add_argument("--csv", required=True, help="Input CSV with OHLCV data")
    parser.add_argument("--out-csv", default="hyperion_grid.csv", help="Destination CSV for results")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(args.csv, args.out_csv, args.seed)
