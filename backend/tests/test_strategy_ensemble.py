"""Phase 64 deterministic contracts, arithmetic, persistence and API tests."""

from copy import deepcopy
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import db
from app.strategy_ensemble import core, demo, links, service, store
from app.strategy_ensemble.models import RunCreate, WeightPolicy, timestamp


@pytest.fixture(autouse=True)
def fresh_db(isolated_lab_db):
    return isolated_lab_db


def analyze(payload=None):
    return core.analyze(RunCreate.model_validate(payload or demo.payload()))


def completed(payload=None):
    r = service.create_run(payload or demo.payload())
    return service.execute_run(r["id"])


@pytest.mark.parametrize("change", [
    lambda p: p["definitions"].append(p["definitions"][0]),
    lambda p: p["definitions"][0].update(return_convention="log"),
    lambda p: p["definitions"][0].update(gross_or_net="net"),
    lambda p: p["definitions"][0].update(frequency="weekly"),
    lambda p: p["definitions"][0].update(currency="EUR"),
    lambda p: p["observations"].append(p["observations"][0]),
    lambda p: p["observations"][0].update(return_value=-1),
    lambda p: p["observations"][0].update(return_value=float("nan")),
    lambda p: p["observations"][0].update(cost_return=float("inf")),
    lambda p: p["observations"][0].update(return_value=True),
    lambda p: p["observations"][0].update(period_end="2023-01-01"),
    lambda p: p["observations"][0].update(strategy_id="unknown"),
    lambda p: p.update(policy={"mode": "user_static", "weights": {"a": -.1, "b": 1.1}}),
    lambda p: p.update(analysis={"minimum_samples": True}),
    lambda p: p.update(scenarios=[{"label": "x", "policy": {}}]*13),
])
@pytest.mark.db_free
def test_strict_input(change):
    p = demo.payload()
    change(p)
    with pytest.raises(ValueError):
        service.create_run(p)


@pytest.mark.db_free
def test_alignment_uses_exact_periods_no_fill():
    p = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [.2, -.2, .1, -.1], "c": [.1, .2, -.1, -.2]})
    p["observations"] = [r for i, r in enumerate(p["observations"]) if i not in (0, 5)]
    p["analysis"] = {"pairwise_alignment": "pairwise_complete"}
    r = analyze(p)
    assert r["coverage"]["strict_intersection_periods"] == 2
    assert sorted(x["n"] for x in r["pairwise"]) == [2, 3, 3]
    assert r["matrix"]["n"] == 2
    assert r["matrix"]["values"] is None
    assert len(r["ensemble"]["periods"]) == 2


@pytest.mark.db_free
def test_timestamp_normalization_and_different_end_not_aligned():
    assert timestamp("2024-01-01T08:00:00+08:00") == timestamp("2024-01-01")
    p = demo.payload()
    p["observations"][0]["period_end"] = "2024-01-01T12:00:00"
    assert analyze(p)["coverage"]["strict_intersection_periods"] == 39


@pytest.mark.db_free
def test_identical_correlation_matrix_and_tail():
    r = analyze()
    pair = r["pairwise"][0]
    for method in ("pearson", "spearman"):
        assert pair["correlations"][method]["value"] == pytest.approx(1)
        assert pair["correlations"][method]["p_value"] <= 1e-10
    assert pair["empirical_lower_tail_overlap"]["jaccard"] == 1
    m = r["matrix"]
    assert m["rank"] == 1 and m["condition"] is None
    assert m["eigenvalues"] == pytest.approx([0, 2])
    assert m["effective_strategy_count"] == pytest.approx(1)
    assert m["sample"] == "strict_intersection"


