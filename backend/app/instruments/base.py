"""
Instrument specification base layer (Phase 1 — instrument spec layer).

Defines the generic, immutable :class:`InstrumentSpec` plus the shared enums and
exceptions used across the instrument registry.  This module is intentionally
pure: no I/O, no pandas, no file or network access — just the spec model and its
validation (notably the ``tick_value`` invariant).

Asset-class-specific specs (e.g. futures expiry / rollover) live in
:mod:`app.instruments.futures`; YAML loading lives in
:mod:`app.instruments.registry`.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetClass(str, Enum):
    """Supported instrument asset classes (Phase 1 = futures only)."""

    EQUITY_INDEX_FUTURE = "equity_index_future"
    COMMODITY_FUTURE = "commodity_future"
    FX_FUTURE = "fx_future"
    RATES_FUTURE = "rates_future"


class SettlementType(str, Enum):
    CASH = "cash"
    PHYSICAL = "physical"


class AdjustmentMethod(str, Enum):
    """Continuous-contract back-adjustment method (used by the data layer)."""

    RATIO = "ratio"
    PANAMA = "panama"
    NONE = "none"


class InstrumentError(Exception):
    """Base class for instrument-registry errors."""


class UnknownInstrumentError(InstrumentError):
    """Raised when a requested instrument has no spec file."""


class InstrumentSpec(BaseModel):
    """Generic, immutable contract specification (asset-class agnostic).

    Frozen and strict (``extra="forbid"``) so that a malformed or typo'd spec
    file raises a :class:`pydantic.ValidationError` instead of silently loading.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    root_symbol: str
    name: str
    asset_class: AssetClass
    exchange: str
    underlying: Optional[str] = None
    settlement_type: SettlementType
    currency: str
    contract_multiplier: float = Field(gt=0)
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    price_quotation: str
    warnings: list[str] = Field(default_factory=list)

    @field_validator("root_symbol")
    @classmethod
    def _root_upper_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("root_symbol must be non-empty")
        if v != v.upper():
            raise ValueError(f"root_symbol must be uppercase: {v!r}")
        return v

    @model_validator(mode="after")
    def _check_tick_value(self) -> "InstrumentSpec":
        expected = self.contract_multiplier * self.tick_size
        if not math.isclose(self.tick_value, expected, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"tick_value ({self.tick_value}) must equal contract_multiplier * "
                f"tick_size ({self.contract_multiplier} * {self.tick_size} = {expected})"
            )
        return self
