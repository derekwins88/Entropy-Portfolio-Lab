"""Generate a sensitivity heatmap for Praetorian entropy/breakout settings."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backtest.core.data import (
    ensure_datetime_index,
    infer_periods_per_year,
    require_columns,
    standardize_columns,
)
from backtest.core.engine import run_backtest
from backtest.strategies.praetorian import ThePraetorianEngine


def _load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = standardize_columns(frame)
    frame = ensure_datetime_index(frame)
    require_columns(frame, ["close"])
    if "high" not in frame.columns:
        frame["high"] = frame["close"]
    if "low" not in frame.columns:
        frame["low"] = frame["close"]
    if "volume" not in frame.columns:
        frame["volume"] = 1.0
    return frame


def _compute_sharpe(equity: pd.Series) -> float:
    returns = equity.pct_change().dropna()
    if returns.empty:
        return 0.0
    periods = infer_periods_per_year(equity.index)
    std = float(returns.std(ddof=0))
    if std <= 0:
        return 0.0
    mean = float(returns.mean())
    return float(mean / std * np.sqrt(periods))


def run_sensitivity(frame: pd.DataFrame, out_path: Path) -> None:
    ent_vals = [0.010, 0.012, 0.015, 0.018, 0.020]
    brk_vals = [30, 40, 55, 70, 90]
    z = np.zeros((len(ent_vals), len(brk_vals)))

    for i, entropy_threshold in enumerate(ent_vals):
        for j, breakout_period in enumerate(brk_vals):
            params: Dict[str, object] = dict(
                entropy_lookback=40,
                entry_entropy_threshold=entropy_threshold,
                breakout_period=breakout_period,
                ema_fast=21,
                ema_slow=100,
                vwap_len=20,
                vwap_max_distance_atr=1.0,
                base_risk_percent=1.0,
                turbo=1,
                nr7=1,
                conviction_gain=0.25,
                conviction_loss=0.50,
                min_conviction=0.5,
                max_conviction=1.75,
            )
            strategy = ThePraetorianEngine(params)
            result = run_backtest(
                frame,
                strategy,
                mode="target",
                atr_len=14,
                risk_R=1.0,
                risk_pct=0.01,
                maxR_per_day=3.0,
            )
            z[i, j] = _compute_sharpe(result.equity_curve)

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(z, cmap="viridis", origin="lower", aspect="auto")
    ax.set_xticks(range(len(brk_vals)), brk_vals)
    ax.set_yticks(range(len(ent_vals)), ent_vals)
    ax.set_xlabel("Breakout Period (N)")
    ax.set_ylabel("Entry Entropy Threshold")
    ax.set_title("OOS Sharpe — Sensitivity (Entropy vs Breakout)")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Sharpe")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Input OHLCV CSV")
    parser.add_argument(
        "--out",
        default="artifacts/sensitivity_entropy_breakout.png",
        help="Output image path",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    frame = _load_frame(csv_path)
    out_path = Path(args.out)
    run_sensitivity(frame, out_path)


if __name__ == "__main__":  # pragma: no cover - manual usage
    main()
