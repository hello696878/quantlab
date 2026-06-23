"""
Tests for the futures roll calendar (Commit 3).

Synthetic data only — no network, no real ES downloads. Covers determinism, the
volume/OI crossover path, fallback (missing OI and no-crossover), the
unresolved-roll error, field population, roll_date > decision_date, expiry-order
processing, and off-cycle rejection.
"""

import datetime
import logging

import numpy as np
import pandas as pd
import pytest
import yaml

from app.instruments import FuturesSpec, RollMethod, default_instruments_dir, get_instrument
from app.datastore import RawFuturesStore
from app.datastore.store import CONTINUOUS_COLUMNS, finalize_continuous, validate_raw_futures
from app.datastore.futures_continuous import (
    ContinuousBuildError,
    RollEvent,
    RollScheduleError,
    build_continuous_futures,
    compute_roll_schedule,
    continuous_config_hash,
)


def _es_spec(**dotted_overrides) -> FuturesSpec:
    """ES spec from es.yaml, with optional dotted overrides e.g.
    ``_es_spec(**{"rollover.fallback_days_before_expiry": 5})``."""
    data = yaml.safe_load((default_instruments_dir() / "es.yaml").read_text(encoding="utf-8"))
    for dotted, value in dotted_overrides.items():
        keys = dotted.split(".")
        node = data
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    return FuturesSpec(**data)

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
        p = price[i] if isinstance(price, (list, tuple)) else price
        open_ = p
        close = p + 1.0
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


# --------------------------------------------------------------------------- #
# Continuous builder (Commit 4)
# --------------------------------------------------------------------------- #

ROLL = datetime.date(2024, 3, 7)   # fallback roll: EXP_H24 (Mar 15) - 8 calendar days
PREV = datetime.date(2024, 3, 6)   # last held session of the old contract

# Seam fixture price levels: ESH24 close = 5001+i, ESM24 close = 5101+i (gap 100).
# At PREV (i=7): ESH24 close 5008, ESM24 close 5108. At ROLL (i=8): ESM24 close 5109.
_ESH_CLOSE_PREV = 5008.0
_ESM_CLOSE_PREV = 5108.0
_ESM_CLOSE_ROLL = 5109.0


def _seam_df():
    """Two contracts at different price levels (100-pt gap); OI missing -> fallback roll."""
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    n = len(dates)
    rows = _rows("ESH24", dates, 1000, None, EXP_H24, price=[5000 + i for i in range(n)])
    rows += _rows("ESM24", dates, 1000, None, EXP_M24, price=[5100 + i for i in range(n)])
    return pd.DataFrame(rows)


def _by_date(out):
    return out.set_index(out["timestamp"].dt.date)


# --- structure ---


def test_continuous_has_required_columns():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    assert list(out.columns) == CONTINUOUS_COLUMNS


def test_continuous_timestamps_unique():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    assert out["timestamp"].is_unique


def test_active_contract_never_missing():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    assert out["active_contract"].notna().all()
    assert (out["active_contract"].astype(str) != "").all()


def test_active_contract_switches_on_roll_date():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    d = out["timestamp"].dt.date
    assert (out.loc[d < ROLL, "active_contract"] == "ESH24").all()
    assert (out.loc[d >= ROLL, "active_contract"] == "ESM24").all()


def test_roll_flag_true_only_on_roll_date():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    assert int(out["roll_flag"].sum()) == 1
    roll_row = out[out["roll_flag"]]
    assert roll_row["timestamp"].dt.date.iloc[0] == ROLL
    assert roll_row["active_contract"].iloc[0] == "ESM24"


def test_roll_reason_populated_on_roll_date():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    assert out[out["roll_flag"]]["roll_reason"].iloc[0]  # non-empty
    assert (out[~out["roll_flag"]]["roll_reason"] == "").all()


def test_input_raw_df_not_mutated():
    df = _seam_df()
    before = df.copy(deep=True)
    build_continuous_futures(df, ES, "ratio")
    pd.testing.assert_frame_equal(df, before)


