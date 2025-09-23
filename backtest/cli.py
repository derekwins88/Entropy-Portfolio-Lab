"""Command line interface for the backtest package."""
from __future__ import annotations

import argparse
import json
import os
import random
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd

from . import report as wf_report
from .report import daily_equity_report
from .core.engine import run_backtest
from .core.metrics import summarize
from .portfolio import run_portfolio
from .walkforward import anchored_walk_forward, parse_grid_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def set_seed(seed: Optional[int]) -> None:
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

def _load_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(p, parse_dates=[0], index_col=0)


def _load_benchmark_series(path: str) -> pd.Series:
    df = _load_csv(path)
    bcols = {col.lower(): col for col in df.columns}
    numeric = df.select_dtypes("number")
    column = (
        bcols.get("adj close")
        or bcols.get("close")
        or (numeric.columns.tolist()[-1] if not numeric.empty else None)
    )
    if column is None:
        raise ValueError(f"Could not infer benchmark column from: {path}")
    series = df[column].astype(float).rename("bench")
    series.index = pd.to_datetime(series.index)
    return series.sort_index()


def _load_strategy_class(path: str):
    module_path, class_name = path.rsplit(":", 1)
    module = import_module(module_path)
    return getattr(module, class_name)


def _resolve_strategy(path: str, params: Dict[str, Any]) -> Any:
    cls = _load_strategy_class(path)
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


def _coerce_grid_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"none", "null"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if raw.startswith("0") and raw not in {"0", "0.0"} and not raw.startswith("0."):
            raise ValueError
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def _parse_simple_grid(tokens: Optional[Sequence[str]]) -> Dict[str, Sequence[Any]]:
    if not tokens:
        return {}
    grid: Dict[str, list[Any]] = {}
    for token in tokens:
        if "=" not in token:
            raise ValueError(f"Malformed grid token: {token}")
        name, raw_values = token.split("=", 1)
        values = [_coerce_grid_value(v.strip()) for v in raw_values.split(",") if v.strip()]
        if not values:
            raise ValueError(f"No values supplied for grid parameter '{name}'")
        grid[name] = values
    return grid


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    df = _load_csv(args.csv)
    strategy = _resolve_strategy(args.strategy, {})
    bench: Optional[pd.Series] = _load_benchmark_series(args.bench) if args.bench else None
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

    if args.out_daily:
        daily_equity_report(result.equity_curve).to_csv(args.out_daily)


