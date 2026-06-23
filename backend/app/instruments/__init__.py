"""Instrument spec layer: a registry of validated, immutable contract specs."""

from app.instruments.base import (
    AdjustmentMethod,
    AssetClass,
    InstrumentError,
    InstrumentSpec,
    SettlementType,
    UnknownInstrumentError,
)
from app.instruments.futures import (
    CME_MONTH_CODES,
    ContractCode,
    CostConfig,
    DataConfig,
    ExpiryRule,
    FuturesSpec,
    MarginConfig,
    RollMethod,
    RolloverConfig,
    SessionConfig,
    parse_contract_symbol,
    third_friday,
)
from app.instruments.registry import (
    default_instruments_dir,
    get_instrument,
    list_instruments,
    load_spec,
)

__all__ = [
    # enums
    "AdjustmentMethod",
    "AssetClass",
    "SettlementType",
    "ExpiryRule",
    "RollMethod",
    # specs
    "InstrumentSpec",
    "FuturesSpec",
    # nested config
    "RolloverConfig",
    "SessionConfig",
    "CostConfig",
    "MarginConfig",
    "DataConfig",
    # symbol/calendar helpers
    "CME_MONTH_CODES",
    "ContractCode",
    "parse_contract_symbol",
    "third_friday",
    # registry
    "get_instrument",
    "list_instruments",
    "load_spec",
    "default_instruments_dir",
    # errors
    "InstrumentError",
    "UnknownInstrumentError",
]