def test_build_is_deterministic():
    df = _seam_df()
    pd.testing.assert_frame_equal(
        build_continuous_futures(df, ES, "ratio"),
        build_continuous_futures(df, ES, "ratio"),
    )


# --- ratio adjustment ---


def test_ratio_no_pct_spike_at_roll():
    s = _by_date(build_continuous_futures(_seam_df(), ES, "ratio"))["close_adjusted"]
    seam_return = s[ROLL] / s[PREV] - 1.0
    held_return = _ESM_CLOSE_ROLL / _ESM_CLOSE_PREV - 1.0  # new contract's own return
    raw_gap_return = _ESM_CLOSE_ROLL / _ESH_CLOSE_PREV - 1.0  # the WRONG, spiky one
    assert seam_return == pytest.approx(held_return, rel=1e-12)
    assert abs(seam_return - raw_gap_return) > 1e-4


def test_ratio_newest_segment_factor_is_one():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    newest = out[out["active_contract"] == "ESM24"]
    assert (newest["adjustment_factor"] == 1.0).all()


def test_ratio_older_segment_factor_is_multiplicative():
    out = build_continuous_futures(_seam_df(), ES, "ratio")
    older = out[out["active_contract"] == "ESH24"]
    assert older["adjustment_factor"].nunique() == 1
    assert older["adjustment_factor"].iloc[0] == pytest.approx(_ESM_CLOSE_PREV / _ESH_CLOSE_PREV)
    assert np.allclose(older["close_adjusted"], older["close_raw"] * older["adjustment_factor"])


def test_ratio_raw_prices_unchanged():
    s = _by_date(build_continuous_futures(_seam_df(), ES, "ratio"))
    assert s.loc[PREV, "close_raw"] == pytest.approx(_ESH_CLOSE_PREV)   # held ESH24 close
    assert s.loc[ROLL, "close_raw"] == pytest.approx(_ESM_CLOSE_ROLL)   # held ESM24 close


# --- Panama adjustment ---


def test_panama_no_phantom_pnl_at_roll():
    s = _by_date(build_continuous_futures(_seam_df(), ES, "panama"))["close_adjusted"]
    seam_diff = s[ROLL] - s[PREV]
    held_diff = _ESM_CLOSE_ROLL - _ESM_CLOSE_PREV       # new contract's own point change (1.0)
    raw_gap_diff = _ESM_CLOSE_ROLL - _ESH_CLOSE_PREV     # the WRONG, phantom one (101.0)
    assert seam_diff == pytest.approx(held_diff)
    assert abs(seam_diff - raw_gap_diff) > 1e-6


def test_panama_newest_segment_factor_is_zero():
    out = build_continuous_futures(_seam_df(), ES, "panama")
    newest = out[out["active_contract"] == "ESM24"]
    assert (newest["adjustment_factor"] == 0.0).all()


def test_panama_older_segment_factor_is_additive():
    out = build_continuous_futures(_seam_df(), ES, "panama")
    older = out[out["active_contract"] == "ESH24"]
    assert older["adjustment_factor"].iloc[0] == pytest.approx(_ESM_CLOSE_PREV - _ESH_CLOSE_PREV)
    assert np.allclose(older["close_adjusted"], older["close_raw"] + older["adjustment_factor"])


def test_panama_raw_prices_unchanged():
    s = _by_date(build_continuous_futures(_seam_df(), ES, "panama"))
    assert s.loc[PREV, "close_raw"] == pytest.approx(_ESH_CLOSE_PREV)
    assert s.loc[ROLL, "close_raw"] == pytest.approx(_ESM_CLOSE_ROLL)


# --- error handling ---


def test_unsupported_adjustment_method_raises():
    with pytest.raises(ContinuousBuildError):
        build_continuous_futures(_seam_df(), ES, "bogus")


