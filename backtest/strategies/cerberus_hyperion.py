"""Cerberus Hyperion strategy implementation.

This mirrors the NinjaTrader counterpart with entropy gating, breakout
confirmation, and a hyper-conviction blend. The strategy emits delta-style
signals so it works with the existing backtesting engine without additional
adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..core.indicators import atr as compute_atr
from ..core.strategy import BarStrategy


@dataclass
class HyperParams:
    """Configuration parameters for :class:`CerberusHyperion`."""

    entropy_lookback: int = 40
    entry_entropy_threshold: float = 0.042
    ema_fast: int = 21
    ema_slow: int = 100
    breakout_period: int = 55
    vwap_enabled: bool = True
    vwap_max_atr: float = 1.0
    use_vol_delta: bool = True
    use_imbalance: bool = True
    w_res: float = 0.40
    w_vwap: float = 0.20
    w_vol: float = 0.20
    w_imb: float = 0.20
    hyper_min: float = 0.70
    hyper_tier2: float = 0.85
    base_risk_pct: float = 1.5
    kelly_cap_pct: float = 4.0
    stop_atr_mult: float = 1.2
    target_atr_mult: float = 3.5
    win_boost: float = 1.25
    loss_damp: float = 0.85
    trail_after_1r: bool = True


def _coerce_params(params: Optional[Dict[str, object]]) -> HyperParams:
    if not params:
        return HyperParams()
    valid = {f.name for f in fields(HyperParams)}
    clean: Dict[str, object] = {}
    for key, value in params.items():
        if key in valid:
            clean[key] = value
    return HyperParams(**clean)


class CerberusHyperion(BarStrategy):
    """Entropy-aware breakout strategy emitting delta signals."""

    def __init__(self, params: Optional[Dict[str, object]] = None) -> None:
        super().__init__(params)
        self.config = _coerce_params(params)

        self._side_units: int = 0
        self._ema_fast: Optional[pd.Series] = None
        self._ema_slow: Optional[pd.Series] = None
        self._ema_fast_diff: Optional[pd.Series] = None
        self._atr: Optional[pd.Series] = None
        self._entropy: Optional[pd.Series] = None
        self._breakout_high: Optional[pd.Series] = None
        self._vwap: Optional[pd.Series] = None
        self._close: Optional[pd.Series] = None
        self._max_vol60: Optional[pd.Series] = None
        self._dyn_risk: float = 1.0
        self._echo_block: int = -1

        # Compatibility knobs for the engine (bracket sizing lives there)
        self.stop_pct = 0.0
        self.take_pct = 0.0

    # ------------------------------------------------------------------
    # Life-cycle hooks
    # ------------------------------------------------------------------
    def bind(self, data: pd.DataFrame) -> None:  # type: ignore[override]
        super().bind(data)

        frame = self.data
        close = frame["close"].astype(float)
        high = frame["high"].astype(float) if "high" in frame else close
        low = frame["low"].astype(float) if "low" in frame else close
        volume = frame["volume"].astype(float) if "volume" in frame else pd.Series(
            np.ones(len(frame)), index=frame.index, dtype=float
        )

        log_returns = np.log(close).diff().fillna(0.0)
        self._entropy = log_returns.rolling(
            self.config.entropy_lookback, min_periods=self.config.entropy_lookback
        ).std()

        self._ema_fast = close.ewm(span=self.config.ema_fast, adjust=False).mean()
        self._ema_slow = close.ewm(span=self.config.ema_slow, adjust=False).mean()
        self._ema_fast_diff = self._ema_fast.diff().fillna(0.0)

        breakout = high.rolling(
            self.config.breakout_period, min_periods=self.config.breakout_period
        ).max()
        self._breakout_high = breakout.shift(1)

        self._atr = compute_atr(high, low, close, length=14)

        vwap_window = 20
        vol_roll = volume.rolling(vwap_window, min_periods=vwap_window)
        price_volume_sum = (close * volume).rolling(vwap_window, min_periods=vwap_window).sum()
        with np.errstate(divide="ignore", invalid="ignore"):
            vwap = price_volume_sum / vol_roll.sum().replace(0.0, np.nan)
        self._vwap = vwap.fillna(close)

        self._close = close
        self._max_vol60 = volume.rolling(60, min_periods=1).max()
        frame["_maxvol60"] = self._max_vol60

        self._side_units = 0
        self._dyn_risk = 1.0
        self._echo_block = -1

    def warmup(self) -> int:  # type: ignore[override]
        return int(
            max(
                self.config.entropy_lookback,
                self.config.ema_slow,
                self.config.breakout_period,
                60,
            )
        )

    # ------------------------------------------------------------------
    # Engine helpers
    # ------------------------------------------------------------------
    def get_effective_risk(self) -> float:
        base = float(self.config.base_risk_pct) * float(self._dyn_risk)
        return float(min(base, self.config.kelly_cap_pct))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _ensure_bound(self) -> None:
        if (
            self._ema_fast is None
            or self._ema_slow is None
            or self._ema_fast_diff is None
            or self._atr is None
            or self._entropy is None
            or self._breakout_high is None
            or self._vwap is None
            or self._close is None
        ):
            raise RuntimeError("Strategy not bound to data")

    def _close_at(self, index: int) -> float:
        assert self._close is not None
        return float(self._close.iat[index])

    def _resonance_score(self, index: int) -> float:
        assert self._ema_fast is not None and self._ema_slow is not None and self._atr is not None
        atr_value = float(self._atr.iat[index]) if not np.isnan(self._atr.iat[index]) else 0.0
        atr_value = max(atr_value, 1e-9)
        spread = (float(self._ema_fast.iat[index]) - float(self._ema_slow.iat[index])) / atr_value
        spread_score = self._clamp01((spread + 1.0) / 2.0)
        slope = float(self._ema_fast_diff.iat[index]) if index >= 0 else 0.0
        slope_score = self._clamp01((slope + 0.0025) / 0.005)
        return self._clamp01(0.7 * spread_score + 0.3 * slope_score)

    def _vwap_score(self, index: int) -> float:
        if not self.config.vwap_enabled:
            return 1.0
        assert self._vwap is not None and self._atr is not None
        atr_value = float(self._atr.iat[index]) if not np.isnan(self._atr.iat[index]) else 0.0
        atr_value = max(atr_value, 1e-9)
        dist_atr = abs(float(self._vwap.iat[index]) - self._close_at(index)) / atr_value
        return self._clamp01(1.0 - (dist_atr / max(self.config.vwap_max_atr, 1e-6)))

    def _vol_delta_score(self, index: int, row: pd.Series) -> float:
        if not self.config.use_vol_delta:
            return 1.0
        vol = float(row.get("volume", 0.0))
        if vol <= 0.0:
            return 0.5
        max_vol = float(row.get("_maxvol60", vol))
        if max_vol <= 0.0:
            max_vol = vol
        open_px = float(row.get("open", self._close_at(index)))
        sign = np.sign(self._close_at(index) - open_px)
        norm = min(vol / max(max_vol, 1e-9), 1.0)
        return self._clamp01(0.5 + 0.5 * sign * norm)

    def _imbalance_score(self, row: pd.Series) -> float:
        if not self.config.use_imbalance:
            return 1.0
        high = float(row.get("high", row.get("close", 0.0)))
        low = float(row.get("low", row.get("close", 0.0)))
        close = float(row.get("close", 0.0))
        rng = max(high - low, 1e-9)
        return self._clamp01((close - low) / rng)

    def _hyper_score(self, index: int, row: pd.Series) -> float:
        res = self._resonance_score(index)
        vwap = self._vwap_score(index)
        vol_delta = self._vol_delta_score(index, row)
        imbalance = self._imbalance_score(row)
        weight_sum = max(
            self.config.w_res + self.config.w_vwap + self.config.w_vol + self.config.w_imb,
            1e-9,
        )
        blended = (
            self.config.w_res * res
            + self.config.w_vwap * vwap
            + self.config.w_vol * vol_delta
            + self.config.w_imb * imbalance
        )
        return self._clamp01(blended / weight_sum)

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------
    def on_bar(  # type: ignore[override]
        self,
        timestamp: pd.Timestamp,
        row: pd.Series,
        index: int,
        broker,
    ) -> int:
        warmup = self.warmup()
        if index < warmup:
            return 0

        self._ensure_bound()
        assert self._entropy is not None
        assert self._ema_fast is not None and self._ema_slow is not None
        assert self._atr is not None and self._breakout_high is not None

        if index <= self._echo_block and self._side_units == 0:
            return 0

        close = float(row["close"])
        ema_fast = float(self._ema_fast.iat[index])
        ema_slow = float(self._ema_slow.iat[index])
        entropy_value = float(self._entropy.iat[index]) if not np.isnan(self._entropy.iat[index]) else np.inf
        breakout_prev = (
            float(self._breakout_high.iat[index])
            if not np.isnan(self._breakout_high.iat[index])
            else -np.inf
        )

        # Exit condition – lose momentum
        if self._side_units > 0 and (close < ema_fast or ema_fast < ema_slow):
            delta = -self._side_units
            self._side_units = 0
            self._echo_block = index + 3
            self._dyn_risk = max(0.5, self._dyn_risk * self.config.loss_damp)
            return delta

        # Entry condition – entropy gate + breakout + hyper conviction
        if self._side_units == 0:
            low_entropy = np.isfinite(entropy_value) and entropy_value <= self.config.entry_entropy_threshold
            price_ok = close > breakout_prev and ema_fast > ema_slow

            if low_entropy and price_ok:
                hyper = self._hyper_score(index, row)
                if hyper >= self.config.hyper_min:
                    tier_delta = 2 if hyper >= self.config.hyper_tier2 else 1
                    self._side_units = tier_delta
                    if tier_delta == 2:
                        self._dyn_risk = min(self._dyn_risk * self.config.win_boost, 2.5)
                    else:
                        self._dyn_risk = max(self._dyn_risk, 1.0)
                    return tier_delta

        return 0
