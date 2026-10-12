"""Immutable v1 declarations; knowledge times are not historical attestations."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.instruments import FuturesSpec, get_instrument, parse_contract_symbol


def identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}", value):
        raise ValueError("identity must be a bounded inert identifier")
    return value


def finite(value):
    if type(value) not in (int, float) or abs(value) > 2**53 - 1 or not math.isfinite(value):
        raise ValueError("number must be finite; no strings or Boolean coercion")
    return float(value)


def integer(value):
    if type(value) is not int:
        raise ValueError("integer required; no numeric or Boolean coercion")
    return value


def label(value):
    if type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    if type(value) is not date:
        raise ValueError("session label requires an ISO date, not an instant")
    return value


def instant(value):
    if type(value) is str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
            raise ValueError("instant requires an explicit ISO UTC offset")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive/unknown instants are not accepted")
    return value.astimezone(timezone.utc)


Id = Annotated[str, BeforeValidator(identifier)]
Number = Annotated[float, BeforeValidator(finite)]
Integer = Annotated[int, BeforeValidator(integer)]
Label = Annotated[date, BeforeValidator(label)]
Instant = Annotated[datetime, BeforeValidator(instant)]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Availability(Frozen):
    price: Instant | None
    volume: Instant | None
    open_interest: Instant | None
    local_received_at: Instant | None

    def source_time(self, *, oi_required: bool = True) -> datetime | None:
        required = (self.price, self.volume, self.open_interest) if oi_required else (self.price, self.volume)
        return None if any(t is None for t in required) else max(required)

    @model_validator(mode="after")
    def receipt_order(self):
        known = [t for t in (self.price, self.volume, self.open_interest) if t is not None]
        if self.local_received_at is not None and known and self.local_received_at < max(known):
            raise ValueError("local receipt cannot precede a declared field availability")
        return self


class Bar(Frozen):
    source: Id
    root_symbol: Id
    contract_symbol: Id
    session: Label
    expiry: Label
    revision_id: Id
    supersedes: Id | None = None
    open: Number = Field(gt=0)
    high: Number = Field(gt=0)
    low: Number = Field(gt=0)
    close: Number = Field(gt=0)
    volume: Integer = Field(ge=0, le=2**53 - 1)
    open_interest: Number | None = Field(ge=0)
    availability: Availability

    @property
    def key(self):
        return self.source, self.root_symbol, self.contract_symbol, self.session

    @model_validator(mode="after")
    def market_contract(self):
        spec = get_instrument(self.root_symbol)
        code = parse_contract_symbol(self.contract_symbol)
        if not isinstance(spec, FuturesSpec) or self.root_symbol != spec.root_symbol:
            raise ValueError("unsupported futures root")
        if code.root != spec.root_symbol or not spec.is_cycle_month(code.month_code):
            raise ValueError("contract is not in the declared instrument cycle")
        if self.contract_symbol != spec.build_contract_symbol(code.month_code, code.year):
            raise ValueError("contract symbol must use its canonical spelling")
        if self.expiry != spec.expiry_for_symbol(self.contract_symbol) or self.session > self.expiry:
            raise ValueError("expiry/session violates existing spec-derived restrictions")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC envelope")
        if self.supersedes == self.revision_id:
            raise ValueError("revision cannot supersede itself")
        return self


class LicenseDeclaration(Frozen):
    status: Literal["unknown", "synthetic", "user_declared"]
    intended_use: str = Field(min_length=1, max_length=300)
    redistribution: str = Field(min_length=1, max_length=300)
    attribution: str = Field(min_length=1, max_length=300)


class Snapshot(Frozen):
    schema_version: Literal["futures_snapshot_v1"]
    snapshot_id: Id
    source: Id
    root_symbol: Id
    timestamp_role: Literal["trading_session_label"]
    price_basis: Literal["last_trade", "settlement", "unknown"]
    calendar_id: Id
    calendar_version: Id
    instrument_metadata_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_policy: Literal["explicit_supersession_v1"]
    license: LicenseDeclaration
    bars: tuple[Bar, ...] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def identities(self):
        seen = set()
        for bar in self.bars:
            if (bar.source, bar.root_symbol) != (self.source, self.root_symbol):
                raise ValueError("snapshot source/root mismatch")
            key = (*bar.key, bar.revision_id)
            if key in seen:
                raise ValueError("duplicate observation/revision identity")
            seen.add(key)
        return self
