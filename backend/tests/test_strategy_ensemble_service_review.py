"""Independent Phase 64 lifecycle/link regressions using test-owned data only."""

from copy import deepcopy
import json

import pytest

from app import db
from app.strategy_ensemble import demo, links, service, store
from app.strategy_ensemble.models import RunCreate


@pytest.fixture(autouse=True)
def isolated_database(isolated_lab_db):
    return isolated_lab_db


@pytest.mark.parametrize("failure", ["stale_link", "malformed_input", "analysis", "final_verify"])
def test_failed_reexecution_clears_success_and_baseline(monkeypatch, failure):
    run = service.execute_run(service.create_run(demo.payload())["id"])
    service.mark_baseline(run["id"])
    if failure == "stale_link":
        monkeypatch.setattr(links, "snapshot", lambda request: {"changed": True})
    elif failure == "malformed_input":
        with store.connection() as conn:
            conn.execute("UPDATE strategy_ensemble_runs SET request_json='{}' WHERE id=?", (run["id"],))
    elif failure == "analysis":
        def fail_analysis(request):
            raise RuntimeError("synthetic private implementation detail")
        monkeypatch.setattr(service.core, "analyze", fail_analysis)
    else:
        original = service._verify
        attempts = []
        def second_verification(current, **kwargs):
            attempts.append(current["id"])
            if len(attempts) == 2:
                raise service.ConflictError("linked content changed during calculation")
            return original(current, **kwargs)
        monkeypatch.setattr(service, "_verify", second_verification)
    with pytest.raises((ValueError, RuntimeError)):
        service.execute_run(run["id"])
    failed = store.get(run["id"])
    assert failed["status"] == "failed"
    assert failed["results"] is None
    assert not failed["is_baseline"] and failed["baseline_scope"] is None
    assert "result" not in failed["fingerprints"]
    assert "private implementation detail" not in failed["error_message"]


def test_invalidation_during_calculation_preserves_history(monkeypatch):
    run = service.execute_run(service.create_run(demo.payload())["id"])
    original = service.core.analyze
    def invalidate_then_analyze(request):
        service.invalidate(run["id"], "explicit concurrent invalidation")
        return original(request)
    monkeypatch.setattr(service.core, "analyze", invalidate_then_analyze)
    with pytest.raises(service.ConflictError):
        service.execute_run(run["id"])
    invalid = store.get(run["id"])
    assert invalid["status"] == "invalidated" and invalid["results"] == run["results"]
    assert invalid["error_message"] == "explicit concurrent invalidation"


def test_registry_failure_is_once_requested_and_primary_result_survives(monkeypatch):
    calls = []
    def unavailable(**kwargs):
        calls.append(kwargs)
        return None
    monkeypatch.setattr(service, "record_experiment", unavailable)
    run = service.create_run(demo.payload())
    first = service.execute_run(run["id"], True)
    second = service.execute_run(run["id"], True)
    assert first["status"] == second["status"] == "completed"
    assert first["results"] == second["results"]
    assert second["experiment_requested"] and second["experiment_id"] is None
    assert len(calls) == 1  # once requested is not atomic exactly-once recording


@pytest.mark.db_free
def test_dataset_actual_content_pinned_without_exporting_locator(monkeypatch):
    dataset = {"id": 7, "name": "Synthetic", "is_active": True, "created_at": "runtime"}
    version = {"id": 8, "dataset_id": 7, "version_label": "v1", "schema_snapshot": {"columns": ["return"]},
               "statistics_summary": {"rows": 40}, "content_fingerprint": "a" * 64,
               "storage_locator": "fixture://synthetic/private", "created_at": "runtime"}
    monkeypatch.setattr(links.datasets, "get_dataset", lambda rid: deepcopy(dataset))
    monkeypatch.setattr(links.datasets, "get_version", lambda rid: deepcopy(version))
    payload = demo.payload()
    for definition in payload["definitions"]:
        definition["dataset_version_id"] = 8
    request = RunCreate.model_validate(payload)
    before = links.snapshot(request)
    assert "private" not in json.dumps(before) and "storage_locator" not in json.dumps(before)
    version.update(id=18, dataset_id=17, created_at="later", storage_locator="fixture://moved")
    dataset.update(id=17, created_at="later")
    assert links.snapshot(request) == before
    version["statistics_summary"]["rows"] = 41
    after = links.snapshot(request)
    assert after != before
    assert after["datasets"]["a"]["content_fingerprint"] == before["datasets"]["a"]["content_fingerprint"]
    version["effective_from"] = "2024-01-01T12:00:00Z"
    assert links.snapshot(request) != after


