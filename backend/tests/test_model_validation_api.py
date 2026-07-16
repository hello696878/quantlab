"""
Service + API tests for the Model Validation Lab (Phase 50.0) on fresh
temporary SQLite databases: persistence/migration, run lifecycle, execution,
baseline scope, registry/lineage links, comparison, export privacy, demo
idempotence, adversarial paths, and coexistence with the existing registries.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
service = pytest.importorskip("app.model_validation.service")
mv_store = pytest.importorskip("app.model_validation.store")

BASE = datetime(2025, 1, 1)
BASEURL = "/model-validation"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def samples(n=30, horizon=5, **extra):
    out = []
    for i in range(n):
        pred = BASE + timedelta(days=i)
        out.append({
            "sample_id": f"s{i:03d}",
            "prediction_time": pred.isoformat(),
            "evaluation_time": (pred + timedelta(days=horizon)).isoformat(),
            "label": 1 if i % 2 else 0,
            "prediction": 1 if i % 3 else 0,
            "score": 0.1 + (i % 8) / 10.0,
            "ret": 0.01 * ((i % 5) - 2),
            **extra,
        })
    return out


def create(client, **over):
    payload = {
        "name": "Run",
        "method": "purged_kfold",
        "configuration": {"n_folds": 4},
        "samples": samples(),
    }
    payload.update(over)
    return client.post(f"{BASEURL}/runs", json=payload)


# ---------------------------------------------------------------------------
# Persistence / migration
# ---------------------------------------------------------------------------


def test_fresh_db_has_tables_and_upgrade_preserves(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    conn = sqlite3.connect(str(db_file))
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    assert {"validation_runs", "validation_splits"} <= names
    # Re-running init_db never drops data.
    run = service.create_run(
        {"name": "kept", "method": "purged_kfold",
         "configuration": {"n_folds": 4}, "samples": samples()})
    db_module.init_db()
    assert service.get_run(run["id"])["name"] == "kept"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_create_execute_roundtrip(client):
    created = create(client)
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "pending"
    assert run["configuration_fingerprint"]

    done = client.post(f"{BASEURL}/runs/{run['id']}/execute", json={})
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "completed"
    assert body["leakage_clean"] is True
    assert body["split_count"] == 4
    assert body["result_fingerprint"]
    assert body["key_metric_preview"]

    splits = client.get(f"{BASEURL}/runs/{run['id']}/splits").json()
    assert len(splits) == 4
    assert all(s["status"] == "valid" for s in splits)
    assert all(s["diagnostics"]["remaining_overlap_count"] == 0 for s in splits)

    audit = client.get(f"{BASEURL}/runs/{run['id']}/leakage-audit").json()
    assert audit["leakage_summary"]["leakage_clean"] is True


def test_reexecution_is_idempotent_on_experiment_and_splits(client):
    run = create(client).json()
    first = client.post(f"{BASEURL}/runs/{run['id']}/execute",
                        json={"create_experiment": True}).json()
    exp_id = first["experiment_id"]
    assert exp_id is not None
    second = client.post(f"{BASEURL}/runs/{run['id']}/execute",
                         json={"create_experiment": True}).json()
    assert second["experiment_id"] == exp_id  # no duplicate experiment
    assert len(client.get(f"{BASEURL}/runs/{run['id']}/splits").json()) == 4


def test_failed_execution_recorded_honestly(client):
    run = create(client).json()
    # Corrupt the stored configuration via a fresh run with bypassed validation.
    bad = service.create_run(
        {"name": "bad", "method": "purged_kfold", "configuration": {"n_folds": 20},
         "samples": samples(6)},
        validate_configuration=False,
    )
    result = client.post(f"{BASEURL}/runs/{bad['id']}/execute", json={})
    assert result.status_code == 200
    assert result.json()["status"] == "failed"
    assert "n_folds" in (result.json()["error_message"] or "")


def test_invalidate_and_execute_conflict(client):
    run = create(client).json()
    inv = client.post(f"{BASEURL}/runs/{run['id']}/invalidate", json={"reason": "obsolete"})
    assert inv.status_code == 200
    assert inv.json()["status"] == "invalidated"
    assert client.post(f"{BASEURL}/runs/{run['id']}/execute", json={}).status_code == 409
    assert client.post(f"{BASEURL}/runs/{run['id']}/invalidate", json={"reason": "x"}).status_code == 409


# ---------------------------------------------------------------------------
# Baseline policy
# ---------------------------------------------------------------------------


def test_baseline_requires_completed_and_clean(client):
    pending = create(client).json()
    assert client.post(f"{BASEURL}/runs/{pending['id']}/mark-baseline").status_code == 409
    # A dirty (standard k-fold) run cannot be baseline.
    dirty = create(client, name="dirty", method="standard_kfold",
                   configuration={"n_folds": 4}).json()
    client.post(f"{BASEURL}/runs/{dirty['id']}/execute", json={})
    assert client.post(f"{BASEURL}/runs/{dirty['id']}/mark-baseline").status_code == 409
    # A clean run can; repeat marking is idempotent.
    clean = create(client, name="clean").json()
    client.post(f"{BASEURL}/runs/{clean['id']}/execute", json={})
    assert client.post(f"{BASEURL}/runs/{clean['id']}/mark-baseline").status_code == 200
    assert client.post(f"{BASEURL}/runs/{clean['id']}/mark-baseline").status_code == 200


def test_baseline_scope_replacement(client):
    a = create(client, name="a").json()
    b = create(client, name="b").json()
    for r in (a, b):
        client.post(f"{BASEURL}/runs/{r['id']}/execute", json={})
    client.post(f"{BASEURL}/runs/{a['id']}/mark-baseline")
    client.post(f"{BASEURL}/runs/{b['id']}/mark-baseline")
    assert client.get(f"{BASEURL}/runs/{a['id']}").json()["is_baseline"] is False
    assert client.get(f"{BASEURL}/runs/{b['id']}").json()["is_baseline"] is True
    # Different method scope stays untouched.
    wf = create(client, name="wf", method="walk_forward",
                configuration={"min_train_size": 10, "test_size": 5}).json()
    client.post(f"{BASEURL}/runs/{wf['id']}/execute", json={})
    client.post(f"{BASEURL}/runs/{wf['id']}/mark-baseline")
    assert client.get(f"{BASEURL}/runs/{b['id']}").json()["is_baseline"] is True


# ---------------------------------------------------------------------------
# Registry / lineage links
# ---------------------------------------------------------------------------


def test_dataset_link_hydration_and_invalidation_warning(client):
    ds = client.post("/datasets", json={
        "name": "VDS", "domain": "x", "dataset_type": "prices"}).json()
    v = client.post(f"/datasets/{ds['id']}/versions", json={
        "version_label": "v1", "storage_locator": "fixture://v/x"}).json()
    run = create(client, dataset_version_id=v["id"]).json()
    assert run["dataset_name"] == "VDS"
    assert run["dataset_invalidated"] is False
    client.post(f"/dataset-versions/{v['id']}/invalidate", json={"reason": "old"})
    again = client.get(f"{BASEURL}/runs/{run['id']}").json()
    assert again["dataset_invalidated"] is True
    # Recorded identity is retained even after invalidation.
    assert again["dataset_version_id"] == v["id"]


def test_missing_links_rejected(client):
    assert create(client, dataset_version_id=9999).status_code == 404
    assert create(client, experiment_id=9999).status_code == 404


# ---------------------------------------------------------------------------
# Comparison + list/filter + export
# ---------------------------------------------------------------------------


def test_compare_runs_neutral(client):
    kf = create(client, name="kf", method="standard_kfold").json()
    pk = create(client, name="pk").json()
    for r in (kf, pk):
        client.post(f"{BASEURL}/runs/{r['id']}/execute", json={})
    cmp = client.get(f"{BASEURL}/compare", params={"a": kf["id"], "b": pk["id"]}).json()
    leak = {e["field"]: e for e in cmp["groups"]["leakage"]}
    assert leak["leakage_clean"]["a"] is False
    assert leak["leakage_clean"]["b"] is True
    assert cmp["fingerprint_match"]["configuration"] is False
    assert client.get(f"{BASEURL}/compare", params={"a": kf["id"], "b": kf["id"]}).status_code == 422


def test_list_filters_and_pagination(client):
    for i in range(3):
        r = create(client, name=f"r{i}").json()
        client.post(f"{BASEURL}/runs/{r['id']}/execute", json={})
    wf = create(client, name="wf-x", method="walk_forward",
                configuration={"min_train_size": 10, "test_size": 5}).json()
    client.post(f"{BASEURL}/runs/{wf['id']}/execute", json={})
    assert client.get(f"{BASEURL}/runs", params={"method": "walk_forward"}).json()["total"] == 1
    assert client.get(f"{BASEURL}/runs", params={"query": "wf-x"}).json()["total"] == 1
    assert client.get(f"{BASEURL}/runs", params={"leakage_clean": "true"}).json()["total"] == 4
    paged = client.get(f"{BASEURL}/runs", params={"page_size": 2}).json()
    assert paged["total"] == 4 and len(paged["items"]) == 2 and paged["total_pages"] == 2


def test_export_privacy_and_shape(client):
    r = create(client).json()
    client.post(f"{BASEURL}/runs/{r['id']}/execute", json={})
    ex = client.get(f"{BASEURL}/export")
    assert ex.status_code == 200
    body = ex.json()
    assert body["schema_version"] and len(body["runs"]) == 1 and len(body["splits"]) == 4
    text = json.dumps(body).lower()
    for needle in ("c:\\", "c:/", "/users/", "/home/", "password", "api_key", "quantlab.db"):
        assert needle not in text


# ---------------------------------------------------------------------------
# Demo loader
# ---------------------------------------------------------------------------


def test_demo_seed_idempotent_and_semantics(client):
    first = client.post(f"{BASEURL}/demo-seed").json()
    assert first["created_runs"] == 7
    second = client.post(f"{BASEURL}/demo-seed").json()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 7
    summary = client.get(f"{BASEURL}/summary").json()
    assert summary["runs"] == 7 and summary["baselines"] == 1
    runs = {r["name"]: r for r in client.get(f"{BASEURL}/runs", params={"page_size": 20}).json()["items"]}
    kf = runs["Demo — Standard K-fold (leakage reference)"]
    assert kf["leakage_clean"] is False and kf["invalid_split_count"] > 0
    bad = runs["Demo — Invalid configuration (folds > samples)"]
    assert bad["status"] == "failed"
    base = runs["Demo — Baseline candidate (purged + embargo, linked)"]
    assert base["is_baseline"] and base["dataset_name"] and base["experiment_id"]


def test_demo_preserves_user_runs_and_registries(client):
    mine = create(client, name="user run").json()
    client.post(f"{BASEURL}/demo-seed")
    client.post(f"{BASEURL}/demo-seed")
    assert client.get(f"{BASEURL}/runs/{mine['id']}").json()["name"] == "user run"
    # Existing registries still function.
    assert client.get("/experiment-registry/summary").status_code == 200
    assert client.get("/datasets/summary").status_code == 200
    report = client.post("/saved-reports", json={
        "title": "R", "report_type": "markdown", "source_type": "manual",
        "markdown_content": "# hi"})
    assert report.status_code == 200


# ---------------------------------------------------------------------------
# Adversarial API paths
# ---------------------------------------------------------------------------


def test_adversarial_rejections(client):
    base_samples = samples(8)
    mk = lambda **o: {"name": "X", "method": "purged_kfold",
                      "configuration": {"n_folds": 3}, "samples": base_samples, **o}
    # eval < pred
    bad = [dict(base_samples[0], sample_id="z",
                prediction_time="2025-02-01T00:00:00",
                evaluation_time="2025-01-01T00:00:00")] + base_samples[1:]
    assert client.post(f"{BASEURL}/runs", json=mk(samples=bad)).status_code == 422
    # duplicates
    assert client.post(f"{BASEURL}/runs", json=mk(samples=[base_samples[0]] * 8)).status_code == 422
    # too few samples
    assert client.post(f"{BASEURL}/runs", json=mk(samples=base_samples[:2])).status_code == 422
    # folds > samples (eager)
    assert client.post(f"{BASEURL}/runs", json=mk(configuration={"n_folds": 30})).status_code == 422
    # CPCV explosion (eager)
    assert client.post(f"{BASEURL}/runs", json=mk(
        method="cpcv", configuration={"n_groups": 12, "test_groups": 6})).status_code == 422
    # negative embargo / bad fraction (eager)
    assert client.post(f"{BASEURL}/runs", json=mk(
        configuration={"n_folds": 3, "embargo": {"mode": "duration_days", "value": -2}})).status_code == 422
    assert client.post(f"{BASEURL}/runs", json=mk(
        configuration={"n_folds": 3, "embargo": {"mode": "fraction", "value": 0.9}})).status_code == 422
    # unknown method / extra field / blank name
    assert client.post(f"{BASEURL}/runs", json=mk(method="magic")).status_code == 422
    assert client.post(f"{BASEURL}/runs", json={**mk(), "evil": 1}).status_code == 422
    assert client.post(f"{BASEURL}/runs", json=mk(name="   ")).status_code == 422
    # non-finite label via raw NaN token → stable 422
    raw_body = json.dumps(mk()).replace('"label": 1', '"label": NaN', 1)
    assert client.post(f"{BASEURL}/runs", content=raw_body,
                       headers={"Content-Type": "application/json"}).status_code == 422
    # unknown ids
    assert client.get(f"{BASEURL}/runs/9999").status_code == 404
    assert client.get(f"{BASEURL}/runs/9999/splits").status_code == 404
    assert client.post(f"{BASEURL}/runs/9999/execute", json={}).status_code == 404
