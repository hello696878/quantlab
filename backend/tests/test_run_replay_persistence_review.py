"""Adversarial replay persistence checks against independent disposable databases."""
import copy
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.run_replay import adapter, environment, identity, service, store
from app.saved_backtests import create_saved_backtest, delete_saved_backtest, get_saved_backtest
from .test_run_replay import config, payload
from .test_ml_lifecycle_import import legacy

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


def _registered():
    saved = create_saved_backtest(payload())
    return service.register_legacy(saved["id"])


def _reseal(context_id, change):
    """An attacker can recompute checksums; independent bindings must still hold."""
    row = store.get(context_id)
    snapshot = identity.loads(row["snapshot_json"])
    change(snapshot)
    saved = get_saved_backtest(row["saved_backtest_id"])
    snapshot["input_hash"] = identity.digest(snapshot["inputs"])
    snapshot["environment_hash"] = identity.digest(snapshot["execution_environment"]) if snapshot["execution_environment"] else None
    snapshot["result_hash"] = service.result_identity(saved)
    snapshot["execution_hash"] = identity.digest({"schema_version": "saved_execution_v1", "saved_backtest_id": saved["id"],
        "created_at": saved["created_at"], "result_hash": snapshot["result_hash"], "input_hash": snapshot["input_hash"],
        "environment_hash": snapshot["environment_hash"]})
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE run_replay_contexts SET snapshot_json=?,snapshot_hash=? WHERE id=?",
                     (identity.validate(snapshot), identity.digest(snapshot), context_id))


@pytest.mark.parametrize("field,value", [("adapter", "config_only"), ("effective_cost_bps", 23),
                                         ("diagnostics", {"robustness": {"enabled": True}}),
                                         ("schema_version", "future_input_v2")])
def test_rehashed_input_contradictions_are_changed(field, value):
    context = _registered()
    _reseal(context["context_id"], lambda snap: snap["inputs"].__setitem__(field, value))
    with pytest.raises(service.Changed, match="bindings"):
        service.preflight(context["context_id"])


def test_rehashed_embedded_configuration_cannot_disagree_with_saved_run():
    context = _registered()
    _reseal(context["context_id"], lambda snap: snap["inputs"]["canonical_config"].__setitem__("ticker", "QQQ"))
    assert TestClient(main.app).get(f'/run-replay/contexts/{context["context_id"]}').status_code == 409


@pytest.mark.parametrize("kind", ["schema", "original_request", "request_provenance", "execution_environment", "save_environment", "trust"])
def test_rehashed_context_requires_valid_independent_metadata(kind):
    context = _registered()

    def alter(snapshot):
        if kind == "schema":
            snapshot["schema_version"] = "replay_context_v99"
        elif kind == "original_request":
            snapshot["original_request"] = {**adapter.restore(config()), "fast_window": 5}
        elif kind == "request_provenance":
            snapshot["request_provenance"] = "wire_json"
        elif kind == "execution_environment":
            snapshot["execution_environment"] = environment.collect("inspection")
            snapshot["environment_trust"] = "declared_execution_metadata_not_attestation"
        elif kind == "save_environment":
            snapshot["save_environment"]["classification"] = "execution"
        else:
            snapshot["environment_trust"] = "verified_historical_execution"

    _reseal(context["context_id"], alter)
    with pytest.raises(service.Changed):
        service.resolve_hash(context["config_hash_full"])


def test_rehashed_result_identity_cannot_change_saved_ticker_independently():
    context = _registered()
    row = store.get(context["context_id"])
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE saved_backtests SET ticker='QQQ' WHERE id=?", (row["saved_backtest_id"],))
    _reseal(context["context_id"], lambda snap: None)
    with pytest.raises(service.Changed, match="Saved result identity"):
        service.preflight(context["context_id"])


