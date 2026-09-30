"""Phase 65: pure checks avoid schema setup; persistence tests opt into isolation."""

import copy

import pytest

from app.ml_lifecycle.identity import canonical, fingerprint, read_json, table
from tests.test_ml_lifecycle_import import legacy

pytestmark = [pytest.mark.usefixtures("isolated_lab_db")]


@pytest.fixture(scope="module")
def snapshot():
    from app.ml_lifecycle.demo import fit_snapshot, prepare_demo
    return fit_snapshot(prepare_demo())


@pytest.mark.db_free
def test_identity_is_canonical_and_rejects_unsafe_json():
    assert fingerprint("x", {"b": 2, "a": 1}) == fingerprint("x", {"a": 1, "b": 2})
    assert fingerprint("x", ["a", "b"]) != fingerprint("x", ["b", "a"])
    for value in (float("nan"), float("inf"), object()):
        with pytest.raises(ValueError):
            canonical(value)
    with pytest.raises(ValueError, match="duplicate"):
        read_json(b'{"x":1,"x":2}')


@pytest.mark.db_free
def test_table_uses_full_timestamps_and_rejects_duplicate_keys():
    columns = [{"name": "timestamp", "type": "timestamp"}, {"name": "x", "type": "number"}]
    rows = [["2024-01-01T12:00:00Z", 1], ["2024-01-01T13:00:00Z", 2]]
    assert table(columns, rows, ["timestamp"]) == table(columns, rows[::-1], ["timestamp"])
    with pytest.raises(ValueError, match="duplicate"):
        table(columns, rows + rows[:1], ["timestamp"])
    with pytest.raises(ValueError, match="offset"):
        table(columns, [["2024-01-01T12:00:00", 1]], ["timestamp"])


@pytest.mark.db_free
def test_demo_genuine_oof_and_heldout_mutation():
    from app.ml_lifecycle.demo import fit_snapshot, prepare_demo

    prepared = prepare_demo()
    original = fit_snapshot(prepared)
    canonical(original)
    from app.ml_lifecycle.validation import validate
    validate(original, allow_demo=True)
    assert len(original["samples"]) == 169
    assert len(original["models"]) == 5
    changed = copy.deepcopy(prepared)
    for i in changed["outer"]["test_pos"]:
        changed["ds"].loc[i, "label__direction_1"] *= -1
        changed["samples"][i]["label"] *= -1
    second = fit_snapshot(changed)
    assert original["models"] == second["models"]
    assert original["calibration"] == second["calibration"]
    assert len(original["models"]) > 2
    for model in original["models"]:
        generated = [p for p in original["predictions"] if p["model_hash"] == model["hash"]]
        assert generated
        assert not set(model["train_ids"]) & {p["sample_id"] for p in generated}


@pytest.mark.fresh_schema
def test_complete_demo_and_idempotent_links():
    from app.ml_lifecycle import service
    run = service.demo()
    assert run["completeness"] == "complete", run["links"]
    assert run["integrity"] == "intact"
    assert len(run["links"]) == 5
    again = service.demo()
    assert again["id"] == run["id"]
    assert again["links"] == run["links"]
    assert service.export(run["id"])["schema_version"] == 1
    assert service.compare(run["id"], run["id"])["metrics"][0] == run["snapshot"]["evaluation"]["metrics"]


@pytest.mark.db_free
@pytest.mark.parametrize("case", ["features", "order", "oof", "availability", "duplicate", "membership", "calibration"])
def test_invalid_provenance_refused(snapshot, case):
    from app.ml_lifecycle.validation import validate
    changed = copy.deepcopy(snapshot)
    if case == "features":
        changed["samples"][0].pop("features")
    elif case == "order":
        changed["feature_order"].reverse()
    elif case == "oof":
        changed["predictions"][-1]["role"] = "inner_oof"
    elif case == "availability":
        changed["samples"][0]["feature_available_at"] = "2030-01-01T00:00:00Z"
    elif case == "duplicate":
        changed["predictions"].append(changed["predictions"][0])
    elif case == "membership":
        changed["models"][0]["train_ids"].append(changed["predictions"][0]["sample_id"])
    else:
        changed["calibration"]["fit_ids"].append(changed["predictions"][-1]["sample_id"])
    with pytest.raises(ValueError):
        validate(changed, allow_demo=True)


@pytest.mark.db_free
def test_single_lag_gross_net_and_exact_keys(snapshot):
    from app.ml_lifecycle.adapters import records
    periods = records(snapshot["evaluation"]["periods"])
    signals = records(snapshot["evaluation"]["signals"])
    assert len(periods) == len(signals) == 32
    for index, row in enumerate(periods):
        assert row["effective_position"] == (0 if index == 0 else periods[index - 1]["target_position"])
        assert row["strategy_return"] - row["net_strategy_return"] == pytest.approx(row["transaction_cost"])
        assert (row["timestamp"], row["root_symbol"], row["active_contract"]) == (signals[index]["timestamp"], signals[index]["root_symbol"], signals[index]["active_contract"])


@pytest.mark.db_free
def test_trailing_features_are_prefix_invariant():
    from app.ml_lifecycle.demo import prepare_demo
    from app.features import build_feature_matrix
    from app.features.spec import FeatureSpec
    import pandas as pd
    prepared = prepare_demo()
    specs = [FeatureSpec.model_validate(s) for s in prepared["specs"]["features"]]
    full = build_feature_matrix(prepared["cont"], specs=specs)
    prefix = build_feature_matrix(prepared["cont"].iloc[:170], specs=specs)
    pd.testing.assert_frame_equal(full.iloc[:170].reset_index(drop=True), prefix)


