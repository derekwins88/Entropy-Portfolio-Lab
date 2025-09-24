"""Trinity strategy combining volatility, price, and volume signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

import numpy as np
import pandas as pd

from ..core.strategy import BarStrategy

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from ..core.broker import Broker


@dataclass
class Params:
    """Configuration schema for :class:`Trinity`."""

    entropy_lookback: int = 40
    entry_entropy_threshold: float = 0.02
    breakout_period: int = 55
    ema_fast: int = 21
    ema_slow: int = 100
    vwap_len: int = 20
    stop_pct: float = 0.02
    take_pct: float = 0.04
    signal_mode: str = "target"

    @classmethod
    def from_dict(cls, params: Optional[Dict[str, object]]) -> "Params":
        base = cls()
        if not params:
            return base

        def _as_int(value: object, fallback: int) -> int:
            try:
                return int(value) if value is not None else fallback
            except (TypeError, ValueError):
                return fallback

        def _as_float(value: object, fallback: float) -> float:
            try:
                return float(value) if value is not None else fallback
            except (TypeError, ValueError):
                return fallback

        def _as_mode(value: object, fallback: str) -> str:
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"target", "delta"}:
                    return lowered
            return fallback

        return cls(
            entropy_lookback=_as_int(params.get("entropy_lookback"), base.entropy_lookback),
            entry_entropy_threshold=_as_float(
                params.get("entry_entropy_threshold"), base.entry_entropy_threshold
            ),
            breakout_period=_as_int(params.get("breakout_period"), base.breakout_period),
            ema_fast=_as_int(params.get("ema_fast"), base.ema_fast),
            ema_slow=_as_int(params.get("ema_slow"), base.ema_slow),
            vwap_len=_as_int(params.get("vwap_len"), base.vwap_len),
            stop_pct=_as_float(params.get("stop_pct"), base.stop_pct),
            take_pct=_as_float(params.get("take_pct"), base.take_pct),
            signal_mode=_as_mode(params.get("signal_mode"), base.signal_mode),
        )


class Trinity(BarStrategy):
    """Consensus strategy using volatility, breakout, and volume alignment."""

    def __init__(self, params: Optional[Dict[str, object]] = None) -> None:
        super().__init__(params)
        self.config = Params.from_dict(params)
        if self.config.entropy_lookback <= 0:
            raise ValueError("entropy_lookback must be a positive integer")
        if self.config.breakout_period <= 0:
            raise ValueError("breakout_period must be a positive integer")
        if self.config.ema_fast <= 0 or self.config.ema_slow <= 0:
            raise ValueError("EMA lengths must be positive integers")
        if self.config.vwap_len <= 0:
            raise ValueError("VWAP length must be a positive integer")

        self._entropy: Optional[pd.Series] = None
        self._breakout_high: Optional[pd.Series] = None
        self._ema_fast: Optional[pd.Series] = None
        self._ema_slow: Optional[pd.Series] = None
        self._vwap: Optional[pd.Series] = None
        self._current_side: int = 0

    def bind(self, data: pd.DataFrame) -> None:
        super().bind(data)

        frame = self.data
        close = frame["close"].astype(float)
        high = frame["high"].astype(float) if "high" in frame else close

        if "volume" in frame:
            volume = frame["volume"].astype(float)
        else:
            volume = pd.Series(np.ones(len(frame)), index=frame.index, dtype=float)

        log_returns = np.log(close / close.shift(1)).fillna(0.0)
        self._entropy = log_returns.rolling(
            self.config.entropy_lookback, min_periods=self.config.entropy_lookback
        ).std()

        breakout = high.rolling(
            self.config.breakout_period, min_periods=self.config.breakout_period
        ).max()
        self._breakout_high = breakout.shift(1)

        self._ema_fast = close.ewm(span=self.config.ema_fast, adjust=False).mean()
        self._ema_slow = close.ewm(span=self.config.ema_slow, adjust=False).mean()

        volume_roll = volume.rolling(self.config.vwap_len, min_periods=self.config.vwap_len)
        volume_sum = volume_roll.sum()
        price_volume_sum = (close * volume).rolling(
            self.config.vwap_len, min_periods=self.config.vwap_len
        ).sum()
        with np.errstate(invalid="ignore", divide="ignore"):
            self._vwap = price_volume_sum / volume_sum.replace(0.0, np.nan)

        # Reset side when binding to new data
        self._current_side = 0

    def warmup(self) -> int:
        return int(
            max(
                self.config.entropy_lookback,
                self.config.breakout_period,
                self.config.ema_slow,
                self.config.vwap_len,
            )
        )

    def _signal_mode(self) -> str:
        return self.config.signal_mode

    def _emit(self, desired_side: int) -> int:
        mode = self._signal_mode()
        if mode == "delta":
            delta = desired_side - self._current_side
            self._current_side = desired_side
            return int(delta)
        self._current_side = desired_side
        return int(desired_side)

    def on_bar(
        self,
        timestamp: pd.Timestamp,
        row: pd.Series,
        index: int,
        broker: "Broker",
    ) -> int:
        warmup = self.warmup()
        if index < warmup:
            return self._emit(0)

        if (
            self._entropy is None
            or self._breakout_high is None
            or self._ema_fast is None
            or self._ema_slow is None
            or self._vwap is None
        ):
            raise RuntimeError("Strategy is not bound to data")

        entropy = float(self._entropy.iloc[index])
        breakout_high = float(self._breakout_high.iloc[index])
        ema_fast = float(self._ema_fast.iloc[index])
        ema_slow = float(self._ema_slow.iloc[index])
        vwap_value = float(self._vwap.iloc[index])

        if not np.isfinite(entropy) or not np.isfinite(breakout_high):
            return self._emit(self._current_side)

        price = float(row["close"])

        volatility_ok = entropy <= float(self.config.entry_entropy_threshold)
        price_ok = np.isfinite(breakout_high) and price > breakout_high and ema_fast > ema_slow
        volume_ok = np.isfinite(vwap_value)
        if volume_ok:
            band = price * 0.005
            volume_ok = abs(price - vwap_value) <= band

        desired_side = self._current_side

        if self._current_side <= 0 and volatility_ok and price_ok and volume_ok:
            desired_side = 1
        elif self._current_side > 0 and price < ema_fast:
            desired_side = 0

        return self._emit(desired_side)


def factory(params: Optional[Dict[str, object]]) -> Trinity:
    return Trinity(params)


__all__ = ["Params", "Trinity", "factory"]
