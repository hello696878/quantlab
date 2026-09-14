"""No services are started: test-owned storage and synthetic connection metadata."""
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("isolated_lab_db")
_SPEC = importlib.util.spec_from_file_location(
    "strategy_ensemble_e2e_harness", Path(__file__).resolve().parents[2] / "scripts" / "strategy_ensemble_e2e.py"
)
harness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(harness)


@pytest.fixture
def identity(tmp_path):
    root = tmp_path / (harness.PREFIX + "unit")
    root.mkdir()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    return harness.DisposableIdentity(root, "a" * 64, checkout)


@pytest.mark.db_free
def test_identity_checks_serving_override_before_opening_connection(identity):
    opened = []
    db = SimpleNamespace(get_db_path=lambda: identity.marker,
                         get_connection=lambda: opened.append(True))
    with pytest.raises(harness.IsolationError, match="Serving backend database"):
        identity.verify(db)
    assert opened == []


@pytest.mark.db_free
def test_changed_marker_rejected_before_connection(identity):
    identity.marker.write_text("changed", encoding="utf-8")
    with pytest.raises(harness.IsolationError, match="marker changed"):
        identity.verify(SimpleNamespace())


@pytest.mark.db_free
def test_cannot_adopt_existing_database_or_checkout_directory(tmp_path):
    root = tmp_path / (harness.PREFIX + "existing")
    root.mkdir()
    database = root / "browser.sqlite3"
    database.write_bytes(b"keep existing evidence")
    checkout = tmp_path / "unrelated"
    checkout.mkdir()
    with pytest.raises(FileExistsError):
        harness.DisposableIdentity(root, "a" * 64, checkout)
    assert database.read_bytes() == b"keep existing evidence"


@pytest.mark.db_free
def test_checkout_storage_and_invalid_token_rejected(tmp_path):
    root = tmp_path / (harness.PREFIX + "inside")
    root.mkdir()
    with pytest.raises(harness.IsolationError, match="outside the checkout"):
        harness.DisposableIdentity(root, "a" * 64, tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with pytest.raises(harness.IsolationError, match="64 lowercase"):
        harness.DisposableIdentity(root, "1", checkout)
    assert not (root / "browser.sqlite3").exists()


@pytest.mark.db_free
def test_connection_identity_mismatch_is_rejected_and_closed(identity):
    class Connection:
        closed = False
        def execute(self, _statement):
            return [(0, "main", str(identity.marker))]
        def close(self):
            self.closed = True
    conn = Connection()
    db = SimpleNamespace(get_db_path=lambda: identity.database, get_connection=lambda: conn)
    with pytest.raises(harness.IsolationError, match="Serving connection"):
        identity.verify(db)
    assert conn.closed


def test_real_disposable_connection_identity(identity):
    # The test DB fixture protects the active DB; this second file is also test-owned.
    with closing(sqlite3.connect(identity.database)) as conn:
        conn.execute("CREATE TABLE e2e_probe (value TEXT)")
        conn.commit()
    db = SimpleNamespace(get_db_path=lambda: identity.database,
                         get_connection=lambda: sqlite3.connect(identity.database))
    proof = identity.verify(db)
    assert proof == {"kind": "quantlab_strategy_ensemble_disposable_v1", "token": "a" * 64,
                     "database_identity": identity.root.name, "database_verified": True}


def test_factory_middleware_blocks_writes_after_identity_changes(tmp_path, monkeypatch):
    from app import db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    written = []

    @app.post("/strategy-ensembles/probe")
    def write_probe():
        written.append(True)
        return {"written": True}

    root = tmp_path / (harness.PREFIX + "factory")
    root.mkdir()
    monkeypatch.setattr(harness.tempfile, "mkdtemp", lambda **kwargs: str(root))
    monkeypatch.delitem(harness.sys.modules, "app.main", raising=False)
    monkeypatch.setenv("E2E_STRATEGY_ENSEMBLE_TOKEN", "a" * 64)
    monkeypatch.setattr(harness, "importlib", SimpleNamespace(import_module=lambda name: db if name == "app.db" else SimpleNamespace(app=app)))
    monkeypatch.setattr(db, "_db_path_override", db._db_path_override)
    original_path = list(harness.sys.path)
    monkeypatch.setattr(harness.sys, "path", original_path.copy())
    application = harness.create_app()
    headers = {harness.HEADER: "a" * 64}
    with TestClient(application) as client:
        assert client.post("/strategy-ensembles/probe").status_code == 409
        proof = client.get(harness.IDENTITY_PATH, headers=headers)
        assert proof.status_code == 200
        assert proof.json()["database_identity"] == root.name
        assert client.post("/strategy-ensembles/probe", headers=headers).status_code == 200
        db._db_path_override = root / "changed.sqlite3"
        assert client.post("/strategy-ensembles/probe", headers=headers).status_code == 409
        assert not db._db_path_override.exists()
    assert written == [True]
