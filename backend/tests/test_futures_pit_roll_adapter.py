from datetime import date
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pandas as pd
import pytest

from app.datastore.ingest import preview_futures_source
from app.datastore.futures_continuous import build_continuous_futures, compute_roll_schedule, continuous_config_hash, RollScheduleError
from app.datastore.store import raw_data_version_hash
from app.futures_pit import adapter
from app.futures_pit.adapter import AdapterFailure, AdapterRequest, CSV_COLUMNS, parse_csv, preview
from app.futures_pit.calendar import DeclaredCalendar
from app.futures_pit.diagnostics import derived_identity, validate_continuous
from app.futures_pit.models import Snapshot
from app.futures_pit.revisions import as_of, legacy_frame
from app.futures_pit.roll import decision_eligibility
from app.instruments import FuturesSpec, get_instrument

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"
ROOT = Path(__file__).parents[2]


def request(root=CORPUS):
    return AdapterRequest(provider="local_file", csv_path=str(root / "bars.csv"),
                          metadata_path=str(root / "metadata.json"), calendar_path=str(root / "calendar.json"))


@pytest.fixture
def data():
    result = preview_futures_source(request())
    return result, legacy_frame(result.snapshot.bars), get_instrument("ES")


def spec_with(spec, **changes):
    value = spec.model_dump(mode="json")
    value["rollover"].update(changes)
    return FuturesSpec.model_validate(value)


def test_explicit_calendar_roll_and_hand_computable_seams(data):
    result, raw, spec = data
    event, = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    assert event.decision_date == date(2025, 6, 12)
    assert event.roll_date == date(2025, 6, 13)
    assert event.metadata["classification"] == "retrospective"
    assert event.metadata["calendar_hash"] == result.calendar.fingerprint
    for method, prior_close, current_close, factor in [("ratio", 110, 111, 1.1), ("panama", 110, 111, 10), ("none", 100, 111, 1)]:
        curve = build_continuous_futures(raw, spec, method, declared_calendar=result.calendar)
        prior = curve.loc[curve.timestamp == pd.Timestamp("2025-06-12", tz="UTC")].iloc[0]
        current = curve.loc[curve.timestamp == pd.Timestamp("2025-06-13", tz="UTC")].iloc[0]
        assert prior.close_raw == 100 and current.close_raw == 111
        assert prior.close_adjusted == pytest.approx(prior_close)
        assert current.close_adjusted == current_close
        assert prior.adjustment_factor == pytest.approx(factor)
        assert current.roll_flag and not prior.roll_flag
        findings = validate_continuous(curve, raw, spec, result.calendar)
        assert not any(f["severity"] == "error" for f in findings)
        assert any(f["code"] == "missing_expected_session" and f["session"] == "2025-06-10" for f in findings)
        assert not any(f.get("session") == "2025-06-11" for f in findings)
        seam, = [f for f in findings if f["code"] == "between_contract_seam"]
        assert seam["raw_jump"] == pytest.approx(0.11)


def test_expected_missing_day_resets_confirmation_not_a_holiday(data):
    result, raw, spec = data
    raw.loc[(raw.contract_symbol == "ESU25") & (raw.timestamp == pd.Timestamp("2025-06-09", tz="UTC")), ["volume", "open_interest"]] = 200
    spec = spec_with(spec, confirmation_days=2)
    event, = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    assert event.decision_date == date(2025, 6, 13)
    assert event.roll_date == date(2025, 6, 16)
    legacy, = compute_roll_schedule(raw, spec)
    assert legacy.decision_date == date(2025, 6, 12)


@pytest.mark.parametrize("symbol,day", [("ESU25", "2025-06-13"), ("ESM25", "2025-06-13"), ("ESM25", "2025-06-12"), ("ESU25", "2025-06-12")])
def test_missing_required_roll_or_previous_quote_refused(data, symbol, day):
    result, raw, spec = data
    cut = raw.loc[~((raw.contract_symbol == symbol) & (raw.timestamp == pd.Timestamp(day, tz="UTC")))]
    # Removing a decision quote changes the candidate to the next session; explicitly
    # force fallback to June 13 so both required seam/roll refusal cases are exercised.
    spec = spec_with(spec, confirmation_days=50, fallback_days_before_expiry=7)
    with pytest.raises(RollScheduleError, match="required quote missing"):
        compute_roll_schedule(cut, spec, declared_calendar=result.calendar)


