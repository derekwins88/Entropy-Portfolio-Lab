"""Reference strategies bundled with the backtester."""

from .flat import Flat
from .flat import Params as FlatParams
from .flat import factory as flat_factory
from .rsi_ema import Params as RSIEmaParams
from .rsi_ema import RSIEmaMeanRevert
from .rsi_ema import factory as rsi_ema_factory
from .sma import Params as SMACrossParams
from .sma import SMACross
from .sma import factory as sma_factory

__all__ = [
    "Flat",
    "FlatParams",
    "flat_factory",
    "SMACross",
    "SMACrossParams",
    "sma_factory",
    "RSIEmaMeanRevert",
    "RSIEmaParams",
    "rsi_ema_factory",
]
