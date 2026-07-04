"""
Tests for the synthetic CSV fixture loader (ingestion phase I1, fake data only).

Covers: the checked-in ES and NQ fixtures load; missing required column,
unknown root symbol, root/contract mismatch, duplicate rows, and empty files
fail; the input file is never mutated.  Complements
test_futures_daily_bar.py (per-record schema) — this exercises the file
entry path.
"""

import datetime
from pathlib import Path

import pytest

from app.datastore import (
    REQUIRED_COLUMNS,
    FixtureFormatError,
    FuturesDailyBar,
    load_futures_bars_csv,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "futures_csv"


def _es_row(**overrides) -> dict:
    """One valid ES bar as CSV cell strings; failure tests mutate this baseline."""
    row = {
        "timestamp": "2025-06-09T21:00:00+00:00",
        "open": "5998.00",
        "high": "6006.50",
        "low": "5990.25",
        "close": "6004.25",
        "volume": "1200000",
        "open_interest": "1800000",
        "root_symbol": "ES",
        "contract_symbol": "ESM25",
        "expiry": "2025-06-20",
        "source": "synthetic",
        "timezone": "America/Chicago",
    }
    row.update(overrides)
    return row


def _write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> Path:
    columns = columns if columns is not None else REQUIRED_COLUMNS
    lines = [",".join(columns)]
    lines += [",".join(row[c] for c in columns) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- checked-in fixtures load ---


def test_es_fixture_loads():
    bars = load_futures_bars_csv(FIXTURES_DIR / "esm25.csv")
    assert len(bars) == 5
    assert all(isinstance(b, FuturesDailyBar) for b in bars)
    assert all(b.root_symbol == "ES" for b in bars)
    assert all(b.contract_symbol == "ESM25" for b in bars)
    assert all(b.expiry == datetime.date(2025, 6, 20) for b in bars)
    assert all(b.source == "synthetic" for b in bars)
    assert all(b.timezone == "America/Chicago" for b in bars)
    assert bars[0].open_interest == 1_800_000.0
    assert bars[0].timestamp.tzinfo is not None


def test_nq_fixture_loads():
    bars = load_futures_bars_csv(FIXTURES_DIR / "nqm25.csv")
    assert len(bars) == 5
    assert all(b.root_symbol == "NQ" for b in bars)
    assert all(b.contract_symbol == "NQM25" for b in bars)
    # The NQ fixture has blank open_interest cells (nullable OI path).
    assert all(b.open_interest is None for b in bars)
    assert all(b.source == "synthetic" for b in bars)
    assert all(b.timezone == "America/Chicago" for b in bars)


def test_input_file_not_mutated():
    path = FIXTURES_DIR / "esm25.csv"
    before = path.read_bytes()
    load_futures_bars_csv(path)
    assert path.read_bytes() == before


def test_bom_header_is_tolerated(tmp_path):
    # Excel's "CSV UTF-8" saves with a BOM; the header check must not see it.
    path = _write_csv(tmp_path / "bom.csv", [_es_row()])
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    bars = load_futures_bars_csv(path)
    assert len(bars) == 1
    assert bars[0].root_symbol == "ES"


# --- file-level failures ---


def test_missing_required_column_fails(tmp_path):
    columns = [c for c in REQUIRED_COLUMNS if c != "volume"]
    path = _write_csv(tmp_path / "no_volume.csv", [_es_row()], columns=columns)
    with pytest.raises(FixtureFormatError, match="volume"):
        load_futures_bars_csv(path)


def test_empty_file_fails(tmp_path):
    path = _write_csv(tmp_path / "empty.csv", [])
    with pytest.raises(FixtureFormatError, match="no data rows"):
        load_futures_bars_csv(path)


def test_duplicate_rows_fail(tmp_path):
    path = _write_csv(tmp_path / "dup.csv", [_es_row(), _es_row()])
    with pytest.raises(FixtureFormatError, match="duplicate"):
        load_futures_bars_csv(path)


def test_extra_cells_in_row_fail(tmp_path):
    # A shifted row (e.g. unquoted comma) must never load with mislabeled fields.
    path = _write_csv(tmp_path / "ragged.csv", [_es_row()])
    content = path.read_text(encoding="utf-8").rstrip("\n") + ",extra\n"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(FixtureFormatError, match="more cells"):
        load_futures_bars_csv(path)


def test_digit_only_timestamp_fails(tmp_path):
    # Pydantic lax mode would read '1749502800' as Unix epoch seconds; the
    # loader parses timestamps strictly as ISO instead.
    path = _write_csv(tmp_path / "epoch.csv", [_es_row(timestamp="1749502800")])
    with pytest.raises(FixtureFormatError, match="timestamp"):
        load_futures_bars_csv(path)


# --- registry-aware failures (row context in the message) ---


def test_unknown_root_symbol_fails(tmp_path):
    row = _es_row(root_symbol="XX", contract_symbol="XXM25")
    path = _write_csv(tmp_path / "unknown_root.csv", [row])
    with pytest.raises(FixtureFormatError, match="XX"):
        load_futures_bars_csv(path)


def test_mismatched_root_contract_fails(tmp_path):
    row = _es_row(contract_symbol="NQM25")
    path = _write_csv(tmp_path / "mismatch.csv", [row])
    with pytest.raises(FixtureFormatError, match="NQM25"):
        load_futures_bars_csv(path)


def test_off_cycle_contract_month_fails(tmp_path):
    # F (January) is a valid CME code but not in the ES H/M/U/Z cycle.
    row = _es_row(contract_symbol="ESF25")
    path = _write_csv(tmp_path / "off_cycle.csv", [row])
    with pytest.raises(FixtureFormatError, match="cycle"):
        load_futures_bars_csv(path)


def test_expiry_not_matching_spec_fails(tmp_path):
    # 2025-06-13 is a Friday, but not the third Friday the spec derives.
    row = _es_row(expiry="2025-06-13")
    path = _write_csv(tmp_path / "bad_expiry.csv", [row])
    with pytest.raises(FixtureFormatError, match="spec-derived"):
        load_futures_bars_csv(path)


def test_timezone_not_matching_spec_fails(tmp_path):
    row = _es_row(timezone="UTC")
    path = _write_csv(tmp_path / "bad_tz.csv", [row])
    with pytest.raises(FixtureFormatError, match="timezone"):
        load_futures_bars_csv(path)
