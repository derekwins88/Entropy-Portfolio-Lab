import numpy as np
import pandas as pd
from typing import Dict

from backtest.indicators.patterns import nr7


class ThePraetorianEngine:
    """
    Trinity consensus (volatility + price + volume) + a fourth core:
    performance-adaptive risk via a Conviction Score.
    Implements optional hooks used by the engine:
      - get_effective_risk()  -> current risk % of equity (0..100)
      - on_trade_closed(pnl)  -> update conviction after realized PnL
    Emits target in {-1,0,1}. Use engine in target mode (recommended).
    """

    def __init__(self, params: Dict):
        p = dict(
            entropy_lookback=40,
            entry_entropy_threshold=0.015,
            breakout_period=55,
            ema_fast=21,
            ema_slow=100,
            vwap_len=20,
            vwap_max_distance_atr=1.0,  # K * ATR
            base_risk_percent=1.5,
            conviction_gain=0.25,
            conviction_loss=0.50,
            min_conviction=0.50,
            max_conviction=1.75,
            turbo=0,
            nr7=0,
        )
        p.update(params or {})
        self.p = p
        self._ind = {}
        self._conv = 1.0  # conviction multiplier

    # ---- optional hooks picked up by the engine ----
    def get_effective_risk(self) -> float:
        base = float(self.p["base_risk_percent"] * self._conv)
        if self.p.get("turbo"):
            try:
                ent = float(self._ind["entropy"].iloc[-1])
            except Exception:
                ent = float("nan")
            threshold = float(self.p.get("entry_entropy_threshold", 0.0))
            if np.isfinite(ent) and ent > 0 and threshold > 0 and ent <= 0.7 * threshold:
                base *= 1.25
        return base

    def on_trade_closed(self, pnl: float):
        if pnl > 0:
            self._conv = min(self.p["max_conviction"], self._conv + self.p["conviction_gain"])
        else:
            self._conv = max(self.p["min_conviction"], self._conv - self.p["conviction_loss"])

    # ---- strategy API ----
    def warmup(self) -> int:
        return max(
            self.p["entropy_lookback"],
            self.p["breakout_period"],
            self.p["ema_slow"],
            self.p["vwap_len"],
            14,
        )

    def bind(self, df: pd.DataFrame):
        df = df.copy()
        c = df["close"].astype(float)
        h = df["high"] if "high" in df.columns else c
        l = df["low"] if "low" in df.columns else c
        v = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)

        logret = np.log(c).diff().fillna(0.0)
        entropy = logret.rolling(self.p["entropy_lookback"], min_periods=self.p["entropy_lookback"]).std()
        ema_f = c.ewm(span=self.p["ema_fast"], adjust=False).mean()
        ema_s = c.ewm(span=self.p["ema_slow"], adjust=False).mean()
        breakout_high = h.rolling(self.p["breakout_period"], min_periods=self.p["breakout_period"]).max()
        vwap = (c * v).rolling(self.p["vwap_len"]).sum() / v.rolling(self.p["vwap_len"]).sum()
        tr = pd.concat([(h - l).abs(), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=14).mean()

        self._ind = dict(
            entropy=entropy,
            ema_f=ema_f,
            ema_s=ema_s,
            breakout_high=breakout_high,
            vwap=vwap,
            atr=atr,
            close=c,
            nr7=nr7(h, l, 7).fillna(False),
        )

    def on_bar(self, t, row, i, broker) -> int:
        if i < self.warmup():
            return 0
        e = float(self._ind["entropy"].iat[i])
        c = float(self._ind["close"].iat[i])
        bh1 = float(self._ind["breakout_high"].iat[i - 1]) if i > 0 else np.nan
        ef = float(self._ind["ema_f"].iat[i])
        es = float(self._ind["ema_s"].iat[i])
        vw = float(self._ind["vwap"].iat[i]) if not np.isnan(self._ind["vwap"].iat[i]) else c
        a14 = float(self._ind["atr"].iat[i]) if not np.isnan(self._ind["atr"].iat[i]) else 0.0

        # Volatility core
        vol_ok = e <= self.p["entry_entropy_threshold"]
        # Price core
        price_ok = (c > bh1) and (ef > es)
        # Volume core
        volm_ok = (a14 == 0.0) or (abs(c - vw) <= self.p["vwap_max_distance_atr"] * a14)

        if self.p.get("nr7"):
            try:
                if not bool(self._ind["nr7"].iat[i]):
                    return 0
            except Exception:
                return 0

        # Momentum trailing exit: lose fast-EMA → flat
        if c < ef:
            return 0
        # Trinity consensus entry
        if vol_ok and price_ok and volm_ok:
            return 1
        return 0


def factory(params: Dict):
    return ThePraetorianEngine(params)
