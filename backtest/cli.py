import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import click
import pandas as pd

from backtest.walkforward import (
    walk_forward as walk_forward_report,
    walk_forward_opt as walk_forward_opt_report,
)
from backtest.strategies import (
    flat_factory,
    praetorian_factory,
    rsi_ema_factory,
    sma_factory,
    trinity_factory,
)
from backtest.walk_forward import run_wf_from_cli
from backtest.core.engine import run_backtest as engine_run_backtest
from engines.multi_asset_backtest import run_backtest as cli_run_backtest
from engines.optimize import grid_search, walk_forward as anchored_walk_forward


@click.group()
def cli():
    ...


@cli.command("run")
@click.option("--strategy", default="sma_cross")
@click.option("--csv", "csv_path", default="data/sample_multi_asset_data.csv")
@click.option("--out-csv", default="equity.csv")
@click.option("--trades-csv", default=None)
@click.option("--plot", is_flag=True)
@click.option("--seed", type=int, default=None, help="Deterministic seed")
def run_cmd(**kw):
    cli_run_backtest(**kw)


@cli.command("metrics")
@click.option("--csv", "csv_path", required=True)
def metrics_cmd(csv_path: str) -> None:
    """Compute ADR and Sharpe for a CSV equity or returns series."""

    import numpy as np

    df = pd.read_csv(csv_path)
    if df.empty:
        raise click.ClickException(f"CSV is empty: {csv_path}")

    if "equity" in df.columns:
        series = pd.Series(df["equity"], dtype=float)
    else:
        series = df.iloc[:, -1].astype(float)

    returns = series.pct_change().dropna()
    if returns.empty:
        click.echo("ADR: 0.000%/day  Sharpe: 0.00  N=0")
        return

    mean = float(returns.mean())
    std = float(returns.std(ddof=0))
    sharpe = (mean / std * np.sqrt(252.0)) if std > 0 else 0.0
    adr = mean * 100.0
    click.echo(f"ADR: {adr:.3f}%/day  Sharpe: {sharpe:.2f}  N={len(returns)}")


@cli.command("optimize")
@click.option("--strategy", default="sma_cross")
@click.option("--csv", "csv_path", required=True)
@click.option("--params", multiple=True)  # e.g. fast=5,10,20 slow=40,80,120
@click.option("--out-csv", default="grid.csv")
def opt_cmd(**kw):
    grid_search(**kw)


@cli.command("walk")
@click.option("--strategy", default="rsi_ema_mean_revert")
@click.option("--csv", "csv_path", required=True)
@click.option("--grid", required=True)
@click.option("--out-csv", default="wf.csv")
def walk_cmd(**kw):
    anchored_walk_forward(**kw)


def _resolve_strategy_factory(name: str) -> Callable[[Dict[str, object]], object]:
    mapping = {
        "flat": flat_factory,
        "sma_cross": sma_factory,
        "sma": sma_factory,
        "rsi_ema": rsi_ema_factory,
        "rsi_ema_mean_revert": rsi_ema_factory,
        "trinity": trinity_factory,
        "praetorian": praetorian_factory,
    }
    key = name.replace("-", "_").lower()
    if key not in mapping:
        raise click.ClickException(f"Unknown strategy: {name}")
    return mapping[key]


def _parse_params(raw: str) -> Dict[str, object]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"Invalid JSON for --params: {exc}") from exc
    if not isinstance(parsed, dict):
        raise click.ClickException("--params must decode to a JSON object")
    return parsed


def _coerce_grid_value(value: object) -> object:
    if isinstance(value, str):
        raw = value.strip()
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
    return value


def _parse_grid(raw: str) -> Dict[str, List[object]]:
    text = (raw or "").strip()
    if not text:
        return {}

    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise click.ClickException(f"Invalid JSON for --grid: {exc}") from exc
        if not isinstance(parsed, dict):
            raise click.ClickException("--grid JSON must decode to an object")
        result: Dict[str, List[object]] = {}
        for key, values in parsed.items():
            if isinstance(values, list):
                choices = values
            else:
                choices = [values]
            if not choices:
                raise click.ClickException(
                    f"No values supplied for grid parameter '{key}'"
                )
            result[str(key)] = [_coerce_grid_value(choice) for choice in choices]
        return result

    tokens = text.split()
    if not tokens:
        return {}

    grid: Dict[str, List[object]] = {}
    for token in tokens:
        if "=" not in token:
            raise click.ClickException(f"Malformed grid token: {token}")
        name, raw_values = token.split("=", 1)
        values = [segment.strip() for segment in raw_values.split(",") if segment.strip()]
        if not values:
            raise click.ClickException(f"No values supplied for grid parameter '{name}'")
        grid[name.strip()] = [_coerce_grid_value(value) for value in values]
    return grid


