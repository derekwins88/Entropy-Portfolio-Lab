"""Fetch historical price data for a list of symbols using yfinance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

try:
    import yfinance as yf
except ImportError as exc:  # pragma: no cover - imported module should exist at runtime
    raise SystemExit(
        "yfinance is required to fetch data. Install it with 'pip install yfinance'."
    ) from exc


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download price history for symbols.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="One or more ticker symbols to download (e.g., AAPL SPY QQQ)",
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Lookback period to request from yfinance (default: 1y)",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Sampling interval (default: 1d). See yfinance docs for options.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data"),
        help="Directory where the CSV files should be saved (default: data)",
    )
    parser.add_argument(
        "--auto-adjust",
        action="store_true",
        help="Apply dividends/splits adjustments when downloading.",
    )
    return parser.parse_args(argv)


def _write_symbol_data(symbol: str, df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty:
        print(f"[warn] No data returned for {symbol}.", file=sys.stderr)
        return

    df = df.rename(columns=str.lower)
    df.index.name = "datetime"
    output_path = output_dir / f"{symbol}.csv"
    df.to_csv(output_path)
    print(f"[ok] Wrote {output_path}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    for symbol in args.symbols:
        print(f"[info] Fetching {symbol}...")
        data = yf.download(
            symbol,
            period=args.period,
            interval=args.interval,
            auto_adjust=args.auto_adjust,
            progress=False,
        )
        _write_symbol_data(symbol, data, output_dir)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
