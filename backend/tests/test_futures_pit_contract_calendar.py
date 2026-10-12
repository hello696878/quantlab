"""Independent synthetic contract/calendar expectations; no SQLite or network."""
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.futures_pit.adapter import AdapterRequest, preview
from app.futures_pit.calendar import DeclaredCalendar, local_to_utc, timezone_provenance
from app.futures_pit.models import Bar, Snapshot, instant
from app.futures_pit.revisions import envelope_hash, legacy_frame, legacy_status, validate_binding

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"


@pytest.fixture
def corpus():
    return preview(AdapterRequest(provider="local_file", csv_path=str(CORPUS / "bars.csv"),
                                  metadata_path=str(CORPUS / "metadata.json"), calendar_path=str(CORPUS / "calendar.json")))


def test_baseline_contract_and_legacy_label(corpus):
    assert len(corpus.snapshot.bars) == 17
    raw = legacy_frame(corpus.snapshot.bars)
    assert raw.iloc[0].timestamp.isoformat() == "2025-06-09T00:00:00+00:00"
    assert raw.iloc[0].timestamp.tz_convert("America/Chicago").date() == date(2025, 6, 8)
    assert corpus.snapshot.bars[0].session == date(2025, 6, 9)
    assert legacy_status(raw)["status"] == "incomplete"
    with pytest.raises(ValidationError):
        corpus.snapshot.bars[0].close = 1
    assert type(corpus.snapshot.bars) is tuple


@pytest.mark.parametrize("field,value", [("close", True), ("close", "100"), ("close", float("nan")),
    ("close", float("inf")), ("close", 0), ("volume", True), ("volume", 1.0), ("volume", "1"),
    ("volume", -1), ("open_interest", float("nan")), ("open_interest", -1),
    ("session", "2025-06-09T00:00:00Z"), ("session", datetime(2025, 6, 9)),
    ("contract_symbol", "esm25"), ("contract_symbol", "ESN25"), ("expiry", "2025-06-21"),
    ("source", "provider://anything"), ("high", 50), ("revision_id", "v1\n")])
def test_strict_bar_refuses_coercion_and_invalid_values(corpus, field, value):
    payload = corpus.snapshot.bars[0].model_dump(mode="json")
    payload[field] = value
    with pytest.raises((ValueError, ValidationError)):
        Bar.model_validate(payload)


@pytest.mark.parametrize("value", ["2025-06-12T21:00:00", 0, True, datetime(2025, 6, 12)])
def test_no_guessed_knowledge_time(value):
    with pytest.raises(ValueError):
        instant(value)


def test_missing_oi_is_not_zero_and_latest_required_field(corpus):
    payload = corpus.snapshot.bars[0].model_dump(mode="json")
    payload["open_interest"] = None
    missing = Bar.model_validate(payload)
    payload["open_interest"] = 0
    zero = Bar.model_validate(payload)
    assert missing.open_interest is None and zero.open_interest == 0
    assert missing != zero
    assert zero.availability.source_time().isoformat() == "2025-06-10T02:00:00+00:00"
    payload["availability"]["open_interest"] = None
    assert Bar.model_validate(payload).availability.source_time() is None
    assert Bar.model_validate(payload).availability.source_time(oi_required=False).hour == 21


def test_receipt_and_pre_session_availability_refused(corpus):
    payload = corpus.snapshot.model_dump(mode="json")
    payload["bars"][0]["availability"]["local_received_at"] = "2025-06-09T21:00:00Z"
    with pytest.raises(ValueError, match="receipt"):
        Snapshot.model_validate(payload)
    payload = corpus.snapshot.model_dump(mode="json")
    payload["bars"][0]["availability"]["price"] = "2025-06-09T20:00:00Z"
    with pytest.raises(ValueError, match="before session end"):
        validate_binding(Snapshot.model_validate(payload), corpus.calendar)


def test_calendar_operations_and_duration(corpus):
    c = corpus.calendar
    assert c.count("2025-05-29", "2025-06-20") == 16
    assert c.count(date(2025, 6, 9), date(2025, 6, 13)) == 4
    assert c.previous("2025-06-12") == date(2025, 6, 10)
    assert c.next(date(2025, 6, 10)) == date(2025, 6, 12)
    assert c.on_or_before("2025-06-11") == date(2025, 6, 10)
    assert not c.lookup("2025-06-11").open
    assert c.lookup("2025-06-12").duration_seconds == 23 * 3600 - 900
    assert c.lookup("2025-06-13").duration_seconds == 20 * 3600
    assert c.lookup("2025-06-13").early_close
    with pytest.raises(ValueError, match="unknown"):
        c.lookup("2025-06-21")
    with pytest.raises(ValueError):
        c.previous("2025-05-29")
    with pytest.raises(ValueError):
        c.next("2025-06-20")