def test_calendar_day_fallback_and_quote_integrity(data):
    result, raw, spec = data
    row = raw.loc[(raw.contract_symbol == "ESM25") & (raw.timestamp == pd.Timestamp("2025-06-09", tz="UTC"))].copy()
    row["timestamp"] = pd.Timestamp("2025-06-10", tz="UTC")
    raw = pd.concat([raw, row], ignore_index=True)
    for days, roll_day, decision in [(8, date(2025, 6, 12), date(2025, 6, 10)), (9, date(2025, 6, 10), date(2025, 6, 9))]:
        selected = spec_with(spec, confirmation_days=50, fallback_days_before_expiry=days)
        event, = compute_roll_schedule(raw, selected, declared_calendar=result.calendar)
        assert event.roll_date == roll_day and event.decision_date == decision
        assert event.metadata["fallback_units"] == "calendar_days"
        assert event.metadata["fallback_used"] is True


def test_as_of_eligible_prefix_keeps_past_roll(data):
    result, raw, spec = data
    correction = preview(AdapterRequest(provider="local_file", csv_path=str(CORPUS / "correction.csv"),
                                        metadata_path=str(CORPUS / "correction-metadata.json"), calendar_path=str(CORPUS / "calendar.json")))
    cutoff = "2025-06-14T12:00:00Z"
    first = as_of((result.snapshot,), cutoff, "declared_source")
    appended = as_of((result.snapshot, correction.snapshot), cutoff, "declared_source")
    assert first.bars == appended.bars
    early = compute_roll_schedule(legacy_frame(first.bars), spec, declared_calendar=result.calendar)
    late = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    assert [(e.decision_date, e.roll_date) for e in early] == [(date(2025, 6, 12), date(2025, 6, 13))]
    assert early == late


def test_decision_audit_delayed_oi_is_not_available_for_overnight_roll(data):
    result, raw, spec = data
    event, = compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    assert not decision_eligibility(event, result.snapshot.bars, result.calendar, "declared_source", "2025-06-12T21:45:00Z")["eligible"]
    assert not decision_eligibility(event, result.snapshot.bars, result.calendar, "declared_source", "2025-06-13T03:00:00Z")["eligible"]
    value = result.snapshot.model_dump(mode="json")
    for bar in value["bars"]:
        if bar["session"] == "2025-06-12":
            bar["availability"] = {"price": "2025-06-12T21:15:00Z", "volume": "2025-06-12T21:30:00Z",
                                   "open_interest": "2025-06-12T21:30:00Z", "local_received_at": "2025-06-12T21:40:00Z"}
    bars = Snapshot.model_validate(value).bars
    assert decision_eligibility(event, bars, result.calendar, "declared_source", "2025-06-12T21:45:00Z")["eligible"]
    assert decision_eligibility(event, bars, result.calendar, "local_observed", "2025-06-12T21:45:00Z")["eligible"]
    assert not decision_eligibility(event, bars, result.calendar, "local_observed", "2025-06-12T21:35:00Z")["eligible"]


@pytest.mark.parametrize("defect", ["order", "duplicate", "flag", "raw", "adjusted", "factor", "nonfinite", "spike"])
def test_continuous_findings_never_repair(data, defect):
    result, raw, spec = data
    curve = build_continuous_futures(raw, spec, declared_calendar=result.calendar)
    if defect == "order":
        curve = curve.iloc[::-1].copy()
    elif defect == "duplicate":
        curve = pd.concat([curve, curve.iloc[[0]]], ignore_index=True)
    elif defect == "flag":
        curve.loc[curve.roll_flag, "roll_flag"] = False
    else:
        column = {"raw": "close_raw", "adjusted": "close_adjusted", "factor": "adjustment_factor",
                  "nonfinite": "close_raw", "spike": "close_raw"}[defect]
        curve.loc[1, column] = float("inf") if defect == "nonfinite" else 10
    original = curve.copy(deep=True)
    findings = validate_continuous(curve, raw, spec, result.calendar)
    assert any(f["severity"] == "error" for f in findings)
    pd.testing.assert_frame_equal(curve, original)


def test_legacy_hash_and_no_calendar_behavior_still_identical(data):
    result, raw, spec = data
    legacy_hash = raw_data_version_hash(raw)
    assert legacy_hash == raw_data_version_hash(raw.iloc[::-1])
    assert compute_roll_schedule(raw, spec) == compute_roll_schedule(raw, spec, declared_calendar=None)
    pd.testing.assert_frame_equal(build_continuous_futures(raw, spec), build_continuous_futures(raw, spec, declared_calendar=None))
    old_identity = continuous_config_hash(raw, spec, "ratio")
    calendar_identity = derived_identity(result.envelope_hash, result.calendar, spec, "ratio")
    assert old_identity != calendar_identity and len(calendar_identity) == 64


