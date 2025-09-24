"""Backtesting engines for CLI convenience."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["run_backtest"]


def __getattr__(name: str) -> Any:  # pragma: no cover - import side-effect glue
    if name == "run_backtest":
        module = import_module("backtest.engines.multi_asset_backtest")
        return getattr(module, "run_backtest")
    raise AttributeError(name)
