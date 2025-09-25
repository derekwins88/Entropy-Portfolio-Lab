"""Command-line entry point for running Entropy-Tilted Risk Parity backtests."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from .strategies import run_etrp


def load_prices(config: Dict) -> pd.DataFrame:
    """Load price data for the configured universe, generating synthetic data if needed."""
    universe = config["data"]["universe"]
    data_dir = Path(config["data"]["data_dir"])
    start = pd.Timestamp(config["backtest"]["start"])
    end = pd.Timestamp(config["backtest"]["end"])

    frames = []
    for symbol in universe:
        file_path = data_dir / f"{symbol}.csv"
        if not file_path.exists():
            frames.append(None)
            continue

        try:
            df = pd.read_csv(file_path)
        except ValueError:
            frames.append(None)
            continue

        date_col = next((c for c in ["Date", "date", "datetime", "timestamp"] if c in df.columns), None)
        if date_col is None:
            frames.append(None)
            continue

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()

        close_col = next((c for c in ["Close", "close", "adj_close", "Adj Close"] if c in df.columns), None)
        if close_col is None:
            frames.append(None)
            continue

        frames.append(df[close_col].rename(symbol))

    if any(frame is None for frame in frames):
        if config["data"].get("use_synth_if_missing", True):
            print("[run] using synthetic GBM-style data for missing files.")
            np.random.seed(config.get("seed", 42))
            index = pd.date_range(start, end, freq="B")
            synth = {}
            for symbol in universe:
                mu, sigma = 0.06, 0.18
                eps = np.random.normal(0, sigma / np.sqrt(252), size=len(index))
                returns = (mu / 252) + eps
                synth[symbol] = 100 * (1 + pd.Series(returns, index=index)).cumprod()
            prices = pd.DataFrame(synth)
        else:
            missing = [sym for sym, frame in zip(universe, frames) if frame is None]
            raise FileNotFoundError(f"Missing data for {missing} and synthetic generation disabled.")
    else:
        prices = pd.concat(frames, axis=1)

    prices = prices.loc[start:end].dropna(how="all")
    return prices


def save_outputs(output_dir: Path, results: Dict) -> None:
    """Persist weights, returns, equity curve, and metrics to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    results["weights_me"].to_csv(output_dir / "weights_monthly.csv")
    results["port_monthly"].to_csv(output_dir / "portfolio_monthly.csv", header=["ret"])
    results["equity"].to_csv(output_dir / "equity.csv", header=["equity"])

    metrics = results["metrics"]
    metrics_path = output_dir / "metrics.txt"
    with metrics_path.open("w", encoding="utf-8") as handle:
        for key, value in metrics.items():
            handle.write(f"{key}: {value:.4f}\n")


def plot_equity_curve(output_dir: Path, equity: pd.Series) -> None:
    """Generate a PNG equity curve plot."""
    fig, ax = plt.subplots(figsize=(9, 4))
    equity.plot(ax=ax, title="ETRP – Equity Curve")
    ax.set_ylabel("Equity (index)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "equity.png", dpi=150)
    plt.close(fig)


def run(config_path: str) -> None:
    """Execute the configured ETRP backtest."""
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(config["output"]["out_dir"]) / timestamp

    prices = load_prices(config)
    results = run_etrp(prices, config)

    save_outputs(output_dir, results)

    metrics = results["metrics"]
    print(
        "[metrics] "
        f"CAGR={metrics['CAGR']:.2%}  "
        f"VolAnn={metrics['VolAnn']:.2%}  "
        f"Sharpe={metrics['Sharpe']:.2f}  "
        f"MaxDD={metrics['MaxDD']:.2%}"
    )

    if config["output"].get("plot", True):
        plot_equity_curve(output_dir, results["equity"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Entropy-Tilted Risk Parity backtest.")
    parser.add_argument("--config", default="configs/etrp.yml", help="Path to YAML configuration file.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
