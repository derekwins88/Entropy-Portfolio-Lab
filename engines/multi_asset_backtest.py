"""Re-export multi-asset backtest helpers."""

from backtest.engines.multi_asset_backtest import legacy_run_backtest

run_backtest = legacy_run_backtest

__all__ = ["run_backtest"]
