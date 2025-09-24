import json
from pathlib import Path
from typing import Callable, Dict, Iterable

import click
import pandas as pd

from backtest.walkforward import walk_forward as walk_forward_report
from backtest.strategies import flat_factory, rsi_ema_factory, sma_factory
from engines.multi_asset_backtest import run_backtest
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
    run_backtest(**kw)


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


@cli.command("wf")
@click.option("--csv", "csv_path", required=True, help="Path to input CSV")
@click.option("--strategy", required=True, help="Strategy name (e.g., sma_cross)")
@click.option("--params", default="{}", help="JSON dictionary of strategy parameters")
@click.option("--train-years", type=float, default=2.0)
@click.option("--test-months", type=float, default=3.0)
@click.option("--step-months", type=float, default=3.0)
@click.option("--seed", type=int, default=42)
@click.option("--out-json", default="wf_report.json")
def wf_cmd(csv_path, strategy, params, train_years, test_months, step_months, seed, out_json):
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
    )

    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    click.echo(f"[wf] wrote {out_path} with {report['fold_count']} folds")


if __name__ == "__main__":
    cli()
