"""Command line interface for the backtest package."""

from __future__ import annotations

import argparse
import json
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .core.engine import run_backtest
from .core.metrics import summarize
from .portfolio import run_portfolio


def _load_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(p, parse_dates=[0], index_col=0)


def _load_price_series(path: str) -> pd.Series:
    df = _load_csv(path)
    for column in ("close", "Close", "adj_close", "Adj Close", "price", "Price"):
        if column in df.columns:
            series = df[column]
            return series.astype(float)
    if isinstance(df, pd.Series):
        return df.astype(float)
    if df.shape[1] == 1:
        return df.iloc[:, 0].astype(float)
    raise ValueError(f"Could not infer price column from benchmark file: {path}")


def _resolve_strategy(path: str, params: Dict[str, Any]) -> Any:
    module_path, class_name = path.rsplit(":", 1)
    module = import_module(module_path)
    cls = getattr(module, class_name)
    return cls(params or {})


def cmd_run(args: argparse.Namespace) -> None:
    df = _load_csv(args.csv)
    strategy = _resolve_strategy(args.strategy, {})
    bench: Optional[pd.Series] = _load_price_series(args.bench) if args.bench else None
    result = run_backtest(
        df,
        strategy,
        starting_cash=args.cash,
        mode=args.mode,
        size=args.size,
        size_notional=args.size_notional,
        risk_R=args.risk_R,
        atr_len=args.atr_len,
        risk_pct=args.risk_pct,
        commission=args.commission,
        slippage_bps=args.slippage,
    )
    stats = summarize(result.equity_curve, result.fills, result.trade_log, bench=bench)
    for key, value in stats.items():
        if key in {"Sharpe_d", "Sharpe_annualized"}:
            continue
        print(f"{key}: {value}")
    sharpe = stats.get("Sharpe_annualized", stats.get("Sharpe_d", 0.0))
    print(f"Sharpe: {sharpe}")


def cmd_portfolio(args: argparse.Namespace) -> None:
    spec = json.load(open(args.spec, "r"))
    factories: Dict[str, Any] = {}
    for item in spec:
        strategy_path = item["strategy"]
        if strategy_path not in factories:
            module, cls = strategy_path.rsplit(":", 1)
            factories[strategy_path] = getattr(import_module(module), cls)
    curve = run_portfolio(
        spec,
        factories,
        starting_cash=args.cash,
        mode=args.mode,
        size=args.size,
        size_notional=args.size_notional,
        risk_R=args.risk_R,
        atr_len=args.atr_len,
        risk_pct=args.risk_pct,
        commission=args.commission,
        slippage_bps=args.slippage,
    )
    print(f"Start: {curve.iloc[0]:.2f} End: {curve.iloc[-1]:.2f}")
    if args.out_csv:
        curve.to_frame("equity").to_csv(args.out_csv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epl")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a single-strategy backtest")
    run_p.add_argument("--csv", required=True)
    run_p.add_argument(
        "--strategy",
        required=True,
        help="module:Class (e.g. backtest.strategies.flat:Flat)",
    )
    run_p.add_argument("--bench", help="Benchmark CSV (Close column used for metrics)")
    run_p.add_argument("--mode", choices=["delta", "target"], default="target")
    run_p.add_argument("--cash", type=float, default=100_000.0)
    run_p.add_argument("--size", type=int, default=1)
    run_p.add_argument("--size-notional", type=float, dest="size_notional")
    run_p.add_argument("--risk-R", type=float, dest="risk_R")
    run_p.add_argument("--atr-len", type=int, dest="atr_len")
    run_p.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct")
    run_p.add_argument("--commission", type=float, default=0.0)
    run_p.add_argument("--slippage", type=float, default=0.0)
    run_p.set_defaults(func=cmd_run)

    port_p = sub.add_parser("portfolio", help="Aggregate multiple strategies")
    port_p.add_argument(
        "--spec",
        required=True,
        help='JSON array with {"name","csv","strategy","params"}',
    )
    port_p.add_argument("--cash", type=float, default=100_000.0)
    port_p.add_argument("--mode", choices=["delta", "target"], default="target")
    port_p.add_argument("--size", type=int, default=1)
    port_p.add_argument("--size-notional", type=float, dest="size_notional")
    port_p.add_argument("--risk-R", type=float, dest="risk_R")
    port_p.add_argument("--atr-len", type=int, dest="atr_len")
    port_p.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct")
    port_p.add_argument("--commission", type=float, default=0.0)
    port_p.add_argument("--slippage", type=float, default=0.0)
    port_p.add_argument("--out-csv")
    port_p.set_defaults(func=cmd_portfolio)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
