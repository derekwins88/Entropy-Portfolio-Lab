"""RSI/EMA mean reversion strategy with bracket exits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd

from ..core.brackets import BracketOrder, BracketState
from ..core.indicators import ema, rsi
from ..core.strategy import BarStrategy

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from ..core.broker import Broker


@dataclass
class Params:
    rsi_length: int = 14
    ema_length: int = 50
    lower: float = 35.0
    upper: float = 65.0
    stop_pct: float = 0.01
    target_pct: float = 0.02
    trailing_pct: Optional[float] = None

    @classmethod
    def from_dict(cls, params: Optional[Dict[str, float]]) -> "Params":
        base = cls()
        if not params:
            return base
        data = {
            "rsi_length": base.rsi_length,
            "ema_length": base.ema_length,
            "lower": base.lower,
            "upper": base.upper,
            "stop_pct": base.stop_pct,
            "target_pct": base.target_pct,
            "trailing_pct": base.trailing_pct,
        }
        for key in data:
            if key in params and params[key] is not None:
                value = params[key]
                if key in {"rsi_length", "ema_length"}:
                    data[key] = int(value)
                elif key == "trailing_pct":
                    data[key] = float(value)
                else:
                    data[key] = float(value)
        return cls(**data)


class RSIEmaMeanRevert(BarStrategy):
    """Fade RSI extremes back toward the EMA using bracket exits."""

    def __init__(self, params: Optional[Dict[str, float]] = None) -> None:
        super().__init__(params)
        self.config = Params.from_dict(params)
        if self.config.rsi_length <= 0 or self.config.ema_length <= 0:
            raise ValueError("Indicator lengths must be positive integers")

        stop_pct = (
            self.config.stop_pct
            if self.config.stop_pct and self.config.stop_pct > 0
            else None
        )
        target_pct = (
            self.config.target_pct
            if self.config.target_pct and self.config.target_pct > 0
            else None
        )
        trailing_pct = (
            self.config.trailing_pct
            if self.config.trailing_pct and self.config.trailing_pct > 0
            else None
        )

        self._bracket_template = BracketOrder(
            stop_pct=stop_pct,
            target_pct=target_pct,
            trailing_pct=trailing_pct,
        )
        self._bracket_state: Optional[BracketState] = None
        self._ema: Optional[pd.Series] = None
        self._rsi: Optional[pd.Series] = None

    def bind(self, data: pd.DataFrame) -> None:
        super().bind(data)
        frame = self.data
        close = frame["close"]
        self._ema = ema(close, self.config.ema_length)
        self._rsi = rsi(close, self.config.rsi_length)

    def warmup(self) -> int:
        return int(max(self.config.rsi_length, self.config.ema_length))

    def _reset_bracket(self) -> None:
        self._bracket_state = None

    def _open_bracket(self, side: int, price: float) -> None:
        self._bracket_state = self._bracket_template.initial_levels(side, price)

    def on_bar(
        self,
        timestamp: pd.Timestamp,
        row: pd.Series,
        index: int,
        broker: "Broker",
    ) -> int:
        if self._ema is None or self._rsi is None:
            raise RuntimeError("Strategy is not bound to data")

        ema_value = self._ema.iloc[index]
        rsi_value = self._rsi.iloc[index]
        if pd.isna(ema_value) or pd.isna(rsi_value):
            return 0

        close_price = float(row["close"])
        position = int(round(broker.position))

        if position == 0:
            self._reset_bracket()
            if close_price < float(ema_value) and float(rsi_value) < self.config.lower:
                self._open_bracket(1, close_price)
                return 1
            if close_price > float(ema_value) and float(rsi_value) > self.config.upper:
                self._open_bracket(-1, close_price)
                return -1
        else:
            if self._bracket_state is not None:
                exit_reason = self._bracket_state.update(row)
                if exit_reason:
                    qty = -position
                    self._reset_bracket()
                    return qty

        return 0


def factory(params: Optional[Dict[str, float]]) -> RSIEmaMeanRevert:
    return RSIEmaMeanRevert(params)


__all__ = ["RSIEmaMeanRevert", "Params", "factory"]
