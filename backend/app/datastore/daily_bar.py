"""
Per-record futures daily bar schema (foundation step after the instrument layer).

:class:`FuturesDailyBar` is the typed, immutable model for a **single** raw
daily bar of one futures contract.  Its fields and rules mirror the canonical
frame-level schema in :mod:`app.datastore.store` (``REQUIRED_COLUMNS`` /
:func:`~app.datastore.store.validate_raw_futures`), and it adds two
registry-aware rules the frame validator deliberately does not enforce:

* ``root_symbol`` must have a spec in the instrument registry;
* ``contract_symbol`` must parse and its root must match ``root_symbol``.

Bulk dataframes should keep going through ``validate_raw_futures``; this model
is for record-at-a-time construction/validation (synthetic fixtures, manual
entry, future API payloads).  No I/O beyond the registry spec lookup.
"""

from __future__ import annotations

import datetime
import math
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.instruments import (
    UnknownInstrumentError,
    get_instrument,
    parse_contract_symbol,
)


class FuturesDailyBar(BaseModel):
    """One validated raw daily bar for a single futures contract.

    Frozen and strict (``extra="forbid"``), matching the instrument-spec
    layer's conventions, so malformed synthetic data fails loudly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime.datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)
    # Required but nullable, mirroring the frame schema (column mandatory,
    # values may be missing for sources without per-contract OI).
    open_interest: Optional[Annotated[float, Field(ge=0)]]
    root_symbol: str
    contract_symbol: str
    expiry: datetime.date
    source: str
    timezone: str

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, v: datetime.datetime) -> datetime.datetime:
        """Normalize to UTC, tz-aware (naive assumed UTC) — mirrors store.py."""
        if v.tzinfo is None:
            return v.replace(tzinfo=datetime.timezone.utc)
        return v.astimezone(datetime.timezone.utc)

    @field_validator("expiry", mode="before")
    @classmethod
    def _expiry_from_datetime(cls, v: object) -> object:
        """Accept the frame schema's expiry representation (tz-aware UTC
        datetime): normalize to UTC (naive assumed UTC, mirroring store.py)
        and truncate to the UTC calendar date."""
        if isinstance(v, datetime.datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=datetime.timezone.utc)
            else:
                v = v.astimezone(datetime.timezone.utc)
            return v.date()
        return v

    @field_validator("open_interest", mode="before")
    @classmethod
    def _oi_nan_is_none(cls, v: object) -> object:
        """Map the frame schema's missing-OI marker (NaN in a float64 column)
        to this model's None."""
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

    @field_validator("root_symbol")
    @classmethod
    def _root_upper_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("root_symbol must be non-empty")
        if v != v.upper():
            raise ValueError(f"root_symbol must be uppercase: {v!r}")
        return v

    @field_validator("contract_symbol")
    @classmethod
    def _contract_upper_nonempty(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("contract_symbol must be non-empty")
        return v

    @field_validator("source", "timezone")
    @classmethod
    def _identity_str_non_empty(cls, v: str, info: ValidationInfo) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must be non-empty")
        return stripped

    @model_validator(mode="after")
    def _check_ohlc(self) -> "FuturesDailyBar":
        if self.high < max(self.open, self.close):
            raise ValueError(
                f"high ({self.high}) must be >= max(open, close) "
                f"({max(self.open, self.close)})"
            )
        if self.low > min(self.open, self.close):
            raise ValueError(
                f"low ({self.low}) must be <= min(open, close) "
                f"({min(self.open, self.close)})"
            )
        return self

    @model_validator(mode="after")
    def _check_against_registry(self) -> "FuturesDailyBar":
        try:
            get_instrument(self.root_symbol)
        except UnknownInstrumentError as exc:
            # Re-raise as ValueError so pydantic reports it as a ValidationError.
            raise ValueError(str(exc)) from exc
        code = parse_contract_symbol(self.contract_symbol)
        if code.root != self.root_symbol:
            raise ValueError(
                f"contract_symbol {self.contract_symbol!r} has root {code.root!r}, "
                f"which does not match root_symbol {self.root_symbol!r}"
            )
        return self
