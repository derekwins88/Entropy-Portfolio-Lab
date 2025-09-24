"""Reference strategies bundled with the backtester."""

from .cerberus_hyperion import CerberusHyperion
from .cerberus_hyperion import HyperParams as CerberusHyperionParams
from .flat import Flat
from .flat import Params as FlatParams
from .flat import factory as flat_factory
from .praetorian import ThePraetorianEngine
from .praetorian import factory as praetorian_factory
from .rsi_ema import Params as RSIEmaParams
from .rsi_ema import RSIEmaMeanRevert
from .rsi_ema import factory as rsi_ema_factory
from .sma import Params as SMACrossParams
from .sma import SMACross
from .sma import factory as sma_factory
from .trinity import Params as TrinityParams
from .trinity import Trinity
from .trinity import factory as trinity_factory

__all__ = [
    "CerberusHyperion",
    "CerberusHyperionParams",
    "Flat",
    "FlatParams",
    "flat_factory",
    "SMACross",
    "SMACrossParams",
    "sma_factory",
    "ThePraetorianEngine",
    "praetorian_factory",
    "Trinity",
    "TrinityParams",
    "trinity_factory",
    "RSIEmaMeanRevert",
    "RSIEmaParams",
    "rsi_ema_factory",
]
