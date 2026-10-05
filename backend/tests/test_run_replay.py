"""Phase 66 independent deterministic contracts, with protected isolated SQLite."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from app import db, main
from app.reproducibility import build_reproducibility, canonical_json, compute_config_hash
from app.run_replay import adapter, environment, identity, service, store
from app.saved_backtests import create_saved_backtest, get_saved_backtest

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


def config(**kwargs):
    request = adapter.request_model({"ticker": "SPY", "start_date": "2020-01-01", "end_date": "2021-01-01", **kwargs})
    return adapter.normalize(request, "yfinance")


def payload(cfg=None):
    cfg = cfg or config()
    return {"name": "Historical", "ticker": cfg["ticker"], "strategy": cfg["strategy"],
            "start_date": cfg["start_date"], "end_date": cfg["end_date"], "initial_capital": cfg["initial_capital"],
            "transaction_cost_bps": cfg["cost_model"]["effective_cost_bps"],
            "params": {"reproducibility": build_reproducibility(cfg).model_dump(mode="json")},
            "metrics": {"total_return": .12}, "equity_curve": [], "trades": [], "notes": "Unchanged"}


@pytest.mark.db_free
def test_legacy_hash_golden_bytes_and_prefix():
    expected = '{"annualization_mode":"trading_days_252","benchmark":{"mode":"buy_and_hold_same_asset"},"cost_model":{"effective_cost_bps":10},"data_provider":"yfinance","end_date":"2021-01-01","initial_capital":100000,"position_mode":"long_only","position_sizing":{"type":"full_allocation"},"risk_management":{"type":"none"},"schema_version":"backtest_config_v1","start_date":"2020-01-01","strategy":"sma_crossover","strategy_params":{"fast_window":20,"slow_window":100},"ticker":"SPY"}'
    assert canonical_json(config()) == expected
    full = hashlib.sha256(expected.encode()).hexdigest()
    assert compute_config_hash(config()) == (full[:12], full)


@pytest.mark.db_free
@pytest.mark.parametrize("change", [
    {}, {"annualization_mode": "auto", "ticker": "BTC-USD"},
    {"cost_model": {"type": "conservative"}},
    {"position_mode": "long_short", "position_sizing": {"type": "fixed_fraction", "fraction": .5}},
    {"risk_management": {"type": "combined", "stop_loss_pct": .1, "trailing_stop_pct": .05, "max_holding_days": 10}},
    {"benchmark": {"mode": "none"}}, {"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    {"position_sizing": {"type": "volatility_target", "target_volatility": .1}},
    {"sensitivity": {"enabled": True, "x_values": [10, 20], "y_values": [50, 100]}}])
def test_canonical_request_round_trip(change):
    original = adapter.request_model({"ticker": "SPY", "start_date": "2020-01-01", "end_date": "2021-01-01", **change})
    cfg = adapter.normalize(original, "yfinance")
    for raw in (None, original.model_dump(mode="json")):
        restored = adapter.request_model(adapter.restore(cfg, raw))
        assert canonical_json(adapter.normalize(restored, "yfinance")) == canonical_json(cfg)


@pytest.mark.db_free
@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":9007199254740993}', '[' * 25 + '0' + ']' * 25])
def test_strict_json_rejections(raw):
    with pytest.raises(ValueError):
        identity.loads(raw)


@pytest.mark.db_free
@pytest.mark.parametrize("raw", [{"fast_window": True}, {"slow_window": "100"}, {"initial_capital": False},
    {"cost_model": {"type": "simple_bps", "transaction_cost_bps": True}},
    {"risk_management": {"type": "max_holding_days", "max_holding_days": 5.5}}, {"extra": "ignored"}])
def test_request_does_not_coerce_or_drop(raw):
    with pytest.raises(ValueError):
        adapter.request_model(raw)


@pytest.mark.db_free
def test_unrepresentable_canonical_rejected():
    cfg = config()
    cfg["unexpected_result_option"] = 42
    with pytest.raises(ValueError, match="round-trip"):
        adapter.restore(cfg)


@pytest.mark.db_free
def test_environment_unknown_is_not_equal_and_patch_difference():
    old = environment.collect("execution")
    current = copy.deepcopy(old)
    current["fields"]["numpy"] = "999.0.1"
    rows = {r["field"]: r for r in environment.compare(old, current)}
    assert rows["numpy"]["state"] == "different"
    assert rows["python"]["state"] == "same"
    assert rows["node"]["state"] == "unknown"
    assert all(r["state"] == "unknown" for r in environment.compare(None, current))


def test_explicit_legacy_registration_is_idempotent_and_get_does_not_write(monkeypatch):
    saved = create_saved_backtest(payload())
    assert saved["config_hash_full"] is None
    client = TestClient(main.app)
    full = saved["params"]["reproducibility"]["config_hash_full"]
    assert client.get("/run-replay/hash/" + full).status_code == 404
    registered = client.post(f'/run-replay/register/{saved["id"]}').json()
    cid = registered["context_id"]
    assert registered["restore_level"] == "config_only"
    assert registered["execution_environment"] is None
    assert registered["data_availability"] == "provider_not_retained"
    assert client.post(f'/run-replay/register/{saved["id"]}').json()["context_id"] == cid
    def forbidden(*args, **kwargs):
        raise AssertionError("GET attempted external/research/write work")
    monkeypatch.setattr(main, "_fetch", forbidden)
    monkeypatch.setattr(main, "run_backtest", forbidden)
    monkeypatch.setattr(service, "register_in_transaction", forbidden)
    before = db.get_db_path().read_bytes()
    assert client.get("/run-replay/hash/" + full).json()["canonical_config"] == json.loads(saved["params"]["reproducibility"]["canonical_config_json"])
    exported = client.get(f"/run-replay/contexts/{cid}/export").json()
    assert exported["data_included"] is False and "csv_text" not in exported
    assert before == db.get_db_path().read_bytes()
    assert get_saved_backtest(saved["id"])["notes"] == "Unchanged"


@pytest.mark.parametrize("value, status", [("abc", 422), ("a" * 12, 422), ("A" * 64, 422), ("f" * 64, 404)])
def test_hash_errors(value, status):
    assert TestClient(main.app).get("/run-replay/hash/" + value).status_code == status


def test_multiple_executions_share_config_not_result_or_environment():
    first = create_saved_backtest(payload())
    one = service.register_legacy(first["id"])
    second_payload = payload()
    second_payload["metrics"]["total_return"] = -.2
    second_payload["replay"] = environment.capture(adapter.restore(config()))
    second_payload["replay"]["execution_environment"]["fields"]["numpy"] = "1.0.1"
    second = create_saved_backtest(second_payload)
    result = service.resolve_hash(second["config_hash_full"])
    assert result["total"] == 2 and result["ambiguous"] and result["selection_required"]
    assert len({r["input_hash"] for r in result["contexts"]}) == 2  # legacy diagnostics unknown vs known
    assert len({r["result_hash"] for r in result["contexts"]}) == 2
    assert one["environment_hash"] is None
    assert "selected_context" not in result


def test_atomic_save_rollback_and_duplicate_keys():
    client = TestClient(main.app)
    data = payload()
    data["replay"] = {"schema_version": "replay_capture_v1", "original_request": {"fast_window": True}}
    assert client.post("/saved-backtests", json=data).status_code == 422
    assert client.get("/saved-backtests").json() == []
    assert client.post("/run-replay/contexts/1/check-input", content='{"csv_text":"x","csv_text":"y"}', headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/saved-backtests", content='{"name":"a","name":"b"}', headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/saved-backtests", content=b' ' * (4 * 1024 * 1024 + 1), headers={"Content-Type": "application/json"}).status_code == 422


def test_corrupt_canonical_and_snapshot_are_not_green():
    saved = create_saved_backtest(payload())
    registered = service.register_legacy(saved["id"])
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE run_replay_contexts SET snapshot_json=? WHERE id=?", ('{}', registered["context_id"]))
    assert TestClient(main.app).get("/run-replay/hash/" + registered["config_hash_full"]).status_code == 409


def test_demo_actual_engine_retained_roundtrip_and_changed_dataset(monkeypatch):
    monkeypatch.setattr(main, "_fetch", lambda *args: pytest.fail("Offline demo fetched provider data"))
    created = service.demo()
    pre = service.preflight(created["context_id"])
    assert pre["ready_with_retained_data"]
    restored = adapter.request_model(pre["restore_request"])
    assert canonical_json(adapter.normalize(restored, "csv_upload", pre["canonical_config"]["dataset_fingerprint"])) == canonical_json(pre["canonical_config"])
    rerun = service.execute_local(created["context_id"], pre["restore_request"])
    saved = get_saved_backtest(created["saved_backtest_id"])
    assert rerun.strategy_metrics.model_dump(mode="json") == saved["metrics"]
    assert rerun.equity_curve and rerun.trades
    assert rerun.execution_context["parent_context_id"] == created["context_id"]
    with pytest.raises(ValueError, match="hash"):
        service.check_input(created["context_id"], "date,close\n2020-01-01,1\n2020-01-02,2\n")
    with closing(db.get_connection()) as conn, conn:
        # Material mutation while advertised checksums remain untouched.
        conn.execute("UPDATE dataset_versions SET row_count=row_count+1 WHERE id=?", (pre["dataset"]["version_id"],))
    changed = service.preflight(created["context_id"])
    assert changed["integrity"] == "changed" and not changed["ready_with_retained_data"]
    with pytest.raises(service.Changed):
        service.execute_local(created["context_id"], pre["restore_request"])


def test_missing_csv_is_reselection_not_provider_fallback(monkeypatch):
    created = service.demo()
    row = store.get(created["context_id"])
    snapshot = identity.loads(row["snapshot_json"])
    snapshot["csv_text"] = None
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE run_replay_contexts SET snapshot_json=?, snapshot_hash=? WHERE id=?",
                     (identity.validate(snapshot), identity.digest(snapshot), row["id"]))
    monkeypatch.setattr(main, "_fetch", lambda *args: pytest.fail("Unexpected provider fallback"))
    pre = service.preflight(row["id"])
    assert pre["data_availability"] == "reselection_required"
    with pytest.raises(ValueError):
        service.execute_local(row["id"], pre["restore_request"])


def test_missing_optional_artifact_blocks_context(monkeypatch):
    from app.ml_lifecycle import service as lifecycle
    record = {"integrity": "intact", "completeness": "complete", "lifecycle_hash": "a" * 64,
              "snapshot_hash": "b" * 64, "dataset_material_hash": "c" * 64, "identities": {}, "links": []}
    monkeypatch.setattr(lifecycle, "get_run", lambda _: record)
    data = payload()
    data["replay"] = {"schema_version": "replay_capture_v1", "artifact_run_id": 3}
    saved = create_saved_backtest(data)
    context = service.resolve_hash(saved["config_hash_full"])["contexts"][0]
    def missing(_):
        raise LookupError("Deleted lifecycle")
    monkeypatch.setattr(lifecycle, "get_run", missing)
    assert service.preflight(context["id"])["integrity"] == "changed"


def test_explicit_demo_api_and_new_result_save_without_rerun(monkeypatch):
    client = TestClient(main.app)
    created = client.post("/run-replay/demo")
    assert created.status_code == 200
    pre = service.preflight(created.json()["context_id"])
    result = service.execute_local(pre["context_id"], pre["restore_request"])
    data = payload(pre["canonical_config"])
    data.update(metrics=result.strategy_metrics.model_dump(mode="json"),
                equity_curve=[p.model_dump(mode="json") for p in result.equity_curve],
                trades=[p.model_dump(mode="json") for p in result.trades], replay=result.execution_context)
    monkeypatch.setattr(main, "run_backtest", lambda *args, **kwargs: pytest.fail("Save attempted a rerun"))
    saved = client.post("/saved-backtests", json=data)
    assert saved.status_code == 200
    assert saved.json()["id"] != created.json()["saved_backtest_id"]
    contexts = service.resolve_hash(pre["config_hash_full"])
    assert contexts["total"] == 2
    assert len({c["input_hash"] for c in contexts["contexts"]}) == 1
    assert len({c["result_hash"] for c in contexts["contexts"]}) == 1  # same numerical result, distinct execution records
    assert len({c["execution_hash"] for c in contexts["contexts"]}) == 2
    client.delete(f'/saved-backtests/{saved.json()["id"]}')
    assert service.resolve_hash(pre["config_hash_full"])["total"] == 1


def test_unsupported_strategy_is_config_only():
    cfg = config()
    cfg["strategy"] = "rsi_mean_reversion"
    cfg["strategy_params"] = {"rsi_window": 14, "oversold_threshold": 30, "exit_threshold": 50}
    saved = create_saved_backtest(payload(cfg))
    pre = service.register_legacy(saved["id"])
    assert pre["restore_request"] is None and not pre["ready_with_retained_data"]
    with pytest.raises(ValueError, match="safe v1 export"):
        service.export_context(pre["context_id"])


def test_corrupt_legacy_content_and_unsupported_schema():
    saved = create_saved_backtest(payload())
    pre = service.register_legacy(saved["id"])
    data = saved["params"]
    data["reproducibility"]["canonical_config_json"] = data["reproducibility"]["canonical_config_json"].replace('"SPY"', '"QQQ"')
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE saved_backtests SET params_json=? WHERE id=?", (json.dumps(data), saved["id"]))
    with pytest.raises(service.Changed):
        service.resolve_hash(pre["config_hash_full"])
    cfg = config()
    cfg["schema_version"] = "future_backtest_v2"
    data = payload(cfg)
    data["params"]["reproducibility"]["schema_version"] = "future_backtest_v2"
    future = service.register_legacy(create_saved_backtest(data)["id"])
    assert future["restore_request"] is None


def test_wire_request_is_retained_separately_from_effective_settings(monkeypatch):
    import pandas as pd
    monkeypatch.setattr(main, "_fetch", lambda *args: pd.DataFrame({"Close": range(100, 240)}, index=pd.date_range("2020-01-01", periods=140)))
    original = {"ticker": "spy", "start_date": "2020-01-01", "end_date": "2021-01-01", "cost_model": {"type": "conservative"}, "annualization_mode": "auto"}
    response = TestClient(main.app).post("/backtest/sma-crossover", json=original)
    assert response.status_code == 200
    capture = response.json()["execution_context"]
    assert capture["original_request"] == original
    assert capture["request_provenance"] == "wire_json"
    effective = json.loads(response.json()["reproducibility"]["canonical_config_json"])
    assert effective["cost_model"] == {"effective_cost_bps": 25}
    assert effective["annualization_mode"] == "trading_days_252"


def test_dataset_invalidation_and_missing_reference():
    created = service.demo()
    pre = service.preflight(created["context_id"])
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE dataset_versions SET invalidated_at='2026-10-05T00:00:00Z' WHERE id=?", (pre["dataset"]["version_id"],))
    assert service.preflight(created["context_id"])["integrity"] == "changed"


def test_optional_artifact_material_change_is_detected(monkeypatch):
    from app.ml_lifecycle import service as lifecycle
    # Public read-only boundary only: no diagnostic adapter execution.
    material = {"integrity": "intact", "completeness": "complete", "lifecycle_hash": "a" * 64,
                "snapshot_hash": "b" * 64, "dataset_material_hash": "c" * 64, "identities": {"model": "d" * 64}, "links": []}
    monkeypatch.setattr(lifecycle, "get_run", lambda _: material)
    saved_data = payload()
    saved_data["replay"] = {"schema_version": "replay_capture_v1", "artifact_run_id": 3}
    saved = create_saved_backtest(saved_data)
    row = service.resolve_hash(saved["config_hash_full"])["contexts"][0]
    assert service.preflight(row["id"])["integrity"] == "intact"
    material["identities"]["model"] = "e" * 64
    assert service.preflight(row["id"])["integrity"] == "changed"


def test_local_replay_refuses_remote_benchmark_and_changed_identity():
    created = service.demo()
    pre = service.preflight(created["context_id"])
    for patch in ({"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}}, {"ticker": "SPY"}, {"start_date": "2020-01-02"}):
        with pytest.raises(ValueError):
            service.execute_local(pre["context_id"], {**pre["restore_request"], **patch})


def test_disposable_browser_guard_checks_every_write(tmp_path, monkeypatch):
    from fastapi import FastAPI
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from scripts import run_replay_e2e
    from scripts.strategy_ensemble_e2e import DisposableIdentity, HEADER, PREFIX
    root = tmp_path / (PREFIX + "phase66")
    root.mkdir()
    identity_owner = DisposableIdentity(root, "a" * 64, Path(__file__).resolve().parents[2])
    monkeypatch.setattr(db, "_db_path_override", identity_owner.database)
    db.init_db()
    app = FastAPI()
    app.include_router(main.run_replay_router)
    app.state.strategy_ensemble_e2e_identity = identity_owner
    monkeypatch.setattr(run_replay_e2e, "base_app", lambda: app)
    client = TestClient(run_replay_e2e.create_app())
    assert client.post("/run-replay/demo").status_code == 409
    proof = client.get("/run-replay/e2e/isolation", headers={HEADER: identity_owner.token})
    assert proof.status_code == 200 and proof.json()["database_verified"]
    monkeypatch.setattr(db, "_db_path_override", tmp_path / "different.db")
    assert client.post("/run-replay/demo", headers={HEADER: identity_owner.token}).status_code == 409


def test_real_additive_migration_is_idempotent_preserves_rows(tmp_path):
    # Standalone owned upgrade schema, no application initialization.
    with closing(sqlite3.connect(tmp_path / "upgrade.db")) as conn:
        conn.execute("CREATE TABLE saved_backtests(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO saved_backtests VALUES(1,'Preserved')")
        store.initialize(conn)
        store.initialize(conn)
        assert conn.execute("SELECT name, config_hash_full FROM saved_backtests").fetchone() == ("Preserved", None)
        assert conn.execute("SELECT COUNT(*) FROM run_replay_contexts").fetchone()[0] == 0
