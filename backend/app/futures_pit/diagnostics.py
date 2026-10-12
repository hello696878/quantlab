"""Read-only daily quality findings; no filling, clipping or price repair."""
import math
import pandas as pd

from app.datastore.futures_continuous import build_continuous_futures
from app.datastore.store import CONTINUOUS_COLUMNS
from app.run_replay.identity import digest
from .models import finite


def validate_continuous(frame, raw, spec, calendar, *, spike_threshold=0.1):
    spike_threshold = finite(spike_threshold)
    if not 0 < spike_threshold <= 10:
        raise ValueError("diagnostic spike threshold must be in (0,10]")
    findings = []

    def add(code, severity, session=None, **details):
        findings.append({"code": code, "severity": severity, "session": session, **details})

    if not 1 <= len(frame) <= 4000 or not set(CONTINUOUS_COLUMNS) <= set(frame.columns):
        return ({"code": "empty_or_invalid_schema", "severity": "error", "session": None},)
    if any(not isinstance(t, pd.Timestamp) or pd.isna(t) or t.tzinfo is None or t.utcoffset().total_seconds() != 0 or
           t.hour or t.minute or t.second or t.microsecond or t.nanosecond for t in frame.timestamp):
        return ({"code": "invalid_session_timestamp", "severity": "error", "session": None},)
    dates = [t.date() for t in frame.timestamp]
    if dates != sorted(dates):
        add("unordered_sessions", "error")
    if len(set(dates)) != len(dates):
        add("duplicate_session_identity", "error")
    for day in dates:
        try:
            if not calendar.lookup(day).open:
                add("quote_on_closed_session", "error", str(day))
        except ValueError:
            add("unknown_calendar_coverage", "error", str(day))
    try:
        for day in calendar.between(min(dates), max(dates)):
            if day not in dates:
                add("missing_expected_session", "warning", str(day))
    except ValueError:
        add("unknown_calendar_coverage", "error")
    numeric = [c for c in CONTINUOUS_COLUMNS if c.startswith(("open_", "high_", "low_", "close_"))]
    numeric += ["adjustment_factor", "volume"]
    unsafe = False
    for row in frame.itertuples():
        try:
            valid = all(type(getattr(row, c)) is not bool and math.isfinite(getattr(row, c)) for c in numeric)
            valid = valid and all(getattr(row, c) > 0 for c in numeric if c.endswith("_raw"))
            valid = valid and type(row.volume) is int and row.volume >= 0
            valid = valid and type(row.open_interest) is not bool and (pd.isna(row.open_interest) or
                                                                      math.isfinite(row.open_interest) and row.open_interest >= 0)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            add("nonfinite_or_invalid_numeric", "error", str(row.timestamp.date()))
            unsafe = True
        if valid and row.adjustment_method == "ratio" and row.adjustment_factor <= 0:
            add("invalid_ratio_factor", "error", str(row.timestamp.date()))
        if valid and row.adjustment_method == "panama" and row.close_adjusted <= 0:
            add("nonpositive_panama_level", "warning", str(row.timestamp.date()),
                limitation="Additive adjusted levels can be nonpositive; not suitable for percentage-return logic")
    methods = set(frame.adjustment_method)
    if len(methods) != 1:
        add("mixed_adjustment_policy", "error")
        return tuple(findings)
    if not methods <= {"ratio", "panama", "none"}:
        add("unsupported_adjustment_policy", "error")
        return tuple(findings)
    if unsafe:
        return tuple(findings)
    expected = build_continuous_futures(raw, spec, next(iter(methods)), declared_calendar=calendar)
    wanted = {r.timestamp: r for r in expected.itertuples()}
    for row in frame.itertuples():
        target = wanted.get(row.timestamp)
        if target is None:
            add("unexpected_quote", "error", str(row.timestamp.date()))
            continue
        for name in CONTINUOUS_COLUMNS:
            a, b = getattr(row, name), getattr(target, name)
            equal = (a == b or a != a and b != b)
            if name in numeric:
                equal = math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)
            if not equal:
                add("source_or_adjustment_mismatch", "error", str(row.timestamp.date()), column=name)
        if type(row.roll_flag) is not bool:
            add("invalid_roll_flag_type", "error", str(row.timestamp.date()))
    for a, b in zip(frame.itertuples(), list(frame.itertuples())[1:]):
        if a.active_contract != b.active_contract:
            adjusted_change = (b.close_adjusted - a.close_adjusted if b.adjustment_method == "panama" else
                               b.close_adjusted / a.close_adjusted - 1 if a.close_adjusted != 0 else None)
            add("between_contract_seam", "info", str(b.timestamp.date()),
                raw_jump=b.close_raw / a.close_raw - 1, adjusted_change=adjusted_change,
                adjusted_change_unit="price_points" if b.adjustment_method == "panama" else "fractional_close_change",
                limitation="Raw roll spread is not a tradable return")
            if not b.roll_flag:
                add("unflagged_contract_transition", "error", str(b.timestamp.date()))
        elif b.roll_flag:
            add("unexpected_roll_flag", "error", str(b.timestamp.date()))
        elif abs(b.close_raw / a.close_raw - 1) > spike_threshold:
            add("same_contract_spike", "warning", str(b.timestamp.date()))
    # Per-contract missing quotes may exist even when the active series is complete.
    for symbol, group in raw.groupby("contract_symbol"):
        observed = {t.date() for t in group.timestamp}
        for day in calendar.between(min(observed), max(observed)):
            if day not in observed:
                add("missing_contract_quote", "warning", str(day), contract=symbol)
    return tuple(findings)


def derived_identity(envelope, calendar, spec, adjustment):
    return digest({"namespace": "declared_continuous_futures_v1", "input_envelope": envelope,
                   "calendar": calendar.fingerprint, "spec": spec.model_dump(mode="json"),
                   "roll_policy": "expiry_anchored_expected_sessions_retrospective_v1",
                   "adjustment": adjustment})
