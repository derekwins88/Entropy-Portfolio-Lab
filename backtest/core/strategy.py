"""Strategy base classes for bar-oriented backtests.

The backtesting engine expects strategies to derive from :class:`BarStrategy`
which exposes a minimalist life-cycle:

```
strat = MyStrategy(params)
strat.bind(dataframe)
warmup_bars = strat.warmup()
for each bar >= warmup_bars:
    qty_delta_or_target = strat.on_bar(timestamp, row, index, broker)
```

Strategies are given a handle to the :class:`~backtest.core.broker.Broker`
instance so they can inspect current equity, exposure, and outstanding orders.
The `params` dictionary is intentionally flexible which keeps the engine free
from tight coupling to strategy configuration schemas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - avoids import cycles at runtime
    from .broker import Broker


class BarStrategy(ABC):
    """Minimal base class for bar-driven strategies."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params: Dict[str, Any] = params or {}
        self._data: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def bind(self, data: pd.DataFrame) -> None:
        """Attach the source data to the strategy.

        Storing a reference makes it possible for strategies to pull auxiliary
        columns (e.g. indicators) without the engine having to pass everything
        through `on_bar` directly.
        """

        self._data = data

    def warmup(self) -> int:
        """Return the number of bars required before emitting signals.

        The default implementation assumes no warmup. Strategies can override
        this to reserve leading bars for indicator bootstrapping.
        """

        return 0

    @abstractmethod
    def on_bar(self, timestamp: pd.Timestamp, row: pd.Series, index: int, broker: "Broker") -> int:
        """Emit a signal for the given bar.

        The return value is interpreted by the engine depending on the active
        sizing mode:

        - ``mode="delta"`` → the value represents a delta adjustment in units.
        - ``mode="target"`` → the value represents the desired target position.

        Derived strategies should keep their return values unit-less. The engine
        will translate them into actual order quantities using the supplied
        sizing knobs (``size``, ``size_notional``, ``risk_R``...).
        """

    # ------------------------------------------------------------------
    # Helper properties
    # ------------------------------------------------------------------
    @property
    def data(self) -> pd.DataFrame:
        if self._data is None:
            raise RuntimeError("Strategy is not bound to a data frame. Call bind() before running.")
        return self._data
