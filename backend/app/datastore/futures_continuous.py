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
import hashlib
import json
import logging
from dataclasses import dataclass, field

import pandas as pd

from app.instruments import AdjustmentMethod, FuturesSpec, RollMethod, parse_contract_symbol
from app.datastore.store import finalize_continuous, raw_data_version_hash, validate_raw_futures

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


# --------------------------------------------------------------------------- #
# Continuous series builder (stitching + ratio / Panama adjustment)
# --------------------------------------------------------------------------- #


class ContinuousBuildError(ValueError):
    """Raised when a continuous series cannot be built from the inputs."""


_ADJUSTMENT_ALIASES = {
    "ratio": AdjustmentMethod.RATIO,
    "panama": AdjustmentMethod.PANAMA,
    "none": AdjustmentMethod.NONE,
}

_OHLC_ADJUSTED = [
    ("open_adjusted", "open_raw"),
    ("high_adjusted", "high_raw"),
    ("low_adjusted", "low_raw"),
    ("close_adjusted", "close_raw"),
]


def _coerce_adjustment(method: object) -> AdjustmentMethod:
    if isinstance(method, AdjustmentMethod):
        return method
    try:
        return _ADJUSTMENT_ALIASES[str(method).strip().lower()]
    except KeyError:
        raise ContinuousBuildError(
            f"unsupported adjustment_method {method!r}; expected one of "
            f"{sorted(_ADJUSTMENT_ALIASES)}"
        ) from None


def build_continuous_futures(
    raw_df: pd.DataFrame,
    spec: FuturesSpec,
    adjustment_method: str | AdjustmentMethod = "ratio",
) -> pd.DataFrame:
    """Build one deterministic continuous daily series for ``spec``.

    ``*_raw`` columns are always the held active contract's genuine unadjusted
    prices.  ``*_adjusted`` are back-adjusted so the newest segment is unchanged
    (ratio factor 1.0 / Panama offset 0.0) and older segments are corrected at
    each roll seam using the latest common prior session, so that:

    * ratio: ``pct_change(close_adjusted)`` at the seam is the new contract's own
      held return (not the raw inter-contract gap);
    * Panama: ``diff(close_adjusted)`` at the seam is the new contract's own point
      change (no phantom PnL).

    Does not mutate ``raw_df``.  Raises :class:`ContinuousBuildError` on an
    unsupported method or a roll seam with no common prior session.
    """
    method = _coerce_adjustment(adjustment_method)
    norm = validate_raw_futures(raw_df)  # returns a copy; input never mutated
    events = compute_roll_schedule(norm, spec)

    if events:
        ordered = [events[0].from_contract] + [ev.to_contract for ev in events]
    else:
        ordered = sorted(norm["contract_symbol"].unique())  # single in-cycle contract
    roll_dates = [ev.roll_date for ev in events]
    n = len(ordered)

    by_contract: dict[str, pd.DataFrame] = {}
    close_map: dict[str, dict[datetime.date, float]] = {}
    date_set: dict[str, set[datetime.date]] = {}
    for sym in ordered:
        g = norm[norm["contract_symbol"] == sym].copy()
        g["date"] = g["timestamp"].dt.date
        g = g.sort_values("date", kind="stable")
        by_contract[sym] = g
        close_map[sym] = dict(zip(g["date"], g["close"]))
        date_set[sym] = set(g["date"])

    # Per-roll seam factors from the latest common prior session (both closes).
    ratios = [1.0] * len(events)
    gaps = [0.0] * len(events)
    for k, ev in enumerate(events):
        old, new, r = ev.from_contract, ev.to_contract, ev.roll_date
        if r not in date_set[new]:
            raise ContinuousBuildError(
                f"roll {old}->{new}: new contract has no bar on roll_date {r}"
            )
        commons = [d for d in date_set[old] if d < r and d in date_set[new]]
        if not commons:
            raise ContinuousBuildError(
                f"roll {old}->{new}: no common prior session before {r} with both "
                f"closes; cannot compute the adjustment"
            )
        ov = max(commons)
        old_close = float(close_map[old][ov])
        new_close = float(close_map[new][ov])
        ratios[k] = new_close / old_close
        gaps[k] = new_close - old_close

    # Back-adjust: newest segment untouched, cumulate over later rolls.
    cum_ratio = [1.0] * n
    cum_offset = [0.0] * n
    for i in range(n - 2, -1, -1):
        cum_ratio[i] = cum_ratio[i + 1] * ratios[i]
        cum_offset[i] = cum_offset[i + 1] + gaps[i]

    blocks: list[pd.DataFrame] = []
    for i, sym in enumerate(ordered):
        g = by_contract[sym]
        d = g["date"]
        sel = pd.Series(True, index=g.index)
        if i > 0:
            sel &= d >= roll_dates[i - 1]
        if i < n - 1:
            sel &= d < roll_dates[i]
        seg = g[sel].reset_index(drop=True)

        if method is AdjustmentMethod.RATIO:
            factor = cum_ratio[i]
        elif method is AdjustmentMethod.PANAMA:
            factor = cum_offset[i]
        else:
            factor = 1.0

        block = pd.DataFrame(
            {
                "timestamp": seg["timestamp"],
                "root_symbol": spec.root_symbol,
                "active_contract": sym,
                "open_raw": seg["open"],
                "high_raw": seg["high"],
                "low_raw": seg["low"],
                "close_raw": seg["close"],
                "volume": seg["volume"],
                "open_interest": seg["open_interest"],
                "adjustment_method": method.value,
                "adjustment_factor": factor,
            }
        )
        for adj_col, raw_col in _OHLC_ADJUSTED:
            if method is AdjustmentMethod.PANAMA:
                block[adj_col] = block[raw_col] + factor
            elif method is AdjustmentMethod.RATIO:
                block[adj_col] = block[raw_col] * factor
            else:
                block[adj_col] = block[raw_col]
        block["roll_flag"] = False
        block["roll_reason"] = ""
        blocks.append(block)

    out = pd.concat(blocks, ignore_index=True)
    out["_date"] = out["timestamp"].dt.date
    for ev in events:
        mask = (out["_date"] == ev.roll_date) & (out["active_contract"] == ev.to_contract)
        out.loc[mask, "roll_flag"] = True
        out.loc[mask, "roll_reason"] = ev.roll_reason
    out = out.drop(columns="_date")
    return finalize_continuous(out)