def _local_payload(*, ticker="LOCAL", price_offset=0):
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate

    rows = [f"{date(2020, 1, 1) + timedelta(days=i)},{100 + i + price_offset}" for i in range(140)]
    text = "date,close\n" + "\n".join(rows) + "\n"
    raw_hash = hashlib.sha256(text.encode()).hexdigest()
    original = {"ticker": ticker, "start_date": "2020-01-01", "end_date": "2020-05-19"}
    cfg = adapter.normalize(adapter.request_model(original), "csv_upload", raw_hash)
    data = payload(cfg)
    dataset = datasets.create_dataset(DatasetCreate(name=f"Owned {ticker} {price_offset}", domain="backtest",
                                      dataset_type="price_series", source_type="generated").model_dump(mode="json"))
    fields = [{"name": "date", "type": "date", "nullable": False}, {"name": "close", "type": "float64", "nullable": False}]
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", row_count=140, column_count=2,
        content_fingerprint=raw_hash, file_size_bytes=len(text.encode()), storage_locator="fixture://replay/owned",
        schema_snapshot={"fields": fields, "ordering_significant": True}).model_dump(mode="json"))
    data["replay"] = {"schema_version": "replay_capture_v1", "original_request": original,
                      "dataset_version_id": version["id"], "csv_text": text}
    return data, version


def test_unretained_csv_cannot_pin_an_unrelated_dataset_and_save_rolls_back():
    data, _ = _local_payload()
    _, unrelated = _local_payload(ticker="OTHER", price_offset=1)
    data["replay"].pop("csv_text")
    data["replay"]["dataset_version_id"] = unrelated["id"]
    with pytest.raises(ValueError, match="configured input"):
        create_saved_backtest(data)
    with closing(db.get_connection()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM saved_backtests").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM run_replay_contexts").fetchone()[0] == 0


def test_rehashed_dataset_reference_cannot_bypass_configuration_binding():
    data, _ = _local_payload()
    saved = create_saved_backtest(data)
    context = store.for_saved(saved["id"])
    _, unrelated = _local_payload(ticker="OTHER", price_offset=1)
    pin = service.dataset_pin(unrelated["id"])
    _reseal(context["id"], lambda snap: snap["inputs"].__setitem__("dataset", pin))
    with pytest.raises(service.Changed, match="configured input"):
        service.preflight(context["id"])


