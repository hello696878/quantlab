"""No services: replay and save guards reject drift after a real SQLite proof."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


@pytest.mark.parametrize("route", ["/run-replay/demo", "/saved-backtests"])
@pytest.mark.parametrize("change", ["token", "marker", "override", "connection"])
def test_replay_and_save_fail_before_mutation_after_proof(tmp_path, monkeypatch, route, change):
    from app import db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from scripts import run_replay_e2e
    from scripts.strategy_ensemble_e2e import DisposableIdentity, HEADER, PREFIX

    root = tmp_path / (PREFIX + "review-replay")
    root.mkdir()
    identity = DisposableIdentity(root, "a" * 64, Path(__file__).resolve().parents[2])
    monkeypatch.setattr(db, "_db_path_override", identity.database)
    app = FastAPI()
    app.state.strategy_ensemble_e2e_identity = identity
    written = []

    @app.post("/run-replay/demo")
    @app.post("/saved-backtests")
    def write_probe():
        written.append(True)
        return {"written": True}

    monkeypatch.setattr(run_replay_e2e, "base_app", lambda: app)
    headers = {HEADER: identity.token}
    other = tmp_path / "wrong.sqlite3"
    closed = []

    class WrongConnection:
        def execute(self, statement):
            assert statement == "PRAGMA database_list"
            return [(0, "main", str(other))]

        def close(self):
            closed.append(True)

    with TestClient(run_replay_e2e.create_app()) as client:
        proof = client.get("/run-replay/e2e/isolation", headers=headers)
        assert proof.status_code == 200
        assert proof.json()["database_verified"] is True
        assert proof.json()["database_identity"] == root.name
        assert proof.json()["token"] == identity.token
        assert written == []
        if change == "token":
            headers = {HEADER: "b" * 64}
        elif change == "marker":
            identity.marker.write_text("changed", encoding="utf-8")
        elif change == "override":
            monkeypatch.setattr(db, "_db_path_override", other)
        else:
            monkeypatch.setattr(db, "get_connection", WrongConnection)
        assert client.post(route, headers=headers).status_code == 409
    assert written == []
    assert not other.exists()
    if change == "connection":
        assert closed == [True]
