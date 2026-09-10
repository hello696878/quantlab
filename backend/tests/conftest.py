"""Opt-in lab fixtures: no production database, no shared writable state."""

from contextlib import closing
from pathlib import Path
import shutil
import sqlite3

import pytest


@pytest.fixture(scope="session")
def lab_schema_template(tmp_path_factory):
    from app import db

    path = tmp_path_factory.mktemp("lab-schema") / "empty.db"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(db, "_db_path_override", path)
        db.init_db()
    # init_db closes its connection. Explicitly finish any journal before copying.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert not Path(str(path) + "-wal").exists()
    return path


@pytest.fixture
def isolated_lab_db(request, tmp_path, monkeypatch):
    from app import db

    path = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db, "_db_path_override", path)
    database_free = request.node.get_closest_marker("db_free") is not None
    if not database_free:
        if request.node.get_closest_marker("fresh_schema"):
            db.init_db()
        else:
            shutil.copyfile(request.getfixturevalue("lab_schema_template"), path)

    connect = sqlite3.connect
    violations = []

    def guarded_connect(database, *args, **kwargs):
        if database_free or str(database).lower().startswith("file:") or (str(database) != ":memory:" and
                             not Path(database).resolve().is_relative_to(tmp_path.resolve())):
            violations.append(str(database))
            raise AssertionError("test attempted unauthorized SQLite access")
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
    yield path
    # A broad raises(Exception) must not hide a forbidden connection attempt.
    assert not violations, f"unauthorized SQLite attempts: {violations}"
    if database_free:
        assert not path.exists(), "database-free test created an application database"