@pytest.mark.db_free
def test_inverse_and_constant():
    p = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [-.1, .1, -.2, .2]})
    r = analyze(p)
    assert r["pairwise"][0]["correlations"]["pearson"]["value"] == pytest.approx(-1)
    assert all(row["ensemble_return"] == 0 for row in r["ensemble"]["periods"])
    assert r["ensemble"]["drawdown"]["max_drawdown"] == 0
    p = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [0.]*4})
    r = analyze(p)
    assert r["matrix"]["state"] == "unavailable"
    assert r["pairwise"][0]["correlations"]["pearson"]["value"] is None
    assert r["pairwise"][0]["empirical_lower_tail_overlap"]["state"] == "unavailable"


@pytest.mark.db_free
def test_drawdown_initial_loss_and_recovery_trailing_only():
    keys = [(str(i), str(i+1)) for i in range(4)]
    r = core.drawdowns(keys, [-.2, .1, -.1, .5])
    assert [p["wealth"] for p in r["periods"]] == pytest.approx([.8, .88, .792, 1.188])
    assert r["max_drawdown"] == pytest.approx(-.208)
    assert r["episodes"][0]["trough"] == "3"
    assert r["episodes"][0]["recovery"] == "4"
    assert r["episodes"][0]["duration_periods"] == 4
    assert core.drawdowns(keys[:3], [-.2, .1, -.1])["periods"] == r["periods"][:3]


@pytest.mark.db_free
def test_deepest_episode_overlap_uses_reported_pair_sample():
    p = demo.payload(values={"a": [-.1]*4, "b": [-.1]*4, "c": [-.1]*4})
    c = [r for r in p["observations"] if r["strategy_id"] == "c"]
    p["observations"] = [r for r in p["observations"] if r not in c[:2]]
    pair = analyze(p)["pairwise"][0]
    assert pair["n"] == 2
    assert pair["drawdown_overlap"]["deepest_episode_overlap"] == 2
    p["analysis"] = {"pairwise_alignment": "pairwise_complete"}
    pair = analyze(p)["pairwise"][0]
    assert pair["n"] == 4
    assert pair["drawdown_overlap"]["deepest_episode_overlap"] == 4


@pytest.mark.parametrize("value", ["/tmp/research/private.csv", "location /etc/private", "FILE:///tmp/private"])
@pytest.mark.db_free
def test_supplied_metadata_rejects_local_paths(value):
    p = demo.payload()
    p["definitions"][0]["metadata"] = {"note": value}
    with pytest.raises(ValueError, match="machine-local paths"):
        service.create_run(p)


@pytest.mark.parametrize("normalization,weights,expected", [
    ("require_sum_to_one", {"a": .75, "b": .25}, {"a": .75, "b": .25}),
    ("normalize_by_sum", {"a": 3., "b": 1.}, {"a": .75, "b": .25}),
    ("normalize_by_gross", {"a": 3., "b": 1.}, {"a": .75, "b": .25}),
    ("none", {"a": 1., "b": 1.}, {"a": 1., "b": 1.}),
])
@pytest.mark.db_free
def test_weights_and_contributions(normalization, weights, expected):
    p = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [.02, -.02, .01, -.01]})
    p["policy"] = {"mode": "user_static", "weights": weights, "normalization": normalization}
    r = analyze(p)["ensemble"]
    assert r["weights"]["effective"] == expected
    assert r["periods"][0]["ensemble_return"] == pytest.approx(expected["a"]*.1+expected["b"]*.02)
    assert r["reconciliation_max_residual"] == 0
    assert sum(s["arithmetic_contribution"] for s in r["contribution_summary"]) == pytest.approx(r["arithmetic_sum"])


@pytest.mark.parametrize("weights", [{"a": 1.}, {"a": 0., "b": 0.}, {"a": .8, "b": .8}])
def test_invalid_weight_totals(weights):
    p = demo.payload()
    p["policy"] = {"mode": "user_static", "weights": weights}
    with pytest.raises(ValueError):
        service.create_run(p)