def test_swapped_parent_context_refuses_new_save_without_changing_history():
    parent_data, _ = _local_payload(ticker="PARENT")
    parent = create_saved_backtest(parent_data)
    parent_context = store.for_saved(parent["id"])
    child_data, _ = _local_payload(ticker="CHILD")
    child_data["replay"]["parent_context_id"] = parent_context["id"]
    before = get_saved_backtest(parent["id"])
    with pytest.raises(ValueError, match="Parent context disagrees"):
        create_saved_backtest(child_data)
    assert get_saved_backtest(parent["id"]) == before
    with closing(db.get_connection()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM saved_backtests").fetchone()[0] == 1


def test_provider_restore_parameter_edit_saves_new_declared_execution(monkeypatch):
    parent = _registered()
    restored = copy.deepcopy(parent["restore_request"])
    restored["fast_window"] = 5
    cfg = adapter.normalize(adapter.request_model(restored), "yfinance")
    data = payload(cfg)
    data["replay"] = environment.capture(restored, "declared_request")
    data["replay"]["parent_context_id"] = parent["context_id"]
    historical = get_saved_backtest(store.get(parent["context_id"])["saved_backtest_id"])
    monkeypatch.setattr(main, "_fetch", lambda *_args, **_kwargs: pytest.fail("save fetched provider data"))
    monkeypatch.setattr(main, "run_backtest", lambda *_args, **_kwargs: pytest.fail("save reran research"))
    response = TestClient(main.app).post("/saved-backtests", json=data)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"] != historical["id"]
    assert get_saved_backtest(historical["id"]) == historical
    context = store.for_saved(saved["id"])
    snapshot = identity.loads(context["snapshot_json"])
    assert snapshot["parent_context_id"] == parent["context_id"]
    preflight = service.preflight(context["id"])
    assert preflight["canonical_config"]["strategy_params"]["fast_window"] == 5
    assert preflight["data_availability"] == "provider_not_retained"
    assert not preflight["ready_with_retained_data"]
    assert preflight["execution_hash"] != parent["execution_hash"]


def test_provider_save_refuses_unrelated_provider_parent_and_rolls_back():
    parent_saved = create_saved_backtest(payload(config(ticker="QQQ")))
    parent = service.register_legacy(parent_saved["id"])
    historical = get_saved_backtest(parent_saved["id"])
    data = payload()
    data["replay"] = environment.capture(adapter.restore(config()), "declared_request")
    data["replay"]["parent_context_id"] = parent["context_id"]
    response = TestClient(main.app).post("/saved-backtests", json=data)
    assert response.status_code == 422 and "Parent context disagrees" in response.json()["detail"]
    with closing(db.get_connection()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM saved_backtests").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM run_replay_contexts").fetchone()[0] == 1
    assert get_saved_backtest(parent_saved["id"]) == historical


def test_reselected_input_checks_independent_registry_schema_before_engine(monkeypatch):
    data, version = _local_payload()
    text = data["replay"].pop("csv_text")
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE dataset_versions SET row_count=139 WHERE id=?", (version["id"],))
    saved = create_saved_backtest(data)
    context = store.for_saved(saved["id"])
    preflight = service.preflight(context["id"])
    assert preflight["data_availability"] == "reselection_required"
    monkeypatch.setattr(main, "_run_csv_single_asset", lambda *_args, **_kwargs: pytest.fail("invalid input reached engine"))
    with pytest.raises(ValueError, match="row count"):
        service.check_input(context["id"], text)
    with pytest.raises(ValueError, match="row count"):
        service.execute_local(context["id"], preflight["restore_request"], text)


def test_retained_payload_tamper_is_409_before_execution(monkeypatch):
    data, _ = _local_payload()
    saved = create_saved_backtest(data)
    context = store.for_saved(saved["id"])
    _reseal(context["id"], lambda snap: snap.__setitem__("csv_text", snap["csv_text"].replace(",100\n", ",101\n", 1)))
    monkeypatch.setattr(main, "_run_csv_single_asset", lambda *_args, **_kwargs: pytest.fail("tampered input reached engine"))
    client = TestClient(main.app)
    assert client.get(f'/run-replay/contexts/{context["id"]}/export').status_code == 409
    assert client.post(f'/run-replay/contexts/{context["id"]}/execute-local', json={"request": data["replay"]["original_request"]}).status_code == 409


def test_pagination_selection_and_deleted_context_are_explicit():
    saved = [create_saved_backtest(payload()) for _ in range(3)]
    registered = [service.register_legacy(item["id"]) for item in saved]
    full = registered[0]["config_hash_full"]
    pages = [service.resolve_hash(full, page=page, page_size=1) for page in (1, 2, 3)]
    assert [page["contexts"][0]["saved_backtest_id"] for page in pages] == [item["id"] for item in saved]
    assert all(page["total"] == 3 and page["ambiguous"] and page["selection_required"] for page in pages)
    with pytest.raises(service.Missing, match="page"):
        service.resolve_hash(full, page=4, page_size=1)
    assert delete_saved_backtest(saved[1]["id"])
    assert service.resolve_hash(full)["total"] == 2
    with pytest.raises(service.Missing):
        service.preflight(registered[1]["context_id"])


@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (True, 20), (1, 51)])
def test_internal_resolver_enforces_page_bounds(page, size):
    with pytest.raises(ValueError, match="bounds"):
        service.resolve_hash("a" * 64, page, size)


def test_demo_finds_its_context_beyond_first_fifty(monkeypatch):
    first = service.demo()
    row = store.get(first["context_id"])
    snap = identity.loads(row["snapshot_json"])
    data = get_saved_backtest(first["saved_backtest_id"])
    data["replay"] = {"schema_version": "replay_capture_v1", "original_request": snap["original_request"],
                      "request_provenance": snap["request_provenance"], "execution_environment": snap["execution_environment"],
                      "dataset_version_id": snap["inputs"]["dataset"]["version_id"], "csv_text": snap["csv_text"]}
    for _ in range(49):
        create_saved_backtest(copy.deepcopy(data))
    monkeypatch.setattr(main, "_fetch", lambda *_args, **_kwargs: pytest.fail("demo fetched a provider"))
    newest = service.demo()
    assert newest["config_hash_full"] == first["config_hash_full"]
    assert store.for_saved(newest["saved_backtest_id"])["id"] == newest["context_id"]
    assert service.resolve_hash(first["config_hash_full"])["total"] == 51


