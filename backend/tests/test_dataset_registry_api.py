"""
API tests for the Dataset Lineage registry (Phase 49.0).

Exercises the FastAPI routes end to end against a fresh temporary SQLite
database: happy paths, error paths (404/409/422), lineage + quality + link
endpoints, export privacy (no absolute paths / credentials), demo-seed
idempotence, and preservation of the existing Experiment Registry and Saved
Reports APIs.
"""

from __future__ import annotations

import json

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _dataset(client, **over):
    payload = {
        "name": "DS",
        "domain": "equities",
        "dataset_type": "prices",
        "source_type": "deterministic_fixture",
        "format": "csv",
    }
    payload.update(over)
    return client.post("/datasets", json=payload)


def _version(client, dataset_id, label="v1", **over):
    payload = {
        "version_label": label,
        "storage_locator": f"fixture://test/{label}",
        "deterministic": True,
        "row_count": 100,
        "schema_snapshot": {
            "fields": [{"name": "date", "type": "date", "nullable": False}],
            "ordering_significant": False,
        },
        "provenance": {"source": "test"},
    }
    payload.update(over)
    return client.post(f"/datasets/{dataset_id}/versions", json=payload)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_dataset_crud_and_versions(client):
    created = _dataset(client, name="Prices")
    assert created.status_code == 201
    ds = created.json()

    v = _version(client, ds["id"])
    assert v.status_code == 201
    body = v.json()
    assert body["manifest_fingerprint"]
    assert body["is_current"] is True

    listed = client.get("/datasets")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["version_count"] == 1

    patched = client.patch(f"/datasets/{ds['id']}", json={"notes": "hi"})
    assert patched.status_code == 200
    assert patched.json()["notes"] == "hi"

    versions = client.get(f"/datasets/{ds['id']}/versions")
    assert versions.status_code == 200
    assert len(versions.json()) == 1


def test_summary(client):
    ds = _dataset(client).json()
    _version(client, ds["id"])
    summary = client.get("/datasets/summary").json()
    assert summary["datasets"] == 1
    assert summary["versions"] == 1


def test_lineage_and_graph_endpoints(client):
    ds = _dataset(client).json()
    a = _version(client, ds["id"], "a").json()
    b = _version(client, ds["id"], "b").json()
    edge = client.post(
        "/dataset-lineage",
        json={
            "parent_version_id": a["id"],
            "child_version_id": b["id"],
            "relationship_type": "derived_from",
            "transformation_name": "resample",
            "parameters": {"freq": "5min"},
        },
    )
    assert edge.status_code == 201
    graph = client.get(f"/dataset-versions/{b['id']}/lineage").json()
    assert {n["version_id"] for n in graph["nodes"]} == {a["id"], b["id"]}
    assert graph["truncated"] is False


def test_quality_endpoints(client):
    ds = _dataset(client).json()
    v = _version(client, ds["id"], statistics_summary={"missing_ratio": 0.5}).json()
    run = client.post(
        f"/dataset-versions/{v['id']}/quality-checks",
        json={"checks": ["missing_ratio_within_limit"], "expectations": {}},
    )
    assert run.status_code == 200
    assert run.json()[0]["status"] == "warning"
    listed = client.get(f"/dataset-versions/{v['id']}/quality")
    assert len(listed.json()) == 1
    assert client.get(f"/dataset-versions/{v['id']}").json()["quality_status"] == "warning"


def test_compare_endpoint(client):
    ds = _dataset(client).json()
    a = _version(client, ds["id"], "a").json()
    b = _version(client, ds["id"], "b", row_count=200).json()
    cmp = client.get("/dataset-versions/compare", params={"a": a["id"], "b": b["id"]})
    assert cmp.status_code == 200
    assert cmp.json()["fingerprints"]["manifest"] is False


def test_invalidate_endpoint(client):
    ds = _dataset(client).json()
    v = _version(client, ds["id"]).json()
    inv = client.post(
        f"/dataset-versions/{v['id']}/invalidate", json={"reason": "bad data"}
    )
    assert inv.status_code == 200
    assert inv.json()["invalidated_at"]
    again = client.post(
        f"/dataset-versions/{v['id']}/invalidate", json={"reason": "x"}
    )
    assert again.status_code == 409


def test_experiment_link_endpoints(client):
    exp = client.post(
        "/experiment-registry/experiments",
        json={"name": "E", "module": "m", "experiment_type": "t"},
    ).json()
    ds = _dataset(client).json()
    v = _version(client, ds["id"]).json()
    link = client.post(
        "/dataset-links",
        json={"experiment_id": exp["id"], "dataset_version_id": v["id"], "role": "input"},
    )
    assert link.status_code == 201
    from_version = client.get(f"/dataset-versions/{v['id']}/experiments").json()
    assert from_version[0]["experiment_name"] == "E"
    from_experiment = client.get(
        f"/experiment-registry/experiments/{exp['id']}/datasets"
    ).json()
    assert from_experiment[0]["version_label"] == "v1"


# ---------------------------------------------------------------------------
# Demo seed + export
# ---------------------------------------------------------------------------


def test_demo_seed_idempotent(client):
    first = client.post("/datasets/demo-seed").json()
    assert first["created_datasets"] == 7
    second = client.post("/datasets/demo-seed").json()
    assert second["created_datasets"] == 0
    assert second["skipped_existing"] > 0


def test_export_shape_and_privacy(client):
    client.post("/datasets/demo-seed")
    r = client.get("/datasets/export")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"]
    assert len(body["datasets"]) == 7
    assert len(body["lineage"]) == 5
    text = json.dumps(body).lower()
    for needle in ("c:\\", "c:/", "/users/", "/home/", "password", "api_key", "secret",
                   "quantlab.db", "\\\\"):
        assert needle not in text, f"export leaked {needle!r}"