@pytest.mark.db_free
def test_net_costs_never_deducted_twice_and_turnover_separate():
    p = demo.payload(basis="net_of_strategy_costs")
    for row in p["observations"]:
        row.update(cost_return=.001, turnover=.4)
    p["policy"] = {"initial_build": "zero_prior_weights"}
    r = analyze(p)["ensemble"]
    assert r["periods"][0]["ensemble_return"] == -.02
    assert r["turnover"]["initial_allocation"] == .5
    assert r["turnover"]["subsequent_target_weight_change"] == 0
    assert r["turnover"]["underlying"][0]["turnover_sum"] == pytest.approx(16)
    assert r["costs"]["net_of_strategy_costs_reference"] == r["drawdown"]["compounded_return"]
    assert r["costs"]["gross_ensemble_reference"] is None
    assert r["costs"]["allocation_cost"] is None
    assert r["costs"]["underlying_cost_deducted_again"] is False
    assert analyze()["ensemble"]["turnover"]["underlying"][0]["cost_return_sum"] is None


def test_mixed_basis_not_promoted():
    p = demo.payload()
    p["definitions"][0]["gross_or_net"] = "unknown"
    for row in p["observations"]:
        if row["strategy_id"] == "a":
            row["gross_or_net"] = "unknown"
    r = completed(p)
    assert not r["results"]["baseline_eligible"]
    assert r["results"]["ensemble"]["costs"]["gross_ensemble_reference"] is None


@pytest.mark.db_free
def test_sensitivity_deduplicates_effective_policy():
    p = demo.payload()
    p["scenarios"] = [{"label": "duplicate", "policy": {}},
                      {"label": "scaled duplicate", "policy": {"mode": "user_static", "weights": {"a": 2., "b": 2.}, "normalization": "normalize_by_sum"}},
                      {"label": "explicit", "policy": {"mode": "user_static", "weights": {"a": .7, "b": .3}}}]
    assert len(analyze(p)["sensitivity"]) == 2


@pytest.mark.parametrize("field", ["information_available_at", "configuration_available_at", "weights_available_at"])
def test_invalid_timing_persists_failure_and_cannot_baseline(field):
    p = demo.payload()
    if field == "information_available_at":
        p["observations"][0][field] = "2024-01-01"
    elif field == "configuration_available_at":
        p["definitions"][0][field] = "2025-01-01"
    else:
        p[field] = "2025-01-01"
    r = service.create_run(p)
    with pytest.raises(ValueError, match="timing violation"):
        service.execute_run(r["id"])
    assert service.get_run(r["id"])["status"] == "failed"
    with pytest.raises(service.ConflictError):
        service.mark_baseline(r["id"])


@pytest.mark.fresh_schema
def test_persistence_rerun_fingerprints_baseline_invalidation():
    first = completed()
    db.init_db()
    second = completed()
    assert first["fingerprints"] == second["fingerprints"]
    assert service.execute_run(first["id"])["results"] == first["results"]
    service.mark_baseline(first["id"])
    service.mark_baseline(second["id"])
    assert not service.get_run(first["id"])["is_baseline"]
    assert service.get_run(second["id"])["is_baseline"]
    service.invalidate(second["id"], "manual test")
    with pytest.raises(service.ConflictError):
        service.execute_run(second["id"])
    assert service.export(first["id"])["schema_version"] == "strategy_ensemble_v1"


@pytest.mark.parametrize("change", [
    lambda p: p["observations"][0].update(return_value=.07),
    lambda p: p["observations"][0].update(turnover=.1),
    lambda p: p["observations"][0].update(information_available_at="2024-01-03"),
    lambda p: p["definitions"][0].update(source_fingerprint="a"*64),
    lambda p: p.update(policy={"mode": "user_static", "weights": {"a": .7, "b": .3}}),
    lambda p: p.update(analysis={"tail_quantile": .2}),
])
def test_material_changes_fingerprint(change):
    first = service.create_run(demo.payload())
    p = demo.payload()
    change(p)
    second = service.create_run(p)
    assert first["fingerprints"]["configuration"] != second["fingerprints"]["configuration"]