def test_posted_nonobject_capture_is_422_and_never_inserts():
    client = TestClient(main.app)
    for value in ([], "capture", True):
        data = payload()
        data["replay"] = value
        assert client.post("/saved-backtests", json=data).status_code == 422
    with closing(db.get_connection()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM saved_backtests").fetchone()[0] == 0


def test_swapped_saved_record_reference_refuses_unrelated_context():
    first = _registered()
    other = create_saved_backtest(payload(config(ticker="QQQ")))
    row = store.get(first["context_id"])
    snap = identity.loads(row["snapshot_json"])
    snap["saved_backtest_id"] = other["id"]
    # This changes both IDs and the snapshot checksum. The distinct record's
    # canonical/result bindings must still be checked independently.
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE run_replay_contexts SET saved_backtest_id=?,snapshot_json=?,snapshot_hash=? WHERE id=?",
                     (other["id"], identity.validate(snap), identity.digest(snap), row["id"]))
    assert TestClient(main.app).get(f'/run-replay/contexts/{row["id"]}').status_code == 409


def test_rehashed_canonical_schema_index_must_match_saved_content():
    context = _registered()
    row = store.get(context["context_id"])
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE saved_backtests SET config_schema='other_v1' WHERE id=?", (row["saved_backtest_id"],))
        conn.execute("UPDATE run_replay_contexts SET config_schema='other_v1' WHERE id=?", (row["id"],))
    with pytest.raises(service.Changed, match="Schema"):
        service.preflight(row["id"])


def test_reads_export_and_input_check_preserve_database_bytes(monkeypatch):
    data, _ = _local_payload()
    saved = create_saved_backtest(data)
    context = store.for_saved(saved["id"])

    def forbidden(*_args, **_kwargs):
        pytest.fail("inspection attempted an execution, provider call or write")

    monkeypatch.setattr(main, "_fetch", forbidden)
    monkeypatch.setattr(main, "run_backtest", forbidden)
    monkeypatch.setattr(main, "_run_csv_single_asset", forbidden)
    monkeypatch.setattr(service, "register_in_transaction", forbidden)
    monkeypatch.setattr(service, "demo", forbidden)
    before = db.get_db_path().read_bytes()
    client = TestClient(main.app)
    assert client.get("/run-replay/hash/" + saved["config_hash_full"]).status_code == 200
    assert client.get(f'/run-replay/contexts/{context["id"]}').json()["ready_with_retained_data"]
    exported = client.get(f'/run-replay/contexts/{context["id"]}/export')
    assert exported.status_code == 200
    assert not exported.json()["data_included"] and "csv_text" not in exported.json()
    checked = client.post(f'/run-replay/contexts/{context["id"]}/check-input', json={"csv_text": data["replay"]["csv_text"]})
    assert checked.status_code == 200 and checked.json()["matched"]
    assert db.get_db_path().read_bytes() == before
    assert get_saved_backtest(saved["id"])["notes"] == "Unchanged"


