"""
Meta-Labeling Lab tests (Phase 51.0): observation validation, label policy,
calibration (sigmoid/isotonic/one-class), probability metrics, reliability
bins + ECE/MCE, threshold analysis + abstention, fingerprints, persistence,
OOF integrity via Model Validation splits, policies/baselines, comparison,
export privacy, demo idempotence, and adversarial API paths.
"""

from __future__ import annotations

import json
import math

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
core = pytest.importorskip("app.meta_labeling.core")
cal = pytest.importorskip("app.meta_labeling.calibration")
thr = pytest.importorskip("app.meta_labeling.thresholds")
fp_mod = pytest.importorskip("app.meta_labeling.fingerprints")
service = pytest.importorskip("app.meta_labeling.service")

BASE = "/meta-labeling"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def obs(i, side=1, prob=0.5, outcome=0.01, **extra):
    return {
        "sample_id": f"o{i:03d}",
        "prediction_time": f"2025-01-{(i % 27) + 1:02d}T00:00:00",
        "evaluation_time": f"2025-02-{(i % 27) + 1:02d}T00:00:00",
        "primary_side": side, "raw_probability": prob,
        "realized_outcome": outcome, **extra,
    }


def spread_obs(n=40):
    """Both classes, spread probabilities."""
    return [obs(i, side=1 if i % 2 else -1,
                prob=0.1 + 0.8 * (i % 10) / 9.0,
                outcome=(0.01 if (i * 7) % 10 < 5 else -0.01) * (1 if i % 2 else -1))
            for i in range(n)]


# ---------------------------------------------------------------------------
# Label policy (§5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("side,outcome,expected", [
    (1, 0.02, 1),    # positive side, positive result
    (1, -0.02, 0),   # positive side, negative result
    (-1, -0.02, 1),  # negative side, negative result (correct short)
    (-1, 0.02, 0),   # negative side, positive result
    (1, 0.0, 0),     # zero outcome at threshold 0 → strict inequality → 0
])
def test_meta_label_policy(side, outcome, expected):
    rows = [obs(0, side=side, outcome=outcome)] + [obs(i) for i in range(1, 8)]
    norm = core.normalize_observations(rows)
    core.apply_meta_labels(norm, outcome_threshold=0.0)
    target = next(o for o in norm if o["sample_id"] == "o000")
    assert target["meta_label"] == expected


def test_exact_threshold_and_negative_threshold():
    rows = [obs(0, outcome=0.01)] + [obs(i) for i in range(1, 8)]
    norm = core.normalize_observations(rows)
    core.apply_meta_labels(norm, outcome_threshold=0.01)  # exactly at → 0
    assert next(o for o in norm if o["sample_id"] == "o000")["meta_label"] == 0
    norm2 = core.normalize_observations(rows)
    core.apply_meta_labels(norm2, outcome_threshold=-0.02)  # permissive negative
    assert next(o for o in norm2 if o["sample_id"] == "o000")["meta_label"] == 1


def test_side_zero_abstains_and_missing_outcome_rejected():
    rows = [obs(0, side=0, outcome=None)] + [obs(i) for i in range(1, 8)]
    norm = core.normalize_observations(rows)
    counts = core.apply_meta_labels(norm)
    z = next(o for o in norm if o["sample_id"] == "o000")
    assert z["abstained"] and z["meta_label"] is None
    assert counts["abstained_count"] == 1
    bad = [obs(0, side=1, outcome=None)] + [obs(i) for i in range(1, 8)]
    norm_bad = core.normalize_observations(bad)
    with pytest.raises(core.ObservationError):
        core.apply_meta_labels(norm_bad)


def test_observation_validation():
    with pytest.raises(core.ObservationError):  # bad side
        core.normalize_observations([obs(0, side=3)] + [obs(i) for i in range(1, 8)])
    with pytest.raises(core.ObservationError):  # prob out of range
        core.normalize_observations([obs(0, prob=1.2)] + [obs(i) for i in range(1, 8)])
    with pytest.raises(core.ObservationError):  # negative weight
        core.normalize_observations([obs(0, sample_weight=-1)] + [obs(i) for i in range(1, 8)])
    with pytest.raises(core.ObservationError):  # duplicate ids
        core.normalize_observations([obs(0)] * 8)
    with pytest.raises(core.ObservationError):  # eval < pred
        core.normalize_observations(
            [dict(obs(0), prediction_time="2025-03-01T00:00:00")] + [obs(i) for i in range(1, 8)])
    with pytest.raises(core.ObservationError):  # non-finite
        core.normalize_observations([obs(0, outcome=float("inf"))] + [obs(i) for i in range(1, 8)])