def test_disabled_provider_fails_before_io_network_or_env(monkeypatch):
    monkeypatch.setenv("FUTURES_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("GLOBE_FRED_ENABLED", "true")
    monkeypatch.setenv("FRED_API_KEY", "not-used")
    def forbidden(*a, **k):
        pytest.fail("disabled adapter attempted I/O")
    monkeypatch.setattr(adapter, "read_input", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    with pytest.raises(AdapterFailure, match="no network") as error:
        preview_futures_source(AdapterRequest(provider="external", csv_path="provider://inert"))
    assert error.value.code == "provider_disabled"


@pytest.mark.parametrize("contents", [b"", b"date,close\n2025-06-12,1\n", b"x" * (256 * 1024 + 1),
    (",".join(CSV_COLUMNS) + ",close\n").encode(), (",".join(CSV_COLUMNS) + "\nshort\n").encode(),
    b'"unclosed', b"\xff"], ids=["empty", "wrong_layout", "oversized", "duplicate_column", "short_row", "bad_quote", "bad_utf8"])
def test_bounded_malformed_csv_refused(contents):
    with pytest.raises(ValueError):
        parse_csv(contents)


def test_preview_source_immutability_and_no_outputs(tmp_path):
    for name in ("bars.csv", "metadata.json", "calendar.json"):
        (tmp_path / name).write_bytes((CORPUS / name).read_bytes())
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    result = preview(request(tmp_path))
    after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    assert before == after
    assert dict(result.physical_hashes)["csv"] == hashlib.sha256(before["bars.csv"][0]).hexdigest()
    assert "Inspection time is not historical local receipt" in result.limitations


def test_hardlink_and_material_mutation_refused(tmp_path, monkeypatch):
    for name in ("bars.csv", "metadata.json", "calendar.json"):
        (tmp_path / name).write_bytes((CORPUS / name).read_bytes())
    os.link(tmp_path / "bars.csv", tmp_path / "alias.csv")
    with pytest.raises(AdapterFailure):
        preview(request(tmp_path))
    (tmp_path / "alias.csv").unlink()
    real = adapter.read_input
    calls = 0
    def changing(path):
        nonlocal calls
        raw = real(path)
        calls += 1
        if calls == 3:
            p = tmp_path / "metadata.json"
            p.write_bytes(p.read_bytes() + b"\n")
        return raw
    monkeypatch.setattr(adapter, "read_input", changing)
    with pytest.raises(AdapterFailure, match="changed during preview"):
        preview(request(tmp_path))


def test_physical_symlink_refused(tmp_path):
    link = tmp_path / "linked.csv"
    try:
        link.symlink_to(CORPUS / "bars.csv")
    except OSError as exc:
        pytest.skip(f"physical symlink unavailable in this local context: {exc.winerror if hasattr(exc, 'winerror') else exc.errno}")
    with pytest.raises(AdapterFailure, match="symlink"):
        preview(request().model_copy(update={"csv_path": str(link)}))


def test_invalid_fixture_and_missing_inputs_refused():
    with pytest.raises(AdapterFailure):
        preview(request().model_copy(update={"csv_path": str(CORPUS / "invalid/boolean-price.csv")}))
    with pytest.raises(AdapterFailure) as error:
        preview(AdapterRequest(provider="local_file"))
    assert error.value.code == "incomplete"


@pytest.mark.parametrize("defect", ["duplicate_json", "oversize_json", "deep_json", "traversal", "archive", "directory"])
def test_safe_local_input_bounds_and_paths(tmp_path, defect):
    for name in ("bars.csv", "metadata.json", "calendar.json"):
        (tmp_path / name).write_bytes((CORPUS / name).read_bytes())
    req = request(tmp_path)
    if defect == "duplicate_json":
        (tmp_path / "metadata.json").write_text('{"source":"a","source":"b"}', encoding="utf-8")
    elif defect == "oversize_json":
        (tmp_path / "metadata.json").write_bytes(b" " * (256 * 1024 + 1))
    elif defect == "deep_json":
        (tmp_path / "metadata.json").write_text("[" * 50 + "0" + "]" * 50, encoding="utf-8")
    elif defect == "traversal":
        req = req.model_copy(update={"csv_path": str(tmp_path / ".." / tmp_path.name / "bars.csv")})
    elif defect == "archive":
        req = req.model_copy(update={"csv_path": str(tmp_path / "bars.zip")})
    else:
        (tmp_path / "dir.csv").mkdir()
        req = req.model_copy(update={"csv_path": str(tmp_path / "dir.csv")})
    with pytest.raises(AdapterFailure):
        preview(req)


@pytest.mark.parametrize("value", [True, float("inf"), "100"])
def test_declared_roll_direct_frame_refuses_unsafe_numeric(data, value):
    result, raw, spec = data
    raw["close"] = raw.close.astype(object)
    raw.loc[0, "close"] = value
    with pytest.raises(RollScheduleError):
        compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    with pytest.raises(RollScheduleError):
        build_continuous_futures(raw, spec, declared_calendar=result.calendar)


def test_calendar_coverage_and_instant_roles_not_guessed(data):
    result, raw, spec = data
    raw["timestamp"] += pd.Timedelta(hours=12)
    with pytest.raises(RollScheduleError, match="session labels"):
        compute_roll_schedule(raw, spec, declared_calendar=result.calendar)
    raw = legacy_frame(result.snapshot.bars)
    raw["timestamp"] = raw.timestamp.dt.tz_localize(None)
    with pytest.raises(RollScheduleError, match="session labels"):
        build_continuous_futures(raw, spec, declared_calendar=result.calendar)
    raw = legacy_frame(result.snapshot.bars)
    c = result.calendar.model_dump(mode="json")
    c["coverage_end"] = "2025-06-19"
    c["sessions"].pop()
    with pytest.raises(ValueError, match="coverage unknown"):
        compute_roll_schedule(raw, spec, declared_calendar=DeclaredCalendar.model_validate(c))


def test_valid_nonpositive_panama_levels_are_warnings_not_repaired(data):
    result, raw, spec = data
    raw.loc[raw.contract_symbol == "ESU25", ["open", "high", "low", "close"]] -= 105
    raw.loc[(raw.contract_symbol == "ESM25") & (raw.timestamp == pd.Timestamp("2025-06-09", tz="UTC")),
            ["open", "high", "low", "close"]] -= 90
    curve = build_continuous_futures(raw, spec, "panama", declared_calendar=result.calendar)
    assert curve.iloc[0].close_raw == 9 and curve.iloc[0].close_adjusted == -86
    findings = validate_continuous(curve, raw, spec, result.calendar)
    assert any(f["code"] == "nonpositive_panama_level" for f in findings)
    assert not any(f["severity"] == "error" for f in findings)
    seam, = [f for f in findings if f["code"] == "between_contract_seam"]
    assert seam["adjusted_change"] == 1 and seam["adjusted_change_unit"] == "price_points"


def test_cli_success_and_incomplete_without_fake_data(tmp_path):
    for name in ("bars.csv", "metadata.json", "calendar.json"):
        (tmp_path / name).write_bytes((CORPUS / name).read_bytes())
    args = ["--csv", str(tmp_path / "bars.csv"), "--metadata", str(tmp_path / "metadata.json"),
            "--calendar", str(tmp_path / "calendar.json"), "--as-of", "2025-06-21T12:00:00Z"]
    command = [sys.executable, "-B", str(ROOT / "scripts/validate_futures_point_in_time.py"), *args]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    assert done.returncode == 0 and json.loads(done.stdout)["as_of"]["selected"] == 17
    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    metadata["price_basis"] = "unknown"
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    incomplete = subprocess.run(command, capture_output=True, text=True, check=False)
    assert incomplete.returncode == 3 and json.loads(incomplete.stdout)["status"] == "incomplete"


@pytest.mark.parametrize("args,code,status", [((), 2, "invalid"), (("--provider", "external"), 2, "invalid"),
    (("--demo",), 1, "warning")])
def test_public_cli_acceptance_and_exit_semantics(args, code, status):
    done = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/validate_futures_point_in_time.py"), *args],
                          capture_output=True, text=True, check=False)
    assert done.returncode == code, done.stderr
    summary = json.loads(done.stdout)
    assert summary["status"] == status
    if args == ("--demo",):
        assert summary["restatement_demo"] == {"earlier_close": 100, "later_close": 102}
        assert summary["as_of"]["selected"] == 17
        assert summary["rolls"][0]["effective"] == "2025-06-13"
