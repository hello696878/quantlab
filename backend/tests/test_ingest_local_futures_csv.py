"""
Phase 7 commit 1 — local futures ingestion helpers.

Covers the pure, in-memory helpers only (frame builder, result dataclasses,
per-contract hashing / verify).  No store writes, no CLI, no ingestion log yet
(those land in later commits).  Synthetic fixtures + ``tmp_path`` only; no
network; nothing written outside ``tmp_path``.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest

from app.datastore.daily_bar import FuturesDailyBar
from app.datastore.csv_fixtures import FixtureFormatError, load_futures_bars_csv
from app.datastore.ingest import (
    ContractIngestResult,
    DuplicateIngestError,
    IngestReport,
    compute_contract_version_hashes,
    contract_group_key,
    daily_bars_to_frame,
    ingest_local_futures_csv,
    verify_contract_frame_hash,
)
from app.datastore.store import (
    REQUIRED_COLUMNS,
    RawFuturesStore,
    raw_data_version_hash,
    validate_raw_futures,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "futures_csv"
ESM25 = FIXTURES / "esm25.csv"
NQM25 = FIXTURES / "nqm25.csv"

# repo layout: backend/tests/<this> -> parents[1] = backend, parents[2] = repo root
_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_PATH = _REPO_ROOT / "scripts" / "ingest_local_futures_csv.py"

_CSV_HEADER = ",".join(REQUIRED_COLUMNS)
# a single valid ES row (mirrors esm25.csv row 1); mutated per test
_ES_ROW = (
    "2025-06-09T21:00:00+00:00,5998.00,6006.50,5990.25,6004.25,"
    "1200000,1800000,ES,ESM25,2025-06-20,synthetic,America/Chicago"
)


def _write_csv(path: Path, rows: list[str], header: str = _CSV_HEADER) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def _load_cli():
    """Import the thin CLI module by path (executes its sys.path bootstrap)."""
    spec = importlib.util.spec_from_file_location("ingest_cli_mod", _CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _store_files(base: Path) -> list[Path]:
    """Every data file written under a store base (parquet or csv)."""
    root = base / "raw" / "futures"
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


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


# --------------------------------------------------------------------------- #
# Commit 2 — store-backed ingest orchestrator
# --------------------------------------------------------------------------- #


def test_ingest_single_fixture_into_store(tmp_path):
    base = tmp_path / "store"
    report = ingest_local_futures_csv([ESM25], base_dir=base)
    assert isinstance(report, IngestReport)
    assert report.rows_written == 5
    assert report.roots == ["ES"]
    assert len(report.contracts) == 1
    c = report.contracts[0]
    assert (c.root_symbol, c.contract_symbol, c.source) == ("ES", "ESM25", "synthetic")
    assert c.rows == 5 and len(c.version_hash) == 64
    assert not Path(c.path).is_absolute()  # store-relative, never absolute
    assert _store_files(base)  # something was written under the store


def test_ingest_multiple_contracts_and_roots(tmp_path):
    base = tmp_path / "store"
    report = ingest_local_futures_csv([ESM25, NQM25], base_dir=base)
    assert report.roots == ["ES", "NQ"]
    assert {(c.root_symbol, c.contract_symbol) for c in report.contracts} == {
        ("ES", "ESM25"),
        ("NQ", "NQM25"),
    }
    assert report.rows_written == 10
    assert len(_store_files(base)) == 2


@pytest.mark.parametrize("prefer_parquet", [True, False])
def test_read_back_row_count_and_hash_match(tmp_path, prefer_parquet):
    base = tmp_path / "store"
    report = ingest_local_futures_csv([ESM25], base_dir=base, prefer_parquet=prefer_parquet)
    c = report.contracts[0]
    # re-open a fresh store and confirm the round-trip independently.
    store = RawFuturesStore(base, prefer_parquet=prefer_parquet)
    read_back = store.read_raw("ES", "ESM25", "synthetic")
    assert len(read_back) == c.rows == 5
    assert raw_data_version_hash(read_back) == c.version_hash


def test_source_override_changes_store_namespace(tmp_path):
    base = tmp_path / "store"
    report = ingest_local_futures_csv([ESM25], base_dir=base, source="csv_local")
    assert all(c.source == "csv_local" for c in report.contracts)
    store = RawFuturesStore(base)
    # the overridden namespace exists ...
    assert len(store.read_raw("ES", "ESM25", "csv_local")) == 5
    # ... and the file's original "synthetic" namespace was NOT written.
    assert not any(
        store.raw_path("ES", "ESM25", "synthetic", fmt=fmt).exists()
        for fmt in ("parquet", "csv")
    )


def test_duplicate_ingest_without_overwrite_raises(tmp_path):
    base = tmp_path / "store"
    ingest_local_futures_csv([ESM25], base_dir=base)
    with pytest.raises(DuplicateIngestError):
        ingest_local_futures_csv([ESM25], base_dir=base)


def test_duplicate_failure_leaves_existing_file_unchanged(tmp_path):
    base = tmp_path / "store"
    ingest_local_futures_csv([ESM25], base_dir=base)
    store = RawFuturesStore(base)
    before = raw_data_version_hash(store.read_raw("ES", "ESM25", "synthetic"))

    # a second CSV for the same contract but with a bumped close price.
    bumped_rows = [
        _ES_ROW.replace(",6004.25,", ",6005.25,"),  # close 6004.25 -> 6005.25
    ]
    bumped = _write_csv(tmp_path / "esm25_bumped.csv", bumped_rows)
    with pytest.raises(DuplicateIngestError):
        ingest_local_futures_csv([bumped], base_dir=base)

    after = raw_data_version_hash(store.read_raw("ES", "ESM25", "synthetic"))
    assert after == before  # rejected duplicate never touched the stored file


def test_duplicate_ingest_with_overwrite_succeeds_and_is_identical(tmp_path):
    base = tmp_path / "store"
    first = ingest_local_futures_csv([ESM25], base_dir=base)
    second = ingest_local_futures_csv([ESM25], base_dir=base, overwrite=True)
    assert [c.version_hash for c in first.contracts] == [
        c.version_hash for c in second.contracts
    ]
    assert len(_store_files(base)) == 1  # overwrite, not a duplicate file


def test_invalid_csv_rejected_writes_nothing(tmp_path):
    base = tmp_path / "store"
    # drop the trailing timezone column from header + row -> missing required column
    bad_header = ",".join(REQUIRED_COLUMNS[:-1])
    bad_row = ",".join(_ES_ROW.split(",")[:-1])
    bad = _write_csv(tmp_path / "bad.csv", [bad_row], header=bad_header)
    with pytest.raises(FixtureFormatError):
        ingest_local_futures_csv([bad], base_dir=base)
    assert _store_files(base) == []


def test_off_cycle_contract_rejected_writes_nothing(tmp_path):
    base = tmp_path / "store"
    # ESF25: January (F) is not in the ES quarterly cycle (H, M, U, Z)
    off = _write_csv(
        tmp_path / "esf25.csv",
        ["2025-01-09T21:00:00+00:00,5998.00,6006.50,5990.25,6004.25,"
         "1200000,1800000,ES,ESF25,2025-01-17,synthetic,America/Chicago"],
    )
    with pytest.raises(FixtureFormatError):
        ingest_local_futures_csv([off], base_dir=base)
    assert _store_files(base) == []


def test_expiry_mismatch_rejected_writes_nothing(tmp_path):
    base = tmp_path / "store"
    # on-cycle ESM25 but wrong expiry (spec-derived is 2025-06-20)
    mismatch = _write_csv(
        tmp_path / "esm25_badexp.csv",
        [_ES_ROW.replace(",2025-06-20,", ",2025-06-19,")],
    )
    with pytest.raises(FixtureFormatError):
        ingest_local_futures_csv([mismatch], base_dir=base)
    assert _store_files(base) == []


def test_ingest_writes_only_under_base_dir(tmp_path, monkeypatch):
    base = tmp_path / "store"
    before_data = (_REPO_ROOT / "data").exists()
    before_artifacts = (_REPO_ROOT / "artifacts").exists()
    before_backend_data = (_BACKEND / "data").exists()
    monkeypatch.chdir(tmp_path)
    ingest_local_futures_csv([ESM25, NQM25], base_dir=base)
    # everything written lives under base_dir ...
    assert all(str(p).startswith(str(base)) for p in _store_files(base))
    # ... and no repo-root data/artifacts state changed.
    assert (_REPO_ROOT / "data").exists() == before_data
    assert (_REPO_ROOT / "artifacts").exists() == before_artifacts
    assert (_BACKEND / "data").exists() == before_backend_data


# --------------------------------------------------------------------------- #
# Commit 2 — thin CLI
# --------------------------------------------------------------------------- #


def test_cli_valid_input_returns_zero(tmp_path, capsys):
    base = tmp_path / "store"
    cli = _load_cli()
    rc = cli.main([str(ESM25), "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESULT: OK" in out
    assert "[WRITE] synthetic/ES/ESM25 rows=5" in out
    assert len(_store_files(base)) == 1


def test_cli_source_override_and_overwrite(tmp_path):
    base = tmp_path / "store"
    cli = _load_cli()
    assert cli.main([str(ESM25), "--base-dir", str(base), "--source", "csv_local"]) == 0
    # second run without --overwrite is a duplicate -> nonzero
    assert cli.main([str(ESM25), "--base-dir", str(base), "--source", "csv_local"]) == 1
    # ... with --overwrite it succeeds
    assert cli.main(
        [str(ESM25), "--base-dir", str(base), "--source", "csv_local", "--overwrite"]
    ) == 0


def test_cli_duplicate_without_overwrite_returns_nonzero(tmp_path, capsys):
    base = tmp_path / "store"
    cli = _load_cli()
    assert cli.main([str(ESM25), "--base-dir", str(base)]) == 0
    rc = cli.main([str(ESM25), "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RESULT: FAIL" in out
    assert "DuplicateIngestError" in out


def test_cli_invalid_input_returns_nonzero(tmp_path, capsys):
    base = tmp_path / "store"
    bad_header = ",".join(REQUIRED_COLUMNS[:-1])
    bad_row = ",".join(_ES_ROW.split(",")[:-1])
    bad = _write_csv(tmp_path / "bad.csv", [bad_row], header=bad_header)
    cli = _load_cli()
    rc = cli.main([str(bad), "--base-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RESULT: FAIL" in out
    assert _store_files(base) == []


def test_cli_no_parquet_flag_works(tmp_path):
    base = tmp_path / "store"
    cli = _load_cli()
    rc = cli.main([str(ESM25), "--base-dir", str(base), "--no-parquet"])
    assert rc == 0
    store = RawFuturesStore(base, prefer_parquet=False)
    assert len(store.read_raw("ES", "ESM25", "synthetic")) == 5


def test_cli_script_no_network_or_forbidden_imports():
    src = _CLI_PATH.read_text(encoding="utf-8")
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|socket|aiohttp)\b", src
    )
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*"
        r"(futures_continuous|features|labels|ml_signal|signals|futures_backtest|research_cli)\b",
        src,
    )
    # commit 2 must not add the ingestion log yet
    assert "log_path" not in src and "--log-path" not in src