def cmd_portfolio(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    spec = json.load(open(args.spec, "r"))
    factories: Dict[str, Any] = {}
    for item in spec:
        strategy_path = item["strategy"]
        if strategy_path not in factories:
            factories[strategy_path] = _load_strategy_class(strategy_path)
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
    skipped = curve.attrs.get("skipped", [])
    if skipped:
        print(
            "Skipped {} dataset(s) due to invalid data: {}".format(
                len(skipped), ", ".join(skipped)
            )
        )
    if curve.empty:
        print("No valid equity curves produced")
    else:
        print(f"Start: {curve.iloc[0]:.2f} End: {curve.iloc[-1]:.2f}")
        if args.out_daily:
            daily_equity_report(curve).to_csv(args.out_daily)
        if args.out_csv:
            curve.to_frame("equity").to_csv(args.out_csv)
    if args.out_csv and curve.empty:
        pd.DataFrame(columns=["equity"]).to_csv(args.out_csv)


def cmd_walk(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    df = _load_csv(args.csv)

    bench_series: Optional[pd.Series] = (
        _load_benchmark_series(args.bench) if args.bench else None
    )

    use_optimize = any(
        value is not None
        for value in (args.train_years, args.test_years, args.step_years)
    )
    if use_optimize:
        from .optimize import log_results, walk_forward

        grid = _parse_simple_grid(args.grid)
        if not grid:
            raise ValueError("Parameter grid is required for walk-forward optimization")
        base_params = _load_json_payload(args.params)
        Strat = _load_strategy_class(args.strategy)

        def factory(overrides: Dict[str, Any]) -> Any:
            params = dict(base_params)
            params.update(overrides)
            return Strat(params)

        run_kwargs = dict(
            mode=args.mode,
            size=args.size,
            size_notional=args.size_notional,
            risk_R=args.risk_R,
            atr_len=args.atr_len,
            risk_pct=args.risk_pct,
            commission=args.commission,
            slippage_bps=args.slippage,
        )
        results = walk_forward(
            df,
            factory,
            grid,
            train_years=args.train_years or 2,
            test_years=args.test_years or 1,
            step_years=args.step_years or 1,
            run_kwargs=run_kwargs,
            score_key=args.score,
            bench=bench_series,
        )
        log_results(results, args.out_csv, args.out_json)
        if results.empty:
            print("No walk-forward splits produced output")
            return
        with pd.option_context("display.max_rows", None, "display.width", None):
            print(results.to_string(index=False))
        return

    Strat = _load_strategy_class(args.strategy)
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
        bench=bench_series,
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


def cmd_opt(args: argparse.Namespace) -> None:
    from .optimize import grid_search, log_results

    set_seed(args.seed)
    df = _load_csv(args.csv)
    grid = _parse_simple_grid(args.grid)
    base_params = _load_json_payload(args.params)
    Strat = _load_strategy_class(args.strategy)
    bench_series: Optional[pd.Series] = (
        _load_benchmark_series(args.bench) if args.bench else None
    )

    def factory(overrides: Dict[str, Any]) -> Any:
        params = dict(base_params)
        params.update(overrides)
        return Strat(params)

    run_kwargs = dict(
        mode=args.mode,
        size=args.size,
        size_notional=args.size_notional,
        risk_R=args.risk_R,
        atr_len=args.atr_len,
        risk_pct=args.risk_pct,
        commission=args.commission,
        slippage_bps=args.slippage,
    )

    results = grid_search(
        df,
        factory,
        grid,
        run_kwargs=run_kwargs,
        score_key=args.score,
        bench=bench_series,
    )
    log_results(results, args.out_csv, args.out_json)
    if results.empty:
        print("Grid search produced no results")
        return
    top = results.head(args.top)
    with pd.option_context("display.max_rows", None, "display.width", None):
        print(top.to_string(index=False))


def cmd_attr(args: argparse.Namespace) -> None:
    from .attribution import (
        attribute_returns,
        percent_contributions,
        pivot_attribution,
        summarize_attribution,
        plot_attribution,
    )

    trades = pd.read_csv(args.trades).to_dict(orient="records")
    regimes = None
    if args.regimes:
        regime_df = pd.read_csv(args.regimes, parse_dates=[0], index_col=0)
        regimes = regime_df.iloc[:, 0]
    df = attribute_returns(
        trades,
        regimes=regimes,
        asset_key=args.asset_key,
        exit_time_key=args.exit_key,
        pnl_key=args.pnl_key,
    )
    summary = summarize_attribution(df)
    print("Summary:", summary)
    if df.empty:
        return
    print("\nPivot (PnL):\n", pivot_attribution(df))
    print("\nPercent (%):\n", percent_contributions(df))

    if args.plot is not None:
        ax = plot_attribution(df)
        fig = ax.figure
        plot_path = args.plot or "attribution.png"
        fig.tight_layout()
        fig.savefig(plot_path, dpi=150)
        try:
            import matplotlib.pyplot as plt

            plt.close(fig)
        except ImportError:
            pass
        print(f"Saved attribution plot to {plot_path}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

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
    run_p.add_argument("--bench", help="Benchmark CSV (Date,Close/Adj Close)")
    run_p.add_argument("--mode", choices=["delta", "target"], default="target")
    run_p.add_argument("--cash", type=float, default=100_000.0)
    run_p.add_argument("--size", type=int, default=1)
    run_p.add_argument("--size-notional", type=float, dest="size_notional")
    run_p.add_argument("--risk-R", type=float, dest="risk_R")
    run_p.add_argument("--atr-len", type=int, dest="atr_len")
    run_p.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct")
    run_p.add_argument("--commission", type=float, default=0.0)
    run_p.add_argument("--slippage", type=float, default=0.0)
    run_p.add_argument("--out-daily", dest="out_daily", help="Write daily equity CSV")
    run_p.add_argument("--seed", type=int, help="Seed random number generators")
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
    port_p.add_argument("--out-daily", dest="out_daily", help="Write daily equity CSV")
    port_p.add_argument("--seed", type=int, help="Seed random number generators")
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
    walk_p.add_argument("--bench", help="Benchmark CSV (Date,Close/Adj Close)")
    walk_p.add_argument("--select", default="Sharpe_annualized", help="In-sample metric for selection")
    walk_p.add_argument("--min-train", type=int, default=504, dest="min_train")
    walk_p.add_argument("--test-window", type=int, default=252, dest="test_window")
    walk_p.add_argument("--train-years", type=int, dest="train_years")
    walk_p.add_argument("--test-years", type=int, dest="test_years")
    walk_p.add_argument("--step-years", type=int, dest="step_years")
    walk_p.add_argument("--score", default="Sharpe_annualized")
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
    walk_p.add_argument("--out-json")
    walk_p.add_argument("--plot", nargs="?", const="wf_equity.png")
    walk_p.add_argument("--seed", type=int, help="Seed random number generators")
    walk_p.set_defaults(func=cmd_walk)

    opt_p = sub.add_parser("opt", help="Parameter grid search")
    opt_p.add_argument("--csv", required=True)
    opt_p.add_argument(
        "--strategy",
        required=True,
        help="module:Class (e.g. backtest.strategies.flat:Flat)",
    )
    opt_p.add_argument("--grid", nargs="+", required=True, help="param=v1,v2 ...")
    opt_p.add_argument("--params", help="JSON file or string with base parameters")
    opt_p.add_argument("--mode", choices=["delta", "target"], default="target")
    opt_p.add_argument("--size", type=int, default=1)
    opt_p.add_argument("--size-notional", type=float, dest="size_notional")
    opt_p.add_argument("--risk-R", type=float, dest="risk_R")
    opt_p.add_argument("--atr-len", type=int, dest="atr_len")
    opt_p.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct")
    opt_p.add_argument("--commission", type=float, default=0.0)
    opt_p.add_argument("--slippage", type=float, default=0.0)
    opt_p.add_argument("--score", default="Sharpe_annualized")
    opt_p.add_argument("--top", type=int, default=20, help="Rows to display")
    opt_p.add_argument("--out-csv")
    opt_p.add_argument("--out-json")
    opt_p.add_argument("--bench", help="Benchmark CSV (Date,Close/Adj Close)")
    opt_p.add_argument("--seed", type=int, help="Seed random number generators")
    opt_p.set_defaults(func=cmd_opt)

    attr_p = sub.add_parser("attr", help="Performance attribution from trades.csv")
    attr_p.add_argument("--trades", required=True)
    attr_p.add_argument("--regimes", help="CSV with Date + Regime column")
    attr_p.add_argument("--asset-key", default="asset", dest="asset_key")
    attr_p.add_argument("--exit-key", default="exit_time", dest="exit_key")
    attr_p.add_argument("--pnl-key", default="pnl", dest="pnl_key")
    attr_p.add_argument(
        "--plot",
        nargs="?",
        const="attribution.png",
        help="Render stacked bar plot to optional path (default: attribution.png)",
    )
    attr_p.set_defaults(func=cmd_attr)

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
