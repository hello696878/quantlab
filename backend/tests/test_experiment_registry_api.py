"""
API tests for the Research Experiment Registry (Phase 48.0).

Exercises the FastAPI routes end to end against a fresh temporary SQLite
database: happy paths, error paths (404/409/422), the reproducibility and
comparison endpoints, JSON export (no local paths / secrets), idempotent demo
seeding, and confirmation that the existing Saved Reports API is unaffected.
"""

from __future__ import annotations

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")

BASE = "/experiment-registry"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _create(client, **over):
    payload = {
        "name": "Run",
        "module": "scenario_studio",
        "experiment_type": "stress",
        "status": "completed",
        "parameters": {"a": 1},
        "metrics": {"sharpe": 1.0},
        "dataset_name": "fx",
        "dataset_identity": {"rows": 5},
    }
    payload.update(over)
    return client.post(f"{BASE}/experiments", json=payload)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_create_list_get(client):
    r = _create(client, name="Alpha")
    assert r.status_code == 201
    body = r.json()
    assert body["configuration_fingerprint"]
    assert body["result_fingerprint"]

    lst = client.get(f"{BASE}/experiments")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    got = client.get(f"{BASE}/experiments/{body['id']}")
    assert got.status_code == 200
    assert got.json()["name"] == "Alpha"


def test_lifecycle_complete_and_baseline(client):
    rec = _create(client, status="running", metrics={}).json()
    done = client.post(f"{BASE}/experiments/{rec['id']}/complete", json={"metrics": {"sharpe": 2.0}})
    assert done.status_code == 200
    assert done.json()["status"] == "completed"

    base = client.post(f"{BASE}/experiments/{rec['id']}/mark-baseline")
    assert base.status_code == 200
    assert base.json()["is_baseline"] is True


def test_patch_updates_mutable_fields(client):
    rec = _create(client).json()
    r = client.patch(f"{BASE}/experiments/{rec['id']}", json={"notes": "reviewed", "tags": ["keep"]})
    assert r.status_code == 200
    assert r.json()["notes"] == "reviewed"
    assert r.json()["tags"] == ["keep"]


def test_invalidate(client):
    rec = _create(client).json()
    r = client.post(f"{BASE}/experiments/{rec['id']}/invalidate")
    assert r.status_code == 200
    assert r.json()["status"] == "invalidated"


def test_delete(client):
    rec = _create(client).json()
    assert client.delete(f"{BASE}/experiments/{rec['id']}").status_code == 200
    assert client.get(f"{BASE}/experiments/{rec['id']}").status_code == 404