def test_missing_overlap_at_roll_seam_raises():
    # ESM24 only starts on the roll date -> no common prior session with ESH24.
    esh = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    esm = list(pd.date_range("2024-03-07", "2024-03-15", freq="B"))
    rows = _rows("ESH24", esh, 1000, None, EXP_H24, price=[5000 + i for i in range(len(esh))])
    rows += _rows("ESM24", esm, 1000, None, EXP_M24, price=[5100 + i for i in range(len(esm))])
    with pytest.raises(ContinuousBuildError):
        build_continuous_futures(pd.DataFrame(rows), ES, "ratio")


# --------------------------------------------------------------------------- #
# Reproducibility hash (Commit 5)
# --------------------------------------------------------------------------- #


def test_hash_same_for_same_inputs():
    df = _seam_df()
    assert continuous_config_hash(df, ES, "ratio") == continuous_config_hash(df, ES, "ratio")


def test_hash_stable_for_unsorted_raw():
    df = _seam_df()
    shuffled = df.sample(frac=1, random_state=5).reset_index(drop=True)
    assert continuous_config_hash(shuffled, ES, "ratio") == continuous_config_hash(df, ES, "ratio")


def test_hash_changes_with_adjustment_method():
    df = _seam_df()
    assert continuous_config_hash(df, ES, "ratio") != continuous_config_hash(df, ES, "panama")


def test_hash_changes_with_fallback_days_before_expiry():
    df = _seam_df()
    other = _es_spec(**{"rollover.fallback_days_before_expiry": 5})
    assert continuous_config_hash(df, ES, "ratio") != continuous_config_hash(df, other, "ratio")


def test_hash_changes_with_raw_prices():
    df = _seam_df()
    changed = _seam_df()
    for col in ("open", "high", "low", "close"):  # shift one bar coherently
        changed.loc[0, col] = changed.loc[0, col] + 5.0
    assert continuous_config_hash(df, ES, "ratio") != continuous_config_hash(changed, ES, "ratio")


# --------------------------------------------------------------------------- #
# End-to-end Phase 1 pipeline (Commit 5)
# --------------------------------------------------------------------------- #


def test_end_to_end_phase1_pipeline(tmp_path):
    raw = _seam_df()

    # 1. validate raw
    norm = validate_raw_futures(raw)
    assert len(norm) == len(raw)

    # 2. roll schedule
    events = compute_roll_schedule(raw, ES)
    assert len(events) == 1 and events[0].from_contract == "ESH24"

    # 3-4. build both adjustments
    ratio = build_continuous_futures(raw, ES, "ratio")
    panama = build_continuous_futures(raw, ES, "panama")

    # 5. write + read both back
    store = RawFuturesStore(tmp_path)
    ratio_path = store.write_continuous(ratio, "synthetic")
    panama_path = store.write_continuous(panama, "synthetic")
    assert ratio_path != panama_path and ratio_path.exists() and panama_path.exists()
    pd.testing.assert_frame_equal(
        store.read_continuous("ES", "synthetic", "ratio"), finalize_continuous(ratio)
    )
    pd.testing.assert_frame_equal(
        store.read_continuous("ES", "synthetic", "panama"), finalize_continuous(panama)
    )

    # 6. raw and adjusted remain separate (older segment adjusted != raw)
    older = ratio[ratio["active_contract"] == "ESH24"]
    assert not np.allclose(older["close_raw"], older["close_adjusted"])
    assert np.allclose(older["close_raw"], [_ESH_CLOSE_PREV - (7 - i) for i in range(len(older))])

    # 7. no artificial roll seam spike (ratio reflects the held return)
    s = _by_date(ratio)["close_adjusted"]
    assert s[ROLL] / s[PREV] - 1.0 == pytest.approx(_ESM_CLOSE_ROLL / _ESM_CLOSE_PREV - 1.0, rel=1e-12)

    # 8. deterministic output + stable hash (incl. row reordering)
    pd.testing.assert_frame_equal(build_continuous_futures(raw, ES, "ratio"), ratio)
    shuffled = raw.sample(frac=1, random_state=3).reset_index(drop=True)
    assert continuous_config_hash(shuffled, ES, "ratio") == continuous_config_hash(raw, ES, "ratio")
