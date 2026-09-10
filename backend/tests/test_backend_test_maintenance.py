"""Test-only infrastructure contracts; no production numerical work is replaced."""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from .conftest import isolated_lab_db

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/backend_test_runner.py"
spec = importlib.util.spec_from_file_location("backend_test_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FixtureRequest:
    def __init__(self, template=None, *, db_free=False, fresh=False):
        self.node = self
        self.template = template
        self.marks = {"db_free": db_free, "fresh_schema": fresh}

    def get_closest_marker(self, name):
        return True if self.marks.get(name, False) else None

    def getfixturevalue(self, name):
        assert name == "lab_schema_template" and self.template is not None
        return self.template


def test_database_free_fixture_rejects_even_a_caught_connection(tmp_path, monkeypatch):
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(db_free=True), tmp_path, monkeypatch)
    path = next(fixture)
    assert not path.exists()
    with pytest.raises(AssertionError, match="unauthorized SQLite"):
        sqlite3.connect(path)
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        next(fixture)
    assert not path.exists()


def test_schema_copies_are_independently_writable_and_template_unchanged(tmp_path, lab_schema_template):
    before = hashlib.sha256(lab_schema_template.read_bytes()).hexdigest()
    for index in range(2):
        directory = tmp_path / str(index)
        directory.mkdir()
        with pytest.MonkeyPatch.context() as patch:
            fixture = isolated_lab_db.__wrapped__(FixtureRequest(lab_schema_template), directory, patch)
            path = next(fixture)
            with closing(sqlite3.connect(path)) as conn:
                assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'test_sentinel'").fetchone() is None
                conn.execute("CREATE TABLE test_sentinel (value TEXT)")
                conn.execute("INSERT INTO test_sentinel VALUES ('only this copy')")
                conn.commit()
            with pytest.raises(StopIteration):
                next(fixture)
    assert hashlib.sha256(lab_schema_template.read_bytes()).hexdigest() == before


def test_fresh_schema_fixture_runs_real_initialization(tmp_path, monkeypatch):
    from app import db

    original = db.init_db
    calls = []

    def initialize():
        calls.append(db.get_db_path())
        original()

    monkeypatch.setattr(db, "init_db", initialize)
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(fresh=True), tmp_path, monkeypatch)
    path = next(fixture)
    assert calls == [path]
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'saved_backtests'").fetchone()
    with pytest.raises(StopIteration):
        next(fixture)


def test_writable_fixture_rejects_outside_paths_and_sqlite_uris(tmp_path, monkeypatch, lab_schema_template):
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(lab_schema_template), tmp_path, monkeypatch)
    next(fixture)
    outside = tmp_path.parent / "not-a-test-database.db"
    for target in (str(outside), outside.as_uri() + "?mode=rwc"):
        with pytest.raises(AssertionError, match="unauthorized SQLite"):
            sqlite3.connect(target, uri=True)
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        next(fixture)
    assert not outside.exists()


def test_full_lane_has_no_filters_and_fast_lane_is_explicit():
    assert runner.selection("full", []) == ["backend/tests"]
    assert runner.selection("fast", []) == [*runner.FAST_FILES, "-m", "db_free"]


@pytest.mark.parametrize("scope,tests", [
    ("focused", []), ("profile", []), ("full", ["backend/tests/test_x.py"]),
    ("fast", ["backend/tests/test_x.py"]), ("focused", ["../outside.py"]),
    ("focused", ["backend/tests/../../outside.py"]), ("focused", ["-k"]),
])
def test_runner_rejects_ambiguous_or_outside_selections(scope, tests):
    with pytest.raises(ValueError):
        runner.selection(scope, tests)


def test_snapshot_preserves_dirty_and_untracked_bytes_without_user_data(tmp_path):
    repo, target = tmp_path / "repo", tmp_path / "snapshot"
    contents = {"backend/app/a.py": b"uncommitted source", "backend/tests/test_new.py": b"untracked test",
                "backend/tests/fixtures/example.db": b"frozen fixture", "backend/data/quantlab.db": b"user db",
                "backend/data/quantlab.db-wal": b"user journal", "artifacts/prior.txt": b"prior evidence",
                ".env.local": b"secret"}
    for name, data in contents.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest, omitted = runner.copy_snapshot(repo, target, list(contents))
    assert set(manifest) == {"backend/app/a.py", "backend/tests/test_new.py", "backend/tests/fixtures/example.db"}
    assert set(omitted) == set(contents) - set(manifest)
    for name, data in contents.items():
        assert (repo / name).read_bytes() == data
        if name in manifest:
            assert (target / name).read_bytes() == data


@pytest.mark.parametrize("body,extra,expected", [
    ("def test_ok(): assert True", [], 0),
    ("def test_fail(): assert False", [], 1),
    ("# deliberately empty test module", [], 5),
    ("def test_ok(): assert True", ["-k", "does_not_exist"], 5),
])
def test_child_preserves_failure_and_no_test_exit_codes(tmp_path, body, extra, expected):
    probe = tmp_path / "test_probe.py"
    probe.write_text(body, encoding="utf-8")
    config = tmp_path / "run-config.json"
    runner.write_json(config, {"scope": "profile", "collect_only": False,
                              "pytest_args": [str(probe), "-q", "-p", "no:cacheprovider", *extra]})
    result = subprocess.run([sys.executable, str(SCRIPT), "--execute", str(config)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == expected, result.stdout + result.stderr
    assert json.loads((tmp_path / "pytest-result.json").read_text())["exit_code"] == expected
    collection = json.loads((tmp_path / "collection.json").read_text())
    assert len(collection["selected"]) == (1 if expected in (0, 1) else 0)
    assert len(collection["deselected"]) == (1 if extra else 0)
    assert (tmp_path / "profile.pstats").stat().st_size > 0


def test_child_records_a_forbidden_connection_even_when_caught(tmp_path):
    probe = tmp_path / "test_guard.py"
    forbidden = tmp_path.parent / "never-created-by-runner.db"
    probe.write_text(
        "import sqlite3\ndef test_guard():\n"
        f"    try: sqlite3.connect({str(forbidden)!r})\n"
        "    except RuntimeError: pass\n", encoding="utf-8")
    config = tmp_path / "run-config.json"
    runner.write_json(config, {"scope": "focused", "collect_only": False,
                              "pytest_args": [str(probe), "-q", "-p", "no:cacheprovider"]})
    result = subprocess.run([sys.executable, str(SCRIPT), "--execute", str(config)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads((tmp_path / "sqlite-violations.json").read_text()) == [str(forbidden)]
    assert not forbidden.exists()


def test_runner_keeps_nested_subprocess_text_encoding_consistent(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONUTF8", "0")
    env = runner.child_environment(tmp_path / "source", tmp_path)
    program = (
        "import json, subprocess, sys; "
        "result = subprocess.run([sys.executable, '-c', 'print(chr(0x2014))'], "
        "capture_output=True, text=True, check=True); "
        "print(json.dumps({'utf8_mode': sys.flags.utf8_mode, 'output': result.stdout}))"
    )
    result = subprocess.run([sys.executable, "-c", program], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"utf8_mode": 1, "output": "\u2014\n"}