@pytest.mark.parametrize("change", ["missing", "duplicate", "overlap", "closed_interval", "naive", "bool", "bad_zone"])
def test_invalid_calendar(corpus, change):
    value = corpus.calendar.model_dump(mode="json")
    if change == "missing":
        value["sessions"].pop(2)
    elif change == "duplicate":
        value["sessions"][1]["label"] = "2025-05-29"
    elif change == "overlap":
        value["sessions"][1]["interval"]["start"] = "2025-05-29T20:00:00Z"
    elif change == "closed_interval":
        value["sessions"][2]["interval"] = value["sessions"][0]["interval"]
    elif change == "naive":
        value["sessions"][0]["interval"]["end"] = "2025-05-29T21:00:00"
    elif change == "bool":
        value["sessions"][0]["open"] = 1
    else:
        value["timezone"] = "Guessed/Timezone"
    with pytest.raises(ValueError):
        DeclaredCalendar.model_validate(value)


def test_material_calendar_and_spec_binding(corpus):
    value = corpus.calendar.model_dump(mode="json")
    value["sessions"][15]["interval"]["end"] = "2025-06-13T17:00:00Z"
    changed = DeclaredCalendar.model_validate(value)
    assert changed.fingerprint != corpus.calendar.fingerprint
    assert envelope_hash(corpus.snapshot, changed) != corpus.envelope_hash
    payload = corpus.snapshot.model_dump(mode="json")
    payload["instrument_metadata_hash"] = "0" * 64
    with pytest.raises(ValueError, match="metadata content"):
        envelope_hash(Snapshot.model_validate(payload), corpus.calendar)
    payload = corpus.snapshot.model_dump(mode="json")
    payload["calendar_version"] = "v2"
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_binding(Snapshot.model_validate(payload), corpus.calendar)


def test_real_chicago_dst_gap_fold_and_offset():
    with pytest.raises(ValueError, match="nonexistent"):
        local_to_utc(datetime(2025, 3, 9, 2, 30), "America/Chicago")
    with pytest.raises(ValueError, match="ambiguous"):
        local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago")
    assert local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago", fold=0) == datetime(2025, 11, 2, 6, 30, tzinfo=timezone.utc)
    assert local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago", fold=1) == datetime(2025, 11, 2, 7, 30, tzinfo=timezone.utc)
    assert local_to_utc(datetime(2025, 3, 8, 12), "America/Chicago").hour == 18
    assert local_to_utc(datetime(2025, 3, 9, 12), "America/Chicago").hour == 17
    for fold in (True, 0.0, 2):
        with pytest.raises(ValueError):
            local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago", fold=fold)
    provenance = timezone_provenance("America/Chicago")
    assert provenance["source"] in ("system_TZPATH", "tzdata_package")
    assert provenance["pinned"] is False


def test_dst_duration_does_not_change_session_count():
    # Invented intervals spanning actual US spring/fall changes, not exchange sessions.
    for day, start, end, hours in [
        ("2025-03-09", "2025-03-09T00:00:00Z", "2025-03-09T23:00:00Z", 23),
        ("2025-11-02", "2025-11-01T23:00:00Z", "2025-11-03T00:00:00Z", 25),
    ]:
        c = DeclaredCalendar.model_validate({"schema_version": "declared_futures_calendar_v1", "calendar_id": "dst",
            "version": "v1", "timezone": "America/Chicago", "coverage_start": day, "coverage_end": day,
            "declared_available_at": None, "sessions": [{"label": day, "open": True,
                                                       "interval": {"start": start, "end": end}}]})
        assert c.count(day, day) == 1
        assert c.lookup(day).duration_seconds == hours * 3600


def test_absent_calendar_material_and_duplicate_bars_are_not_accepted(corpus):
    value = corpus.snapshot.model_dump(mode="json")
    value["bars"].append(value["bars"][0])
    with pytest.raises(ValueError, match="duplicate"):
        Snapshot.model_validate(value)
    value = corpus.snapshot.model_dump(mode="json")
    value.pop("calendar_version")
    with pytest.raises(ValueError):
        Snapshot.model_validate(value)
    value = corpus.snapshot.model_dump(mode="json")
    value["bars"][0]["session"] = "2025-06-11"
    with pytest.raises(ValueError, match="closed"):
        validate_binding(Snapshot.model_validate(value), corpus.calendar)


def test_unknown_calendar_availability_and_price_basis_remain_unknown(corpus):
    c = DeclaredCalendar.model_validate({**corpus.calendar.model_dump(mode="json"), "declared_available_at": None})
    s = Snapshot.model_validate({**corpus.snapshot.model_dump(mode="json"), "price_basis": "unknown"})
    validate_binding(s, c)
    assert c.declared_available_at is None and s.price_basis == "unknown"
    assert envelope_hash(s, c) != corpus.envelope_hash
