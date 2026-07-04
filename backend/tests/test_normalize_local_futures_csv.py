"""
Tests for scripts/normalize_local_futures_csv.py (local CSV normalizer).

Runs the script as a subprocess (it is a CLI, not a package module) against
the synthetic fixtures only.  Pins: per-root output files, the canonical
12-column schema, sort order, the round-trip invariant (output re-validates
through the loader), the all-or-nothing failure contract (invalid input
writes nothing), and that inputs are never mutated.
"""

import csv
import shutil
import subprocess
import sys
from pathlib import Path

from app.datastore import REQUIRED_COLUMNS, load_futures_bars_csv

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "normalize_local_futures_csv.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "futures_csv"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_es_fixture_normalizes_to_output_csv(tmp_path):
    result = _run(
        "--input", str(FIXTURES_DIR / "esm25.csv"), "--output-dir", str(tmp_path)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    out = tmp_path / "ES_daily.csv"
    assert out.is_file()
    rows = _read_rows(out)
    assert len(rows) == 5
    assert all(r["root_symbol"] == "ES" for r in rows)
    assert "ES_daily.csv" in result.stdout
    assert "RESULT: OK" in result.stdout


def test_nq_fixture_normalizes_to_output_csv(tmp_path):
    result = _run(
        "--input", str(FIXTURES_DIR / "nqm25.csv"), "--output-dir", str(tmp_path)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    rows = _read_rows(tmp_path / "NQ_daily.csv")
    assert len(rows) == 5
    # The NQ fixture has blank open_interest cells; blank must be preserved.
    assert all(r["open_interest"] == "" for r in rows)


def test_folder_input_writes_one_csv_per_root(tmp_path):
    result = _run("--input", str(FIXTURES_DIR), "--output-dir", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ES_daily.csv",
        "NQ_daily.csv",
    ]


def test_merged_multi_contract_rows_are_sorted(tmp_path):
    # Two files, interleaved contracts, out-of-order timestamps: the output
    # order must come from the script's sort, not from input order.
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    header = ",".join(REQUIRED_COLUMNS)
    tail = ",ES,{c},{e},synthetic,America/Chicago"
    esu = "2025-06-10T21:00:00+00:00,6050.0,6055.0,6045.0,6052.0,1000," + tail.format(
        c="ESU25", e="2025-09-19"
    )
    esm_late = "2025-06-11T21:00:00+00:00,6010.5,6015.0,6002.25,6006.75,1180000," + tail.format(
        c="ESM25", e="2025-06-20"
    )
    esm_early = "2025-06-09T21:00:00+00:00,5998.0,6006.5,5990.25,6004.25,1200000," + tail.format(
        c="ESM25", e="2025-06-20"
    )
    (in_dir / "a.csv").write_text(f"{header}\n{esu}\n", encoding="utf-8")
    (in_dir / "b.csv").write_text(f"{header}\n{esm_late}\n{esm_early}\n", encoding="utf-8")
    result = _run("--input", str(in_dir), "--output-dir", str(out_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    rows = _read_rows(out_dir / "ES_daily.csv")
    assert [(r["contract_symbol"], r["timestamp"]) for r in rows] == [
        ("ESM25", "2025-06-09T21:00:00+00:00"),
        ("ESM25", "2025-06-11T21:00:00+00:00"),
        ("ESU25", "2025-06-10T21:00:00+00:00"),
    ]


def test_output_columns_match_normalized_schema(tmp_path):
    result = _run(
        "--input", str(FIXTURES_DIR / "esm25.csv"), "--output-dir", str(tmp_path)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with (tmp_path / "ES_daily.csv").open("r", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == REQUIRED_COLUMNS


def test_output_revalidates_through_loader(tmp_path):
    result = _run("--input", str(FIXTURES_DIR), "--output-dir", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("ES_daily.csv", "NQ_daily.csv"):
        bars = load_futures_bars_csv(tmp_path / name)
        assert len(bars) == 5


def test_invalid_input_fails_and_writes_nothing(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "esm25.csv", in_dir / "esm25.csv")
    (in_dir / "bad.csv").write_text("timestamp,open\n2025-06-09,1\n", encoding="utf-8")
    result = _run("--input", str(in_dir), "--output-dir", str(out_dir))
    assert result.returncode != 0
    assert "nothing written" in result.stdout
    assert not out_dir.exists() or not list(out_dir.iterdir())


def test_duplicate_bars_across_files_fail_and_write_nothing(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "esm25.csv", in_dir / "a.csv")
    shutil.copy(FIXTURES_DIR / "esm25.csv", in_dir / "b.csv")
    result = _run("--input", str(in_dir), "--output-dir", str(out_dir))
    assert result.returncode != 0
    assert "duplicate" in result.stdout
    assert not out_dir.exists() or not list(out_dir.iterdir())


def test_output_colliding_with_input_file_is_rejected(tmp_path):
    # Re-normalizing a previous output in place must fail, not truncate it.
    src = tmp_path / "ES_daily.csv"
    shutil.copy(FIXTURES_DIR / "esm25.csv", src)
    before = src.read_bytes()
    result = _run("--input", str(src), "--output-dir", str(tmp_path))
    assert result.returncode != 0
    assert "also an input file" in result.stdout
    assert src.read_bytes() == before


def test_output_dir_inside_input_folder_is_rejected(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "esm25.csv", in_dir / "esm25.csv")
    result = _run("--input", str(in_dir), "--output-dir", str(in_dir / "out"))
    assert result.returncode != 0
    assert "inside input folder" in result.stdout


def test_input_files_not_mutated(tmp_path):
    before = {p.name: p.read_bytes() for p in FIXTURES_DIR.glob("*.csv")}
    result = _run("--input", str(FIXTURES_DIR), "--output-dir", str(tmp_path))
    assert result.returncode == 0
    after = {p.name: p.read_bytes() for p in FIXTURES_DIR.glob("*.csv")}
    assert before == after
