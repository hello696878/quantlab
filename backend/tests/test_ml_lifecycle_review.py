"""Review regressions: trust boundaries and stored material, in owned fixtures."""

import copy
import sqlite3

import pytest

from app.ml_lifecycle.identity import canonical, fingerprint, table, timestamp
from tests.test_ml_lifecycle_import import legacy
from tests.test_ml_lifecycle import snapshot

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


@pytest.fixture
def imported(legacy):
    from app.ml_lifecycle import service
    from app.ml_lifecycle.importer import preview
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate
    source = preview(legacy[0], legacy[1])
    dataset = datasets.create_dataset(DatasetCreate(name="Review fixture", domain="test",
        dataset_type="experiment_snapshot", source_type="local_file").model_dump(mode="json"))
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1",
        storage_locator="fixture://review/legacy", content_fingerprint=source["source_hash"]).model_dump(mode="json"))
    return service.register({"name": "Review import", "dataset_version_id": version["id"],
        "dataset_content_hash": source["source_hash"], "snapshot": source})


@pytest.mark.parametrize("column,value", [
    ("schema_snapshot_json", '{"fields":[{"name":"changed"}]}'),
    ("statistics_json", '{"mean":99}'),
    ("provenance_json", '{"available_at":"2024-01-01T00:00:00Z"}'),
    ("row_count", 999), ("effective_from", "2024-01-01T00:00:00Z")])
def test_dataset_material_mutation_refuses_export_and_compare(imported, column, value):
    from app.ml_lifecycle import service, store
    from app.dataset_registry import store as datasets
    version_id = imported["dataset_version_id"]
    before = datasets.get_version(version_id)
    with store.connection() as conn:
        # Column comes exclusively from the fixed test parameter list.
        conn.execute(f"UPDATE dataset_versions SET {column}=? WHERE id=?", (value, version_id))
    after = datasets.get_version(version_id)
    assert before["content_fingerprint"] == after["content_fingerprint"]
    assert before["manifest_fingerprint"] == after["manifest_fingerprint"]
    assert service.get_run(imported["id"])["integrity"] == "changed"
    for action in (lambda: service.export(imported["id"]),
                   lambda: service.compare(imported["id"], imported["id"])):
        with pytest.raises(service.ConflictError):
            action()


def test_inactive_dataset_and_missing_material_pin_fail_closed(imported):
    from app.ml_lifecycle import service, store
    with store.connection() as conn:
        conn.execute("UPDATE ml_lifecycles SET dataset_material_hash=NULL WHERE id=?", (imported["id"],))
    assert service.get_run(imported["id"])["validation_state"] == "unverified"
    assert service.get_run(imported["id"])["integrity"] == "changed"
    with store.connection() as conn:
        conn.execute("UPDATE datasets SET is_active=0 WHERE id=(SELECT dataset_id FROM dataset_versions WHERE id=?)",
                     (imported["dataset_version_id"],))
    with pytest.raises(service.ConflictError, match="inactive"):
        service.dataset_binding(imported["dataset_version_id"])


@pytest.mark.db_free
def test_dataset_pin_excludes_location_and_row_ids_but_keeps_event_metadata(monkeypatch):
    from app.ml_lifecycle import service
    dataset = {"id": 1, "is_active": True, "metadata": {"event_id": 1, "available_at": "2024-01-01"}}
    version = {"id": 2, "dataset_id": 1, "storage_locator": "fixture://first", "created_at": "first"}
    monkeypatch.setattr(service.dataset_store, "get_dataset", lambda _: dataset)
    monkeypatch.setattr(service.dataset_store, "get_version", lambda _: version)
    digest = service.dataset_binding(2)[1]
    dataset.update(id=10, updated_at="later", current_version_id=20)
    version.update(id=20, dataset_id=10, storage_locator="fixture://second", created_at="later")
    assert service.dataset_binding(20)[1] == digest
    dataset["metadata"]["event_id"] = 2
    assert service.dataset_binding(20)[1] != digest


