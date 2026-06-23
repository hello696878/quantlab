"""
Futures roll calendar computation (Phase 1 — commit 3).

Scope is deliberately narrow: compute a deterministic **roll schedule** for a
futures root.  This module does *not* stitch a continuous series and does *not*
compute ratio/Panama adjustments — those land in a later commit.

Public surface:

* :class:`RollEvent` — one front->next roll decision.
* :class:`RollScheduleError` — raised on any unresolved/invalid input.
* :func:`compute_roll_schedule` — raw per-contract bars + spec -> list[RollEvent].

Rollover logic (V1, conservative — mirrors ``FuturesSpec.rollover``):

* **Primary** (``volume_open_interest``): within the last ``lookback_window_days``
  overlap sessions on/before the front contract's expiry, roll when the next
  contract's volume *and* open interest both exceed the front's for
  ``confirmation_days`` consecutive sessions.  ``decision_date`` is the
  confirmation day; ``roll_date`` is the next calendar session after it.
* **Fallback** (``days_before_expiry``): used when open interest is missing or no
  crossover confirms.  ``roll_date`` is the nearest calendar session on/before
  ``expiry - fallback_days_before_expiry`` (calendar days); ``decision_date`` is
  the session immediately before it.  A warning is logged and recorded in
  ``metadata``.
* **No silent assumptions**: if neither rule resolves, raise.

Documented V1 interpretations (there is no holiday calendar in V1):

* ``lookback_window_days`` is a count of trailing *overlap sessions* present in
  the data (not a wall-clock window), so the scan is calendar-free.
* Daily bars are assumed: at most one row per session-date per contract, else we
  raise rather than guess.
* The roll calendar uses the **spec-derived** expiry (third Friday); the raw
  ``expiry`` column is treated as informational.
"""

from __future__ import annotations

import bisect
import datetime
import logging
from dataclasses import dataclass, field

import pandas as pd

from app.instruments import FuturesSpec, RollMethod, parse_contract_symbol
from app.datastore.store import validate_raw_futures

logger = logging.getLogger(__name__)


class RollScheduleError(ValueError):
    """Raised when a roll schedule cannot be resolved or the input is invalid."""


@dataclass(frozen=True)
class RollEvent:
    """A single front->next roll decision."""

    roll_date: datetime.date
    from_contract: str
    to_contract: str
    roll_reason: str
    decision_date: datetime.date
    rule_used: RollMethod
    metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Calendar helpers (deterministic, calendar = sorted list of session dates)
# --------------------------------------------------------------------------- #


def _next_after(calendar: list[datetime.date], d: datetime.date) -> datetime.date | None:
    i = bisect.bisect_right(calendar, d)
    return calendar[i] if i < len(calendar) else None


def _prev_before(calendar: list[datetime.date], d: datetime.date) -> datetime.date | None:
    i = bisect.bisect_left(calendar, d)
    return calendar[i - 1] if i > 0 else None


def _on_or_before(calendar: list[datetime.date], d: datetime.date) -> datetime.date | None:
    i = bisect.bisect_right(calendar, d)
    return calendar[i - 1] if i > 0 else None


# --------------------------------------------------------------------------- #
# Per-contract extraction
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _ContractBars:
    symbol: str
    expiry: datetime.date
    sessions: list[datetime.date]
    volume: dict[datetime.date, float]
    open_interest: dict[datetime.date, float]


def _extract_contract(symbol: str, group: pd.DataFrame, expiry: datetime.date) -> _ContractBars:
    dates = group["timestamp"].dt.date
    if dates.duplicated().any():
        raise RollScheduleError(
            f"contract {symbol!r} has multiple bars on the same session date; "
            f"V1 expects daily bars"
        )
    sessions = sorted(dates)
    volume = dict(zip(dates, group["volume"]))
    open_interest = dict(zip(dates, group["open_interest"]))
    return _ContractBars(symbol, expiry, sessions, volume, open_interest)