def test_missing_mismatched_invalidated_dataset_refused(snapshot):
    from app.ml_lifecycle import service
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate
    request = {"name": "Fixture", "dataset_version_id": 99999, "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot}
    with pytest.raises(ValueError, match="existing"):
        service.register(request, demo_key="fixture")
    dataset = datasets.create_dataset(DatasetCreate(name="Fixture", domain="test", dataset_type="table", source_type="deterministic_fixture").model_dump(mode="json"))
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", storage_locator="fixture://test/ml", content_fingerprint="a" * 64).model_dump(mode="json"))
    request["dataset_version_id"] = version["id"]
    with pytest.raises(ValueError, match="fingerprint"):
        service.register(request, demo_key="fixture")
    datasets.invalidate_version(version["id"], "Fixture invalidation")
    with pytest.raises(service.ConflictError, match="invalidated"):
        service.register(request, demo_key="fixture")


def test_partial_failure_retries_same_destination_and_detects_mutation(monkeypatch):
    from app.ml_lifecycle import service, adapters, store
    original = adapters.execute
    attempts = []

    def fail_once(adapter, run_id, record):
        if adapter == "features":
            attempts.append(run_id)
            if len(attempts) == 1:
                raise ValueError("synthetic adapter failure")
        return original(adapter, run_id, record)

    monkeypatch.setattr(adapters, "execute", fail_once)
    run = service.demo()
    assert run["processing_status"] == "failed" and run["completeness"] == "incomplete"
    completed = service.demo()
    assert completed["completeness"] == "complete"
    assert attempts[0] == attempts[1]
    # Alter material downstream content without updating the advertised hash.
    validation = next(l for l in completed["links"] if l["adapter"] == "validation")
    with store.connection() as conn:
        conn.execute("UPDATE validation_splits SET train_ids_json='[]' WHERE validation_run_id=?", (validation["destination_id"],))
    assert service.get_run(run["id"])["integrity"] == "changed"
    with pytest.raises(service.ConflictError):
        service.export(run["id"])


def test_snapshot_mutation_and_dataset_invalidation():
    from app.ml_lifecycle import service, store
    from app.dataset_registry import service as datasets
    run = service.demo()
    datasets.invalidate_version(run["dataset_version_id"], "Fixture-only invalidation")
    assert service.get_run(run["id"])["integrity"] == "changed"
    with pytest.raises(service.ConflictError):
        service.compare(run["id"], run["id"])
    tampered = copy.deepcopy(run["snapshot"])
    tampered["predictions"][0]["raw_probability"] = .9876
    with store.connection() as conn:
        conn.execute("UPDATE ml_lifecycles SET snapshot_json=? WHERE id=?", (canonical(tampered), run["id"]))
    assert service.get_run(run["id"])["completeness"] == "incomplete"


def test_api_is_bounded_and_never_accepts_paths(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ml_lifecycle_routes import router
    from app.ml_lifecycle import service
    application = FastAPI()
    application.include_router(router)
    client = TestClient(application)
    monkeypatch.setattr(service, "demo", lambda: pytest.fail("read invoked demo"))
    assert client.get("/ml-lifecycles").json()["items"] == []
    assert client.get("/ml-lifecycles/999").status_code == 404
    for query in ("page=0", "page_size=51", "integrity=green", "completeness=verified"):
        assert client.get("/ml-lifecycles?" + query).status_code == 422
    assert client.post("/ml-lifecycles", json={"source_root": "C:/not-a-real-fixture"}).status_code == 422
    assert client.post("/ml-lifecycles", json={"name": "Malformed", "dataset_version_id": 1,
                                              "dataset_content_hash": "a" * 64,
                                              "snapshot": {"schema_version": 1, "origin": "experiment_store"}}).status_code == 422
    assert client.post("/ml-lifecycles/1/links", json={"adapter": "shell"}).status_code == 422


def test_legacy_api_registration_roundtrip_never_trains(legacy, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ml_lifecycle_routes import router
    from app.ml_lifecycle.importer import preview
    from app.ml_lifecycle import demo as demo_module
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate

    snapshot = preview(legacy[0], legacy[1])
    dataset = datasets.create_dataset(DatasetCreate(name="Imported artifacts fixture", domain="research", dataset_type="experiment_snapshot", source_type="local_file").model_dump(mode="json"))
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", format="json", storage_locator="fixture://legacy/snapshot", content_fingerprint=snapshot["source_hash"]).model_dump(mode="json"))
    monkeypatch.setattr(demo_module, "train_model", lambda *a, **kw: pytest.fail("import/list/view trained a model"))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    payload = {"name": "Imported fixture", "dataset_version_id": version["id"], "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot}
    response = client.post("/ml-lifecycles", json=payload)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["completeness"] == "incomplete" and run["validation_state"] == "unverified"
    assert run["integrity"] == "intact"
    assert client.post("/ml-lifecycles", json=payload).json()["id"] == run["id"]
    assert client.get("/ml-lifecycles?completeness=incomplete").json()["total"] == 1
    exported = client.get(f"/ml-lifecycles/{run['id']}/export").json()
    assert exported["lifecycle"]["snapshot"] == snapshot
    assert client.post(f"/ml-lifecycles/{run['id']}/links", json={"adapter": "features"}).status_code == 422
