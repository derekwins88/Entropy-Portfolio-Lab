"""Execution simulator used by the backtesting engine."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class Fill:
    """A single execution event."""

    timestamp: pd.Timestamp
    price: float
    quantity: float
    commission: float
    cash: float
    position: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Trade:
    """Represents a position entry with optional exit information."""

    entry_time: pd.Timestamp
    quantity: float
    entry_price: float
    direction: str
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    return_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "direction": self.direction,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
        }


class Broker:
    """Simple cash equities broker.

    The broker keeps track of positions, cash, and fills. It assumes that
    signals are filled at the close of the bar they were generated on, adjusted
    by optional slippage and commission controls.
    """

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        commission: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        self.starting_cash = float(starting_cash)
        self.commission = float(commission)
        self.slippage_bps = float(slippage_bps)

        self.cash = float(starting_cash)
        self.position = 0.0
        self.avg_price = 0.0
        self.last_price: Optional[float] = None
        self.equity = float(starting_cash)

        self.fills: List[Dict[str, Any]] = []
        self.trade_log: List[Trade] = []
        self._open_trade: Optional[Trade] = None

    # ------------------------------------------------------------------
    # Market data plumbing
    # ------------------------------------------------------------------
    def update_market(self, timestamp: pd.Timestamp, price: float) -> None:
        self.last_price = float(price)
        self.equity = self.cash + self.position * self.last_price

    # ------------------------------------------------------------------
    # Order routing helpers
    # ------------------------------------------------------------------
    def order_delta(self, quantity_delta: float, price: float, timestamp: pd.Timestamp) -> None:
        if quantity_delta:
            self._execute(quantity_delta, price, timestamp)

    def order_target(self, target_position: float, price: float, timestamp: pd.Timestamp) -> None:
        delta = target_position - self.position
        if delta:
            self._execute(delta, price, timestamp)

    # ------------------------------------------------------------------
    # Internal bookkeeping
    # ------------------------------------------------------------------
    def _execute(self, quantity: float, price: float, timestamp: pd.Timestamp) -> None:
        if quantity == 0:
            return

        direction = 1.0 if quantity > 0 else -1.0
        slip = price * self.slippage_bps / 10_000.0
        fill_price = float(price + slip * direction)
        commission = self.commission

        # Cash accounting (buying reduces cash; selling adds to cash)
        self.cash -= fill_price * quantity
        if commission:
            self.cash -= commission

        old_position = self.position
        new_position = old_position + quantity

        # Record the fill before changing internal state to make debugging easier
        self.fills.append(
            Fill(
                timestamp=timestamp,
                price=fill_price,
                quantity=quantity,
                commission=commission,
                cash=self.cash,
                position=new_position,
            ).to_dict()
        )

        if old_position == 0 or old_position * quantity > 0:
            self._handle_opening(new_position, fill_price, timestamp)
        else:
            self._handle_closing(quantity, fill_price, timestamp, old_position, new_position)

        self.position = new_position
        self.last_price = fill_price
        self.equity = self.cash + self.position * self.last_price

        if self.position == 0:
            self.avg_price = 0.0

    def _handle_opening(self, new_position: float, fill_price: float, timestamp: pd.Timestamp) -> None:
        if self.position == 0:
            self.avg_price = fill_price
            direction = "long" if new_position > 0 else "short"
            trade = Trade(
                entry_time=timestamp,
                quantity=new_position,
                entry_price=self.avg_price,
                direction=direction,
            )
            self.trade_log.append(trade)
            self._open_trade = trade
        else:
            total_qty = abs(self.position) + abs(new_position - self.position)
            if total_qty:
                self.avg_price = (
                    self.avg_price * abs(self.position) + fill_price * abs(new_position - self.position)
                ) / total_qty
            if self._open_trade:
                self._open_trade.quantity = new_position
                self._open_trade.entry_price = self.avg_price

    def _handle_closing(
        self,
        quantity: float,
        fill_price: float,
        timestamp: pd.Timestamp,
        old_position: float,
        new_position: float,
    ) -> None:
        direction = "long" if old_position > 0 else "short"
        closed_qty = min(abs(quantity), abs(old_position))
        pnl = (
            (fill_price - self.avg_price) * closed_qty
            if direction == "long"
            else (self.avg_price - fill_price) * closed_qty
        )

        if abs(quantity) >= abs(old_position) and self._open_trade is not None:
            trade = self._open_trade
            qty = abs(old_position)
            basis = trade.entry_price * qty
            trade.exit_time = timestamp
            trade.exit_price = fill_price
            trade.pnl = pnl
            trade.return_pct = pnl / basis if basis else 0.0
            trade.quantity = 0.0
            self._open_trade = None
            self.avg_price = 0.0
        else:
            # Partial close keeps the trade open
            if self._open_trade is not None:
                remaining = old_position + quantity
                self._open_trade.quantity = remaining

        # If we reversed, seed a new trade for the residual exposure
        if new_position != 0 and (old_position == 0 or old_position * new_position < 0):
            self.avg_price = fill_price
            direction = "long" if new_position > 0 else "short"
            trade = Trade(
                entry_time=timestamp,
                quantity=new_position,
                entry_price=self.avg_price,
                direction=direction,
            )
            self.trade_log.append(trade)
            self._open_trade = trade

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def export_trades(self) -> List[Dict[str, Any]]:
        return [trade.to_dict() for trade in self.trade_log]
