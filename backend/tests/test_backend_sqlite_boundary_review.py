"""Small owned-path controls: URI semantics, cached calls, and guard evidence."""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from .conftest import _sqlite_boundary

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/backend_test_runner.py"
spec = importlib.util.spec_from_file_location("sqlite_boundary_review_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CACHED_CONNECT = sqlite3.connect


@pytest.mark.parametrize("alter", [
    lambda uri: uri.replace("file:", "FILE:", 1),
    lambda uri: uri + "&vfs=",
    lambda uri: uri.replace("mode=ro", "mode=ro&mode="),
    lambda uri: uri.replace("mode=ro", "%6dode=ro"),
    lambda uri: uri.replace("file:", "file:\t", 1),
    lambda uri: uri.replace("?mode=ro", "%00suffix?mode=ro"),
    lambda uri: uri.replace("?mode=ro", "?mode=rw"),
    lambda uri: uri.replace("?mode=ro", "?mode=rwc"),
    lambda uri: uri.replace("?mode=ro", "?mode=memory&cache=shared"),
], ids=["scheme", "blank_vfs", "duplicate_mode", "encoded_key", "control", "nul", "rw", "rwc", "shared_memory"])
def test_guard_rejects_uri_spellings_not_emitted_by_reader(tmp_path, alter):
    target = tmp_path / "space owned.db"
    with pytest.raises(ValueError):
        runner.sqlite_test_path(alter(target.as_uri() + "?mode=ro"))
    assert not target.exists()


@pytest.mark.parametrize("connect", [pytest.param(CACHED_CONNECT, id="cached"), pytest.param(sqlite3.dbapi2.connect, id="dbapi2")])
def test_owned_read_only_uri_works_but_write_fails_with_cached_connections(tmp_path, connect):
    target = tmp_path / "owned.db"
    with closing(sqlite3.connect(target)) as conn:
        conn.execute("CREATE TABLE sentinel(value INTEGER)")
        conn.execute("INSERT INTO sentinel VALUES(7)")
        conn.commit()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with _sqlite_boundary(tmp_path), closing(connect(target.as_uri() + "?mode=ro", uri=True)) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == (7,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO sentinel VALUES(9)")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("kind", ["plain", "uri", "bytes"])
@pytest.mark.parametrize("connect", [pytest.param(CACHED_CONNECT, id="cached"), pytest.param(sqlite3.dbapi2.connect, id="dbapi2")])
def test_caught_lookalike_root_connection_still_fails_boundary(tmp_path, kind, connect):
    allowed = tmp_path / "owned"
    outside = tmp_path / "owned-lookalike"
    allowed.mkdir(); outside.mkdir()
    target = outside / "missing.db"
    database = target.as_uri() + "?mode=ro" if kind == "uri" else os.fsencode(target) if kind == "bytes" else target
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        with _sqlite_boundary(allowed):
            with pytest.raises(AssertionError, match="unauthorized SQLite access"):
                connect(database, uri=kind == "uri")
    assert not list(allowed.iterdir()) and not list(outside.iterdir())


@pytest.mark.parametrize("kind", ["plain", "uri", "memory"])
@pytest.mark.parametrize("connect", [pytest.param(CACHED_CONNECT, id="cached"), pytest.param(sqlite3.dbapi2.connect, id="dbapi2")])
def test_database_free_refuses_caught_connections_without_file_effects(tmp_path, kind, connect):
    target = tmp_path / "missing.db"
    database = ":memory:" if kind == "memory" else target.as_uri() + "?mode=ro" if kind == "uri" else target
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        with _sqlite_boundary(tmp_path, database_free=True):
            with pytest.raises(AssertionError, match="unauthorized SQLite access"):
                connect(database, uri=kind == "uri")
    assert not list(tmp_path.iterdir())


def test_repeated_guard_installation_keeps_existing_wrappers():
    before = sqlite3.connect, sqlite3.dbapi2.connect
    runner.install_sqlite_uri_guard()
    assert (sqlite3.connect, sqlite3.dbapi2.connect) == before


def test_test_monkeypatch_teardown_cannot_restore_stale_fixture_wrapper(tmp_path):
    before = sqlite3.connect, sqlite3.dbapi2.connect
    test_patch = pytest.MonkeyPatch()
    calls = []

    def observed(*args, **kwargs):
        calls.append(True)
        return before[0](*args, **kwargs)

    try:
        # Match pytest dependency teardown order: boundary exits first, then the
        # test's monkeypatch fixture restores its captured connection callable.
        with _sqlite_boundary(tmp_path):
            test_patch.setattr(sqlite3, "connect", observed)
            with closing(sqlite3.connect(":memory:")) as conn:
                assert conn.execute("SELECT 7").fetchone() == (7,)
    finally:
        test_patch.undo()
    assert calls == [True]
    assert (sqlite3.connect, sqlite3.dbapi2.connect) == before
    runner.install_sqlite_uri_guard()
    assert (sqlite3.connect, sqlite3.dbapi2.connect) == before
    # A later scope still denies access; an old scope is neither retained nor
    # accidentally used for subsequent calls.
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        with _sqlite_boundary(tmp_path, database_free=True):
            with pytest.raises(AssertionError, match="unauthorized SQLite access"):
                sqlite3.connect(":memory:")
    with closing(sqlite3.connect(":memory:")) as conn:
        assert conn.execute("SELECT 9").fetchone() == (9,)


def test_fixture_rejects_explicit_false_uri_before_outer_guard(tmp_path):
    target = tmp_path / "never.db"
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        with _sqlite_boundary(tmp_path):
            with pytest.raises(AssertionError, match="unauthorized SQLite access"):
                sqlite3.connect(target.as_uri() + "?mode=ro", uri=False)
    assert not list(tmp_path.iterdir())


def test_child_guard_reports_caught_unsafe_uri_without_entering_sqlite(tmp_path):
    # One tiny --execute child, no source snapshot/full-suite recursion.
    allowed = tmp_path / "run"
    allowed.mkdir()
    outside = tmp_path / "run-lookalike"
    outside.mkdir()
    target = outside / "missing.db"
    invalid = [target.as_uri() + "?mode=ro", (allowed / "writable.db").as_uri() + "?mode=rwc",
               (allowed / "literal.db").as_uri() + "?mode=ro", (allowed / "unwrapped.db").as_uri() + "?mode=ro"]
    body = "import sqlite3\nfrom sqlite3 import connect as cached\ndef test_controls():\n"
    for database in invalid[:2]:
        body += "    try: cached(" + repr(database) + ", uri=True)\n    except RuntimeError: pass\n"
    body += "    try: sqlite3.dbapi2.connect(" + repr(invalid[2]) + ", uri=False)\n    except RuntimeError: pass\n"
    body += "    try: cached.__wrapped__(" + repr(invalid[3]) + ", uri=True)\n    except RuntimeError: pass\n"
    (allowed / "test_guard.py").write_text(body, encoding="utf-8")
    config = allowed / "run-config.json"
    runner.write_json(config, {"scope": "focused", "collect_only": False,
                              "pytest_args": [str(allowed / "test_guard.py"), "-q", "-p", "no:cacheprovider"]})
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute", str(config)], cwd=allowed,
                            capture_output=True, text=True, encoding="utf-8", timeout=45)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads((allowed / "sqlite-violations.json").read_text()) == invalid
    assert json.loads((allowed / "pytest-result.json").read_text())["exit_code"] == 0
    assert not list(outside.iterdir()) and not list(allowed.glob("*.db"))
    assert not list(tmp_path.rglob("*-wal")) and not list(tmp_path.rglob("*-shm")) and not list(tmp_path.rglob("*-journal"))
