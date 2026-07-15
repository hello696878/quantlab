"""
Integration-helper tests for the Research Experiment Registry (Phase 48.0).

The helper lets existing modules record runs incrementally.  These tests confirm
the happy path (record / start+complete / fail) and, crucially, the **best-effort
failure policy**: a registry failure returns ``None`` and never raises into the
caller's main flow.
"""

from __future__ import annotations

import pytest

db_module = pytest.importorskip("app.db")
integration = pytest.importorskip("app.experiment_registry.integration")
store = pytest.importorskip("app.experiment_registry.store")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


def test_record_experiment_persists():
    rec = integration.record_experiment(
        name="Scenario Studio run",
        module="scenario_studio",
        experiment_type="cross_asset_stress",
        parameters={"scenario": "severe"},
        metrics={"severity_score": 100.0},
        dataset_name="scenario_fixtures",
    )
    assert rec is not None
    stored = store.get_experiment(rec["id"])
    assert stored["module"] == "scenario_studio"
    assert stored["result_fingerprint"]  # metrics -> result fingerprint


def test_start_then_complete():
    exp_id = integration.start_experiment(
        name="KO/PEP pairs",
        module="pairs_backtest",
        experiment_type="pairs_trading",
        parameters={"asset_a": "KO", "asset_b": "PEP"},
    )
    assert isinstance(exp_id, int)
    assert store.get_experiment(exp_id)["status"] == "running"
    done = integration.complete_experiment(exp_id, metrics={"trades": 119})
    assert done is not None
    assert done["status"] == "completed"


def test_fail_and_invalidate():
    exp_id = integration.start_experiment(
        name="failing run", module="m", experiment_type="t"
    )
    failed = integration.fail_experiment(exp_id, error_message="boom")
    assert failed["status"] == "failed"
    started = integration.start_experiment(name="to invalidate", module="m", experiment_type="t")
    inv = integration.mark_experiment_invalid(started)
    assert inv["status"] == "invalidated"


def test_record_is_best_effort_and_never_raises():
    # Invalid input (blank name) must not raise — it returns None.
    result = integration.record_experiment(
        name="   ", module="m", experiment_type="t"
    )
    assert result is None


def test_complete_missing_experiment_returns_none():
    # Best-effort: completing a non-existent id returns None rather than raising.
    assert integration.complete_experiment(999_999, metrics={"x": 1}) is None
    assert integration.fail_experiment(999_999, error_message="x") is None
    assert integration.mark_experiment_invalid(999_999) is None