def test_owned_pre_phase66_full_schema_upgrade_preserves_every_saved_field(tmp_path):
    path = tmp_path / "owned-pre-phase66.db"
    values = (7, "2020-01-01T00:00:00Z", "Saved before replay", "SPY", "sma_crossover", "2019-01-01", "2020-01-01",
              12345.5, 7.5, '{"legacy":"params"}', '{"total_return":0.25}', '[{"date":"2019-01-01","value":12345.5}]',
              '[{"side":"buy"}]', "Historical notes remain byte-for-byte")
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("""CREATE TABLE saved_backtests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, name TEXT NOT NULL,
            ticker TEXT NOT NULL, strategy TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            initial_capital REAL NOT NULL, transaction_cost_bps REAL NOT NULL,
            params_json TEXT NOT NULL DEFAULT '{}', metrics_json TEXT NOT NULL DEFAULT '{}',
            equity_curve_json TEXT NOT NULL DEFAULT '[]', trades_json TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '')""")
        conn.execute("INSERT INTO saved_backtests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
        store.initialize(conn)
        store.initialize(conn)
        assert conn.execute("SELECT * FROM saved_backtests").fetchone() == (*values, None, None)
        assert conn.execute("SELECT COUNT(*) FROM run_replay_contexts").fetchone()[0] == 0


def test_real_public_lifecycle_rejects_incomplete_and_mutated_import(legacy, monkeypatch):
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate
    from app.ml_lifecycle import importer, service as lifecycle

    snapshot = importer.preview(legacy[0], legacy[1])
    dataset = datasets.create_dataset(DatasetCreate(name="Owned imported lifecycle", domain="research",
        dataset_type="experiment_snapshot", source_type="local_file").model_dump(mode="json"))
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", format="json",
        content_fingerprint=snapshot["source_hash"], storage_locator="fixture://replay/legacy").model_dump(mode="json"))
    record = lifecycle.register({"name": "Owned incomplete import", "dataset_version_id": version["id"],
        "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot})
    assert record["integrity"] == "intact" and record["completeness"] == "incomplete"
    monkeypatch.setattr(lifecycle, "link", lambda *_args, **_kwargs: pytest.fail("read attempted diagnostics"))
    with pytest.raises(ValueError, match="incomplete or changed"):
        service.artifact_pin(record["id"])
    with closing(db.get_connection()) as conn, conn:
        corrupt = copy.deepcopy(snapshot)
        corrupt["source"]["metrics"]["accuracy"] = 0.9
        conn.execute("UPDATE ml_lifecycles SET snapshot_json=? WHERE id=?", (json.dumps(corrupt), record["id"]))
    assert lifecycle.get_run(record["id"])["integrity"] == "changed"
    with pytest.raises(ValueError, match="incomplete or changed"):
        service.artifact_pin(record["id"])


def test_demo_partial_failure_reports_retained_owned_records(monkeypatch):
    def fail_engine(*_args, **_kwargs):
        raise RuntimeError("owned injected engine failure")

    monkeypatch.setattr(main, "_run_csv_single_asset", fail_engine)
    result = TestClient(main.app).post("/run-replay/demo")
    assert result.status_code == 409
    with closing(db.get_connection()) as conn:
        dataset = conn.execute("SELECT id,is_demo FROM datasets").fetchone()
        version = conn.execute("SELECT id,dataset_id FROM dataset_versions").fetchone()
        assert dataset is not None and dataset["is_demo"] == 1
        assert version is not None and version["dataset_id"] == dataset["id"]
        assert conn.execute("SELECT COUNT(*) FROM saved_backtests").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM run_replay_contexts").fetchone()[0] == 0
    detail = result.json()["detail"]
    assert "Demo incomplete" in detail and f"dataset {dataset['id']}" in detail and f"version {version['id']}" in detail
    assert "remain" in detail and "owned injected engine failure" not in detail


def test_material_change_after_preflight_refused_at_explicit_execution(monkeypatch):
    data, version = _local_payload()
    saved = create_saved_backtest(data)
    context = store.for_saved(saved["id"])
    request = service.preflight(context["id"])["restore_request"]
    original = adapter.request_model

    def changed_during_request(raw):
        result = original(raw)
        if raw is request:
            with closing(db.get_connection()) as conn, conn:
                conn.execute("UPDATE dataset_versions SET invalidated_at='2026-10-05T00:00:00Z' WHERE id=?", (version["id"],))
        return result

    monkeypatch.setattr(adapter, "request_model", changed_during_request)
    monkeypatch.setattr(main, "_run_csv_single_asset", lambda *_args, **_kwargs: pytest.fail("changed material reached engine"))
    with pytest.raises(service.Changed, match="before execution"):
        service.execute_local(context["id"], request)