def _find_crossover(
    window: list[datetime.date],
    front: _ContractBars,
    nxt: _ContractBars,
    confirmation_days: int,
) -> datetime.date | None:
    """First session where next > front on volume AND OI for N consecutive days."""
    run = 0
    for d in window:
        fo = front.open_interest.get(d)
        no = nxt.open_interest.get(d)
        if fo is None or no is None or pd.isna(fo) or pd.isna(no):
            run = 0  # open interest required to evaluate the primary rule
            continue
        if nxt.volume[d] > front.volume[d] and no > fo:
            run += 1
            if run >= confirmation_days:
                return d
        else:
            run = 0
    return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def compute_roll_schedule(raw_df: pd.DataFrame, spec: FuturesSpec) -> list[RollEvent]:
    """Compute a deterministic roll schedule for ``spec`` from raw per-contract bars.

    Returns one :class:`RollEvent` per front->next transition, ordered by expiry.
    Raises :class:`RollScheduleError` on off-cycle contracts, duplicate-session
    bars, root mismatch, or an unresolvable roll.
    """
    norm = validate_raw_futures(raw_df)

    roots = set(norm["root_symbol"].unique())
    if roots != {spec.root_symbol}:
        raise RollScheduleError(
            f"raw data roots {sorted(roots)} do not match spec root {spec.root_symbol!r}"
        )

    # Order contracts by (spec expiry, symbol); reject off-cycle months explicitly.
    info: list[tuple[datetime.date, str]] = []
    for symbol in sorted(norm["contract_symbol"].unique()):
        code = parse_contract_symbol(symbol)
        if not spec.is_cycle_month(code.month_code):
            raise RollScheduleError(
                f"contract {symbol!r} month {code.month_code!r} is not in the "
                f"{spec.root_symbol} cycle {spec.contract_months}; refusing to include it silently"
            )
        info.append((spec.expiry_for_symbol(symbol), symbol))
    info.sort(key=lambda t: (t[0], t[1]))
    ordered = [symbol for _, symbol in info]

    if len(ordered) < 2:
        return []

    calendar = sorted(set(norm["timestamp"].dt.date))
    bars = {
        symbol: _extract_contract(symbol, norm[norm["contract_symbol"] == symbol], expiry)
        for expiry, symbol in info
    }

    events: list[RollEvent] = []
    for front_sym, next_sym in zip(ordered, ordered[1:]):
        events.append(
            _resolve_pair(bars[front_sym], bars[next_sym], calendar, spec)
        )
    return events


def _resolve_pair(
    front: _ContractBars,
    nxt: _ContractBars,
    calendar: list[datetime.date],
    spec: FuturesSpec,
) -> RollEvent:
    cfg = spec.rollover
    expiry = front.expiry

    overlap = sorted(set(front.sessions) & set(nxt.sessions))
    overlap = [d for d in overlap if d <= expiry]
    window = overlap[-cfg.lookback_window_days:] if overlap else []

    # --- primary: volume / open-interest crossover ---
    if cfg.primary_rule is RollMethod.VOLUME_OPEN_INTEREST:
        decision = _find_crossover(window, front, nxt, cfg.confirmation_days)
        if decision is not None:
            roll_date = _next_after(calendar, decision)
            if roll_date is None:
                raise RollScheduleError(
                    f"roll {front.symbol}->{nxt.symbol}: crossover on {decision} has no "
                    f"following session to roll into"
                )
            reason = (
                f"{nxt.symbol} volume and open interest exceeded {front.symbol} for "
                f"{cfg.confirmation_days} consecutive session(s)"
            )
            return RollEvent(
                roll_date=roll_date,
                from_contract=front.symbol,
                to_contract=nxt.symbol,
                roll_reason=reason,
                decision_date=decision,
                rule_used=RollMethod.VOLUME_OPEN_INTEREST,
                metadata={
                    "front_expiry": expiry.isoformat(),
                    "lookback_window_days": cfg.lookback_window_days,
                    "confirmation_days": cfg.confirmation_days,
                    "fallback_used": False,
                },
            )

    # --- fallback: days before expiry ---
    if cfg.fallback_rule is RollMethod.DAYS_BEFORE_EXPIRY:
        target = expiry - datetime.timedelta(days=cfg.fallback_days_before_expiry)
        roll_date = _on_or_before(calendar, target)
        if roll_date is not None:
            decision = _prev_before(calendar, roll_date)
            if decision is None:
                raise RollScheduleError(
                    f"roll {front.symbol}->{nxt.symbol}: fallback roll on {roll_date} has no "
                    f"preceding session for a decision date"
                )
            logger.warning(
                "roll %s->%s: primary rule unresolved; using days_before_expiry fallback "
                "(target %s, roll %s)",
                front.symbol,
                nxt.symbol,
                target,
                roll_date,
            )
            reason = (
                f"fallback: nearest session on/before {target.isoformat()} "
                f"({cfg.fallback_days_before_expiry} calendar days before {front.symbol} "
                f"expiry {expiry.isoformat()})"
            )
            return RollEvent(
                roll_date=roll_date,
                from_contract=front.symbol,
                to_contract=nxt.symbol,
                roll_reason=reason,
                decision_date=decision,
                rule_used=RollMethod.DAYS_BEFORE_EXPIRY,
                metadata={
                    "front_expiry": expiry.isoformat(),
                    "target_date": target.isoformat(),
                    "fallback_days_before_expiry": cfg.fallback_days_before_expiry,
                    "fallback_used": True,
                },
            )

    raise RollScheduleError(
        f"roll {front.symbol}->{nxt.symbol}: could not resolve — primary rule did not "
        f"confirm and fallback found no session on/before the target date"
    )