def test_tampered_results_block_baseline():
    run = completed()
    with store.connection() as conn:
        conn.execute("UPDATE strategy_ensemble_runs SET results_json='{}' WHERE id=?", (run["id"],))
    with pytest.raises(service.ConflictError):
        service.mark_baseline(run["id"])


def test_regime_and_exact_heldout_membership_read_only():
    p = demo.payload()
    p.update(demo.linked_fixture())
    before = links.snapshot(RunCreate.model_validate(p))
    r = completed(p)["results"]
    assert len(r["regimes"]) == 2
    assert all(row["n"] == 20 and not row["rare"] for row in r["regimes"])
    assert r["validation"]["weights_frozen"]
    assert r["validation"]["training"]["sample_ids"] == before["validation"]["memberships"]["train_ids"]
    assert r["validation"]["held_out"]["weights"] == {"a": .5, "b": .5}
    assert links.snapshot(RunCreate.model_validate(p)) == before


def test_no_heldout_refit():
    p = demo.payload()
    p.update(demo.linked_fixture())
    first = completed(p)["results"]["validation"]
    heldout_ids = set(first["held_out"]["sample_ids"])
    for r in p["observations"]:
        if r["source_observation_id"] in heldout_ids:
            r["return_value"] = .2
    second = completed(p)["results"]["validation"]
    assert first["training"] == second["training"]
    assert first["held_out"]["mean_return"] != second["held_out"]["mean_return"]


@pytest.mark.db_free
def test_multiple_testing_uses_real_p_values():
    results = analyze()["multiple_testing"]["results"]
    assert len(results) == 2
    assert all(r["holm"] >= r["raw_p_value"] for r in results)


def test_experiment_record_idempotent():
    r = service.create_run(demo.payload())
    first = service.execute_run(r["id"], True)
    assert first["experiment_id"] is not None
    assert service.execute_run(r["id"], True)["experiment_id"] == first["experiment_id"]


def test_demo_idempotence_and_api_contract():
    client = TestClient(pytest.importorskip("app.main").app)
    a = client.post("/strategy-ensembles/demo-seed")
    assert a.status_code == 200, a.text
    assert a.json()["created_count"] == 10
    b = client.post("/strategy-ensembles/demo-seed")
    assert b.json()["created_count"] == 0
    assert b.json()["run_ids"] == a.json()["run_ids"]
    assert client.get("/strategy-ensembles/runs").json()["total"] == 10
    run_id = a.json()["run_ids"][0]
    data = client.get(f"/strategy-ensembles/runs/{run_id}").json()
    assert data["results"]["ensemble"]["n"] == 40
    exported = client.get("/strategy-ensembles/export", params={"run_id": run_id})
    assert exported.status_code == 200
    assert "NaN" not in exported.text and "Infinity" not in exported.text
    assert client.get("/strategy-ensembles/compare", params={"a": run_id, "b": run_id+1}).status_code == 200


@pytest.mark.parametrize("path,code", [("/runs/99999", 404), ("/runs?page_size=101", 422), ("/compare?a=1&b=1", 422)])
def test_api_error_paths(path, code):
    assert TestClient(pytest.importorskip("app.main").app).get("/strategy-ensembles"+path).status_code == code


def test_privacy_validation_and_unknown_dataset():
    p = demo.payload()
    p["definitions"][0]["metadata"] = {"api_key": "should_not_store"}
    with pytest.raises(ValueError):
        service.create_run(p)
    p = demo.payload()
    p["definitions"][0]["dataset_version_id"] = 9999
    with pytest.raises(ValueError, match="dataset"):
        service.create_run(p)


