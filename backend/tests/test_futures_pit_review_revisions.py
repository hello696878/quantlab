"""Independent small-record revision, identity and immutability regressions."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.datastore.store import raw_data_version_hash
from app.futures_pit.calendar import DeclaredCalendar
from app.futures_pit.models import Availability, Bar, Snapshot, instant
from app.futures_pit.revisions import as_of, compare, envelope_hash, legacy_frame, table_hash

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"


def _availability(when):
    return {field: when for field in ("price", "volume", "open_interest", "local_received_at")}


def _bar(**changes):
    return {
        "source": "synthetic", "root_symbol": "ES", "contract_symbol": "ESM25",
        "session": "2025-06-12", "expiry": "2025-06-20", "revision_id": "v1",
        "supersedes": None, "open": 100, "high": 104, "low": 98, "close": 100,
        "volume": 100, "open_interest": 100,
        "availability": _availability("2025-06-13T03:00:00Z"), **changes,
    }


def _payload(bars):
    declaration = json.loads((CORPUS / "metadata.json").read_text(encoding="utf-8"))
    return {**declaration, "bars": bars}


def _snapshot(bars):
    return Snapshot.model_validate(_payload(bars))


@pytest.fixture
def calendar():
    return DeclaredCalendar.model_validate_json((CORPUS / "calendar.json").read_text(encoding="utf-8"))


def test_snapshot_does_not_retain_callers_nested_dicts_or_bar_list(calendar):
    caller_bar = _bar()
    caller_bars = [caller_bar]
    payload = _payload(caller_bars)
    snapshot = Snapshot.model_validate(payload)
    original_dump = snapshot.model_dump(mode="json")
    original_envelope = envelope_hash(snapshot, calendar)
    original_market = table_hash(snapshot.bars)

    caller_bar["close"] = 103
    caller_bar["availability"]["price"] = "2025-06-19T03:00:00Z"
    payload["license"]["status"] = "unknown"
    caller_bars.append(_bar(session="2025-06-13"))
    caller_bars.clear()

    assert type(snapshot.bars) is tuple and len(snapshot.bars) == 1
    assert snapshot.bars[0].close == 100
    assert snapshot.bars[0].availability.price == datetime(2025, 6, 13, 3, tzinfo=timezone.utc)
    assert snapshot.license.status == "synthetic"
    assert snapshot.model_dump(mode="json") == original_dump
    assert envelope_hash(snapshot, calendar) == original_envelope
    assert table_hash(snapshot.bars) == original_market


def test_mutating_exported_dump_or_frame_cannot_change_snapshot_or_reused_hash(calendar):
    snapshot = _snapshot([_bar()])
    original_envelope = envelope_hash(snapshot, calendar)
    original_market = table_hash(snapshot.bars)
    frame = legacy_frame(snapshot.bars)
    original_legacy = raw_data_version_hash(frame)

    exported = snapshot.model_dump(mode="json")
    exported["bars"][0]["availability"]["open_interest"] = None
    exported["bars"][0]["close"] = 103
    exported["license"]["attribution"] = "changed caller copy"
    exported["bars"].clear()
    frame.loc[0, "close"] = 102
    assert raw_data_version_hash(frame) != original_legacy

    fresh_frame = legacy_frame(snapshot.bars)
    assert len(snapshot.bars) == 1 and snapshot.bars[0].close == 100
    assert snapshot.bars[0].availability.open_interest is not None
    assert fresh_frame.loc[0, "close"] == 100
    assert raw_data_version_hash(fresh_frame) == original_legacy
    assert envelope_hash(snapshot, calendar) == original_envelope
    assert table_hash(snapshot.bars) == original_market


@pytest.mark.parametrize("mode,before,cutoff,equivalent", [
    ("declared_source", "2025-06-19T02:00:00.123455Z", "2025-06-19T02:00:00.123456Z",
     "2025-06-18T21:00:00.123456-05:00"),
    ("local_observed", "2025-06-19T03:00:00.654320Z", "2025-06-19T03:00:00.654321Z",
     "2025-06-18T22:00:00.654321-05:00"),
], ids=["source", "receipt"])
def test_microsecond_cutoff_is_inclusive_and_offset_equivalent(mode, before, cutoff, equivalent):
    original = _snapshot([_bar()])
    correction = _snapshot([_bar(revision_id="v2", supersedes="v1", close=102, availability={
        "price": "2025-06-18T21:15:00Z", "volume": "2025-06-18T21:30:00Z",
        "open_interest": "2025-06-19T02:00:00.123456Z",
        "local_received_at": "2025-06-19T03:00:00.654321Z",
    })])

    early = as_of((original, correction), before, mode)
    exact = as_of((original, correction), cutoff, mode)
    offset = as_of((correction, original), equivalent, mode)
    assert early.bars[0].close == 100 and early.excluded_future == 1
    assert exact.bars[0].close == 102 and exact.excluded_future == 0
    assert offset == exact
    assert exact.cutoff == cutoff.replace("Z", "+00:00")


@pytest.mark.parametrize("mode", ["declared_source", "local_observed"])
def test_disconnected_cycle_is_refused_even_with_an_eligible_root(mode):
    original = _snapshot([_bar()])
    disconnected = _snapshot([
        _bar(revision_id="v2", supersedes="v3", close=102,
             availability=_availability("2025-06-19T03:00:00Z")),
        _bar(revision_id="v3", supersedes="v2", close=103,
             availability=_availability("2025-06-20T03:00:00Z")),
    ])
    with pytest.raises(ValueError, match="disconnected revision cycle"):
        as_of((original, disconnected), "2025-06-18T00:00:00Z", mode)


@pytest.mark.parametrize("value", [
    "0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
], ids=["utc-underflow", "utc-overflow"])
def test_offset_conversion_outside_datetime_range_is_a_validation_error(value):
    with pytest.raises(ValueError, match="supported UTC range"):
        instant(value)
    with pytest.raises(ValidationError, match="supported UTC range"):
        Availability.model_validate(_availability(value))


@pytest.mark.parametrize("changes", [
    {"root_symbol": "UNKNOWN"}, {"contract_symbol": "ES"},
], ids=["unknown-root", "malformed-contract"])
def test_invalid_instrument_declaration_stays_at_model_validation_boundary(changes):
    with pytest.raises(ValidationError):
        Bar.model_validate(_bar(**changes))


@pytest.mark.parametrize("root", ["D:ES", "ES:stream", "es", "ES.."])
def test_root_cannot_become_a_drive_relative_or_stream_spec_locator(monkeypatch, root):
    def forbidden(_root):
        pytest.fail("noncanonical root reached the local instrument registry")
    monkeypatch.setattr("app.futures_pit.models.get_instrument", forbidden)
    with pytest.raises(ValidationError, match="canonical letters/digits"):
        Bar.model_validate(_bar(root_symbol=root))


@pytest.mark.parametrize("new_observation", [False, True], ids=["existing-key", "new-key"])
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reversed"])
def test_compare_resolves_explicit_parents_in_the_same_incoming_batch(new_observation, reverse):
    original = _snapshot([_bar(session="2025-06-09" if new_observation else "2025-06-12")])
    if new_observation:
        first, second = "v1", "v2"
        expected_statuses = {"v1": "new_observation", "v2": "explicit_revision"}
    else:
        first, second = "v2", "v3"
        expected_statuses = {"v2": "explicit_revision", "v3": "explicit_revision"}
    incoming_bars = [
        _bar(revision_id=first, supersedes=None if new_observation else "v1", close=102,
             availability=_availability("2025-06-19T03:00:00Z")),
        _bar(revision_id=second, supersedes=first, close=103,
             availability=_availability("2025-06-20T03:00:00Z")),
    ]
    incoming = _snapshot(list(reversed(incoming_bars)) if reverse else incoming_bars)
    assert {item["revision_id"]: item["status"] for item in compare(original, incoming)} == expected_statuses
    selected = as_of((original, incoming), "2025-06-21T00:00:00Z", "declared_source")
    revised_bar = next(bar for bar in selected.bars if bar.session.isoformat() == "2025-06-12")
    assert revised_bar.close == 103 and revised_bar.revision_id == second
