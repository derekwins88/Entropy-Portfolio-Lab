import click
from engines.multi_asset_backtest import run_backtest
from engines.optimize import grid_search, walk_forward


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
    walk_forward(**kw)


if __name__ == "__main__":
    cli()
