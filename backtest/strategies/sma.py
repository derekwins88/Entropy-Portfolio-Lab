"""Simple moving average cross strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd

from ..core.indicators import sma
from ..core.strategy import BarStrategy

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from ..core.broker import Broker


@dataclass
class Params:
    fast: int = 10
    slow: int = 30

    @classmethod
    def from_dict(cls, params: Optional[Dict[str, int]]) -> "Params":
        base = cls()
        if not params:
            return base
        data = {"fast": base.fast, "slow": base.slow}
        for key in ("fast", "slow"):
            if key in params and params[key] is not None:
                data[key] = int(params[key])
        return cls(**data)


class SMACross(BarStrategy):
    """Go long when the fast SMA is above the slow SMA."""

    def __init__(self, params: Optional[Dict[str, int]] = None) -> None:
        super().__init__(params)
        self.config = Params.from_dict(params)
        if self.config.fast <= 0 or self.config.slow <= 0:
            raise ValueError("SMA lengths must be positive integers")
        self._fast_series: Optional[pd.Series] = None
        self._slow_series: Optional[pd.Series] = None

    def bind(self, data: pd.DataFrame) -> None:
        super().bind(data)
        frame = self.data
        close = frame["close"]
        self._fast_series = sma(close, self.config.fast)
        self._slow_series = sma(close, self.config.slow)

    def warmup(self) -> int:
        return int(max(self.config.fast, self.config.slow))

    def on_bar(
        self,
        timestamp: pd.Timestamp,
        row: pd.Series,
        index: int,
        broker: "Broker",
    ) -> int:
        if self._fast_series is None or self._slow_series is None:
            raise RuntimeError("Strategy is not bound to data")

        fast = self._fast_series.iloc[index]
        slow = self._slow_series.iloc[index]
        if pd.isna(fast) or pd.isna(slow):
            return 0

        return 1 if float(fast) > float(slow) else 0


def factory(params: Optional[Dict[str, int]]) -> SMACross:
    return SMACross(params)


__all__ = ["SMACross", "Params", "factory"]