def test_additive_schema_preserves_old_record_without_inventing_pin():
    from app.ml_lifecycle import store
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("""CREATE TABLE ml_lifecycles(id INTEGER PRIMARY KEY, name TEXT,
            created_at TEXT, lifecycle_hash TEXT, dataset_version_id INTEGER,
            dataset_content_hash TEXT, dataset_manifest_hash TEXT, snapshot_json TEXT,
            snapshot_hash TEXT, trusted_demo INTEGER, demo_key TEXT)""")
        conn.execute("INSERT INTO ml_lifecycles(id,name,snapshot_json) VALUES (1,'old','{}')")
        store.initialize(conn)
        store.initialize(conn)
        assert conn.execute("SELECT name,snapshot_json,dataset_material_hash FROM ml_lifecycles").fetchone() == ("old", "{}", None)
    finally:
        conn.close()


@pytest.mark.db_free
@pytest.mark.parametrize("body", [
    b'{"name":"first","name":"second"}',
    b'{"snapshot":{"schema_version":1,"schema_version":2}}',
    b'{"adapter":"validation","adapter":"costs"}',
    b'{"snapshot":{"x":NaN}}'])
def test_api_refuses_ambiguous_json_before_actions(monkeypatch, body):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ml_lifecycle_routes import router
    from app.ml_lifecycle import service
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(service, "register", lambda *_: pytest.fail("ambiguous registration executed"))
    monkeypatch.setattr(service, "link", lambda *_: pytest.fail("ambiguous link executed"))
    client = TestClient(app)
    for path in ("/ml-lifecycles", "/ml-lifecycles/1/links"):
        assert client.post(path, content=body, headers={"Content-Type": "application/json"}).status_code == 422


@pytest.mark.db_free
def test_copied_complete_demo_cannot_gain_trust_via_public_api(snapshot, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ml_lifecycle import store
    from app.ml_lifecycle_routes import router
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(store, "insert", lambda *a, **kw: pytest.fail("client demo persisted"))
    forged = copy.deepcopy(snapshot)
    payload = {"name": "Copied complete demo", "dataset_version_id": 1,
               "dataset_content_hash": forged["source_hash"], "snapshot": forged}
    client = TestClient(app)
    assert client.post("/ml-lifecycles", json=payload).status_code == 422
    for field in ("trusted_demo", "integrity", "validation_state"):
        assert client.post("/ml-lifecycles", json={**payload, field: True}).status_code == 422
    forged["origin"] = "experiment_store"
    assert client.post("/ml-lifecycles", json=payload).status_code == 422


@pytest.mark.db_free
@pytest.mark.parametrize("value", [True, 1.0, "1", 2])
def test_schema_version_never_coerces_scalar(value):
    from app.ml_lifecycle.models import Registration
    from app.ml_lifecycle.validation import validate
    with pytest.raises(ValueError):
        Registration.model_validate({"schema_version": value, "name": "x", "dataset_version_id": 1,
                                     "dataset_content_hash": "a" * 64, "snapshot": {}})
    with pytest.raises(ValueError, match="schema"):
        validate({"schema_version": value})


@pytest.mark.db_free
@pytest.mark.parametrize("field,value", [("schema_version", True), ("n_oos_rows", True),
    ("n_scored_rows", 2.0), ("feature_columns", ["feature__x", "feature__x"])])
def test_self_rehashed_legacy_metadata_cannot_erase_scalar_semantics(legacy, field, value):
    from app.ml_lifecycle.importer import preview
    from app.ml_lifecycle.validation import validate
    source = preview(legacy[0], legacy[1])
    source["source"]["metadata"][field] = value
    source["source_hash"] = fingerprint("experiment_source", source["source"])
    with pytest.raises(ValueError):
        validate(source)


@pytest.mark.db_free
def test_declared_table_types_are_strict_even_with_no_rows():
    for column, keys in [({"name": "x", "type": "object"}, ["x"]),
                         ({"name": "x", "type": "number", "nullable": "false"}, ["x"]),
                         ({"name": "x", "type": "number"}, ["x", "x"])]:
        with pytest.raises(ValueError):
            table([column], [], keys)
    for number in (True, 2 ** 53 + 1, 10 ** 400):
        with pytest.raises(ValueError):
            table([{"name": "x", "type": "number"}], [[number]], ["x"])
    assert len({canonical(x) for x in (None, False, 0, 0.0, "0")}) == 5
    with pytest.raises(ValueError, match="offset"):
        timestamp("0001-01-01T00:00:00+14:00")
