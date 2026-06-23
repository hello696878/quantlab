"""
Tests for the futures roll calendar (Commit 3).

Synthetic data only — no network, no real ES downloads. Covers determinism, the
volume/OI crossover path, fallback (missing OI and no-crossover), the
unresolved-roll error, field population, roll_date > decision_date, expiry-order
processing, and off-cycle rejection.
"""

import datetime
import logging

import pandas as pd
import pytest

from app.instruments import RollMethod, get_instrument
from app.datastore.futures_continuous import (
    RollEvent,
    RollScheduleError,
    compute_roll_schedule,
)

ES = get_instrument("ES")

# Spec-derived (third-Friday) expiries used by the synthetic fixtures.
EXP_H24 = datetime.date(2024, 3, 15)
EXP_M24 = datetime.date(2024, 6, 21)
EXP_U24 = datetime.date(2024, 9, 20)


def _rows(symbol, dates, volume, open_interest, expiry, price=5000.0, source="synthetic"):
    """Build raw rows for one contract. volume/open_interest may be scalar or per-date list."""
    rows = []
    for i, d in enumerate(dates):
        vol = volume[i] if isinstance(volume, (list, tuple)) else volume
        oi = open_interest[i] if isinstance(open_interest, (list, tuple)) else open_interest
        open_ = price
        close = price + 1.0
        rows.append(
            {
                "timestamp": pd.Timestamp(d),
                "open": open_,
                "high": max(open_, close) + 1.0,
                "low": min(open_, close) - 1.0,
                "close": close,
                "volume": vol,
                "open_interest": oi,
                "root_symbol": "ES",
                "contract_symbol": symbol,
                "expiry": pd.Timestamp(expiry),
                "source": source,
                "timezone": "America/Chicago",
            }
        )
    return rows


def _crossover_df():
    """ESH24 leads early, ESM24 overtakes on both volume and OI before expiry."""
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))  # 15 sessions
    n = len(dates)
    front_vol = [10000 - 300 * i for i in range(n)]
    next_vol = [1000 + 700 * i for i in range(n)]
    front_oi = [50000 - 1000 * i for i in range(n)]
    next_oi = [5000 + 5000 * i for i in range(n)]
    rows = _rows("ESH24", dates, front_vol, front_oi, EXP_H24)
    rows += _rows("ESM24", dates, next_vol, next_oi, EXP_M24)
    return pd.DataFrame(rows), dates


def test_crossover_path_works():
    df, dates = _crossover_df()
    events = compute_roll_schedule(df, ES)
    assert len(events) == 1
    ev = events[0]
    assert ev.from_contract == "ESH24"
    assert ev.to_contract == "ESM24"
    assert ev.rule_used is RollMethod.VOLUME_OPEN_INTEREST
    # both conditions first hold at index 10 (2024-03-11); roll is the next session.
    assert ev.decision_date == datetime.date(2024, 3, 11)
    assert ev.roll_date == datetime.date(2024, 3, 12)


def test_roll_schedule_is_deterministic():
    df, _ = _crossover_df()
    assert compute_roll_schedule(df, ES) == compute_roll_schedule(df, ES)
    # row order must not matter
    shuffled = df.sample(frac=1, random_state=11).reset_index(drop=True)
    assert compute_roll_schedule(shuffled, ES) == compute_roll_schedule(df, ES)


def test_roll_date_after_decision_date():
    df, _ = _crossover_df()
    for ev in compute_roll_schedule(df, ES):
        assert ev.roll_date > ev.decision_date


def test_roll_event_fields_are_populated():
    df, _ = _crossover_df()
    ev = compute_roll_schedule(df, ES)[0]
    assert isinstance(ev, RollEvent)
    assert isinstance(ev.roll_date, datetime.date)
    assert isinstance(ev.decision_date, datetime.date)
    assert ev.from_contract and ev.to_contract
    assert isinstance(ev.roll_reason, str) and ev.roll_reason
    assert isinstance(ev.rule_used, RollMethod)
    assert isinstance(ev.metadata, dict)
    assert ev.metadata["front_expiry"] == EXP_H24.isoformat()


def test_missing_open_interest_triggers_fallback(caplog):
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    rows = _rows("ESH24", dates, 5000, None, EXP_H24)  # OI missing
    rows += _rows("ESM24", dates, 6000, None, EXP_M24)
    df = pd.DataFrame(rows)
    with caplog.at_level(logging.WARNING):
        events = compute_roll_schedule(df, ES)
    assert len(events) == 1
    ev = events[0]
    assert ev.rule_used is RollMethod.DAYS_BEFORE_EXPIRY
    assert ev.metadata["fallback_used"] is True
    assert any("fallback" in r.message.lower() for r in caplog.records)
    # target = 2024-03-15 - 8 days = 2024-03-07 (a session) -> roll there, decide the day before
    assert ev.roll_date == datetime.date(2024, 3, 7)
    assert ev.decision_date == datetime.date(2024, 3, 6)


def test_fallback_days_before_expiry_when_no_crossover():
    # OI present but the next contract never overtakes the front -> no crossover.
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    rows = _rows("ESH24", dates, 9000, 90000, EXP_H24)
    rows += _rows("ESM24", dates, 100, 1000, EXP_M24)
    df = pd.DataFrame(rows)
    events = compute_roll_schedule(df, ES)
    assert len(events) == 1
    assert events[0].rule_used is RollMethod.DAYS_BEFORE_EXPIRY
    assert events[0].roll_date == datetime.date(2024, 3, 7)


def test_unresolved_rollover_raises():
    # OI missing (primary unresolvable) AND all sessions are after the fallback
    # target (expiry - 8 = 2024-03-07), so the fallback finds no eligible session.
    dates = list(pd.date_range("2024-03-11", "2024-03-15", freq="B"))
    rows = _rows("ESH24", dates, 5000, None, EXP_H24)
    rows += _rows("ESM24", dates, 6000, None, EXP_M24)
    df = pd.DataFrame(rows)
    with pytest.raises(RollScheduleError):
        compute_roll_schedule(df, ES)


def test_contracts_processed_in_expiry_order():
    # Three contracts, OI missing -> each pair resolves via the fallback rule.
    esh = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    esm = list(pd.date_range("2024-02-26", "2024-06-21", freq="B"))
    esu = list(pd.date_range("2024-04-01", "2024-09-20", freq="B"))
    rows = _rows("ESH24", esh, 1000, None, EXP_H24)
    rows += _rows("ESM24", esm, 1000, None, EXP_M24)
    rows += _rows("ESU24", esu, 1000, None, EXP_U24)
    df = pd.DataFrame(rows)
    events = compute_roll_schedule(df, ES)
    assert [(e.from_contract, e.to_contract) for e in events] == [
        ("ESH24", "ESM24"),
        ("ESM24", "ESU24"),
    ]
    assert events[0].roll_date < events[1].roll_date
    assert all(e.rule_used is RollMethod.DAYS_BEFORE_EXPIRY for e in events)


def test_off_cycle_contract_is_not_silently_included():
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    rows = _rows("ESH24", dates, 5000, 50000, EXP_H24)
    # ESF24: F = January, NOT in the ES quarterly cycle [H, M, U, Z].
    rows += _rows("ESF24", dates, 6000, 60000, datetime.date(2024, 1, 19))
    df = pd.DataFrame(rows)
    with pytest.raises(RollScheduleError) as exc:
        compute_roll_schedule(df, ES)
    assert "ESF24" in str(exc.value)