# ---------------------------------------------------------------------------
# Calibration (§7)
# ---------------------------------------------------------------------------


def _fit_data(n=60):
    probs = [0.05 + 0.9 * (i % 20) / 19.0 for i in range(n)]
    labels = [1 if (i * 13) % 20 < (i % 20) else 0 for i in range(n)]
    if len(set(labels)) < 2:
        labels[0] = 1 - labels[0]
    return probs, labels


def test_sigmoid_deterministic_and_monotone():
    probs, labels = _fit_data()
    p1, p2 = cal.fit_sigmoid(probs, labels), cal.fit_sigmoid(probs, labels)
    assert p1 == p2
    out = cal.apply_sigmoid(p1, [0.1, 0.5, 0.9])
    assert all(0 < p < 1 for p in out)


def test_isotonic_monotone_and_deterministic():
    probs, labels = _fit_data()
    params = cal.fit_isotonic(probs, labels)
    assert params == cal.fit_isotonic(probs, labels)
    out = cal.apply_isotonic(params, [0.05, 0.3, 0.6, 0.95])
    assert out == sorted(out)  # isotonic → non-decreasing


def test_one_class_and_min_samples_rejected():
    with pytest.raises(cal.CalibrationError):
        cal.fit_sigmoid([0.5] * 20, [1] * 20)
    with pytest.raises(cal.CalibrationError):
        cal.fit_isotonic([0.5] * 20, [0] * 20)
    with pytest.raises(cal.CalibrationError):
        cal.fit_sigmoid([0.5, 0.6], [0, 1])


def test_probability_metrics_and_undefined_cases():
    m = cal.probability_metrics([0.9, 0.1, 0.8, 0.2], [1, 0, 1, 0])
    assert m["metrics"]["brier"] < 0.1
    assert m["metrics"]["roc_auc"] == 1.0
    assert m["metrics"]["pr_auc"] == 1.0
    one = cal.probability_metrics([0.5, 0.6], [1, 1])
    assert one["metrics"]["roc_auc"] is None and "roc_auc" in one["reasons"]
    assert one["metrics"]["pr_auc"] is None
    empty = cal.probability_metrics([], [])
    assert empty["metrics"]["brier"] is None and empty["valid_count"] == 0


def test_reliability_bins_and_ece_mce():
    probs = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    labels = [0, 0, 0, 0, 1, 0, 1, 1, 1, 1]
    bins = cal.reliability_bins(probs, labels, n_bins=5, binning="equal_width")
    assert len(bins) == 5
    assert all(b["sample_count"] == 2 for b in bins)
    errs = cal.calibration_errors(bins, len(probs))
    assert errs["ece"] is not None and 0 <= errs["ece"] <= 1
    assert errs["mce"] is not None and errs["mce"] >= errs["ece"]
    # equal frequency
    binsf = cal.reliability_bins(probs, labels, n_bins=5, binning="equal_frequency")
    assert [b["sample_count"] for b in binsf] == [2, 2, 2, 2, 2]
    # empty bins safe (all probs in one bin)
    bins_sparse = cal.reliability_bins([0.5] * 10, [1, 0] * 5, n_bins=10, binning="equal_width")
    assert sum(1 for b in bins_sparse if b["sample_count"] == 0) == 9
    assert cal.calibration_errors([], 0) == {"ece": None, "mce": None}
    with pytest.raises(cal.CalibrationError):
        cal.reliability_bins(probs, labels, n_bins=1)


# ---------------------------------------------------------------------------
# Thresholds (§9)
# ---------------------------------------------------------------------------


