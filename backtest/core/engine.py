"""Event-driven backtesting engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .broker import Broker
from .data import ensure_datetime_index, standardize_columns
from .indicators import atr as compute_atr
from .strategy import BarStrategy


@dataclass
class RunResult:
    """Bundle returned by :func:`run_backtest`."""

    equity_curve: pd.Series
    position_curve: pd.Series
    fills: pd.DataFrame
    trade_log: pd.DataFrame


def _warmup_for_risk_controls(strategy: BarStrategy, atr_len: Optional[int]) -> int:
    warmup = strategy.warmup() if hasattr(strategy, "warmup") else 0
    if atr_len:
        warmup = max(warmup, int(atr_len))
    return int(warmup)


def _resolve_base_size(
    price: float,
    broker: Broker,
    size: Optional[int],
    size_notional: Optional[float],
    risk_R: Optional[float],
    risk_pct: float,
    atr_value: Optional[float],
) -> int:
    base = int(size or 1)
    if size_notional:
        base = max(int(size_notional / price), 0)
    if risk_R and atr_value and atr_value > 0:
        capital_at_risk = broker.equity * float(risk_pct)
        risk_per_unit = atr_value * float(risk_R)
        if risk_per_unit > 0:
            risk_units = int(capital_at_risk / risk_per_unit)
            if risk_units > 0:
                base = risk_units
    return max(base, 0)


def run_backtest(
    data: pd.DataFrame,
    strategy: BarStrategy,
    *,
    starting_cash: float = 100_000.0,
    mode: str = "target",
    size: int = 1,
    size_notional: Optional[float] = None,
    risk_R: Optional[float] = None,
    atr_len: Optional[int] = None,
    risk_pct: float = 0.01,
    commission: float = 0.0,
    slippage_bps: float = 0.0,
) -> RunResult:
    """Run a bar-by-bar backtest.

    Parameters mirror the knobs exposed by the CLI. ``mode`` dictates how the
    strategy output is interpreted:

    - ``"delta"`` → treat return values as delta adjustments
    - ``"target"`` → treat return values as target positions
    """

    if mode not in {"delta", "target"}:
        raise ValueError(f"Unsupported mode: {mode}")

    frame = ensure_datetime_index(data.copy())
    frame = standardize_columns(frame)
    if "close" not in frame.columns:
        raise ValueError("Input data must contain a 'close' column")

    strategy.bind(frame)
    warmup = _warmup_for_risk_controls(strategy, atr_len)

    if atr_len and {"high", "low", "close"}.issubset(frame.columns):
        frame["_atr"] = compute_atr(frame["high"], frame["low"], frame["close"], length=int(atr_len))
    else:
        frame["_atr"] = np.nan

    broker = Broker(starting_cash=starting_cash, commission=commission, slippage_bps=slippage_bps)

    equity_curve: list[float] = []
    positions: list[float] = []
    index: list[pd.Timestamp] = []
    closed_trades_seen: set[int] = set()

    def _notify_trade_closures() -> None:
        if not hasattr(strategy, "on_trade_closed"):
            return
        for trade in broker.trade_log:
            if trade.exit_time is None:
                continue
            trade_id = id(trade)
            if trade_id in closed_trades_seen:
                continue
            pnl_value = float(trade.pnl) if trade.pnl is not None else 0.0
            try:
                strategy.on_trade_closed(pnl_value)
            except Exception:
                pass
            closed_trades_seen.add(trade_id)

    for i, (ts, row) in enumerate(frame.iterrows()):
        price = float(row["close"])
        broker.update_market(ts, price)

        atr_value = row.get("_atr", np.nan)
        dyn_risk_pct = None
        if hasattr(strategy, "get_effective_risk"):
            try:
                dyn_risk_pct = max(0.0, float(strategy.get_effective_risk()) / 100.0)
            except Exception:
                dyn_risk_pct = None
        effective_risk_pct = dyn_risk_pct if dyn_risk_pct is not None else risk_pct
        base_size = _resolve_base_size(
            price,
            broker,
            size=size,
            size_notional=size_notional,
            risk_R=risk_R,
            risk_pct=effective_risk_pct,
            atr_value=float(atr_value) if not np.isnan(atr_value) else None,
        )

        if i >= warmup:
            signal = strategy.on_bar(ts, row, i, broker)
            signal = 0 if signal is None else signal

            if mode == "delta":
                qty = int(round(signal)) * base_size
                if qty:
                    broker.order_delta(qty, price, ts)
            else:  # mode == "target"
                target = int(round(signal)) * base_size
                broker.order_target(target, price, ts)

            _notify_trade_closures()

        equity_curve.append(broker.equity)
        positions.append(broker.position)
        index.append(ts)

    equity_series = pd.Series(equity_curve, index=index, name="equity")
    position_series = pd.Series(positions, index=index, name="position")

    fills = pd.DataFrame(broker.fills)
    if not fills.empty:
        fills["timestamp"] = pd.to_datetime(fills["timestamp"])
        fills = fills.set_index("timestamp").sort_index()

    trades = pd.DataFrame(broker.export_trades())
    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])
        trades = trades.sort_values("exit_time").reset_index(drop=True)

    return RunResult(
        equity_curve=equity_series,
        position_curve=position_series,
        fills=fills,
        trade_log=trades,
    )