def test_dataset_identity_read_only_invalidation_and_export_privacy():
    from app.dataset_registry import service as ds
    dataset = ds.create_dataset({"name": "Phase64 dataset", "domain": "equities", "dataset_type": "prices",
                                 "source_type": "deterministic_fixture", "format": "csv"})
    version = ds.create_version(dataset["id"], {"version_label": "v1", "storage_locator": "fixture://private/location",
        "format": "csv", "deterministic": True, "row_count": 40,
        "schema_snapshot": {"fields": [{"name": "ret", "type": "float", "nullable": False}]},
        "content_fingerprint": "a" * 64})
    p = demo.payload()
    for d in p["definitions"]:
        d["dataset_version_id"] = version["id"]
    run = completed(p)
    exported = service.export(run["id"])
    assert exported["source_identities"]["datasets"]["a"]["dataset_name"] == "Phase64 dataset"
    assert exported["source_identities"]["datasets"]["a"]["content_fingerprint"] == "a" * 64
    assert "private/location" not in json.dumps(exported)
    assert "storage_locator" not in json.dumps(exported)
    ds.invalidate_version(version["id"], "test invalidation")
    with pytest.raises(service.ConflictError):
        service.mark_baseline(run["id"])
    with pytest.raises(ValueError, match="invalidated"):
        service.create_run(p)


def test_link_mutation_rejected_even_without_fingerprint_change():
    p = demo.payload()
    p.update(demo.linked_fixture())
    run = completed(p)
    with store.connection() as conn:
        conn.execute("UPDATE regime_definitions SET assignments_json=? WHERE run_id=?",
                     (json.dumps(["altered"] * 40), p["regime"]["run_id"]))
    with pytest.raises(service.ConflictError, match="changed"):
        service.execute_run(run["id"])


def test_rare_regime_and_missing_validation_membership():
    p = demo.payload()
    p.update(demo.linked_fixture())
    p["analysis"] = {"rare_regime_minimum": 30}
    assert all(r["statistics"] is None and r["rare"] for r in completed(p)["results"]["regimes"])
    p["observations"] = p["observations"][1:]
    run = service.create_run(p)
    with pytest.raises(ValueError, match="exact common"):
        service.execute_run(run["id"])


def test_no_overlap_and_leveraged_loss_fail_without_nonfinite_results():
    p = demo.payload()
    p["observations"] = [r for r in p["observations"] if
        (r["strategy_id"] == "a" and r["period_start"] < "2024-01-20") or
        (r["strategy_id"] == "b" and r["period_start"] >= "2024-01-20")]
    run = service.create_run(p)
    with pytest.raises(ValueError, match="strict-intersection"):
        service.execute_run(run["id"])
    p = demo.payload(values={"a": [-.5, -.5], "b": [-.5, -.5]})
    p["policy"] = {"mode": "user_static", "weights": {"a": 2., "b": 2.}, "normalization": "none"}
    run = service.create_run(p)
    with pytest.raises(ValueError, match="-100%"):
        service.execute_run(run["id"])
    assert service.get_run(run["id"])["results"] is None


def test_api_create_validation_execute_and_baseline():
    client = TestClient(pytest.importorskip("app.main").app)
    assert client.post("/strategy-ensembles/runs", json={"name": "missing streams"}).status_code == 422
    p = demo.payload()
    r = client.post("/strategy-ensembles/runs", json=p)
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.post(f"/strategy-ensembles/runs/{rid}/mark-baseline").status_code == 409
    assert client.post(f"/strategy-ensembles/runs/{rid}/execute", json={}).status_code == 200
    assert client.post(f"/strategy-ensembles/runs/{rid}/mark-baseline").json()["is_baseline"]
    assert client.post(f"/strategy-ensembles/runs/{rid}/invalidate", json={"reason": " "}).status_code == 422


def test_order_invariance_and_bad_metadata_are_explicit():
    p = demo.payload()
    original = completed(p)
    p["name"] = "Another display label"
    p["definitions"].reverse()
    p["observations"].reverse()
    assert completed(p)["fingerprints"] == original["fingerprints"]
    p["description"] = "C:\\private\\research.csv"
    with pytest.raises(ValueError, match="paths"):
        service.create_run(p)
