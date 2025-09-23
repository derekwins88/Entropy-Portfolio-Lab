"""Bracket order helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BracketOrder:
    """Simple bracket order representation.

    Parameters represent offsets relative to the entry price. They can be
    absolute points (``stop_offset`` / ``target_offset``) or percentage moves
    (``stop_pct`` / ``target_pct``). A trailing stop can be expressed in
    percentage terms relative to the most favourable move.
    """

    stop_pct: Optional[float] = None
    stop_offset: Optional[float] = None
    target_pct: Optional[float] = None
    target_offset: Optional[float] = None
    trailing_pct: Optional[float] = None

    def initial_levels(self, side: int, entry_price: float) -> "BracketState":
        stop = None
        target = None

        if self.stop_pct is not None:
            stop = entry_price * (1.0 - self.stop_pct * side)
        elif self.stop_offset is not None:
            stop = entry_price - self.stop_offset * side

        if self.target_pct is not None:
            target = entry_price * (1.0 + self.target_pct * side)
        elif self.target_offset is not None:
            target = entry_price + self.target_offset * side

        return BracketState(side=side, stop=stop, target=target, trailing_pct=self.trailing_pct, extreme=entry_price)


@dataclass
class BracketState:
    side: int
    stop: Optional[float]
    target: Optional[float]
    trailing_pct: Optional[float]
    extreme: float

    def update(self, bar: pd.Series) -> Optional[str]:
        """Return "stop" or "target" when an exit is triggered."""

        high = float(bar.get("high", bar.get("close")))
        low = float(bar.get("low", bar.get("close")))

        if self.side > 0:
            self.extreme = max(self.extreme, high)
            if self.trailing_pct:
                trail_level = self.extreme * (1.0 - self.trailing_pct)
                if self.stop is None or trail_level > self.stop:
                    self.stop = trail_level
            if self.stop is not None and low <= self.stop:
                return "stop"
            if self.target is not None and high >= self.target:
                return "target"
        else:
            self.extreme = min(self.extreme, low)
            if self.trailing_pct:
                trail_level = self.extreme * (1.0 + self.trailing_pct)
                if self.stop is None or trail_level < self.stop:
                    self.stop = trail_level
            if self.stop is not None and high >= self.stop:
                return "stop"
            if self.target is not None and low <= self.target:
                return "target"
        return None
