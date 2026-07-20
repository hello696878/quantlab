"""
Feature Diagnostics Lab tests (Phase 52.0): input validation + target-leakage
detection, deterministic estimators, metric direction, held-out permutation
importance, rank aggregation + tie handling, Spearman/Kendall/top-k stability,
correlation groups + constant features, distribution/importance drift + PSI/KS,
fingerprints, persistence + migration, held-out integrity via Model Validation
splits, baselines, registry integrations, comparison, export privacy, demo
idempotence, and adversarial API paths.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
core = pytest.importorskip("app.feature_diagnostics.core")
estimators = pytest.importorskip("app.feature_diagnostics.estimators")
metrics_mod = pytest.importorskip("app.feature_diagnostics.metrics")
imp_mod = pytest.importorskip("app.feature_diagnostics.importance")
stab_mod = pytest.importorskip("app.feature_diagnostics.stability")
corr_mod = pytest.importorskip("app.feature_diagnostics.correlation")
drift_mod = pytest.importorskip("app.feature_diagnostics.drift")
fp_mod = pytest.importorskip("app.feature_diagnostics.fingerprints")
service = pytest.importorskip("app.feature_diagnostics.service")
fd_store = pytest.importorskip("app.feature_diagnostics.store")

BASE = "/feature-diagnostics"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _defs(names=("f0", "f1", "f2")):
    return [{"feature_name": n} for n in names]


def _samples(n=60, names=("f0", "f1", "f2"), driver="f0"):
    """Deterministic samples where `driver` drives a binary target."""
    out = []
    for i in range(n):
        feats = {}
        for j, name in enumerate(names):
            feats[name] = round(((i * (7 + 4 * j)) % (11 + 2 * j) - 5 - j) / 6.0, 6)
        logit = 2.5 * feats[driver] + (((i * 31) % 7) - 3) / 10.0
        out.append({
            "sample_id": f"s{i:03d}",
            "timestamp": f"2025-01-{(i % 27) + 1:02d}T00:00:00",
            "features": feats,
            "target": 1 if logit > 0 else 0,
        })
    return out


def _payload(**overrides):
    payload = {
        "name": "run", "method": "permutation",
        "model_type": "logistic_regression",
        "target_type": "binary_classification", "metric": "log_loss",
        "features": _defs(), "samples": _samples(),
        "permutation_repeats": 3, "seed": 5,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Input validation + target leakage (§4, §26)
# ---------------------------------------------------------------------------


def test_input_validation():
    with pytest.raises(core.FeatureInputError):  # duplicate feature names
        core.normalize_feature_definitions([{"feature_name": "a"}, {"feature_name": "a"}])
    with pytest.raises(core.FeatureInputError):  # feature named target
        core.normalize_feature_definitions([{"feature_name": "target"}])
    with pytest.raises(core.FeatureInputError):  # categorical unsupported
        core.normalize_feature_definitions([{"feature_name": "a", "data_type": "categorical"}])
    samples = _samples(20)
    with pytest.raises(core.FeatureInputError):  # duplicate sample ids
        core.normalize_samples(samples + [samples[0]], ["f0", "f1", "f2"],
                               "binary_classification")
    bad = [dict(samples[0], features=dict(samples[0]["features"], f0=float("nan")))]
    with pytest.raises(core.FeatureInputError):  # non-finite feature
        core.normalize_samples(bad + samples[1:], ["f0", "f1", "f2"],
                               "binary_classification")
    with pytest.raises(core.FeatureInputError):  # non-binary target
        core.normalize_samples([dict(samples[0], target=0.5)] + samples[1:],
                               ["f0", "f1", "f2"], "binary_classification")
    with pytest.raises(core.FeatureInputError):  # missing feature value
        core.normalize_samples([dict(samples[0], features={"f0": 1.0})] + samples[1:],
                               ["f0", "f1", "f2"], "binary_classification")
    with pytest.raises(core.FeatureInputError):  # tz mix
        core.normalize_samples(
            [dict(samples[0], timestamp="2025-01-01T00:00:00Z")] + samples[1:],
            ["f0", "f1", "f2"], "binary_classification")
    with pytest.raises(core.FeatureInputError):  # too few samples
        core.normalize_samples(samples[:4], ["f0", "f1", "f2"], "binary_classification")


def test_target_leakage_detection():
    y = np.array([0.0, 1.0, 0.0, 1.0] * 5)
    X_ident = np.column_stack([y, np.arange(20.0)])
    with pytest.raises(core.FeatureInputError):
        core.check_target_leakage(X_ident, y, ["leak", "ok"])
    X_affine = np.column_stack([2.0 * y + 3.0, np.arange(20.0)])
    with pytest.raises(core.FeatureInputError):  # exact affine transform
        core.check_target_leakage(X_affine, y, ["leak", "ok"])
    X_ok = np.column_stack([np.arange(20.0), np.arange(20.0)[::-1]])
    core.check_target_leakage(X_ok, y, ["a", "b"])  # no raise


# ---------------------------------------------------------------------------
# Estimators (§5) — deterministic, dependency-light
# ---------------------------------------------------------------------------


def test_estimators_deterministic_and_predictive():
    samples = _samples(80)
    X, y, _ = core.build_matrix(samples, ["f0", "f1", "f2"])
    m1 = estimators.fit_estimator("logistic_regression", X, y, "binary_classification")
    m2 = estimators.fit_estimator("logistic_regression", X, y, "binary_classification")
    assert m1["weights"] == m2["weights"]
    preds = estimators.predict(m1, X)
    assert metrics_mod.score("roc_auc", y, preds) > 0.8
    coef = estimators.coefficient_reference(m1, ["f0", "f1", "f2"])
    assert coef[0]["standardized"] is True
    assert abs(coef[0]["coefficient"]) > abs(coef[2]["coefficient"])

    t1 = estimators.fit_estimator("decision_tree", X, y, "binary_classification")
    t2 = estimators.fit_estimator("decision_tree", X, y, "binary_classification")
    assert t1["native_importance"] == t2["native_importance"]
    native = estimators.native_reference(t1, ["f0", "f1", "f2"])
    assert native[0]["native_importance"] == max(r["native_importance"] for r in native)
    assert abs(sum(r["native_importance"] for r in native) - 1.0) < 1e-9

    with pytest.raises(estimators.EstimatorError):  # one-class training data
        estimators.fit_estimator("logistic_regression", X, np.zeros(len(y)),
                                 "binary_classification")
    with pytest.raises(estimators.EstimatorError):  # task mismatch
        estimators.fit_estimator("linear_regression", X, y, "binary_classification")


def test_linear_regression_and_r2():
    rng_vals = np.array([((i * 13) % 17 - 8) / 8.0 for i in range(60)])
    X = np.column_stack([rng_vals, rng_vals[::-1]])
    y = 3.0 * rng_vals + 0.5
    model = estimators.fit_estimator("linear_regression", X, y, "regression")
    preds = estimators.predict(model, X)
    assert metrics_mod.score("r2", y, preds) > 0.99
    assert metrics_mod.score("rmse", y, preds) < 0.05


# ---------------------------------------------------------------------------
# Metrics + direction (§6)
# ---------------------------------------------------------------------------


def test_metric_directions_and_undefined_cases():
    assert metrics_mod.metric_direction("log_loss") == "lower_is_better"
    assert metrics_mod.metric_direction("roc_auc") == "higher_is_better"
    y = np.array([0, 0, 1, 1], dtype=float)
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert metrics_mod.score("roc_auc", y, p) == 0.75
    with pytest.raises(metrics_mod.MetricUnavailable):  # one-class
        metrics_mod.score("roc_auc", np.ones(4), p)
    with pytest.raises(metrics_mod.MetricUnavailable):  # constant target r2
        metrics_mod.score("r2", np.ones(4), p)
    with pytest.raises(metrics_mod.MetricUnavailable):  # empty fold
        metrics_mod.score("brier", np.array([]), np.array([]))
    with pytest.raises(metrics_mod.MetricUnavailable):  # unsupported metric
        metrics_mod.score("sharpe", y, p)


def test_importance_normalization_direction():
    # higher_is_better: baseline - permuted (drop in AUC → positive importance)
    assert metrics_mod.importance_from_scores("higher_is_better", 0.9, 0.6) == pytest.approx(0.3)
    # lower_is_better: permuted - baseline (rise in loss → positive importance)
    assert metrics_mod.importance_from_scores("lower_is_better", 0.4, 0.7) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Permutation importance (§5A, §7)
# ---------------------------------------------------------------------------


def _fitted_split(n=120):
    samples = _samples(n)
    X, y, _ = core.build_matrix(samples, ["f0", "f1", "f2"])
    train, test = np.arange(0, 80), np.arange(80, n)
    model = estimators.fit_estimator("logistic_regression", X[train], y[train],
                                     "binary_classification")
    return model, X[test], y[test]


def test_permutation_importance_signal_and_determinism():
    model, X_test, y_test = _fitted_split()
    r1 = imp_mod.permutation_split_result(
        model, X_test, y_test, ["f0", "f1", "f2"], "log_loss",
        "lower_is_better", seed=9, split_index=0, repeats=5, split_id="s")
    r2 = imp_mod.permutation_split_result(
        model, X_test, y_test, ["f0", "f1", "f2"], "log_loss",
        "lower_is_better", seed=9, split_index=0, repeats=5, split_id="s")
    assert r1 == r2  # deterministic seeds
    assert r1["features"]["f0"]["rank"] == 1.0  # driver dominates
    assert r1["features"]["f0"]["mean_importance"] > 0
    assert r1["features"]["f0"]["valid_repeats"] == 5
    r3 = imp_mod.permutation_split_result(
        model, X_test, y_test, ["f0", "f1", "f2"], "log_loss",
        "lower_is_better", seed=10, split_index=0, repeats=5, split_id="s")
    assert r3 != r1  # seed changes permutations


def test_permutation_changes_one_feature_only():
    model, X_test, y_test = _fitted_split()
    before = X_test.copy()
    y_before = y_test.copy()
    imp_mod.permutation_split_result(
        model, X_test, y_test, ["f0", "f1", "f2"], "brier",
        "lower_is_better", seed=1, split_index=0, repeats=3, split_id="s")
    assert np.array_equal(X_test, before)  # inputs untouched (copies permuted)
    assert np.array_equal(y_test, y_before)  # target never permuted


def test_negative_importance_recorded_honestly():
    model, X_test, y_test = _fitted_split()
    record = imp_mod.permutation_split_result(
        model, X_test, y_test, ["f0", "f1", "f2"], "log_loss",
        "lower_is_better", seed=9, split_index=0, repeats=8, split_id="s")
    noise = [record["features"][n] for n in ("f1", "f2")]
    assert any(f["negative_repeats"] > 0 for f in noise)
    assert all(f["min_importance"] is not None for f in noise)


def test_rank_aggregation_and_tied_ranks():
    assert imp_mod._rank_desc([1.0, 1.0, 0.0]) == [1.5, 1.5, 3.0]
    assert imp_mod._rank_desc([None, 2.0, 1.0]) == [None, 1.0, 2.0]

    def rec(idx, values):
        feats = {}
        for name, v in values.items():
            feats[name] = dict(imp_mod._feature_stats([v], 1), rank=None)
        rec_ = {"split_id": f"sp{idx}", "split_index": idx, "status": "valid",
                "baseline_score": 0.5, "evaluated_count": 10,
                "features": feats, "warning": None}
        imp_mod._assign_split_ranks(feats, list(values))
        return rec_

    records = [rec(0, {"a": 0.5, "b": 0.1}), rec(1, {"a": 0.4, "b": 0.2}),
               rec(2, {"a": 0.6, "b": 0.0}), rec(3, {"a": 0.3, "b": 0.05})]
    agg = imp_mod.aggregate_features(records, ["a", "b"])
    a = next(e for e in agg if e["feature_name"] == "a")
    assert a["rank"] == 1.0 and a["mean_rank"] == 1.0
    assert a["mean_importance"] == pytest.approx(0.45)
    assert a["positive_split_fraction"] == 1.0
    assert a["quantile_interval"] is not None  # 4 valid splits
    short = imp_mod.aggregate_features(records[:2], ["a", "b"])
    assert short[0]["quantile_interval"] is None  # never fabricated from < 4


# ---------------------------------------------------------------------------
# Stability (§8)
# ---------------------------------------------------------------------------


def _stab_records(vectors):
    records = []
    for idx, values in enumerate(vectors):
        feats = {n: dict(imp_mod._feature_stats([v], 1)) for n, v in values.items()}
        imp_mod._assign_split_ranks(feats, list(values))
        records.append({"split_id": f"sp{idx}", "split_index": idx,
                        "status": "valid", "baseline_score": 0.5,
                        "evaluated_count": 10, "features": feats, "warning": None})
    return records


def test_stability_summary_spearman_kendall_topk():
    names = ["a", "b", "c"]
    same = _stab_records([{"a": 3.0, "b": 2.0, "c": 1.0}] * 3)
    s = stab_mod.stability_summary(same, names)
    assert s["mean_spearman"] == pytest.approx(1.0)
    assert s["mean_kendall"] == pytest.approx(1.0)
    assert s["mean_top_k_overlap"] == pytest.approx(1.0)
    flipped = _stab_records([{"a": 3.0, "b": 2.0, "c": 1.0},
                             {"a": 1.0, "b": 2.0, "c": 3.0}])
    s2 = stab_mod.stability_summary(flipped, names)
    assert s2["mean_spearman"] == pytest.approx(-1.0)
    constant = _stab_records([{"a": 1.0, "b": 1.0, "c": 1.0}] * 2)
    s3 = stab_mod.stability_summary(constant, names)
    assert s3["pairs"][0]["spearman"] is None  # undefined, not NaN
    one = stab_mod.stability_summary(_stab_records([{"a": 1.0}]), ["a"])
    assert one["pairs"] == [] and one["mean_spearman"] is None


def test_stability_score_and_classification():
    assert stab_mod.stability_score(0.0, 5, 3) == 1.0
    assert stab_mod.classify_stability(1.0) == "stable"
    assert stab_mod.classify_stability(0.6) == "moderately_stable"
    assert stab_mod.classify_stability(0.2) == "unstable"
    assert stab_mod.stability_score(0.5, 5, 1) is None  # < 2 splits
    assert stab_mod.stability_score(0.5, 1, 3) is None  # single feature
    assert stab_mod.classify_stability(None) == "unknown"


def test_sign_consistency():
    agg = [{"feature_name": "a", "rank_std": 0.0, "valid_split_count": 4,
            "positive_split_fraction": 0.75, "negative_split_fraction": 0.25}]
    stab_mod.apply_stability(agg, 3)
    assert agg[0]["sign_consistency"] == 0.75
    assert agg[0]["sign_changed_across_splits"] is True


# ---------------------------------------------------------------------------
# Correlation diagnostics (§9)
# ---------------------------------------------------------------------------


def test_correlation_groups_and_signs():
    base = np.array([((i * 7) % 13 - 6) / 6.0 for i in range(60)])
    X = np.column_stack([base, base * 0.95 + 0.01, -base + 0.02,
                         np.array([((i * 11) % 17 - 8) / 8.0 for i in range(60)])])
    names = ["a", "a_copy", "a_neg", "other"]
    diag = corr_mod.correlation_diagnostics(X, names, "pearson", 0.9,
                                            {"a": 0.5, "a_copy": 0.3, "a_neg": 0.1,
                                             "other": 0.2})
    assert len(diag["groups"]) == 1
    group = diag["groups"][0]
    assert set(group["features"]) == {"a", "a_copy", "a_neg"}
    assert group["combined_mean_importance"] == pytest.approx(0.9)
    signs = {(p["feature_a"], p["feature_b"]): p["sign"] for p in diag["pairs"]}
    assert signs[("a", "a_copy")] == 1 and signs[("a", "a_neg")] == -1
    diag2 = corr_mod.correlation_diagnostics(X, names, "spearman", 0.9, None)
    assert len(diag2["groups"]) == 1  # spearman path agrees here


def test_correlation_constant_feature_and_threshold_validation():
    X = np.column_stack([np.ones(30), np.arange(30.0)])
    diag = corr_mod.correlation_diagnostics(X, ["const", "ramp"], "pearson", 0.8, None)
    assert diag["constant_features"] == ["const"]
    assert diag["constant_feature_warning"]
    assert diag["pairs"] == []
    with pytest.raises(corr_mod.CorrelationError):
        corr_mod.validate_correlation_config({"threshold": 1.5})
    with pytest.raises(corr_mod.CorrelationError):
        corr_mod.validate_correlation_config({"method": "kendall-b"})


# ---------------------------------------------------------------------------
# Drift (§10, §11)
# ---------------------------------------------------------------------------


def test_distribution_drift_psi_ks():
    ref = np.array([((i * 13) % 97) / 97.0 for i in range(200)])
    same = np.array([((i * 29) % 97) / 97.0 for i in range(200)])
    shifted = ref + 2.0
    th = drift_mod.DEFAULT_PSI_THRESHOLDS
    none_row = drift_mod.numeric_distribution_drift(ref, same, 10, th)
    assert none_row["classification"] in ("none", "low")
    assert none_row["small_sample_warning"] is None
    high_row = drift_mod.numeric_distribution_drift(ref, shifted, 10, th)
    assert high_row["classification"] == "high"
    assert high_row["mean_difference"] == pytest.approx(2.0)
    assert high_row["out_of_range_fraction"] == 1.0
    assert high_row["ks_statistic"] == pytest.approx(1.0)
    const = drift_mod.numeric_distribution_drift(np.ones(50), np.ones(50), 10, th)
    assert const["psi"] is None and const["classification"] == "unknown"
    small = drift_mod.numeric_distribution_drift(ref[:10], same[:10], 10, th)
    assert small["small_sample_warning"]
    empty = drift_mod.numeric_distribution_drift(np.array([]), ref, 10, th)
    assert empty["status"] == "unavailable" and empty["classification"] == "unknown"


def test_drift_config_validation():
    cfg = drift_mod.validate_drift_config({"psi_bins": 8})
    assert cfg["psi_bins"] == 8 and cfg["mode"] == "early_vs_late"
    with pytest.raises(drift_mod.DriftError):
        drift_mod.validate_drift_config({"psi_bins": 2})
    with pytest.raises(drift_mod.DriftError):
        drift_mod.validate_drift_config({"mode": "future_vs_past"})
    with pytest.raises(drift_mod.DriftError):  # low < moderate < high violated
        drift_mod.validate_drift_config({"psi_thresholds": {"low": 0.5, "moderate": 0.2}})


def test_importance_drift_classification():
    records = _stab_records([{"a": 1.0, "b": 0.2}, {"a": 1.0, "b": 0.2},
                             {"a": 0.1, "b": 0.2}, {"a": 0.1, "b": 0.2}])
    result = drift_mod.importance_drift(records, ["a", "b"])
    a = next(f for f in result["features"] if f["feature_name"] == "a")
    assert a["direction"] == "decreased" and a["classification"] == "high"
    b = next(f for f in result["features"] if f["feature_name"] == "b")
    assert b["classification"] == "none"
    short = drift_mod.importance_drift(records[:1], ["a", "b"])
    assert short["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Fingerprints (§13)
# ---------------------------------------------------------------------------


def test_fingerprint_sensitivity():
    kwargs = dict(
        method="permutation", model_type="logistic_regression",
        hyperparameters={"l2": 0.01}, target_type="binary_classification",
        metric="log_loss", metric_direction="lower_is_better",
        feature_names=["a", "b"],
        samples=[{"sample_id": "s1", "timestamp": "2025-01-01T00:00:00",
                  "features": {"a": 1.0, "b": 2.0}, "target": 1.0}],
        split_source="none", validation_run_fp=None, declared_splits=None,
        permutation_repeats=5, seed=7,
        correlation_config={"method": "pearson", "threshold": 0.8},
        drift_config={"mode": "early_vs_late", "psi_bins": 10},
        missing_value_policy="reject", encoding_policy="numeric only",
    )
    fp1 = fp_mod.configuration_fingerprint(**kwargs)
    assert fp1 == fp_mod.configuration_fingerprint(**kwargs)
    assert fp1 != fp_mod.configuration_fingerprint(**{**kwargs, "seed": 8})
    assert fp1 != fp_mod.configuration_fingerprint(**{**kwargs, "metric": "brier"})
    assert fp1 != fp_mod.configuration_fingerprint(
        **{**kwargs, "feature_names": ["b", "a"]})  # order matters

    result_kwargs = dict(
        configuration_fp=fp1,
        split_results=[{"split_id": "s", "status": "valid", "baseline_score": 0.4,
                        "features": {"a": {"mean_importance": 0.2}}}],
        aggregates=[{"feature_name": "a", "mean_importance": 0.2}],
        stability={"mean_spearman": 1.0}, correlation={"groups": []},
        distribution_drift=[], importance_drift={"status": "ok"},
        warnings=[], integrity_status="not_held_out",
    )
    r1 = fp_mod.result_fingerprint(**result_kwargs)
    changed = dict(result_kwargs,
                   aggregates=[{"feature_name": "a", "mean_importance": 0.3}])
    assert r1 != fp_mod.result_fingerprint(**changed)
    b1 = fp_mod.baseline_fingerprint(result_fp=r1, scope={"metric": "log_loss"})
    assert b1 != fp_mod.baseline_fingerprint(result_fp=r1, scope={"metric": "brier"})


# ---------------------------------------------------------------------------
# Service: integrity via Model Validation (§12)
# ---------------------------------------------------------------------------


def _clean_validation_run(mv_service, n=60):
    """A leakage-clean purged run over short-horizon samples s000..s0NN."""
    from datetime import datetime, timedelta
    base = datetime(2025, 1, 1)
    samples = [{"sample_id": f"s{i:03d}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 2)).isoformat()}
               for i in range(n)]
    vrun = mv_service.create_run({"name": "v", "method": "purged_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is True
    return vrun


def test_verified_held_out_via_validation_run(client):
    from app.model_validation import service as mv_service
    vrun = _clean_validation_run(mv_service)
    run = client.post(f"{BASE}/runs", json=_payload(validation_run_id=vrun["id"])).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["integrity_status"] == "verified_held_out"
    assert done["valid_split_count"] >= 3
    # split fingerprints preserved from the validation run
    assert all(s["split_fingerprint"] for s in done["splits"])
    splits = client.get(f"{BASE}/runs/{run['id']}/splits").json()
    assert splits["items"] and all(r["baseline_score"] is not None
                                   for r in splits["items"])
    # driver ranks first in aggregate
    feats = client.get(f"{BASE}/runs/{run['id']}/features").json()["items"]
    assert feats[0]["feature_name"] == "f0" and feats[0]["rank"] == 1.0


def test_leaky_validation_run_fails_honestly(client):
    from datetime import datetime, timedelta
    from app.model_validation import service as mv_service
    base = datetime(2025, 1, 1)
    samples = [{"sample_id": f"s{i:03d}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 5)).isoformat()}
               for i in range(60)]
    vrun = mv_service.create_run({"name": "leaky", "method": "standard_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is False
    run = client.post(f"{BASE}/runs", json=_payload(validation_run_id=vrun["id"])).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "leakage-clean" in done["error_message"]


def test_membership_mismatch_fails_honestly(client):
    from app.model_validation import service as mv_service
    vrun = _clean_validation_run(mv_service)
    samples = [dict(s, sample_id=f"other-{i:03d}")
               for i, s in enumerate(_samples())]
    run = client.post(f"{BASE}/runs", json=_payload(
        samples=samples, validation_run_id=vrun["id"])).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "not members" in done["error_message"]


def test_declared_splits_and_not_held_out(client):
    ids = [f"s{i:03d}" for i in range(60)]
    declared = [
        {"split_id": "d1", "train_sample_ids": ids[:40], "test_sample_ids": ids[40:]},
        {"split_id": "d2", "train_sample_ids": ids[20:], "test_sample_ids": ids[:20]},
    ]
    run = client.post(f"{BASE}/runs", json=_payload(declared_splits=declared)).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["integrity_status"] == "declared_held_out"  # declared stays declared
    # no splits at all → not_held_out, disclosed
    run2 = client.post(f"{BASE}/runs", json=_payload()).json()
    done2 = client.post(f"{BASE}/runs/{run2['id']}/execute", json={}).json()
    assert done2["integrity_status"] == "not_held_out"
    assert any("NOT held-out" in w for w in done2["warnings"])
    # overlap rejected at creation
    bad = [{"split_id": "x", "train_sample_ids": ids[:40],
            "test_sample_ids": ids[30:]}]
    assert client.post(f"{BASE}/runs",
                       json=_payload(declared_splits=bad)).status_code == 422


def test_native_and_coefficient_references(client):
    run = client.post(f"{BASE}/runs", json=_payload(
        method="native_impurity", model_type="decision_tree")).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["integrity_status"] == "not_held_out"  # training-data derived
    native = done["references"]["native_impurity"]
    assert native["caveats"] and native["rows"][0]["feature_name"] == "f0"
    assert any("not causal" in c for c in native["caveats"])

    run2 = client.post(f"{BASE}/runs", json=_payload(method="coefficient")).json()
    done2 = client.post(f"{BASE}/runs/{run2['id']}/execute", json={}).json()
    coef = done2["references"]["coefficients"]
    assert coef["rows"][0]["standardized"] is True
    assert {"mean_coefficient", "mean_abs_coefficient", "sign"} <= set(coef["rows"][0])
    assert any("scale-dependent" in c for c in coef["caveats"])


# ---------------------------------------------------------------------------
# API validation + adversarial paths (§17, §26)
# ---------------------------------------------------------------------------


def test_method_model_metric_compat(client):
    assert client.post(f"{BASE}/runs", json=_payload(
        method="native_impurity")).status_code == 422  # logistic has no impurity
    assert client.post(f"{BASE}/runs", json=_payload(
        method="coefficient", model_type="decision_tree")).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        metric="mae")).status_code == 422  # regression metric, classification target
    assert client.post(f"{BASE}/runs", json=_payload(
        metric="sharpe")).status_code == 422  # unsupported metric
    assert client.post(f"{BASE}/runs", json=_payload(
        model_type="linear_regression")).status_code == 422  # task mismatch


def test_adversarial_api_paths(client):
    assert client.post(f"{BASE}/runs", json=_payload(
        permutation_repeats=999)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(seed=-1)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        correlation={"threshold": 5.0})).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        drift={"psi_bins": 1000})).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        hyperparameters={"max_depth": 99}, model_type="decision_tree",
        method="native_impurity")).status_code == 422
    # duplicate feature names via API
    assert client.post(f"{BASE}/runs", json=_payload(
        features=[{"feature_name": "f0"}] * 3)).status_code == 422
    # raw NaN token → sanitized 422, no crash
    raw = json.dumps(_payload()).replace('"target": 1', '"target": NaN', 1)
    resp = client.post(f"{BASE}/runs", content=raw,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 422
    assert client.get(f"{BASE}/runs/99999").status_code == 404
    assert client.get(f"{BASE}/compare", params={"a": 1, "b": 1}).status_code == 422
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    client.post(f"{BASE}/runs/{run['id']}/invalidate", json={"reason": "test"})
    assert client.post(f"{BASE}/runs/{run['id']}/execute",
                       json={}).status_code == 409
    assert client.post(f"{BASE}/runs/{run['id']}/invalidate",
                       json={"reason": "again"}).status_code == 409


def test_target_leakage_via_api(client):
    samples = _samples()
    for s in samples:
        s["features"]["f1"] = float(s["target"])  # identical to target
    assert client.post(f"{BASE}/runs", json=_payload(samples=samples)).status_code == 422


# ---------------------------------------------------------------------------
# Baseline policy (§15)
# ---------------------------------------------------------------------------


def _declared_run(client, name="a", seed=5):
    ids = [f"s{i:03d}" for i in range(60)]
    declared = [
        {"split_id": "d1", "train_sample_ids": ids[:40], "test_sample_ids": ids[40:]},
        {"split_id": "d2", "train_sample_ids": ids[20:], "test_sample_ids": ids[:20]},
    ]
    run = client.post(f"{BASE}/runs", json=_payload(
        name=name, seed=seed, declared_splits=declared)).json()
    return client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()


def test_baseline_scope_and_transitions(client):
    a = _declared_run(client, "a", seed=5)
    b = _declared_run(client, "b", seed=6)  # same scope (method/metric/model/links)
    marked = client.post(f"{BASE}/runs/{a['id']}/mark-baseline", json={})
    assert marked.status_code == 200 and marked.json()["is_baseline"]
    assert marked.json()["baseline_fingerprint"]
    # marking B transactionally unmarks A (same scope)
    client.post(f"{BASE}/runs/{b['id']}/mark-baseline", json={})
    assert client.get(f"{BASE}/runs/{a['id']}").json()["is_baseline"] is False
    assert client.get(f"{BASE}/runs/{b['id']}").json()["is_baseline"] is True
    # idempotent re-mark
    again = client.post(f"{BASE}/runs/{b['id']}/mark-baseline", json={})
    assert again.status_code == 200 and again.json()["is_baseline"]
    # different scope (different metric) untouched
    c_run = client.post(f"{BASE}/runs", json=_payload(
        name="c", metric="brier",
        declared_splits=[{"split_id": "d1",
                          "train_sample_ids": [f"s{i:03d}" for i in range(40)],
                          "test_sample_ids": [f"s{i:03d}" for i in range(40, 60)]}])).json()
    c = client.post(f"{BASE}/runs/{c_run['id']}/execute", json={}).json()
    client.post(f"{BASE}/runs/{c['id']}/mark-baseline", json={})
    assert client.get(f"{BASE}/runs/{b['id']}").json()["is_baseline"] is True


def test_baseline_rejections(client):
    # not held-out → 409
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["integrity_status"] == "not_held_out"
    resp = client.post(f"{BASE}/runs/{done['id']}/mark-baseline", json={})
    assert resp.status_code == 409 and "held-out" in resp.json()["detail"]
    # pending (never executed) → 409
    pending = client.post(f"{BASE}/runs", json=_payload(name="p", seed=9)).json()
    assert client.post(f"{BASE}/runs/{pending['id']}/mark-baseline",
                       json={}).status_code == 409
    # invalidation clears the baseline flag
    a = _declared_run(client, "inv", seed=7)
    client.post(f"{BASE}/runs/{a['id']}/mark-baseline", json={})
    inv = client.post(f"{BASE}/runs/{a['id']}/invalidate",
                      json={"reason": "stale"}).json()
    assert inv["is_baseline"] is False


# ---------------------------------------------------------------------------
# Persistence, migration, registries preserved (§14)
# ---------------------------------------------------------------------------


def test_migration_idempotent_and_preserves_rows(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    db_module.init_db()  # re-running migrations never drops data
    assert client.get(f"{BASE}/runs/{run['id']}").status_code == 200
    # existing registries still intact
    assert client.get("/experiment-registry/summary").status_code == 200
    assert client.get("/model-validation/summary").status_code == 200
    assert client.get("/meta-labeling/summary").status_code == 200


def test_persistence_roundtrip(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    fetched = client.get(f"{BASE}/runs/{run['id']}").json()
    assert fetched["result_fingerprint"] == done["result_fingerprint"]
    assert fetched["configuration"]["missing_value_policy"].startswith("reject")
    feats = client.get(f"{BASE}/runs/{run['id']}/features").json()["items"]
    assert len(feats) == 3
    corr = client.get(f"{BASE}/runs/{run['id']}/correlations").json()
    assert "groups" in corr
    dr = client.get(f"{BASE}/runs/{run['id']}/drift").json()
    assert dr["context"]["mode"] == "early_vs_late"
    assert all(d["classification"] in ("none", "low", "moderate", "high", "unknown")
               for d in dr["items"])


# ---------------------------------------------------------------------------
# Integrations (§16)
# ---------------------------------------------------------------------------


def test_experiment_integration_idempotent(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute",
                       json={"create_experiment": True}).json()
    assert done["experiment_id"] is not None
    resp = client.get(f"/experiment-registry/experiments/{done['experiment_id']}")
    assert resp.status_code == 200
    exp = resp.json()
    assert exp["module"] == "feature_diagnostics"
    assert "top_features" in exp["parameters"]
    again = client.post(f"{BASE}/runs/{run['id']}/execute",
                        json={"create_experiment": True}).json()
    assert again["experiment_id"] == done["experiment_id"]  # no duplicate


def test_meta_labeling_link(client):
    assert client.post(f"{BASE}/runs", json=_payload(
        meta_label_run_id=99999)).status_code == 404
    from app.meta_labeling.demo import seed_demo_meta_labeling
    from app.meta_labeling.store import run_demo_key_id
    seed_demo_meta_labeling()
    mid = run_demo_key_id("demo:ml:verified-oof")
    run = client.post(f"{BASE}/runs", json=_payload(meta_label_run_id=mid)).json()
    assert run["meta_label_run_id"] == mid
    full = client.get(f"{BASE}/runs/{run['id']}").json()
    assert full["meta_label_oof_status"] == "verified_from_validation_run"
    assert full["meta_label_calibration_method"] == "sigmoid"


def test_dataset_schema_warning_not_fabricated(client):
    from app.dataset_registry.demo import seed_demo_lineage
    from app.dataset_registry.store import version_demo_key_id
    seed_demo_lineage()
    vid = version_demo_key_id("demo:dsv:kopep-features:v1")
    features = [{"feature_name": "f0", "source_column": "zscore"},
                {"feature_name": "f1", "source_column": "not_a_column"},
                {"feature_name": "f2"}]
    run = client.post(f"{BASE}/runs", json=_payload(
        features=features, dataset_version_id=vid)).json()
    warnings = run["configuration"]["schema_warnings"]
    assert len(warnings) == 1 and "not_a_column" in warnings[0]
    assert run["dataset_name"]  # lineage hydrated


# ---------------------------------------------------------------------------
# Comparison, export, demo (§23, §25, §24)
# ---------------------------------------------------------------------------


def test_compare_neutral(client):
    a = _declared_run(client, "a", seed=5)
    b = _declared_run(client, "b", seed=6)
    cmp_ = client.get(f"{BASE}/compare", params={"a": a["id"], "b": b["id"]}).json()
    kinds = {e["kind"] for g in cmp_["groups"].values() for e in g}
    assert kinds <= {"same", "changed", "only_in_a", "only_in_b", "unavailable"}
    assert cmp_["features"][0]["availability"] == "both"
    assert "rank_change" in cmp_["features"][0]
    blob = json.dumps(cmp_).lower()
    for banned in ("winner", "better run", "recommended", "best "):
        assert banned not in blob


def test_export_privacy_and_schema(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    export = client.get(f"{BASE}/export").json()
    assert export["schema_version"] == "feature_diagnostics_export_v1"
    blob = json.dumps(export)
    for banned in ("C:\\\\", "/Users/", "/home/", "api_key", "API_KEY", "secret",
                   "password", "pickle", "joblib"):
        assert banned not in blob
    assert "NaN" not in blob and "Infinity" not in blob
    # raw samples excluded by design
    assert "sample_id" not in json.dumps(export["runs"])
    assert "results" in export and str(run["id"]) in export["results"]


def test_demo_seed_idempotent_and_expected_shapes(client):
    first = client.post(f"{BASE}/demo-seed", json={}).json()
    assert first["created_runs"] == 4
    second = client.post(f"{BASE}/demo-seed", json={}).json()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 4

    runs = client.get(f"{BASE}/runs", params={"page_size": 50}).json()["items"]
    by_name = {r["name"]: r for r in runs}
    flagship = next(r for r in runs if "Held-out permutation" in r["name"])
    assert flagship["status"] == "completed"
    assert flagship["integrity_status"] == "verified_held_out"
    assert flagship["is_baseline"] is True
    assert flagship["top_feature"] == "mom_signal"
    corr = client.get(f"{BASE}/runs/{flagship['id']}/correlations").json()
    assert any(set(g["features"]) == {"corr_pair_a", "corr_pair_b"}
               for g in corr["groups"])
    dr = client.get(f"{BASE}/runs/{flagship['id']}/drift").json()
    drift_class = {d["feature_name"]: d["classification"]
                   for d in dr["items"] if d["kind"] == "distribution"}
    assert drift_class["drift_feature"] == "high"

    imp_drift_run = next(r for r in runs if "Importance drift" in r["name"])
    dr2 = client.get(f"{BASE}/runs/{imp_drift_run['id']}/drift").json()
    dist = {d["feature_name"]: d["classification"]
            for d in dr2["items"] if d["kind"] == "distribution"}
    imp = {d["feature_name"]: d["classification"]
           for d in dr2["items"] if d["kind"] == "importance"}
    assert dist["fade_signal"] == "none" and imp["fade_signal"] == "high"

    failed = next(r for r in runs if "Leakage-failed" in r["name"])
    assert failed["status"] == "failed" and failed["error_message"]
    assert by_name  # sanity

    summary = client.get(f"{BASE}/summary").json()
    assert summary["runs"] == 4 and summary["baselines"] == 1
    assert summary["held_out_verified"] == 1


# ---------------------------------------------------------------------------
# Phase 52 review fixes (regression)
# ---------------------------------------------------------------------------


def test_pr_auc_tie_grouping_is_row_order_invariant():
    """Average precision must depend only on the (label, score) multiset."""
    y = np.array([1.0, 0.0, 1.0, 0.0])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    # A fully uninformative constant predictor scores its base rate, not more.
    assert metrics_mod.score("pr_auc", y, p) == pytest.approx(0.5)
    # Reordering identical (label, score) rows must not change the metric.
    y2 = np.array([0.0, 1.0, 0.0, 1.0])
    p2 = np.array([0.5, 0.5, 0.5, 0.5])
    assert metrics_mod.score("pr_auc", y2, p2) == pytest.approx(
        metrics_mod.score("pr_auc", y, p)
    )
    # A perfect ranking still scores 1.0 (tie grouping did not break the normal case).
    assert metrics_mod.score(
        "pr_auc", np.array([1.0, 1.0, 0.0, 0.0]), np.array([0.9, 0.8, 0.7, 0.6])
    ) == pytest.approx(1.0)


def test_sample_timestamps_are_canonical_and_text_sortable():
    """Persisted timestamps must sort lexicographically in chronological order.

    Samples are read back with an ``ORDER BY timestamp`` TEXT sort, so the
    stored string must be canonical — otherwise the read-back order diverges
    from the order the configuration fingerprint was computed over, and the
    early-vs-late drift partition is split at the wrong point.
    """
    from datetime import datetime, timedelta, timezone

    base = datetime(2024, 1, 5, tzinfo=timezone.utc)
    raw = []
    for i in range(20):
        instant = base + timedelta(hours=i)
        # Alternate the WRITTEN offset; the instants stay strictly increasing.
        shown = (instant.astimezone(timezone(timedelta(hours=-5))).isoformat()
                 if i % 2 else instant.isoformat())
        raw.append({"sample_id": f"s{i:03d}", "timestamp": shown,
                    "features": {"f0": float(i)}, "target": float(i % 2)})

    # Precondition: as written, the raw strings do NOT sort chronologically —
    # this is exactly the input that used to corrupt the read-back ordering.
    raw_ts = [r["timestamp"] for r in raw]
    assert raw_ts != sorted(raw_ts)

    out = core.normalize_samples(raw, ["f0"], "binary_classification")
    ts = [s["timestamp"] for s in out]
    assert ts == sorted(ts), "canonical timestamps must be lexicographically ordered"
    assert all(t.endswith("+00:00") for t in ts)
    # Chronological order is preserved through canonicalization.
    assert [s["sample_id"] for s in out] == [f"s{i:03d}" for i in range(20)]


def test_ks_statistic_defined_for_two_different_constants():
    """Two different constants are maximal drift, not an unavailable statistic."""
    ref = np.zeros(40)
    cmp_ = np.ones(40)
    row = drift_mod.numeric_distribution_drift(
        ref, cmp_, 10, {"moderate": 0.1, "major": 0.25})
    assert row["ks_statistic"] == pytest.approx(1.0)
    assert row["ks_pvalue"] is not None
    # Two EQUAL constants are zero drift, also defined.
    same = drift_mod.numeric_distribution_drift(
        np.zeros(40), np.zeros(40), 10, {"moderate": 0.1, "major": 0.25})
    assert same["ks_statistic"] == pytest.approx(0.0)


def test_stability_note_explains_constant_importance_vector():
    """An undefined rank correlation must carry its reason, not a bare null."""
    # Both splits share >= 2 features, but split B's importances are constant,
    # so Spearman/Kendall are undefined for reasons other than "too few shared".
    records = _stab_records([
        {"f0": 0.30, "f1": 0.20, "f2": 0.10},
        {"f0": 0.10, "f1": 0.10, "f2": 0.10},
    ])
    summary = stab_mod.stability_summary(records, ["f0", "f1", "f2"])
    pair = summary["pairs"][0]
    assert pair["spearman"] is None and pair["kendall"] is None
    assert pair["note"] and "constant" in pair["note"]


def test_failed_reexecution_clears_stale_baseline_and_results(client, monkeypatch):
    """A failed re-execution must not leave an active baseline + stale rows."""
    created = client.post(f"{BASE}/runs", json=_payload(
        name="stale-baseline",
        declared_splits=[{"split_id": "d1",
                          "train_sample_ids": [f"s{i:03d}" for i in range(40)],
                          "test_sample_ids": [f"s{i:03d}" for i in range(40, 60)]}])).json()
    done = client.post(f"{BASE}/runs/{created['id']}/execute", json={}).json()
    assert done["status"] == "completed" and done["result_fingerprint"]
    marked = client.post(f"{BASE}/runs/{done['id']}/mark-baseline", json={}).json()
    assert marked["is_baseline"] is True
    assert client.get(f"{BASE}/runs/{done['id']}/features").json()["items"]

    def _boom(*_a, **_k):
        raise corr_mod.CorrelationError("forced failure for regression test")

    monkeypatch.setattr(service.corr_mod, "correlation_diagnostics", _boom)
    failed = client.post(f"{BASE}/runs/{done['id']}/execute", json={}).json()

    assert failed["status"] == "failed"
    assert failed["integrity_status"] == "unknown"
    # The dangerous part: a failed / unknown-integrity run must not remain the
    # active baseline, nor keep a result fingerprint or stale per-feature rows.
    assert failed["is_baseline"] is False
    assert failed["result_fingerprint"] is None
    assert failed["baseline_fingerprint"] is None
    assert client.get(f"{BASE}/runs/{done['id']}/features").json()["items"] == []


def test_constant_vectors_never_reach_scipy_and_carry_precise_notes():
    """Constant importance vectors must be detected BEFORE scipy is called.

    A dispersion guard (``np.std(v) == 0.0``) is unreliable for values that are
    not exactly representable in binary floating point: ``np.std([0.1]*3)`` is
    1.39e-17, so such a vector used to reach scipy, emit ConstantInputWarning
    and return NaN (silently rescued by the isfinite fallback).

    ConstantInputWarning is escalated to an error *inside this test only* —
    no global warning filter is added anywhere.
    """
    import warnings

    from scipy.stats import ConstantInputWarning

    def pair_for(vec_a, vec_b):
        names = sorted(set(vec_a) | set(vec_b))
        recs = _stab_records([vec_a, vec_b])
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConstantInputWarning)
            return stab_mod.stability_summary(recs, names)["pairs"][0]

    varying = {"f0": 0.30, "f1": 0.20, "f2": 0.10}
    # 0.1 is NOT exactly representable — precisely the case that used to warn.
    constant = {"f0": 0.10, "f1": 0.10, "f2": 0.10}

    # (a) split B constant
    p = pair_for(varying, constant)
    assert p["spearman"] is None and p["kendall"] is None
    assert "constant" in p["note"] and "split B" in p["note"]

    # (b) split A constant
    p = pair_for(constant, varying)
    assert p["spearman"] is None and p["kendall"] is None
    assert "constant" in p["note"] and "split A" in p["note"]

    # (c) both constant (at different levels)
    p = pair_for(constant, {"f0": 0.7, "f1": 0.7, "f2": 0.7})
    assert p["spearman"] is None and p["kendall"] is None
    assert "both" in p["note"] and "constant" in p["note"]

    # (d) fewer than two paired observations
    p = pair_for({"f0": 0.5}, {"f0": 0.9})
    assert p["spearman"] is None and p["kendall"] is None
    assert "fewer than 2" in p["note"]

    # (e) normal non-constant vectors stay DEFINED (perfectly reversed = -1)
    p = pair_for(varying, {"f0": 0.05, "f1": 0.25, "f2": 0.45})
    assert p["spearman"] == pytest.approx(-1.0)
    assert p["note"] is None

    # (f) tied but NOT constant is still defined (scipy average-tie handling)
    p = pair_for({"f0": 0.1, "f1": 0.1, "f2": 0.4},
                 {"f0": 0.2, "f1": 0.5, "f2": 0.5})
    assert p["spearman"] is not None and math.isfinite(p["spearman"])
    assert p["note"] is None

    # An undefined correlation is never reported as zero ("no association").
    for a_vec, b_vec in ((varying, constant), (constant, varying)):
        p = pair_for(a_vec, b_vec)
        assert p["spearman"] is not p and p["spearman"] != 0.0
        assert p["kendall"] != 0.0

    # No NaN/Infinity may reach persistence, export, or the frontend.
    full = stab_mod.stability_summary(
        _stab_records([varying, constant]), ["f0", "f1", "f2"])
    json.dumps(full, allow_nan=False)  # raises if any NaN/Infinity leaked
