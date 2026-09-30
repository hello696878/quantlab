"""In-process harness guards: synthetic routes, no browser, server or user DB."""
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


@pytest.fixture
def guarded_app(tmp_path, monkeypatch):
    from app import db
    from fastapi import FastAPI

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    base = importlib.import_module("scripts.strategy_ensemble_e2e")
    harness = importlib.import_module("scripts.ml_lifecycle_e2e")
    application = FastAPI()
    written = []

    @application.post("/ml-lifecycles/demo")
    @application.post("/strategy-ensembles/demo-seed")
    def seed_probe():
        written.append(True)
        return {"written": True}

    root = tmp_path / (base.PREFIX + "lifecycle-test")
    root.mkdir()
    monkeypatch.setattr(base.tempfile, "mkdtemp", lambda **kwargs: str(root))
    monkeypatch.delitem(base.sys.modules, "app.main", raising=False)
    monkeypatch.setenv("E2E_STRATEGY_ENSEMBLE_TOKEN", "a" * 64)
    monkeypatch.setattr(base, "importlib", SimpleNamespace(import_module=lambda name: db if name == "app.db" else SimpleNamespace(app=application)))
    monkeypatch.setattr(db, "_db_path_override", db._db_path_override)
    monkeypatch.setattr(base.sys, "path", list(base.sys.path))
    application = harness.create_app()
    return application, written, db, application.state.strategy_ensemble_e2e_identity


def test_both_proxy_proofs_identify_the_same_actual_sqlite_database(guarded_app):
    from fastapi.testclient import TestClient

    application, written, _, identity = guarded_app
    headers = {"x-quantlab-e2e-token": identity.token}
    with TestClient(application) as client:
        strategy = client.get("/strategy-ensembles/e2e-isolation", headers=headers)
        lifecycle = client.get("/ml-lifecycles/e2e/isolation", headers=headers)
        assert strategy.status_code == lifecycle.status_code == 200
        assert strategy.json()["kind"] == "quantlab_strategy_ensemble_disposable_v1"
        assert lifecycle.json()["kind"] == "quantlab_ml_lifecycle_disposable_v1"
        for proof in (strategy.json(), lifecycle.json()):
            assert proof["database_identity"] == identity.root.name
            assert proof["database_verified"] is True
            assert proof["token"] == identity.token
        assert written == []
        assert client.post("/ml-lifecycles/demo", headers=headers).status_code == 200
    assert written == [True]


@pytest.mark.parametrize("route", ["/ml-lifecycles/demo", "/strategy-ensembles/demo-seed"])
def test_missing_or_wrong_token_blocks_seed_before_execution(guarded_app, route):
    from fastapi.testclient import TestClient

    application, written, _, _ = guarded_app
    with TestClient(application) as client:
        assert client.post(route).status_code == 409
        assert client.post(route, headers={"x-quantlab-e2e-token": "b" * 64}).status_code == 409
    assert written == []


@pytest.mark.parametrize("change", ["marker", "override", "connection"])
@pytest.mark.parametrize("route", ["/ml-lifecycles/demo", "/strategy-ensembles/demo-seed"])
def test_changed_identity_after_handshake_blocks_seed(guarded_app, tmp_path, monkeypatch, route, change):
    from fastapi.testclient import TestClient

    application, written, db, identity = guarded_app
    headers = {"x-quantlab-e2e-token": identity.token}
    other = tmp_path / "not-the-serving-database.sqlite3"
    closed = []

    class WrongConnection:
        def execute(self, statement):
            assert statement == "PRAGMA database_list"
            return [(0, "main", str(other))]

        def close(self):
            closed.append(True)

    with TestClient(application) as client:
        assert client.get("/ml-lifecycles/e2e/isolation", headers=headers).status_code == 200
        if change == "marker":
            identity.marker.write_text("changed", encoding="utf-8")
        elif change == "override":
            monkeypatch.setattr(db, "_db_path_override", other)
        else:
            # The real configured DB path stays correct; inspect the connection too.
            monkeypatch.setattr(db, "get_connection", WrongConnection)
        assert client.post(route, headers=headers).status_code == 409
    assert written == []
    assert not other.exists()
    if change == "connection":
        assert closed == [True]