def test_threshold_grid_and_confusion():
    probs = [0.2, 0.4, 0.6, 0.8]
    labels = [0, 1, 0, 1]
    table = thr.threshold_table(probs, labels, [None] * 4,
                                grid_config={"start": 0.0, "end": 1.0, "step": 0.5})
    t05 = next(r for r in table["thresholds"] if r["threshold"] == 0.5)
    assert t05["accepted"] == 2 and t05["coverage"] == 0.5
    assert t05["true_positives"] == 1 and t05["false_positives"] == 1
    assert t05["precision"] == 0.5 and t05["recall"] == 0.5
    # boundary: p == threshold accepted
    t_edge = thr.analyze_threshold([0.5], [1], [None], 0.5)
    assert t_edge["accepted"] == 1
    # zero denominators → null
    t_high = thr.analyze_threshold(probs, labels, [None] * 4, 1.0)
    assert t_high["accepted"] == 0 and t_high["precision"] is None


def test_threshold_grid_bounds_and_abstention():
    with pytest.raises(thr.ThresholdError):
        thr.build_grid({"start": 0, "end": 1, "step": 0.001})
    with pytest.raises(thr.ThresholdError):
        thr.build_grid({"start": -0.1, "end": 1, "step": 0.1})
    with pytest.raises(thr.ThresholdError):
        thr.validate_abstention({"lower": 0.7, "upper": 0.3})
    row = thr.analyze_threshold([0.5, 0.9, 0.1], [1, 1, 0], [None] * 3, 0.0,
                                {"lower": 0.4, "upper": 0.6})
    assert row["band_abstained"] == 1 and row["accepted"] == 2


def test_abstained_observations_excluded_from_confusion_matrix():
    # p=0.5 is band-abstained (a POSITIVE); p=0.2 and p=0.8 are decisions.
    # At threshold 0.9 both decisions are rejected: the abstained positive must
    # NOT be counted as a false negative, and the confusion matrix must cover
    # only the decision population (accepted + rejected == total - abstained).
    row = thr.analyze_threshold([0.5, 0.2, 0.8], [1, 0, 1], [None] * 3, 0.9,
                                {"lower": 0.4, "upper": 0.6})
    assert row["band_abstained"] == 1
    assert row["accepted"] == 0 and row["rejected"] == 2
    assert row["false_negatives"] == 1  # only the rejected 0.8 positive, not 0.5
    assert row["true_negatives"] == 1   # the rejected 0.2 negative
    assert (row["true_positives"] + row["false_positives"]
            + row["true_negatives"] + row["false_negatives"]) == 2
    # Coverage is still measured over ALL observations (0 accepted of 3).
    assert row["coverage"] == 0.0


# ---------------------------------------------------------------------------
# Fingerprints (§11)
# ---------------------------------------------------------------------------


def test_fingerprints_sensitivity():
    norm = core.normalize_observations(spread_obs(10))
    base = dict(label_policy={"outcome_threshold": 0.0}, observations=norm,
                calibration_method="sigmoid", calibration_settings={"n_bins": 10},
                oof_policy="none", threshold_grid={})
    a = fp_mod.configuration_fingerprint(**base)
    assert a == fp_mod.configuration_fingerprint(**base)
    assert a != fp_mod.configuration_fingerprint(**{**base, "calibration_method": "isotonic"})
    assert a != fp_mod.configuration_fingerprint(**{**base, "label_policy": {"outcome_threshold": 0.01}})
    r1 = fp_mod.result_fingerprint(configuration_fp=a, calibration_params={"m": 1},
                                   raw_probabilities=[0.5], calibrated_probabilities=[0.5],
                                   labels=[1], metrics={}, bins=[])
    r2 = fp_mod.result_fingerprint(configuration_fp=a, calibration_params={"m": 1},
                                   raw_probabilities=[0.5], calibrated_probabilities=[0.6],
                                   labels=[1], metrics={}, bins=[])
    assert r1 != r2


# ---------------------------------------------------------------------------
# API lifecycle + OOF integrity
# ---------------------------------------------------------------------------


def _create(client, **over):
    payload = {"name": "Run", "calibration_method": "sigmoid",
               "observations": spread_obs(), **over}
    return client.post(f"{BASE}/runs", json=payload)