def test_export_respects_filters(client):
    client.post("/datasets/demo-seed")
    _dataset(client, name="Real one")
    only_demo = client.get("/datasets/export", params={"demo": "true"}).json()
    assert len(only_demo["datasets"]) == 7
    assert only_demo["filters"] == {"demo": True}


# ---------------------------------------------------------------------------
# Error / adversarial paths
# ---------------------------------------------------------------------------


def test_not_found_paths(client):
    assert client.get("/datasets/999").status_code == 404
    assert client.get("/dataset-versions/999").status_code == 404
    assert client.get("/dataset-versions/999/lineage").status_code == 404
    assert client.get("/dataset-versions/999/quality").status_code == 404
    assert client.get("/experiment-registry/experiments/999/datasets").status_code == 404


def test_conflicts(client):
    ds = _dataset(client, name="Dup").json()
    assert _dataset(client, name="Dup").status_code == 409
    _version(client, ds["id"], "v1")
    assert _version(client, ds["id"], "v1").status_code == 409


def test_locator_rejections(client):
    ds = _dataset(client).json()
    for bad in (
        "C:\\Users\\x\\data.csv",
        "/home/x/data.csv",
        "\\\\server\\share.csv",
        "fixture://../../secret",
        "provider://user:tok@fred/x",
        "http://example.com/data.csv",
    ):
        r = _version(client, ds["id"], "vX", storage_locator=bad)
        assert r.status_code == 422, f"{bad!r} not rejected: {r.status_code}"


def test_validation_rejections(client):
    # Credential URL
    assert _dataset(client, name="U", license_url="https://a:b@x.com").status_code == 422
    # Absolute source_reference
    assert _dataset(client, name="V", source_reference="C:\\data").status_code == 422
    # Bad source_type / extra field / blank name
    assert _dataset(client, name="W", source_type="nope").status_code == 422
    assert client.post("/datasets", json={"name": "X", "domain": "d", "dataset_type": "t", "evil": 1}).status_code == 422
    assert _dataset(client, name="   ").status_code == 422
    # Bad SHA
    ds = _dataset(client, name="Y").json()
    assert _version(client, ds["id"], content_fingerprint="zzz").status_code == 422
    # start > end
    assert _version(
        client, ds["id"], "vr",
        start_time="2022-01-01T00:00:00Z", end_time="2021-01-01T00:00:00Z",
    ).status_code == 422
    # Non-finite statistics via raw NaN token → clean 422 (app-wide handler)
    raw = (
        '{"version_label":"vn","storage_locator":"fixture://t/vn",'
        '"statistics_summary":{"x":NaN}}'
    )
    r = client.post(
        f"/datasets/{ds['id']}/versions",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_lineage_rejections(client):
    ds = _dataset(client).json()
    a = _version(client, ds["id"], "a").json()
    b = _version(client, ds["id"], "b").json()
    base = {
        "relationship_type": "derived_from",
        "transformation_name": "t",
    }
    assert client.post("/dataset-lineage", json={**base, "parent_version_id": a["id"], "child_version_id": a["id"]}).status_code == 422
    assert client.post("/dataset-lineage", json={**base, "parent_version_id": a["id"], "child_version_id": 999}).status_code == 404
    assert client.post("/dataset-lineage", json={**base, "relationship_type": "invented", "parent_version_id": a["id"], "child_version_id": b["id"]}).status_code == 422
    client.post("/dataset-lineage", json={**base, "parent_version_id": a["id"], "child_version_id": b["id"]})
    assert client.post("/dataset-lineage", json={**base, "parent_version_id": b["id"], "child_version_id": a["id"]}).status_code == 422
    # Absolute code_reference rejected
    assert client.post(
        "/dataset-lineage",
        json={**base, "parent_version_id": a["id"], "child_version_id": b["id"],
              "code_reference": "C:\\code\\x.py"},
    ).status_code == 422


def test_link_rejections(client):
    ds = _dataset(client).json()
    v = _version(client, ds["id"]).json()
    assert client.post("/dataset-links", json={"experiment_id": 999, "dataset_version_id": v["id"], "role": "input"}).status_code == 404
    exp = client.post(
        "/experiment-registry/experiments",
        json={"name": "E", "module": "m", "experiment_type": "t"},
    ).json()
    assert client.post("/dataset-links", json={"experiment_id": exp["id"], "dataset_version_id": v["id"], "role": "banana"}).status_code == 422
    assert client.post("/dataset-links", json={"experiment_id": exp["id"], "dataset_version_id": 999, "role": "input"}).status_code == 404


def test_compare_same_id_rejected(client):
    ds = _dataset(client).json()
    v = _version(client, ds["id"]).json()
    assert client.get("/dataset-versions/compare", params={"a": v["id"], "b": v["id"]}).status_code == 422


# ---------------------------------------------------------------------------
# Coexistence with existing registries
# ---------------------------------------------------------------------------


def test_experiment_registry_and_saved_reports_still_work(client):
    client.post("/datasets/demo-seed")
    # Experiment registry list works and contains the demo experiments.
    experiments = client.get("/experiment-registry/experiments").json()
    assert experiments["total"] >= 6
    # Saved reports unaffected.
    report = client.post(
        "/saved-reports",
        json={
            "title": "R",
            "report_type": "markdown",
            "source_type": "manual",
            "markdown_content": "# hi",
        },
    )
    assert report.status_code == 200
    assert len(client.get("/saved-reports").json()) == 1
