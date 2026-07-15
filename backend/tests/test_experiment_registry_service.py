"""
Service-layer tests for the Research Experiment Registry (Phase 48.0).

Covers status transitions, baseline eligibility, the reproducibility assessment
for each state (reproducible / partial / not / unknown), and the neutral
two-experiment comparison.
"""

from __future__ import annotations

import pytest

db_module = pytest.importorskip("app.db")
service = pytest.importorskip("app.experiment_registry.service")
store = pytest.importorskip("app.experiment_registry.store")
assessment = pytest.importorskip("app.experiment_registry.assessment")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


def _make(**over):
    payload = {
        "name": "Run",
        "module": "m",
        "experiment_type": "t",
        "status": "completed",
        "parameters": {"a": 1},
        "metrics": {"sharpe": 1.0},
        "dataset_name": "d",
        "dataset_identity": {"rows": 5},  # -> deterministic dataset fingerprint
    }
    payload.update(over)
    return service.create_experiment(payload, source="test")


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def test_complete_only_from_active():
    rec = _make(status="running", metrics={})
    done = service.complete_experiment(rec["id"], {"metrics": {"sharpe": 2.0}})
    assert done["status"] == "completed"
    assert done["result_fingerprint"]
    with pytest.raises(service.ConflictError):
        service.complete_experiment(rec["id"], {"metrics": {}})


def test_fail_requires_active_and_sets_message():
    rec = _make(status="running", metrics={})
    failed = service.fail_experiment(rec["id"], {"error_message": "boom"})
    assert failed["status"] == "failed"
    assert failed["error_message"] == "boom"
    with pytest.raises(service.ConflictError):
        service.fail_experiment(rec["id"], {"error_message": "again"})


def test_create_failed_requires_error_message():
    with pytest.raises(service.RegistryError):
        service.create_experiment(
            {"name": "x", "module": "m", "experiment_type": "t", "status": "failed"},
            source="test",
        )


def test_invalidate_clears_baseline():
    rec = _make()
    service.mark_baseline(rec["id"])
    inv = service.invalidate_experiment(rec["id"])
    assert inv["status"] == "invalidated"
    assert inv["is_baseline"] is False
    with pytest.raises(service.ConflictError):
        service.invalidate_experiment(rec["id"])


def test_only_completed_can_be_baseline():
    running = _make(status="running", metrics={})
    with pytest.raises(service.ConflictError):
        service.mark_baseline(running["id"])
    failed = _make(status="failed", error_message="x", metrics={})
    with pytest.raises(service.ConflictError):
        service.mark_baseline(failed["id"])


def test_parent_must_exist():
    with pytest.raises(service.RegistryError):
        service.create_experiment(
            {
                "name": "child",
                "module": "m",
                "experiment_type": "t",
                "parent_experiment_id": 4242,
            },
            source="test",
        )


def test_not_found_errors():
    with pytest.raises(service.NotFoundError):
        service.get_experiment(999)
    with pytest.raises(service.NotFoundError):
        service.delete_experiment(999)


# ---------------------------------------------------------------------------
# Reproducibility assessment
# ---------------------------------------------------------------------------


def test_assess_unknown_without_reference():
    rec = _make()  # no parent, no baseline in scope
    result = service.assess_experiment(rec["id"])
    assert result["status"] == assessment.UNKNOWN


def test_assess_reproducible():
    base = _make()
    service.mark_baseline(base["id"])
    # Same config + dataset fingerprint + metrics -> reproducible against baseline.
    rerun = _make()
    result = service.assess_experiment(rerun["id"])
    assert result["status"] == assessment.REPRODUCIBLE


def test_assess_not_reproducible_on_config_change():
    base = _make()
    service.mark_baseline(base["id"])
    changed = _make(parameters={"a": 999})  # different config fingerprint
    result = service.assess_experiment(changed["id"])
    assert result["status"] == assessment.NOT_REPRODUCIBLE


def test_assess_not_reproducible_when_deterministic_result_differs():
    # Same config + same dataset fingerprint, but different result fingerprint.
    base = _make()
    service.mark_baseline(base["id"])
    diff_result = _make(metrics={"sharpe": 5.0})
    result = service.assess_experiment(diff_result["id"])
    assert result["status"] == assessment.NOT_REPRODUCIBLE


def test_assess_partially_reproducible_without_dataset_fingerprint():
    # No dataset_identity => dataset fingerprint is None on both; config matches,
    # result differs => partially reproducible (cannot confirm identical dataset).
    base = service.create_experiment(
        {
            "name": "base",
            "module": "mm",
            "experiment_type": "tt",
            "status": "completed",
            "parameters": {"a": 1},
            "metrics": {"score": 0.8},
            "dataset_name": "nofp",
        },
        source="test",
    )
    service.mark_baseline(base["id"])
    child = service.create_experiment(
        {
            "name": "child",
            "module": "mm",
            "experiment_type": "tt",
            "status": "completed",
            "parameters": {"a": 1},
            "metrics": {"score": 0.7},
            "dataset_name": "nofp",
        },
        source="test",
    )
    result = service.assess_experiment(child["id"])
    assert result["status"] == assessment.PARTIALLY_REPRODUCIBLE
    # Persisted status is kept in sync.
    assert store.get_experiment(child["id"])["reproducibility_status"] == assessment.PARTIALLY_REPRODUCIBLE


def test_assess_uses_parent_as_reference():
    parent = _make(name="parent")
    child = _make(name="child", parent_experiment_id=parent["id"])
    result = service.assess_experiment(child["id"])
    assert result["reference_id"] == parent["id"]
    assert result["status"] == assessment.REPRODUCIBLE


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def test_compare_requires_two_distinct():
    rec = _make()
    with pytest.raises(service.RegistryError):
        service.compare(rec["id"], rec["id"])


def test_compare_reports_metric_deltas():
    a = _make(metrics={"sharpe": 1.0, "trades": 100})
    b = _make(metrics={"sharpe": 2.0, "trades": 100})
    result = service.compare(a["id"], b["id"])
    metrics = {e["key"]: e for e in result["groups"]["metrics"]}
    assert metrics["trades"]["state"] == "same"
    assert metrics["sharpe"]["state"] == "changed"
    assert metrics["sharpe"]["abs_diff"] == pytest.approx(1.0)
    assert metrics["sharpe"]["pct_diff"] == pytest.approx(100.0)


def test_compare_guards_zero_denominator():
    a = _make(metrics={"x": 0.0})
    b = _make(metrics={"x": 5.0})
    result = service.compare(a["id"], b["id"])
    x = {e["key"]: e for e in result["groups"]["metrics"]}["x"]
    assert x["abs_diff"] == pytest.approx(5.0)
    assert x["pct_diff"] is None  # division by zero guarded


def test_compare_handles_only_in_one_side():
    a = _make(metrics={"only_a": 1.0})
    b = _make(metrics={"only_b": 2.0})
    result = service.compare(a["id"], b["id"])
    states = {e["key"]: e["state"] for e in result["groups"]["metrics"]}
    assert states["only_a"] == "only_in_a"
    assert states["only_b"] == "only_in_b"