def test_create_execute_roundtrip(client):
    run = _create(client).json()
    assert run["status"] == "pending" and run["configuration_fingerprint"]
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["oof_status"] == "not_out_of_fold"  # fitted on all, disclosed
    assert done["result_fingerprint"]
    assert done["raw_metrics"]["metrics"]["brier"] is not None
    assert done["calibrated_metrics"]["ece"] is not None
    bins = client.get(f"{BASE}/runs/{run['id']}/calibration").json()
    assert len(bins["bins"]["raw"]) == 10 and len(bins["bins"]["calibrated"]) == 10
    tt = client.get(f"{BASE}/runs/{run['id']}/thresholds").json()
    assert tt["grid_size"] > 0


def _clean_validation_run(mv_service, n=40):
    """A leakage-clean purged run over short-horizon samples o000..o0NN."""
    from datetime import datetime, timedelta
    base = datetime(2025, 1, 1)
    samples = [{"sample_id": f"o{i:03d}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 2)).isoformat()}
               for i in range(n)]
    vrun = mv_service.create_run({"name": "v", "method": "purged_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is True
    return vrun


def test_verified_oof_via_validation_run(client):
    # Build a clean purged validation run whose sample ids match observations.
    from app.model_validation import service as mv_service
    vrun = _clean_validation_run(mv_service)
    run = _create(client, validation_run_id=vrun["id"]).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["oof_status"] == "verified_from_validation_run"
    # Per-split params recorded; observations carry their split labels.
    assert done["calibration_params"]["per_split"]
    obs_page = client.get(f"{BASE}/runs/{run['id']}/observations").json()
    assert all(o["split_label"] for o in obs_page["items"] if not o["abstained"])


def test_oof_membership_mismatch_fails_honestly(client):
    from datetime import datetime, timedelta
    from app.model_validation import service as mv_service
    base = datetime(2025, 1, 1)
    samples = [{"sample_id": f"different-{i}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 2)).isoformat()}
               for i in range(20)]
    vrun = mv_service.create_run({"name": "v2", "method": "purged_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is True
    run = _create(client, validation_run_id=vrun["id"]).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "not members" in done["error_message"]


def test_declared_oof_is_declared_not_verified(client):
    run = _create(client, calibration_method="none", declared_out_of_fold=True).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["oof_status"] == "declared_out_of_fold"


def test_one_class_execution_fails_honestly(client):
    rows = [obs(i, side=1, outcome=0.02) for i in range(20)]  # all correct → one class
    run = _create(client, observations=rows).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "both classes" in done["error_message"]


def test_experiment_creation_idempotent(client):
    run = _create(client).json()
    first = client.post(f"{BASE}/runs/{run['id']}/execute",
                        json={"create_experiment": True}).json()
    assert first["experiment_id"]
    second = client.post(f"{BASE}/runs/{run['id']}/execute",
                         json={"create_experiment": True}).json()
    assert second["experiment_id"] == first["experiment_id"]


def test_dataset_link_and_invalidation_warning(client):
    ds = client.post("/datasets", json={"name": "MDS", "domain": "x",
                                        "dataset_type": "t"}).json()
    v = client.post(f"/datasets/{ds['id']}/versions",
                    json={"version_label": "v1",
                          "storage_locator": "fixture://m/x"}).json()
    run = _create(client, dataset_version_id=v["id"]).json()
    assert run["dataset_name"] == "MDS" and run["dataset_invalidated"] is False
    client.post(f"/dataset-versions/{v['id']}/invalidate", json={"reason": "old"})
    assert client.get(f"{BASE}/runs/{run['id']}").json()["dataset_invalidated"] is True


# ---------------------------------------------------------------------------
# Policies + baselines
# ---------------------------------------------------------------------------


def test_policy_and_baseline_rules(client):
    run = _create(client, calibration_method="none", declared_out_of_fold=True).json()
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    pol = client.post(f"{BASE}/runs/{run['id']}/threshold-policies",
                      json={"threshold": 0.5, "name": "p1"})
    assert pol.status_code == 201
    body = pol.json()
    assert body["observed_coverage"] is not None
    assert client.post(f"{BASE}/threshold-policies/{body['id']}/mark-baseline").status_code == 200
    # replacement within the run scope
    pol2 = client.post(f"{BASE}/runs/{run['id']}/threshold-policies",
                       json={"threshold": 0.7}).json()
    client.post(f"{BASE}/threshold-policies/{pol2['id']}/mark-baseline")
    policies = client.get(f"{BASE}/runs/{run['id']}/threshold-policies").json()
    baselines = [p for p in policies if p["is_baseline"]]
    assert len(baselines) == 1 and baselines[0]["id"] == pol2["id"]
    # invalid threshold + bad band rejected
    assert client.post(f"{BASE}/runs/{run['id']}/threshold-policies",
                       json={"threshold": 1.5}).status_code == 422
    assert client.post(f"{BASE}/runs/{run['id']}/threshold-policies",
                       json={"threshold": 0.5,
                             "abstention": {"lower": 0.8, "upper": 0.2}}).status_code == 422


def test_baseline_rejected_for_non_oof_and_failed(client):
    run = _create(client).json()  # sigmoid on all → not_out_of_fold
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    pol = client.post(f"{BASE}/runs/{run['id']}/threshold-policies",
                      json={"threshold": 0.5}).json()
    assert client.post(f"{BASE}/threshold-policies/{pol['id']}/mark-baseline").status_code == 409
    # failed run → policies rejected outright
    rows = [obs(i, side=1, outcome=0.02) for i in range(20)]
    bad = _create(client, observations=rows).json()
    client.post(f"{BASE}/runs/{bad['id']}/execute", json={})
    assert client.post(f"{BASE}/runs/{bad['id']}/threshold-policies",
                       json={"threshold": 0.5}).status_code == 409


# ---------------------------------------------------------------------------
# Comparison + export + demo + coexistence
# ---------------------------------------------------------------------------


def test_compare_and_export(client):
    a = _create(client, name="A", calibration_method="none").json()
    b = _create(client, name="B").json()
    for r in (a, b):
        client.post(f"{BASE}/runs/{r['id']}/execute", json={})
    cmp = client.get(f"{BASE}/compare", params={"a": a["id"], "b": b["id"]}).json()
    assert cmp["fingerprint_match"]["configuration"] is False
    kinds = {e["kind"] for g in cmp["groups"].values() for e in g}
    assert kinds <= {"same", "changed", "only_in_a", "only_in_b", "unavailable"}
    assert client.get(f"{BASE}/compare", params={"a": a["id"], "b": a["id"]}).status_code == 422
    ex = client.get(f"{BASE}/export").json()
    text = json.dumps(ex).lower()
    for needle in ("c:\\", "/users/", "/home/", "password", "api_key", "pickle", "joblib"):
        assert needle not in text


def test_demo_idempotent_and_registries_preserved(client):
    first = client.post(f"{BASE}/demo-seed").json()
    assert first["created_runs"] == 7 and first["created_policies"] == 3
    second = client.post(f"{BASE}/demo-seed").json()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 7
    summary = client.get(f"{BASE}/summary").json()
    assert summary["oof_verified"] == 1 and summary["baselines"] == 1
    # neighbours still fine
    assert client.get("/model-validation/summary").status_code == 200
    assert client.get("/datasets/summary").status_code == 200
    assert client.get("/experiment-registry/summary").status_code == 200
    report = client.post("/saved-reports", json={
        "title": "R", "report_type": "markdown", "source_type": "manual",
        "markdown_content": "# hi"})
    assert report.status_code == 200


def test_adversarial_api(client):
    assert client.get(f"{BASE}/runs/9999").status_code == 404
    assert _create(client, validation_run_id=9999).status_code == 404
    assert _create(client, dataset_version_id=9999).status_code == 404
    assert _create(client, calibration_method="magic").status_code == 422
    assert _create(client, name="  ").status_code == 422
    # raw NaN token → clean 422 via app-wide handler
    body = json.dumps({"name": "X", "calibration_method": "none",
                       "observations": spread_obs(8)}).replace('"raw_probability": 0.1',
                                                               '"raw_probability": NaN', 1)
    assert client.post(f"{BASE}/runs", content=body,
                       headers={"Content-Type": "application/json"}).status_code == 422
    # invalidated run cannot execute
    run = _create(client).json()
    client.post(f"{BASE}/runs/{run['id']}/invalidate", json={"reason": "x"})
    assert client.post(f"{BASE}/runs/{run['id']}/execute", json={}).status_code == 409
