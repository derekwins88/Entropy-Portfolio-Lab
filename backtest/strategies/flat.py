"""Example strategy that never takes risk."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..core.strategy import BarStrategy


@dataclass
class Params:
    pass


class Flat(BarStrategy):
    def warmup(self) -> int:
        return 0

    def on_bar(self, timestamp: pd.Timestamp, row: pd.Series, index: int, broker) -> int:  # type: ignore[override]
        return 0


def factory(params: dict) -> Flat:
    return Flat(params)
