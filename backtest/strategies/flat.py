"""Example strategy that never takes risk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from ..core.strategy import BarStrategy

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from ..core.broker import Broker


@dataclass
class Params:
    pass


class Flat(BarStrategy):
    def warmup(self) -> int:
        return 0

    def on_bar(
        self,
        timestamp: pd.Timestamp,
        row: pd.Series,
        index: int,
        broker: "Broker",
    ) -> int:
        return 0


def factory(params: dict) -> Flat:
    return Flat(params)
