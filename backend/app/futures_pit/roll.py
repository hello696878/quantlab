"""Explicit declared-calendar scheduling. This policy remains retrospective."""
from __future__ import annotations

from datetime import timedelta
import math

import pandas as pd

from app.datastore.futures_continuous import RollEvent, RollScheduleError
from app.datastore.store import validate_raw_futures
from app.instruments import RollMethod, parse_contract_symbol
from .calendar import DeclaredCalendar


def declared_roll_schedule(raw_df, spec, calendar: DeclaredCalendar):
    try:
        if (not pd.api.types.is_datetime64_any_dtype(raw_df.timestamp.dtype) or raw_df.timestamp.dt.tz is None or
                any(t.utcoffset() != timedelta(0) for t in raw_df.timestamp)):
            raise ValueError("timestamp must use aware UTC session labels")
        if not pd.api.types.is_integer_dtype(raw_df.volume.dtype) or pd.api.types.is_bool_dtype(raw_df.volume.dtype):
            raise ValueError("volume must have integer dtype")
        for column in ("open", "high", "low", "close"):
            if any(type(v) is bool or not math.isfinite(v) or v <= 0 for v in raw_df[column]):
                raise ValueError("prices must be finite positive numbers")
        if any(pd.notna(v) and (type(v) is bool or not math.isfinite(v) or v < 0) for v in raw_df.open_interest):
            raise ValueError("invalid open interest")
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise RollScheduleError("invalid typed declared-mode daily values/session labels") from exc
    norm = validate_raw_futures(raw_df)
    if norm.empty or len(norm) > 4000 or set(norm.root_symbol) != {spec.root_symbol}:
        raise RollScheduleError("declared mode requires 1..4000 rows for one spec root")
    if calendar.timezone != spec.session.timezone:
        raise RollScheduleError("declared calendar timezone/spec mismatch")
    if any(t.hour or t.minute or t.second or t.microsecond or t.nanosecond for t in norm.timestamp):
        raise RollScheduleError("declared mode requires midnight UTC session labels, not event instants")
    quotes = {}
    for symbol, group in norm.groupby("contract_symbol"):
        code = parse_contract_symbol(symbol)
        if code.root != spec.root_symbol or not spec.is_cycle_month(code.month_code):
            raise RollScheduleError("contract violates spec cycle")
        expiry = spec.expiry_for_symbol(symbol)
        quotes[symbol] = {}
        for row in group.itertuples():
            day = row.timestamp.date()
            if not calendar.lookup(day).open or day > expiry or row.expiry.date() != expiry:
                raise RollScheduleError("bar violates declared session/spec expiry")
            quotes[symbol][day] = row
    ordered = sorted(quotes, key=lambda s: (spec.expiry_for_symbol(s), s))
    events = []
    cfg = spec.rollover
    for front, nxt in zip(ordered, ordered[1:]):
        expiry = spec.expiry_for_symbol(front)
        calendar.lookup(expiry)
        expected = calendar.between(calendar.coverage_start, expiry)
        if len(expected) < cfg.lookback_window_days:
            raise RollScheduleError("calendar does not cover the complete expiry-anchored lookback")
        window = expected[-cfg.lookback_window_days:]
        consecutive, decision = 0, None
        if cfg.primary_rule == RollMethod.VOLUME_OPEN_INTEREST:
            for day in window:
                old, new = quotes[front].get(day), quotes[nxt].get(day)
                leads = (old is not None and new is not None and
                         old.open_interest == old.open_interest and new.open_interest == new.open_interest and
                         new.volume > old.volume and new.open_interest > old.open_interest)
                consecutive = consecutive + 1 if leads else 0
                if consecutive >= cfg.confirmation_days:
                    decision = day
                    break
        fallback = decision is None
        if fallback:
            if cfg.fallback_rule != RollMethod.DAYS_BEFORE_EXPIRY:
                raise RollScheduleError("declared-calendar fallback unsupported")
            target = expiry - timedelta(days=cfg.fallback_days_before_expiry)
            roll_day = calendar.on_or_before(target)
            decision = calendar.previous(roll_day)
            rule = RollMethod.DAYS_BEFORE_EXPIRY
        else:
            roll_day = calendar.next(decision)
            target = None
            rule = RollMethod.VOLUME_OPEN_INTEREST
        prior = calendar.previous(roll_day)
        # Do not silently slide a roll or its adjustment seam to an observed row.
        for symbol, day in ((front, prior), (nxt, prior), (front, roll_day), (nxt, roll_day)):
            if day not in quotes[symbol]:
                raise RollScheduleError(f"required quote missing: {symbol} on {day}")
        if events and (decision <= events[-1].roll_date or roll_day <= events[-1].roll_date):
            raise RollScheduleError("declared roll chain is not sequential")
        metadata = {"calendar_hash": calendar.fingerprint, "calendar_mode": "declared_v1",
                    "classification": "retrospective", "front_expiry": expiry.isoformat(),
                    "confirmation_days": cfg.confirmation_days, "lookback_expected_sessions": len(window),
                    "fallback_used": fallback, "fallback_units": "calendar_days",
                    "fallback_days_before_expiry": cfg.fallback_days_before_expiry,
                    "target_date": target.isoformat() if target else None,
                    "decision_session_end": calendar.lookup(decision).interval.end.isoformat(),
                    "effective_session_start": calendar.lookup(roll_day).interval.start.isoformat(),
                    "limitations": "Calendar and availability are declarations, not official/PIT certification"}
        events.append(RollEvent(roll_day, front, nxt, "declared calendar: " + rule.value,
                                decision, rule, metadata))
    return events


def decision_eligibility(event, bars, calendar, mode, decision_at):
    """Audit required full-field knowledge, not a causal scheduling engine."""
    from .models import instant

    cutoff = instant(decision_at)
    execution = calendar.lookup(event.roll_date).interval.start
    if cutoff >= execution:
        return {"eligible": False, "reason": "decision must precede effective session start"}
    if mode not in ("declared_source", "local_observed"):
        raise ValueError("explicit availability mode required")
    # Snapshot selection must already have removed competing revisions.
    required_days = [event.decision_date]
    if not event.metadata["fallback_used"]:
        for _ in range(event.metadata["confirmation_days"] - 1):
            required_days.insert(0, calendar.previous(required_days[0]))
    lookup = {(b.contract_symbol, b.session): b for b in bars}
    if len(lookup) != len(bars):
        raise ValueError("audit requires a single selected vintage")
    if event.metadata["fallback_used"]:
        available = calendar.declared_available_at
        ok = available is not None and available <= cutoff
    else:
        ok = True
        for day in required_days:
            for symbol in (event.from_contract, event.to_contract):
                b = lookup.get((symbol, day))
                t = None if b is None else (b.availability.source_time() if mode == "declared_source"
                                             else b.availability.local_received_at)
                ok = ok and t is not None and t <= cutoff
        ok = ok and calendar.declared_available_at is not None and calendar.declared_available_at <= cutoff
    return {"eligible": bool(ok), "reason": "declared inputs eligible" if ok else "unknown/future required knowledge",
            "classification": "retrospective_schedule_audit_only", "decision_at": cutoff.isoformat(),
            "execution_at": execution.isoformat()}
