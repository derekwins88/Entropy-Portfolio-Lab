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
from .walkforward import anchored_walk_forward, parse_grid_spec
from . import report as wf_report


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


def _load_json_payload(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        candidate = Path(value)
        if candidate.exists():
            return json.loads(candidate.read_text())
    except OSError:
        pass
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse params JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Parameters JSON must decode to a dictionary")
    return data


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


def cmd_walk(args: argparse.Namespace) -> None:
    df = _load_csv(args.csv)
    bench = _load_price_series(args.bench) if args.bench else None

    module_path, class_name = args.strategy.rsplit(":", 1)
    module = import_module(module_path)
    Strat = getattr(module, class_name)

    base_params = _load_json_payload(args.params)
    grid = parse_grid_spec(args.grid)
    param_sets = [
        {**base_params, **params} if base_params else dict(params)
        for params in grid
    ]

    def factory(params: Dict[str, Any]) -> Any:
        combined = dict(base_params)
        combined.update(params)
        return Strat(combined)

    results = anchored_walk_forward(
        df,
        factory,
        param_sets,
        selection_metric=args.select,
        min_train=args.min_train,
        test_window=args.test_window,
        starting_cash=args.cash,
        mode=args.mode,
        size=args.size,
        size_notional=args.size_notional,
        risk_R=args.risk_R,
        atr_len=args.atr_len,
        risk_pct=args.risk_pct,
        commission=args.commission,
        slippage_bps=args.slippage,
        bench=bench,
    )

    if not results:
        print("No walk-forward splits produced output")
        return

    table = wf_report.walkforward_table(results)
    wf_report.print_table(table)
    if args.out_csv:
        wf_report.save_table(table, args.out_csv)
    if args.plot is not None:
        plot_path = args.plot if isinstance(args.plot, str) else "wf_equity.png"
        wf_report.plot_walkforward(results, plot_path)


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

    walk_p = sub.add_parser("walk", help="Anchored walk-forward evaluation")
    walk_p.add_argument("--csv", required=True)
    walk_p.add_argument(
        "--strategy",
        required=True,
        help="module:Class (e.g. backtest.strategies.rsi_ema:RSIEmaMeanRevert)",
    )
    walk_p.add_argument("--grid", nargs="+", help="Parameter grid spec e.g. k=10,20 m=2,5")
    walk_p.add_argument("--params", help="JSON file or string with base parameters")
    walk_p.add_argument("--bench", help="Benchmark CSV (Close column used for metrics)")
    walk_p.add_argument("--select", default="Sharpe_annualized", help="In-sample metric for selection")
    walk_p.add_argument("--min-train", type=int, default=504, dest="min_train")
    walk_p.add_argument("--test-window", type=int, default=252, dest="test_window")
    walk_p.add_argument("--mode", choices=["delta", "target"], default="target")
    walk_p.add_argument("--cash", type=float, default=100_000.0)
    walk_p.add_argument("--size", type=int, default=1)
    walk_p.add_argument("--size-notional", type=float, dest="size_notional")
    walk_p.add_argument("--risk-R", type=float, dest="risk_R")
    walk_p.add_argument("--atr-len", type=int, dest="atr_len")
    walk_p.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct")
    walk_p.add_argument("--commission", type=float, default=0.0)
    walk_p.add_argument("--slippage", type=float, default=0.0)
    walk_p.add_argument("--out-csv")
    walk_p.add_argument("--plot", nargs="?", const="wf_equity.png")
    walk_p.set_defaults(func=cmd_walk)

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
