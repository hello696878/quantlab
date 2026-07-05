"""
Phase 7 commit 1 — local futures ingestion helpers.

Covers the pure, in-memory helpers only (frame builder, result dataclasses,
per-contract hashing / verify).  No store writes, no CLI, no ingestion log yet
(those land in later commits).  Synthetic fixtures + ``tmp_path`` only; no
network; nothing written outside ``tmp_path``.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import pandas as pd
import pytest

from app.datastore.daily_bar import FuturesDailyBar
from app.datastore.csv_fixtures import load_futures_bars_csv
from app.datastore.ingest import (
    ContractIngestResult,
    IngestReport,
    compute_contract_version_hashes,
    contract_group_key,
    daily_bars_to_frame,
    verify_contract_frame_hash,
)
from app.datastore.store import (
    REQUIRED_COLUMNS,
    raw_data_version_hash,
    validate_raw_futures,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "futures_csv"
ESM25 = FIXTURES / "esm25.csv"
NQM25 = FIXTURES / "nqm25.csv"

# repo layout: backend/tests/<this> -> parents[1] = backend, parents[2] = repo root
_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _es_bar(**overrides) -> FuturesDailyBar:
    """A single valid ES daily bar; overridable per test (e.g. open_interest)."""
    fields = dict(
        timestamp=datetime.datetime(2025, 6, 9, 21, 0, tzinfo=datetime.timezone.utc),
        open=5998.00,
        high=6006.50,
        low=5990.25,
        close=6004.25,
        volume=1_200_000,
        open_interest=1_800_000.0,
        root_symbol="ES",
        contract_symbol="ESM25",
        expiry=datetime.date(2025, 6, 20),
        source="synthetic",
        timezone="America/Chicago",
    )
    fields.update(overrides)
    return FuturesDailyBar(**fields)


# --------------------------------------------------------------------------- #
# daily_bars_to_frame
# --------------------------------------------------------------------------- #


def test_daily_bars_to_frame_has_exactly_required_columns():
    frame = daily_bars_to_frame([_es_bar()])
    assert list(frame.columns) == REQUIRED_COLUMNS


def test_daily_bars_to_frame_passes_validate_raw_futures():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    norm = validate_raw_futures(frame)  # must not raise
    assert len(norm) == 5
    assert set(norm["contract_symbol"]) == {"ESM25"}


def test_daily_bars_to_frame_open_interest_none_becomes_nan_and_validates():
    frame = daily_bars_to_frame([_es_bar(open_interest=None)])
    assert frame["open_interest"].isna().all()
    norm = validate_raw_futures(frame)  # nullable OI accepted
    assert norm["open_interest"].isna().all()


def test_daily_bars_to_frame_from_fixture_roundtrips_source_and_expiry():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    assert set(frame["source"]) == {"synthetic"}
    assert set(frame["root_symbol"]) == {"ES"}
    # expiry values (date objects) are accepted and normalized to tz-aware UTC.
    norm = validate_raw_futures(frame)
    assert str(norm["expiry"].dt.tz) == "UTC"


# --------------------------------------------------------------------------- #
# grouping + per-contract hashing
# --------------------------------------------------------------------------- #


def test_two_fixtures_group_into_two_contracts():
    bars = load_futures_bars_csv(ESM25) + load_futures_bars_csv(NQM25)
    frame = daily_bars_to_frame(bars)
    results = compute_contract_version_hashes(frame)
    assert len(results) == 2
    assert {r.root_symbol for r in results} == {"ES", "NQ"}
    assert {r.contract_symbol for r in results} == {"ESM25", "NQM25"}
    assert all(isinstance(r, ContractIngestResult) for r in results)
    assert all(r.rows == 5 for r in results)
    assert all(r.path == "" for r in results)  # no writes in this commit


def test_per_contract_version_hash_is_stable():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    first = compute_contract_version_hashes(frame)
    second = compute_contract_version_hashes(frame)
    assert [r.version_hash for r in first] == [r.version_hash for r in second]
    assert len(first) == 1 and len(first[0].version_hash) == 64  # sha256 hex


def test_reordered_rows_hash_the_same_after_validation():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    shuffled = frame.iloc[::-1].reset_index(drop=True)
    # frames differ in row order pre-validation ...
    assert not frame.equals(shuffled)
    # ... but the canonical hash (validation sorts first) is identical.
    assert raw_data_version_hash(frame) == raw_data_version_hash(shuffled)
    assert (
        compute_contract_version_hashes(frame)[0].version_hash
        == compute_contract_version_hashes(shuffled)[0].version_hash
    )


def test_changing_close_price_changes_hash():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    bumped = frame.copy()
    bumped.loc[0, "close"] = float(bumped.loc[0, "close"]) + 0.25
    assert (
        compute_contract_version_hashes(frame)[0].version_hash
        != compute_contract_version_hashes(bumped)[0].version_hash
    )


def test_hash_computed_on_canonical_validated_frame():
    # compute_contract_version_hashes must equal hashing the validated group.
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    norm = validate_raw_futures(frame)
    expected = raw_data_version_hash(norm)
    assert compute_contract_version_hashes(frame)[0].version_hash == expected


# --------------------------------------------------------------------------- #
# contract_group_key + verify_contract_frame_hash
# --------------------------------------------------------------------------- #


def test_contract_group_key_single_contract():
    frame = validate_raw_futures(daily_bars_to_frame(load_futures_bars_csv(ESM25)))
    assert contract_group_key(frame) == ("synthetic", "ES", "ESM25")


def test_contract_group_key_rejects_multiple_contracts():
    bars = load_futures_bars_csv(ESM25) + load_futures_bars_csv(NQM25)
    frame = validate_raw_futures(daily_bars_to_frame(bars))
    with pytest.raises(ValueError):
        contract_group_key(frame)


def test_verify_contract_frame_hash_true_and_false():
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    reordered = frame.iloc[::-1].reset_index(drop=True)
    assert verify_contract_frame_hash(frame, reordered) is True

    bumped = frame.copy()
    bumped.loc[0, "close"] = float(bumped.loc[0, "close"]) + 0.25
    assert verify_contract_frame_hash(frame, bumped) is False


# --------------------------------------------------------------------------- #
# dataclasses
# --------------------------------------------------------------------------- #


def test_result_dataclasses_are_frozen():
    r = ContractIngestResult(
        root_symbol="ES", contract_symbol="ESM25", source="synthetic",
        rows=5, version_hash="deadbeef",
    )
    assert r.path == ""
    with pytest.raises(Exception):
        r.rows = 6  # frozen
    report = IngestReport(
        input_files=["esm25.csv"], base_dir="<tmp>", roots=["ES"],
        contracts=[r], rows_written=5,
    )
    assert report.warnings == []
    with pytest.raises(Exception):
        report.rows_written = 0  # frozen


# --------------------------------------------------------------------------- #
# safety: no writes, no repo artifacts, no forbidden imports
# --------------------------------------------------------------------------- #


def test_helpers_write_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bars = load_futures_bars_csv(ESM25) + load_futures_bars_csv(NQM25)
    frame = daily_bars_to_frame(bars)
    compute_contract_version_hashes(frame)
    verify_contract_frame_hash(frame, frame)
    # the helpers must not have written anything to the working directory.
    assert list(tmp_path.iterdir()) == []


def test_no_repo_root_data_or_artifacts_created(tmp_path, monkeypatch):
    before_data = (_REPO_ROOT / "data").exists()
    before_artifacts = (_REPO_ROOT / "artifacts").exists()
    before_backend_data = (_BACKEND / "data").exists()
    monkeypatch.chdir(tmp_path)
    frame = daily_bars_to_frame(load_futures_bars_csv(ESM25))
    compute_contract_version_hashes(frame)
    # helpers do no I/O, so none of these existence states may change.
    assert (_REPO_ROOT / "data").exists() == before_data
    assert (_REPO_ROOT / "artifacts").exists() == before_artifacts
    assert (_BACKEND / "data").exists() == before_backend_data
    assert list(tmp_path.iterdir()) == []


def test_ingest_module_no_network_imports():
    src = (_BACKEND / "app" / "datastore" / "ingest.py").read_text(encoding="utf-8")
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|socket|aiohttp)\b", src
    )


def test_ingest_module_no_forbidden_pipeline_imports():
    src = (_BACKEND / "app" / "datastore" / "ingest.py").read_text(encoding="utf-8")
    # no continuous-futures / feature / label / ML / signal / research-CLI wiring
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*"
        r"(futures_continuous|features|labels|ml_signal|signals|futures_backtest|research_cli)\b",
        src,
    )
