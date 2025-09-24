"""Daily risk circuit breaker helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd


@dataclass
class RiskGuardian:
    """Tracks realised R per day and blocks new entries after a limit."""

    maxR_per_day: float = 3.0
    dayR: Dict[pd.Timestamp, float] = field(default_factory=dict)

    def can_enter(self, timestamp: pd.Timestamp) -> bool:
        """Return ``True`` if fresh exposure is still allowed on *timestamp*."""

        day = pd.Timestamp(timestamp).normalize()
        limit = -abs(float(self.maxR_per_day))
        return self.dayR.get(day, 0.0) > limit

    def on_trade_closed(
        self, *, t_exit: pd.Timestamp, pnl: float, initial_risk_dollars: float
    ) -> None:
        """Record realised ``R`` for the day of *t_exit*.

        ``initial_risk_dollars`` represents the original risk budget allocated
        to the trade in dollars. When it is zero or negative the update is
        ignored.
        """

        if initial_risk_dollars is None or initial_risk_dollars <= 0:
            return
        r_value = float(pnl) / float(initial_risk_dollars)
        day = pd.Timestamp(t_exit).normalize()
        self.dayR[day] = self.dayR.get(day, 0.0) + r_value


__all__ = ["RiskGuardian"]
