"""
Futures contract specification (Phase 1 — instrument spec layer).

Extends :class:`~app.instruments.base.InstrumentSpec` with the futures-specific
calendar and rollover configuration, plus the calendar math the data layer
needs: CME month codes, contract-symbol parse/build, and third-Friday expiry.

Pure logic only — no data stitching (that is ``data/futures_continuous.py``,
a later commit) and no I/O.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.instruments.base import AdjustmentMethod, InstrumentSpec

# Standard CME/CBOT/NYMEX delivery-month codes.
CME_MONTH_CODES: dict[str, int] = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}


class RollMethod(str, Enum):
    VOLUME_OPEN_INTEREST = "volume_open_interest"
    DAYS_BEFORE_EXPIRY = "days_before_expiry"


class ExpiryRule(str, Enum):
    THIRD_FRIDAY = "third_friday"


@dataclass(frozen=True)
class ContractCode:
    """Structural parse of a contract symbol, e.g. ``ESZ24``."""

    root: str
    month_code: str
    year: int


def third_friday(year: int, month: int) -> datetime.date:
    """Return the third Friday of ``year``/``month``."""
    first = datetime.date(year, month, 1)
    # date.weekday(): Mon=0 .. Sun=6; Friday=4.
    offset = (4 - first.weekday()) % 7
    first_friday = first + datetime.timedelta(days=offset)
    return first_friday + datetime.timedelta(days=14)


def parse_contract_symbol(symbol: str) -> ContractCode:
    """Parse ``"ESZ24"`` -> ``ContractCode(root="ES", month_code="Z", year=2024)``.

    Assumes a 1-character month code and a 2-digit year mapped to 2000-2099
    (futures convention for this century; pre-2000 is not supported in V1).
    """
    s = symbol.strip().upper()
    if len(s) < 4:  # at least root(1) + month(1) + yy(2)
        raise ValueError(f"contract symbol too short to parse: {symbol!r}")
    root, month_code, yy = s[:-3], s[-3], s[-2:]
    if month_code not in CME_MONTH_CODES:
        raise ValueError(f"invalid month code {month_code!r} in {symbol!r}")
    if not yy.isdigit():
        raise ValueError(f"invalid year digits {yy!r} in {symbol!r}")
    return ContractCode(root=root, month_code=month_code, year=2000 + int(yy))


# --- nested config submodels (all frozen + strict) ---


class RolloverConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_rule: RollMethod
    confirmation_days: int = Field(default=1, ge=1)
    lookback_window_days: int = Field(default=15, ge=1)
    fallback_rule: RollMethod
    fallback_days_before_expiry: int = Field(ge=0)


class SessionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timezone: str
    rth_equity_window_et: Optional[str] = None
    globex_window_ct: Optional[str] = None
    bar_frequency: str = "1d"
    holiday_calendar: Optional[str] = None


class CostConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    commission_per_contract_per_side: float = Field(ge=0)
    slippage_ticks_per_side: int = Field(ge=0)
    is_placeholder: bool = True
    note: Optional[str] = None


class MarginConfig(BaseModel):
    """Margin placeholders. Values change frequently, so V1 keeps them nullable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_margin_usd: Optional[float] = Field(default=None, ge=0)
    maintenance_margin_usd: Optional[float] = Field(default=None, ge=0)
    is_placeholder: bool = True
    note: Optional[str] = None


class DataConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    required_fields: list[str]
    contract_symbol_format: str
    default_adjustment: AdjustmentMethod


class FuturesSpec(InstrumentSpec):
    """Futures spec: identity/economics (from base) + calendar + rollover."""

    contract_months: list[str]
    expiry_rule: ExpiryRule
    expiry_time_local: Optional[str] = None
    rollover: RolloverConfig
    session: SessionConfig
    costs: CostConfig
    margin: MarginConfig
    data: DataConfig

    @field_validator("contract_months")
    @classmethod
    def _check_month_codes(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("contract_months must be non-empty")
        bad = [m for m in v if m not in CME_MONTH_CODES]
        if bad:
            raise ValueError(
                f"invalid CME month codes {bad}; valid: {sorted(CME_MONTH_CODES)}"
            )
        return v

    def is_cycle_month(self, month_code: str) -> bool:
        return month_code.upper() in self.contract_months

    def build_contract_symbol(self, month_code: str, year: int) -> str:
        """Build e.g. ``("Z", 2024) -> "ESZ24"`` (rejects off-cycle months)."""
        mc = month_code.upper()
        if mc not in self.contract_months:
            raise ValueError(
                f"{mc!r} is not in the {self.root_symbol} cycle {self.contract_months}"
            )
        return f"{self.root_symbol}{mc}{year % 100:02d}"

    def expiry_date(self, month_code: str, year: int) -> datetime.date:
        mc = month_code.upper()
        if mc not in CME_MONTH_CODES:
            raise ValueError(f"invalid month code {mc!r}")
        if self.expiry_rule is ExpiryRule.THIRD_FRIDAY:
            return third_friday(year, CME_MONTH_CODES[mc])
        raise NotImplementedError(
            f"expiry_rule {self.expiry_rule!r} not supported in V1"
        )

    def expiry_for_symbol(self, symbol: str) -> datetime.date:
        cc = parse_contract_symbol(symbol)
        if cc.root != self.root_symbol:
            raise ValueError(
                f"symbol {symbol!r} root {cc.root!r} != spec root {self.root_symbol!r}"
            )
        return self.expiry_date(cc.month_code, cc.year)