# --------------------------------------------------------------------------- #
# Reproducibility — continuous build config hash
# --------------------------------------------------------------------------- #

_CONTINUOUS_CONFIG_SCHEMA = "continuous_futures_config_v1"


def _canonical_json(config: dict) -> str:
    """Compact, key-sorted, deterministic JSON (mirrors app.reproducibility)."""
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def continuous_config_hash(
    raw_df: pd.DataFrame,
    spec: FuturesSpec,
    adjustment_method: str | AdjustmentMethod = "ratio",
) -> str:
    """Deterministic SHA-256 over the result-changing continuous-build inputs.

    Depends on the raw data version, the adjustment method, and every spec field
    that affects stitching (root, cycle months, expiry rule, and the full
    rollover config).  Because roll events are a deterministic function of these
    inputs, the hash already changes whenever the computed schedule would.

    Stable when equivalent raw rows are reordered (the raw hash sorts first) and
    when the same config is rebuilt.  Never depends on outputs.
    """
    method = _coerce_adjustment(adjustment_method)
    cfg = spec.rollover
    config = {
        "schema_version": _CONTINUOUS_CONFIG_SCHEMA,
        "raw_data_version": raw_data_version_hash(raw_df),
        "root_symbol": spec.root_symbol,
        "adjustment_method": method.value,
        "contract_months": list(spec.contract_months),
        "expiry_rule": spec.expiry_rule.value,
        "rollover": {
            "primary_rule": cfg.primary_rule.value,
            "fallback_rule": cfg.fallback_rule.value,
            "fallback_days_before_expiry": cfg.fallback_days_before_expiry,
            "confirmation_days": cfg.confirmation_days,
            "lookback_window_days": cfg.lookback_window_days,
        },
    }
    return hashlib.sha256(_canonical_json(config).encode("utf-8")).hexdigest()