def _validation_fixture(monkeypatch):
    payload = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [0., .1, -.1, 0.]})
    payload["validation"] = {"run_id": 9, "split_label": "held"}
    observations = [r for r in payload["observations"] if r["strategy_id"] == "a"]
    run = {"id": 9, "status": "completed", "leakage_clean": True,
           "configuration_fingerprint": "a"*64, "result_fingerprint": "b"*64,
           "samples": [{"sample_id": r["source_observation_id"], "prediction_time": r["period_start"],
                        "evaluation_time": r["period_end"], "ret": r["return_value"]} for r in observations]}
    split = {"id": 10, "validation_run_id": 9, "split_label": "held", "status": "valid",
             "split_fingerprint": "c"*64, "train_ids": ["p000", "p002"],
             "test_ids": ["p001", "p003"], "purged_ids": [], "embargoed_ids": []}
    monkeypatch.setattr(links.validation, "get_run", lambda rid: deepcopy(run))
    monkeypatch.setattr(links.validation, "list_splits", lambda rid: [deepcopy(split)])
    return payload, run, split


@pytest.mark.db_free
@pytest.mark.parametrize("mutation", ["duplicate_sample", "duplicate_member", "unknown_purged"])
def test_validation_membership_corruption_rejected(monkeypatch, mutation):
    payload, run, split = _validation_fixture(monkeypatch)
    if mutation == "duplicate_sample":
        run["samples"][1]["sample_id"] = "p000"
    elif mutation == "duplicate_member":
        split["train_ids"].append("p000")
    else:
        split["purged_ids"].append("unknown")
    with pytest.raises(ValueError, match="identities"):
        links.snapshot(RunCreate.model_validate(payload))


@pytest.mark.db_free
def test_validation_content_and_interval_and_source_identity(monkeypatch):
    payload, run, split = _validation_fixture(monkeypatch)
    request = RunCreate.model_validate(payload)
    pinned = links.snapshot(request)
    run["samples"][0]["ret"] += .01
    assert links.snapshot(request) != pinned  # unchanged stored fingerprint strings
    result = service.core.analyze(request)
    _, validation = links.evaluate(request, pinned, result)
    assert validation["training"]["gaps"] == 1
    assert validation["training"]["path_policy"] == "observed_subset_only_not_continuously_investable"
    payload["observations"][0]["source_observation_id"] = "wrong"
    wrong = RunCreate.model_validate(payload)
    with pytest.raises(ValueError, match="source observation ID"):
        links.evaluate(wrong, pinned, service.core.analyze(wrong))
    pinned["validation"]["samples"][0]["evaluation_time"] = "2024-01-02T12:00:00.000000Z"
    with pytest.raises(ValueError, match="exactly match"):
        links.evaluate(request, pinned, result)


@pytest.mark.fresh_schema
def test_additive_schema_reinitialization_preserves_existing_rows():
    with store.connection() as conn:
        conn.execute("CREATE TABLE review_existing_records (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO review_existing_records VALUES (1, 'preserve')")
        conn.execute("DROP TABLE strategy_ensemble_runs")
    db.init_db()
    db.init_db()
    with store.connection() as conn:
        assert conn.execute("SELECT value FROM review_existing_records").fetchone()[0] == "preserve"
        assert conn.execute("SELECT count(*) FROM strategy_ensemble_runs").fetchone()[0] == 0
