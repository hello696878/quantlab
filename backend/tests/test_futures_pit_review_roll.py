"""Independent declared-roll boundary regressions; legacy defaults are untouched."""
from pathlib import Path

import pandas as pd
import pytest

from app.datastore.futures_continuous import (
    RollScheduleError,
    build_continuous_futures,
    compute_roll_schedule,
)
from app.futures_pit.adapter import AdapterRequest, preview
from app.futures_pit.calendar import DeclaredCalendar
from app.futures_pit.revisions import legacy_frame
from app.futures_pit.roll import decision_eligibility
from app.instruments import get_instrument

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"


@pytest.fixture
def data():
    result = preview(AdapterRequest(
        provider="local_file", csv_path=str(CORPUS / "bars.csv"),
        metadata_path=str(CORPUS / "metadata.json"), calendar_path=str(CORPUS / "calendar.json"),
    ))
    return result, legacy_frame(result.snapshot.bars), get_instrument("ES")


def test_decision_audit_rejects_a_substituted_calendar_start(data):
    result, raw, spec = data
    event, = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    cutoff = "2025-06-13T03:15:00Z"
    # The original effective start was June 12 22:00Z: this is already too late.
    assert event.metadata["effective_session_start"] == "2025-06-12T22:00:00+00:00"
    assert decision_eligibility(event, result.snapshot.bars, result.calendar, "local_observed", cutoff)["eligible"] is False
    payload = result.calendar.model_dump(mode="json")
    for session in payload["sessions"]:
        if session["label"] == "2025-06-13":
            session["interval"]["start"] = "2025-06-13T03:30:00Z"
    changed = DeclaredCalendar.model_validate(payload)
    assert changed.calendar_id == result.calendar.calendar_id
    assert changed.version == result.calendar.version
    assert changed.fingerprint != event.metadata["calendar_hash"]
    # Merely moving the start past the known 03:00 receipts cannot qualify
    # an event whose material identity still names the original calendar.
    with pytest.raises(ValueError, match="calendar material mismatch"):
        decision_eligibility(event, result.snapshot.bars, changed, "local_observed", cutoff)


@pytest.mark.parametrize("column,value,dtype", [
    ("volume", 2**63, "uint64"),
    ("volume", 2**53, "int64"),
    ("close", 10**400, "object"),
    ("close", float(2**53), "float64"),
    ("open_interest", 10**400, "object"),
    ("open_interest", float(2**53), "float64"),
], ids=["volume_wrap", "unsafe_volume", "huge_price", "unsafe_price", "huge_oi", "unsafe_oi"])
def test_declared_numeric_bounds_precede_legacy_coercion(data, column, value, dtype):
    result, raw, spec = data
    raw[column] = raw[column].astype(dtype)
    raw.at[0, column] = value
    before = raw.copy(deep=True)
    for operation in (compute_roll_schedule, build_continuous_futures):
        with pytest.raises(RollScheduleError, match="invalid typed declared-mode"):
            operation(raw, spec, declared_calendar=result.calendar)
        pd.testing.assert_frame_equal(raw, before)


def test_exact_volume_boundary_remains_valid(data):
    result, raw, spec = data
    raw.at[0, "volume"] = 2**53 - 1
    event, = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    assert event.roll_date.isoformat() == "2025-06-13"
    curve = build_continuous_futures(raw, spec, declared_calendar=result.calendar)
    assert curve.iloc[0].volume == 2**53 - 1


def test_duplicate_contract_session_from_another_source_is_not_overwritten(data):
    result, raw, spec = data
    duplicate = raw.iloc[[0]].copy()
    duplicate["source"] = "another-source"
    duplicate["volume"] = 1
    duplicate["open_interest"] = 1
    conflicting = pd.concat([raw, duplicate], ignore_index=True)
    for operation in (compute_roll_schedule, build_continuous_futures):
        with pytest.raises(ValueError, match="duplicate rows"):
            operation(conflicting, spec, declared_calendar=result.calendar)