def test_summary_endpoint(client):
    _create(client, module="a")
    _create(client, module="b", status="failed", error_message="x", metrics={})
    r = client.get(f"{BASE}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["by_status"]["failed"] == 1
    assert set(body["modules"]) == {"a", "b"}


def test_filter_query_params(client):
    _create(client, module="a", tags=["special"])
    _create(client, module="b")
    r = client.get(f"{BASE}/experiments", params={"module": "a"})
    assert r.json()["total"] == 1
    r2 = client.get(f"{BASE}/experiments", params={"tag": "special"})
    assert r2.json()["total"] == 1
    r3 = client.get(f"{BASE}/experiments", params={"baseline": "true"})
    assert r3.json()["total"] == 0


# ---------------------------------------------------------------------------
# Reproducibility + comparison endpoints
# ---------------------------------------------------------------------------


def test_reproducibility_endpoint(client):
    base = _create(client, name="base").json()
    client.post(f"{BASE}/experiments/{base['id']}/mark-baseline")
    rerun = _create(client, name="rerun").json()
    r = client.get(f"{BASE}/experiments/{rerun['id']}/reproducibility")
    assert r.status_code == 200
    assert r.json()["status"] == "reproducible"
    assert r.json()["reference_id"] == base["id"]


def test_compare_endpoint(client):
    a = _create(client, metrics={"sharpe": 1.0}).json()
    b = _create(client, metrics={"sharpe": 2.0}).json()
    r = client.get(f"{BASE}/compare", params={"a": a["id"], "b": b["id"]})
    assert r.status_code == 200
    body = r.json()
    assert body["fingerprint_match"]["configuration"] is True
    assert body["fingerprint_match"]["result"] is False


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_shape_and_no_local_paths(client):
    _create(client, name="Exported")
    r = client.get(f"{BASE}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"]
    assert body["exported_at"]
    assert body["count"] == 1
    assert body["experiments"][0]["name"] == "Exported"
    # No absolute local paths / secrets in the serialized export.
    text = r.text.lower()
    for needle in ("c:\\", "/users/", "/home/", "password", "api_key", "secret", ".db"):
        assert needle not in text


def test_export_respects_filters(client):
    _create(client, module="a")
    _create(client, module="b")
    r = client.get(f"{BASE}/export", params={"module": "a"})
    assert r.json()["count"] == 1
    assert r.json()["filters"] == {"module": "a"}


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------


def test_demo_seed_idempotent(client):
    first = client.post(f"{BASE}/demo-seed").json()
    assert first["created"] > 0
    second = client.post(f"{BASE}/demo-seed").json()
    assert second["created"] == 0
    assert second["skipped"] == first["created"]
    # And a reproducible demo record assesses as reproducible.
    lst = client.get(f"{BASE}/experiments", params={"query": "reproduction run"}).json()
    assert lst["total"] == 1
    rid = lst["items"][0]["id"]
    assert client.get(f"{BASE}/experiments/{rid}/reproducibility").json()["status"] == "reproducible"


# ---------------------------------------------------------------------------
# Error / adversarial paths
# ---------------------------------------------------------------------------


def test_error_paths(client):
    assert client.get(f"{BASE}/experiments/99999").status_code == 404
    assert client.post(f"{BASE}/experiments/99999/complete", json={"metrics": {}}).status_code == 404
    assert client.post(f"{BASE}/experiments/99999/mark-baseline").status_code == 404
    # Blank name -> 422
    assert _create(client, name="   ").status_code == 422
    # Extra field forbidden -> 422
    assert client.post(
        f"{BASE}/experiments",
        json={"name": "x", "module": "m", "experiment_type": "t", "evil": 1},
    ).status_code == 422
    # Bad SHA-256 -> 422
    assert _create(client, dataset_fingerprint="zzz").status_code == 422
    # Compare identical -> 422
    rec = _create(client).json()
    assert client.get(f"{BASE}/compare", params={"a": rec["id"], "b": rec["id"]}).status_code == 422


def test_non_finite_metric_returns_clean_422(client):
    # Non-standard JSON literals NaN / Infinity must produce a stable 422, not 500.
    headers = {"Content-Type": "application/json"}
    for token in ("NaN", "Infinity", "-Infinity"):
        body = '{"name":"x","module":"m","experiment_type":"t","metrics":{"a":%s}}' % token
        resp = client.post(f"{BASE}/experiments", content=body, headers=headers)
        assert resp.status_code == 422


def test_baseline_conflict_on_non_completed(client):
    rec = _create(client, status="running", metrics={}).json()
    assert client.post(f"{BASE}/experiments/{rec['id']}/mark-baseline").status_code == 409


def test_complete_conflict_when_already_completed(client):
    rec = _create(client).json()  # already completed
    assert client.post(f"{BASE}/experiments/{rec['id']}/complete", json={"metrics": {}}).status_code == 409


# ---------------------------------------------------------------------------
# Existing Saved Reports API is unaffected
# ---------------------------------------------------------------------------


def test_saved_reports_still_work(client):
    payload = {
        "title": "Report",
        "report_type": "markdown",
        "source_type": "manual",
        "markdown_content": "# hi",
    }
    created = client.post("/saved-reports", json=payload)
    assert created.status_code == 200
    listed = client.get("/saved-reports")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