def _load_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise click.ClickException(f"CSV not found: {csv_path}")
    return pd.read_csv(csv_path)


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    lower_map = {col: col.lower() for col in df.columns}
    if "close" not in lower_map.values():
        close_candidates: Iterable[str] = [
            col for col in df.columns if col.lower().endswith("_close")
        ]
        if close_candidates:
            df["close"] = df[close_candidates].astype(float).mean(axis=1)
    else:
        for column, lowered in lower_map.items():
            if lowered == "close" and column != "close":
                df = df.rename(columns={column: "close"})
                break
    return df


@cli.command("wf-json")
@click.option("--csv", "csv_path", required=True, help="Path to input CSV")
@click.option("--strategy", required=True, help="Strategy name (e.g., sma_cross)")
@click.option("--params", default="{}", help="JSON dictionary of strategy parameters")
@click.option("--train-years", type=float, default=2.0)
@click.option("--test-months", type=float, default=3.0)
@click.option("--step-months", type=float, default=3.0)
@click.option("--mode", type=click.Choice(["target", "delta"]), default="target")
@click.option("--seed", type=int, default=42)
@click.option("--out-json", default="wf_report.json")
def wf_json_cmd(
    csv_path,
    strategy,
    params,
    train_years,
    test_months,
    step_months,
    mode,
    seed,
    out_json,
):
    frame = _prepare_frame(_load_csv(csv_path))
    factory = _resolve_strategy_factory(strategy)
    params_dict = _parse_params(params)

    report = walk_forward_report(
        frame,
        make_strategy=factory,
        params=params_dict,
        train_years=train_years,
        test_months=test_months,
        step_months=step_months,
        seed=seed,
        run_kwargs={"mode": mode},
    )

    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    click.echo(f"[wf] wrote {out_path} with {report['fold_count']} folds")


@cli.command("wf-opt")
@click.option("--csv", "csv_path", required=True, help="Path to input CSV")
@click.option("--strategy", required=True, help="Strategy name (e.g., trinity)")
@click.option(
    "--grid",
    required=True,
    help="Parameter grid as JSON or CLI spec (e.g. fast=10,20 slow=40,60)",
)
@click.option("--metric-key", default="Sharpe_annualized", show_default=True)
@click.option("--train-years", type=float, default=2.0)
@click.option("--test-months", type=float, default=6.0)
@click.option("--step-months", type=float, default=6.0)
@click.option("--mode", type=click.Choice(["target", "delta"]), default="target")
@click.option("--seed", type=int, default=42)
@click.option("--out-json", default="wf_opt_report.json")
def wf_opt_cmd(
    csv_path,
    strategy,
    grid,
    metric_key,
    train_years,
    test_months,
    step_months,
    mode,
    seed,
    out_json,
):
    frame = _prepare_frame(_load_csv(csv_path))
    factory = _resolve_strategy_factory(strategy)
    grid_spec = _parse_grid(grid)
    if not grid_spec:
        raise click.ClickException("--grid specification is empty")

    report = walk_forward_opt_report(
        frame,
        make_strategy=factory,
        param_grid=grid_spec,
        metric_key=metric_key,
        train_years=train_years,
        test_months=test_months,
        step_months=step_months,
        seed=seed,
        run_kwargs={"mode": mode},
    )

    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    click.echo(f"[wf-opt] wrote {out_path} with {report['fold_count']} folds")


@cli.command("wf")
@click.option("--strategy", default="trinity", type=click.Choice(["trinity", "praetorian"]))
@click.option("--csv", "csv_path", required=True)
@click.option("--grid", required=True, help="param grid: k=v1,v2 ...")
@click.option("--mode", default="target", type=click.Choice(["target", "delta"]))
@click.option("--train-days", default=500, type=int)
@click.option("--test-days", default=125, type=int)
@click.option("--out-csv", default="artifacts/wf_oos_returns.csv")
def wf_cmd(strategy, csv_path, grid, mode, train_days, test_days, out_csv):
    """Anchored walk-forward sweep that logs out-of-sample returns."""

    import os

    os.makedirs(Path(out_csv).parent, exist_ok=True)
    key = strategy.replace("-", "_").lower()
    strat_factory = trinity_factory if key == "trinity" else praetorian_factory

    run_wf_from_cli(
        csv_path=csv_path,
        grid=grid,
        StrategyFactory=strat_factory,
        run_backtest=engine_run_backtest,
        mode=mode,
        train_days=train_days,
        test_days=test_days,
        out_csv=out_csv,
        sizing_kwargs={"size_notional": 10_000},
    )


if __name__ == "__main__":
    cli()
