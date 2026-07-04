"""
Tests for scripts/check_local_futures_csv.py (read-only local CSV smoke script).

Runs the script as a subprocess (it is a CLI, not a package module) and pins
its exit-code contract: 0 when every file validates, nonzero for a missing
path, no CSVs, or an invalid file.  The validation logic itself is covered
by test_futures_csv_fixtures.py; this only exercises the script wrapper.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_local_futures_csv.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "futures_csv"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_fixtures_folder_validates_and_exits_zero():
    result = _run("--path", str(FIXTURES_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: OK" in result.stdout
    assert "ESM25" in result.stdout
    assert "NQM25" in result.stdout
    assert "tick_size" in result.stdout


def test_single_file_validates_and_exits_zero():
    result = _run("--path", str(FIXTURES_DIR / "esm25.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rows:       5" in result.stdout


def test_missing_path_exits_nonzero(tmp_path):
    result = _run("--path", str(tmp_path / "does_not_exist"))
    assert result.returncode != 0
    assert "not found" in result.stdout


def test_folder_without_csv_exits_nonzero(tmp_path):
    result = _run("--path", str(tmp_path))
    assert result.returncode != 0
    assert "no CSV files" in result.stdout


def test_invalid_csv_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("timestamp,open\n2025-06-09,1\n", encoding="utf-8")
    result = _run("--path", str(bad))
    assert result.returncode != 0
    assert "[FAIL]" in result.stdout


def test_directory_named_csv_is_ignored(tmp_path):
    # A *directory* named *.csv must not be treated as a candidate file.
    (tmp_path / "old.csv").mkdir()
    shutil.copy(FIXTURES_DIR / "esm25.csv", tmp_path / "esm25.csv")
    result = _run("--path", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "old.csv" not in result.stdout


def test_empty_path_arg_exits_nonzero():
    # Path("") normalizes to "." — must fail cleanly, not scan the cwd.
    result = _run("--path", "")
    assert result.returncode != 0
    assert "must not be empty" in result.stdout
