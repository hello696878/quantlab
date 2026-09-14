"""Opt-in lab fixtures: no production database, no shared writable state."""

from contextlib import closing, contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest


_sqlite_boundaries = []


def _audit_sqlite(event, args):
    if event != "sqlite3.connect" or not _sqlite_boundaries:
        return
    root, database_free, violations = _sqlite_boundaries[-1]
    database = os.fsdecode(args[0])
    if (database_free or database.lower().startswith("file:") or
            database != ":memory:" and not Path(database).resolve().is_relative_to(root)):
        violations.append(database)
        raise AssertionError("test attempted unauthorized SQLite access")


# The hook remains installed but is inert outside an active fixture boundary.
# Audit events cover sqlite3.dbapi2 and connection aliases captured before setup.
sys.addaudithook(_audit_sqlite)


@contextmanager
def _sqlite_boundary(root, *, database_free=False):
    violations = []
    _sqlite_boundaries.append((root.resolve(), database_free, violations))
    try:
        # Preflight ordinary calls before the outer runner's broader audit hook.
        # Audit hooks still cover dbapi2 and aliases cached before this wrapper.
        with pytest.MonkeyPatch.context() as patch:
            connect = sqlite3.connect

            def guarded_connect(database, *args, **kwargs):
                _audit_sqlite("sqlite3.connect", (database,))
                return connect(database, *args, **kwargs)

            patch.setattr(sqlite3, "connect", guarded_connect)
            yield
    finally:
        _sqlite_boundaries.pop()
        assert not violations, f"unauthorized SQLite attempts: {violations}"


@pytest.fixture(scope="session")
def lab_schema_template(tmp_path_factory):
    from app import db

    path = tmp_path_factory.mktemp("lab-schema") / "empty.db"
    with _sqlite_boundary(path.parent), pytest.MonkeyPatch.context() as patch:
        patch.setattr(db, "_db_path_override", path)
        db.init_db()
        # Finish every connection and journal before creating writable copies.
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        assert not any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
    return path


@pytest.fixture
def isolated_lab_db(request, tmp_path, monkeypatch):
    from app import db

    path = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db, "_db_path_override", path)
    database_free = request.node.get_closest_marker("db_free") is not None
    fresh = request.node.get_closest_marker("fresh_schema") is not None
    if database_free and fresh:
        raise ValueError("db_free and fresh_schema markers conflict")
    template = None
    if not database_free and not fresh:
        template = request.getfixturevalue("lab_schema_template")
        template_hash = hashlib.sha256(template.read_bytes()).digest()
    with _sqlite_boundary(tmp_path, database_free=database_free):
        if fresh:
            db.init_db()
        elif template is not None:
            shutil.copyfile(template, path)
        yield path
    if template is not None:
        assert hashlib.sha256(template.read_bytes()).digest() == template_hash, "schema template changed"
    if database_free:
        assert not path.exists(), "database-free test created an application database"
