"""
Service layer: run lifecycle, held-out execution via Model Validation split
memberships, aggregation, stability, correlation, drift, baselines,
comparison, and export.

Held-out integrity statuses (documented):

* ``verified_held_out`` — the model is fitted per split on the linked,
  completed, leakage-clean Model Validation run's recorded train memberships
  and importance is evaluated only on that split's held-out test members;
* ``declared_held_out`` — the caller supplied explicit train/test splits;
  they are validated structurally but the declaration is NOT independently
  verified;
* ``not_held_out`` — no splits: the model is fitted and evaluated on all
  samples (disclosed with a warning), and model-native / coefficient methods
  are always training-data derived;
* ``unknown`` — not executed yet.

Nothing here selects a "best" feature, deletes features, retrains user
models, or produces recommendations.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.feature_diagnostics import EXPORT_SCHEMA_VERSION
from app.feature_diagnostics import correlation as corr_mod
from app.feature_diagnostics import drift as drift_mod
from app.feature_diagnostics import estimators
from app.feature_diagnostics import fingerprints as fp_mod
from app.feature_diagnostics import importance as imp_mod
from app.feature_diagnostics import metrics as metrics_mod
from app.feature_diagnostics import stability as stab_mod
from app.feature_diagnostics.core import (
    CATEGORICAL_POLICY, MIN_TRAIN_SIZE, MISSING_VALUE_POLICY, FeatureInputError,
    build_matrix, check_target_leakage, constant_features,
    normalize_feature_definitions, normalize_samples, validate_declared_splits,
)
from app.meta_labeling import store as meta_store
from app.model_validation import store as validation_store


class FeatureDiagnosticsError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


METHODS = ("permutation", "native_impurity", "coefficient")
SPLIT_SOURCES = ("validation_run", "declared", "none")
INTEGRITY_STATUSES = ("verified_held_out", "declared_held_out", "not_held_out", "unknown")

NATIVE_CAVEATS = [
    "model-native impurity importance may favor high-cardinality features",
    "correlated features may split importance between them",
    "native importance is not held-out performance degradation",
    "native importance is not causal",
]
COEFFICIENT_CAVEATS = [
    "coefficient magnitude is scale-dependent unless standardized",
    "correlation between features affects coefficient interpretation",
    "coefficient sign is not proof of causality",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.feature_diagnostics import store  # noqa: E402  (after error classes for clarity)


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def _validate_int(value: Any, name: str, lo: int, hi: int, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not (lo <= value <= hi):
        raise FeatureDiagnosticsError(f"{name} must be an integer in [{lo}, {hi}]")
    return value


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    try:
        feature_defs = normalize_feature_definitions(payload.get("features") or [])
        feature_names = [d["feature_name"] for d in feature_defs]
        target_type = payload.get("target_type", "binary_classification")
        samples = normalize_samples(payload.get("samples") or [], feature_names, target_type)
        X, y, _ids = build_matrix(samples, feature_names)
        check_target_leakage(X, y, feature_names)
    except FeatureInputError as exc:
        raise FeatureDiagnosticsError(str(exc))

    method = payload.get("method", "permutation")
    if method not in METHODS:
        raise FeatureDiagnosticsError(f"method must be one of {METHODS}")
    model_type = payload.get("model_type", "logistic_regression")
    if model_type not in estimators.MODEL_TYPES:
        raise FeatureDiagnosticsError(f"model_type must be one of {estimators.MODEL_TYPES}")
    if target_type not in estimators.MODEL_TASKS[model_type]:
        raise FeatureDiagnosticsError(
            f"{model_type} does not support target_type {target_type!r}"
        )
    if method == "native_impurity" and model_type not in estimators.NATIVE_IMPORTANCE_MODELS:
        raise FeatureDiagnosticsError(
            f"native_impurity requires a model that exposes native importance "
            f"({estimators.NATIVE_IMPORTANCE_MODELS})"
        )
    if method == "coefficient" and model_type not in estimators.COEFFICIENT_MODELS:
        raise FeatureDiagnosticsError(
            f"coefficient requires a linear model ({estimators.COEFFICIENT_MODELS})"
        )

    metric = payload.get("metric", "log_loss")
    if metric not in metrics_mod.METRICS:
        raise FeatureDiagnosticsError(
            f"metric must be one of {sorted(metrics_mod.METRICS)}"
        )
    if metrics_mod.METRICS[metric]["task"] != target_type:
        raise FeatureDiagnosticsError(
            f"metric {metric!r} is defined for "
            f"{metrics_mod.METRICS[metric]['task']}, not {target_type}"
        )
    direction = metrics_mod.metric_direction(metric)

    try:
        hyperparameters = estimators.validate_hyperparameters(
            model_type, payload.get("hyperparameters") or {})
        correlation_config = corr_mod.validate_correlation_config(
            payload.get("correlation"))
        drift_config = drift_mod.validate_drift_config(payload.get("drift"))
    except (estimators.EstimatorError, corr_mod.CorrelationError,
            drift_mod.DriftError) as exc:
        raise FeatureDiagnosticsError(str(exc))

    repeats = _validate_int(payload.get("permutation_repeats"), "permutation_repeats",
                            imp_mod.MIN_REPEATS, imp_mod.MAX_REPEATS,
                            imp_mod.DEFAULT_REPEATS)
    seed = _validate_int(payload.get("seed"), "seed", 0, imp_mod.MAX_SEED,
                         imp_mod.DEFAULT_SEED)

    validation_run_id = payload.get("validation_run_id")
    declared = payload.get("declared_splits")
    if validation_run_id is not None and declared:
        raise FeatureDiagnosticsError(
            "provide either validation_run_id or declared_splits, not both"
        )
    validation_run_fp = None
    declared_splits = None
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None:
            raise NotFoundError(f"validation run {validation_run_id} not found")
        validation_run_fp = vrun["configuration_fingerprint"]
        split_source = "validation_run"
    elif declared:
        try:
            declared_splits = validate_declared_splits(
                declared, [s["sample_id"] for s in samples])
        except FeatureInputError as exc:
            raise FeatureDiagnosticsError(str(exc))
        split_source = "declared"
    else:
        split_source = "none"

    if drift_config["mode"] == "first_vs_last_split" and split_source == "none":
        raise FeatureDiagnosticsError(
            "drift mode first_vs_last_split requires validation or declared splits"
        )

    dataset_version_id = payload.get("dataset_version_id")
    if dataset_version_id is not None and dataset_store.get_version(dataset_version_id) is None:
        raise NotFoundError(f"dataset version {dataset_version_id} not found")
    if payload.get("experiment_id") is not None:
        if experiment_store.get_experiment(payload["experiment_id"]) is None:
            raise NotFoundError(f"experiment {payload['experiment_id']} not found")
    meta_label_run_id = payload.get("meta_label_run_id")
    if meta_label_run_id is not None and meta_store.get_run(meta_label_run_id) is None:
        raise NotFoundError(f"meta-label run {meta_label_run_id} not found")

    schema_warnings = _dataset_schema_warnings(dataset_version_id, feature_defs)

    configuration = {
        "method": method,
        "model_type": model_type,
        "hyperparameters": hyperparameters,
        "target_type": target_type,
        "metric": metric,
        "metric_direction": direction,
        "importance_formula": (
            "importance = baseline_score - permuted_score"
            if direction == "higher_is_better"
            else "importance = permuted_score - baseline_score"
        ),
        "permutation_repeats": repeats,
        "seed": seed,
        "split_source": split_source,
        "declared_splits": declared_splits,
        "correlation": correlation_config,
        "drift": drift_config,
        "missing_value_policy": MISSING_VALUE_POLICY,
        "categorical_policy": CATEGORICAL_POLICY,
        "feature_definitions": feature_defs,
        "schema_warnings": schema_warnings,
    }
    config_fp = fp_mod.configuration_fingerprint(
        method=method, model_type=model_type, hyperparameters=hyperparameters,
        target_type=target_type, metric=metric, metric_direction=direction,
        feature_names=feature_names, samples=samples, split_source=split_source,
        validation_run_fp=validation_run_fp, declared_splits=declared_splits,
        permutation_repeats=repeats, seed=seed,
        correlation_config=correlation_config, drift_config=drift_config,
        missing_value_policy=MISSING_VALUE_POLICY,
        encoding_policy=CATEGORICAL_POLICY,
    )

    run = store.insert_run({
        "name": payload["name"],
        "description": payload.get("description", ""),
        "method": method, "model_type": model_type, "target_type": target_type,
        "metric": metric, "metric_direction": direction,
        "split_source": split_source,
        "integrity_status": "unknown",
        "validation_run_id": validation_run_id,
        "dataset_version_id": dataset_version_id,
        "experiment_id": payload.get("experiment_id"),
        "meta_label_run_id": meta_label_run_id,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "sample_count": len(samples), "feature_count": len(feature_names),
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""),
        "demo_key": demo_key,
    })
    store.replace_samples(run["id"], samples)
    return get_run(run["id"])


def _dataset_schema_warnings(
    dataset_version_id: Optional[int], feature_defs: List[Dict[str, Any]]
) -> List[str]:
    """Warn (never fabricate) when feature source columns miss the dataset schema."""
    if dataset_version_id is None:
        return []
    version = dataset_store.get_version(dataset_version_id)
    if not version:
        return []
    fields = (version.get("schema_snapshot") or {}).get("fields") or []
    columns = {c.get("name") for c in fields if isinstance(c, dict)}
    if not columns:
        return []
    warnings = []
    for d in feature_defs:
        source = d.get("source_column")
        if source and source not in columns:
            warnings.append(
                f"feature {d['feature_name']!r}: source_column {source!r} is not "
                "in the linked dataset version's schema"
            )
    return warnings


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"feature-diagnostics run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = run["validation_result_fp"] = None
    run["experiment_name"] = None
    run["meta_label_run_name"] = run["meta_label_oof_status"] = None
    run["meta_label_calibration_method"] = run["meta_label_result_fp"] = None
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version:
            dataset = dataset_store.get_dataset(version["dataset_id"])
            run["dataset_name"] = dataset["name"] if dataset else None
            run["dataset_version_label"] = version["version_label"]
            run["dataset_invalidated"] = bool(version.get("invalidated_at"))
            run["dataset_manifest_fingerprint"] = version["manifest_fingerprint"]
            run["dataset_provenance_status"] = dataset["provenance_status"] if dataset else None
            run["dataset_quality_status"] = version["quality_status"]
    if run.get("validation_run_id"):
        vrun = validation_store.get_run(run["validation_run_id"])
        if vrun:
            run["validation_method"] = vrun["method"]
            run["validation_leakage_clean"] = vrun.get("leakage_clean")
            run["validation_config_fp"] = vrun["configuration_fingerprint"]
            run["validation_result_fp"] = vrun.get("result_fingerprint")
    if run.get("experiment_id"):
        exp = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = exp["name"] if exp else None
    if run.get("meta_label_run_id"):
        mrun = meta_store.get_run(run["meta_label_run_id"])
        if mrun:
            run["meta_label_run_name"] = mrun["name"]
            run["meta_label_oof_status"] = mrun["oof_status"]
            run["meta_label_calibration_method"] = mrun["calibration_method"]
            run["meta_label_result_fp"] = mrun.get("result_fingerprint")
    results = store.list_results(run["id"])
    top = next((r for r in results if r["rank"] == 1.0), None)
    run["top_feature"] = top["feature_name"] if top else None
    run["top_feature_importance"] = top["mean_importance"] if top else None
    run["stable_feature_count"] = sum(
        1 for r in results if r["stability_classification"] == "stable")
    run["unstable_feature_count"] = sum(
        1 for r in results if r["stability_classification"] == "unstable")
    drift_rows = store.list_drift_results(run["id"], kind="distribution")
    run["drift_flag_count"] = sum(
        1 for d in drift_rows if d["classification"] in ("moderate", "high"))
    return run


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_runs(**kwargs)
    result["items"] = [_hydrate(r) for r in result["items"]]
    return result


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Split resolution
# ---------------------------------------------------------------------------


def _resolve_validation_splits(
    run: Dict[str, Any], sample_ids: Sequence[str]
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    vrun = validation_store.get_run(run["validation_run_id"])
    if vrun is None:
        raise FeatureDiagnosticsError("linked validation run no longer exists")
    if vrun["status"] != "completed" or vrun.get("leakage_clean") is not True:
        raise FeatureDiagnosticsError(
            "verified held-out importance requires a completed, leakage-clean "
            "validation run"
        )
    splits = validation_store.list_splits(run["validation_run_id"])
    invalid = [s for s in splits if s["status"] != "valid"]
    if invalid:
        raise FeatureDiagnosticsError(
            f"the linked validation run has {len(invalid)} invalid split(s) — "
            "feature diagnostics requires all splits valid"
        )
    if not splits:
        raise FeatureDiagnosticsError("the linked validation run has no splits")
    ours = set(sample_ids)
    known: set = set()
    for s in splits:
        known.update(s["train_ids"], s["test_ids"], s["purged_ids"], s["embargoed_ids"])
    unknown = sorted(ours - known)
    if unknown:
        raise FeatureDiagnosticsError(
            f"{len(unknown)} sample(s) are not members of the linked validation "
            f"run (e.g. {unknown[:3]})"
        )
    resolved = []
    for s in splits:
        overlap = set(s["train_ids"]) & set(s["test_ids"])
        if overlap:
            raise FeatureDiagnosticsError(
                f"split {s['split_label']} has train/test overlap"
            )
        resolved.append({
            "split_id": s["split_label"],
            "split_fingerprint": s.get("split_fingerprint"),
            "train_sample_ids": [sid for sid in s["train_ids"] if sid in ours],
            "test_sample_ids": [sid for sid in s["test_ids"] if sid in ours],
        })
    counts = {"split_count": len(splits), "invalid_split_count": 0}
    return resolved, counts


def _resolve_splits(
    run: Dict[str, Any], sample_ids: Sequence[str]
) -> Tuple[List[Dict[str, Any]], str, Dict[str, int]]:
    source = run["split_source"]
    if source == "validation_run":
        resolved, counts = _resolve_validation_splits(run, sample_ids)
        return resolved, "verified_held_out", counts
    if source == "declared":
        declared = run["configuration"].get("declared_splits") or []
        resolved = [{"split_id": d["split_id"], "split_fingerprint": None,
                     "train_sample_ids": d["train_sample_ids"],
                     "test_sample_ids": d["test_sample_ids"]} for d in declared]
        return resolved, "declared_held_out", {
            "split_count": len(resolved), "invalid_split_count": 0}
    all_ids = list(sample_ids)
    resolved = [{"split_id": "all-samples", "split_fingerprint": None,
                 "train_sample_ids": all_ids, "test_sample_ids": all_ids}]
    return resolved, "not_held_out", {"split_count": 1, "invalid_split_count": 0}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"feature-diagnostics run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")

    t0 = time.monotonic()
    config = run["configuration"]
    feature_defs = config["feature_definitions"]
    feature_names = [d["feature_name"] for d in feature_defs]
    metric, direction = run["metric"], run["metric_direction"]
    method, model_type = run["method"], run["model_type"]
    repeats, seed = config["permutation_repeats"], config["seed"]

    try:
        samples = store.all_samples(run_id)
        X, y, ids = build_matrix(samples, feature_names)
        index_of = {sid: i for i, sid in enumerate(ids)}
        warnings: List[str] = list(config.get("schema_warnings") or [])
        const = constant_features(X, feature_names)
        if const:
            warnings.append(
                f"constant feature(s) {const[:5]}: correlation undefined and "
                "permutation cannot change them"
            )

        resolved, integrity, counts = _resolve_splits(run, ids)
        if integrity == "not_held_out":
            warnings.append(
                "no held-out splits: the model was fitted and evaluated on the "
                "same samples — importance is NOT held-out performance degradation"
            )
        if method == "native_impurity":
            integrity = "not_held_out"
            warnings.extend(NATIVE_CAVEATS)
        if method == "coefficient":
            integrity = "not_held_out"
            warnings.extend(COEFFICIENT_CAVEATS)

        split_records: List[Dict[str, Any]] = []
        coef_by_split: List[List[Dict[str, Any]]] = []
        native_by_split: List[List[Dict[str, Any]]] = []
        for split_index, spec in enumerate(resolved):
            train_idx = np.array([index_of[sid] for sid in spec["train_sample_ids"]],
                                 dtype=np.int64)
            test_idx = np.array([index_of[sid] for sid in spec["test_sample_ids"]],
                                dtype=np.int64)
            failed_reason = None
            if len(train_idx) < MIN_TRAIN_SIZE:
                failed_reason = (
                    f"only {len(train_idx)} of this split's training members are in "
                    f"the sample set (minimum {MIN_TRAIN_SIZE})"
                )
            elif len(test_idx) == 0:
                failed_reason = "no evaluation samples fall in this split's test set"
            if failed_reason is None:
                try:
                    model = estimators.fit_estimator(
                        model_type, X[train_idx], y[train_idx],
                        run["target_type"], config["hyperparameters"])
                    if method == "permutation":
                        record = imp_mod.permutation_split_result(
                            model, X[test_idx], y[test_idx], feature_names,
                            metric, direction, seed, split_index, repeats,
                            spec["split_id"])
                    else:
                        try:
                            baseline = metrics_mod.score(
                                metric, y[test_idx],
                                estimators.predict(model, X[test_idx]))
                        except metrics_mod.MetricUnavailable:
                            baseline = None
                        if method == "native_impurity":
                            values = {
                                r["feature_name"]: r["native_importance"]
                                for r in estimators.native_reference(model, feature_names) or []
                            }
                            note = "model-native impurity importance (training-data derived)"
                        else:
                            values = {
                                r["feature_name"]: r["abs_coefficient"]
                                for r in estimators.coefficient_reference(model, feature_names) or []
                            }
                            note = "absolute standardized coefficient (training-data derived)"
                        record = imp_mod.reference_split_result(
                            values, feature_names, baseline, split_index,
                            spec["split_id"], int(len(test_idx)), note)
                    record["split_fingerprint"] = spec.get("split_fingerprint")
                    record["train_count"] = int(len(train_idx))
                    coef = estimators.coefficient_reference(model, feature_names)
                    if coef is not None:
                        coef_by_split.append(coef)
                    native = estimators.native_reference(model, feature_names)
                    if native is not None:
                        native_by_split.append(native)
                    split_records.append(record)
                    continue
                except (estimators.EstimatorError, metrics_mod.MetricUnavailable) as exc:
                    failed_reason = str(exc)
            split_records.append({
                "split_id": spec["split_id"], "split_index": split_index,
                "split_fingerprint": spec.get("split_fingerprint"),
                "status": "failed", "baseline_score": None,
                "evaluated_count": int(len(test_idx)),
                "train_count": int(len(train_idx)),
                "features": {n: imp_mod._feature_stats([], repeats)
                             for n in feature_names},
                "warning": failed_reason,
            })
            warnings.append(f"split {spec['split_id']} failed: {failed_reason}")

        valid_records = [s for s in split_records if s["status"] == "valid"]
        if not valid_records:
            raise FeatureDiagnosticsError(
                "no split produced a defined baseline metric — nothing to aggregate"
            )
        counts["valid_split_count"] = len(valid_records)
        counts["invalid_split_count"] += len(split_records) - len(valid_records)

        aggregates = imp_mod.aggregate_features(split_records, feature_names)
        stab_mod.apply_stability(aggregates, len(feature_names))
        by_name = {d["feature_name"]: d for d in feature_defs}
        for entry in aggregates:
            entry["definition"] = by_name[entry["feature_name"]]
        stability_summary = stab_mod.stability_summary(split_records, feature_names)

        importance_map = {e["feature_name"]: e["mean_importance"] for e in aggregates}
        corr_cfg = config["correlation"]
        correlation = corr_mod.correlation_diagnostics(
            X, feature_names, corr_cfg["method"], corr_cfg["threshold"],
            importance_by_feature=importance_map)

        drift_cfg = config["drift"]
        ref_idx, cmp_idx, drift_context = _drift_partition(
            drift_cfg["mode"], ids, index_of, resolved, valid_records)
        distribution_drift: List[Dict[str, Any]] = []
        for j, name in enumerate(feature_names):
            row = drift_mod.numeric_distribution_drift(
                X[ref_idx, j], X[cmp_idx, j],
                drift_cfg["psi_bins"], drift_cfg["psi_thresholds"])
            distribution_drift.append({
                "feature_name": name, "kind": "distribution",
                "classification": row["classification"],
                "psi": row.get("psi"), "ks_statistic": row.get("ks_statistic"),
                # Promoted out of `detail` so the small-sample caveat is
                # surfaced alongside the statistic it qualifies.
                "small_sample_warning": row.get("small_sample_warning"),
                "detail": row,
            })
        # Documented in FEATURE_STABILITY_AND_DRIFT_POLICY.md §9: small-sample
        # warnings propagate into the run's warning list as well as the UI.
        small_sample_features = [
            d["feature_name"] for d in distribution_drift if d.get("small_sample_warning")
        ]
        if small_sample_features:
            warnings.append(
                f"distribution drift computed on a small sample for "
                f"{len(small_sample_features)} feature(s) "
                f"(e.g. {sorted(small_sample_features)[:3]}) — indicative only"
            )

        imp_drift = drift_mod.importance_drift(split_records, feature_names)
        importance_drift_rows = [
            {"feature_name": f["feature_name"], "kind": "importance",
             "classification": f.get("classification", "unknown"),
             "psi": None, "ks_statistic": None, "detail": f}
            for f in imp_drift.get("features", [])
        ]

        references = _build_references(coef_by_split, native_by_split, feature_names)

        split_meta = [
            {"split_id": s["split_id"], "split_index": s["split_index"],
             "split_fingerprint": s.get("split_fingerprint"),
             "status": s["status"], "baseline_score": s.get("baseline_score"),
             "train_count": s.get("train_count"),
             "evaluated_count": s.get("evaluated_count"),
             "warning": s.get("warning")}
            for s in split_records
        ]
        result_fp = fp_mod.result_fingerprint(
            configuration_fp=run["configuration_fingerprint"],
            split_results=split_records, aggregates=aggregates,
            stability=stability_summary, correlation=correlation,
            distribution_drift=distribution_drift,
            importance_drift=imp_drift, warnings=warnings,
            integrity_status=integrity,
        )
    except (FeatureDiagnosticsError, FeatureInputError, estimators.EstimatorError,
            metrics_mod.MetricUnavailable, corr_mod.CorrelationError,
            drift_mod.DriftError) as exc:
        # A failed (re-)execution must not leave the PREVIOUS execution's derived
        # state behind: otherwise a run reported as failed / unknown-integrity
        # would still serve a result fingerprint, stale per-feature rows, and —
        # worst — remain the active baseline of its scope, a state mark_baseline
        # itself would refuse to create.
        store.update_run(run_id, {
            "status": "failed", "error_message": str(exc),
            "integrity_status": "unknown",
            "result_fingerprint": None,
            "is_baseline": 0, "baseline_fingerprint": None, "baseline_scope": None,
            "split_count": 0, "valid_split_count": 0, "invalid_split_count": 0,
            "splits_json": "[]", "stability_summary_json": "{}",
            "importance_drift_json": "{}", "references_json": "{}",
            "drift_context_json": "{}",
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        })
        store.replace_results(run_id, [])
        store.replace_split_results(run_id, [])
        store.replace_correlation_groups(run_id, [])
        store.replace_drift_results(run_id, [])
        return get_run(run_id)

    split_rows = []
    for s in split_records:
        for name in feature_names:
            f = s["features"][name]
            split_rows.append({
                "split_id": s["split_id"], "split_index": s["split_index"],
                "feature_name": name, "baseline_score": s.get("baseline_score"),
                **{k: f.get(k) for k in (
                    "mean_importance", "median_importance", "std_importance",
                    "min_importance", "max_importance", "positive_repeats",
                    "negative_repeats", "valid_repeats", "permutation_repeats",
                    "rank", "status", "warning")},
            })
    store.replace_results(run_id, aggregates)
    store.replace_split_results(run_id, split_rows)
    store.replace_correlation_groups(run_id, correlation["groups"])
    store.replace_drift_results(run_id, [*distribution_drift, *importance_drift_rows])
    store.update_run(run_id, {
        "status": "completed",
        "integrity_status": integrity,
        "split_count": counts["split_count"],
        "valid_split_count": counts["valid_split_count"],
        "invalid_split_count": counts["invalid_split_count"],
        "splits_json": json.dumps(split_meta),
        "stability_summary_json": json.dumps(stability_summary),
        "importance_drift_json": json.dumps({
            k: v for k, v in imp_drift.items() if k != "features"}),
        "references_json": json.dumps(references),
        "drift_context_json": json.dumps(drift_context),
        "warnings_json": json.dumps(warnings),
        "result_fingerprint": result_fp,
        "completed_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "error_message": None,
    })

    if create_experiment and not run.get("experiment_id"):
        top = sorted(
            (a for a in aggregates if a["mean_importance"] is not None),
            key=lambda a: a["rank"] if a["rank"] is not None else 1e9)[:5]
        record = experiment_integration.record_experiment(
            name=f"Feature diagnostics: {run['name']}",
            module="feature_diagnostics",
            experiment_type=f"importance_{method}",
            status="completed",
            parameters={
                "method": method, "model_type": model_type,
                "metric": metric, "metric_direction": direction,
                "integrity_status": integrity,
                "top_features": [t["feature_name"] for t in top],
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "valid_splits": counts["valid_split_count"],
                "mean_spearman": stability_summary.get("mean_spearman"),
                "stable_features": sum(
                    1 for a in aggregates
                    if a["stability_classification"] == "stable"),
                "drift_flags": sum(
                    1 for d in distribution_drift
                    if d["classification"] in ("moderate", "high")),
            },
            tags=["feature-diagnostics", method],
            source="feature_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


def _drift_partition(
    mode: str, ids: List[str], index_of: Dict[str, int],
    resolved: List[Dict[str, Any]], valid_records: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    if mode == "first_vs_last_split":
        by_id = {s["split_id"]: s for s in resolved}
        first = by_id[valid_records[0]["split_id"]]
        last = by_id[valid_records[-1]["split_id"]]
        ref = [index_of[sid] for sid in first["test_sample_ids"]]
        cmp_ = [index_of[sid] for sid in last["test_sample_ids"]]
        context = {
            "mode": mode,
            "reference_label": f"test members of split {first['split_id']}",
            "comparison_label": f"test members of split {last['split_id']}",
            "reference_count": len(ref), "comparison_count": len(cmp_),
        }
        return np.array(ref, dtype=np.int64), np.array(cmp_, dtype=np.int64), context
    mid = len(ids) // 2
    context = {
        "mode": "early_vs_late",
        "reference_label": f"earlier half by timestamp ({mid} samples)",
        "comparison_label": f"later half by timestamp ({len(ids) - mid} samples)",
        "reference_count": mid, "comparison_count": len(ids) - mid,
    }
    return (np.arange(0, mid, dtype=np.int64),
            np.arange(mid, len(ids), dtype=np.int64), context)


def _build_references(
    coef_by_split: List[List[Dict[str, Any]]],
    native_by_split: List[List[Dict[str, Any]]],
    feature_names: Sequence[str],
) -> Dict[str, Any]:
    references: Dict[str, Any] = {}
    if coef_by_split:
        rows = []
        for j, name in enumerate(feature_names):
            values = [split[j]["coefficient"] for split in coef_by_split]
            signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in values]
            rows.append({
                "feature_name": name,
                "mean_coefficient": float(np.mean(values)),
                "mean_abs_coefficient": float(np.mean(np.abs(values))),
                "sign": max(set(signs), key=lambda s: (signs.count(s), -abs(s))),
                "sign_consistent": len(set(signs)) == 1,
                "standardized": True,
            })
        references["coefficients"] = {
            "rows": rows, "fitted_splits": len(coef_by_split),
            "caveats": COEFFICIENT_CAVEATS,
        }
    if native_by_split:
        rows = []
        for j, name in enumerate(feature_names):
            values = [split[j]["native_importance"] for split in native_by_split]
            rows.append({
                "feature_name": name,
                "mean_native_importance": float(np.mean(values)),
            })
        references["native_impurity"] = {
            "rows": rows, "fitted_splits": len(native_by_split),
            "caveats": NATIVE_CAVEATS,
        }
    return references


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"feature-diagnostics run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0, "baseline_fingerprint": None})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        run["method"], run["metric"], run["model_type"],
        f"ds:{run['dataset_version_id'] or 'none'}",
        f"vr:{run['validation_run_id'] or 'none'}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"feature-diagnostics run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["integrity_status"] not in ("verified_held_out", "declared_held_out"):
        raise ConflictError(
            "baselines require held-out evidence (verified or declared) — "
            f"this run is {run['integrity_status']}"
        )
    if run["invalid_split_count"] > 0:
        raise ConflictError("baselines require a run with no invalid splits")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    scope = _baseline_scope(run)
    scope_detail = {
        "method": run["method"], "metric": run["metric"],
        "model_type": run["model_type"],
        "dataset_version_id": run["dataset_version_id"],
        "validation_run_id": run["validation_run_id"],
    }
    baseline_fp = fp_mod.baseline_fingerprint(
        result_fp=run["result_fingerprint"], scope=scope_detail)
    store.update_run(run_id, {"baseline_scope": scope})
    store.mark_baseline(run_id, scope, baseline_fp)
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Comparison + export
# ---------------------------------------------------------------------------


def _entry(field: str, a: Any, b: Any) -> Dict[str, Any]:
    if a is None and b is None:
        return {"kind": "unavailable", "field": field, "a": a, "b": b, "note": ""}
    if a is None:
        return {"kind": "only_in_b", "field": field, "a": a, "b": b, "note": ""}
    if b is None:
        return {"kind": "only_in_a", "field": field, "a": a, "b": b, "note": ""}
    kind = "same" if a == b else "changed"
    note = ""
    if (kind == "changed" and isinstance(a, (int, float)) and isinstance(b, (int, float))
            and not isinstance(a, bool) and not isinstance(b, bool)
            and math.isfinite(float(a)) and math.isfinite(float(b))):
        note = f"Δ {round(b - a, 6)}"
        if a != 0:
            note += f" ({(b - a) / abs(a) * 100.0:+.2f}%)"
    return {"kind": kind, "field": field, "a": a, "b": b, "note": note}


def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise FeatureDiagnosticsError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "method", "metric", "metric_direction", "model_type", "target_type",
        "integrity_status", "status", "dataset_name", "validation_method",
        "sample_count", "feature_count", "valid_split_count")]
    stability = [_entry(f, (a.get("stability_summary") or {}).get(f),
                        (b.get("stability_summary") or {}).get(f))
                 for f in ("mean_spearman", "mean_kendall", "mean_top_k_overlap")]
    a_results = {r["feature_name"]: r for r in store.list_results(a_id)}
    b_results = {r["feature_name"]: r for r in store.list_results(b_id)}
    ordered = [n for n in a_results] + [n for n in b_results if n not in a_results]
    features = []
    for name in ordered:
        ra, rb = a_results.get(name), b_results.get(name)
        ia = ra["mean_importance"] if ra else None
        ib = rb["mean_importance"] if rb else None
        availability = ("both" if ra and rb
                        else ("only_in_a" if ra else "only_in_b"))
        entry: Dict[str, Any] = {
            "feature_name": name, "availability": availability,
            "a_importance": ia, "b_importance": ib,
            "a_rank": ra["rank"] if ra else None,
            "b_rank": rb["rank"] if rb else None,
            "a_stability": ra["stability_classification"] if ra else None,
            "b_stability": rb["stability_classification"] if rb else None,
        }
        if ia is not None and ib is not None:
            entry["abs_difference"] = abs(ib - ia)
            entry["pct_difference"] = (
                (ib - ia) / abs(ia) * 100.0 if abs(ia) > 1e-12 else None)
            entry["rank_change"] = (
                entry["b_rank"] - entry["a_rank"]
                if entry["a_rank"] is not None and entry["b_rank"] is not None
                else None)
            entry["sign_changed"] = (ia > 0) != (ib > 0) if ia != 0 and ib != 0 \
                else (ia == 0) != (ib == 0)
            entry["kind"] = "same" if ia == ib else "changed"
        else:
            entry["abs_difference"] = entry["pct_difference"] = None
            entry["rank_change"] = entry["sign_changed"] = None
            entry["kind"] = "unavailable" if availability == "both" else availability
        features.append(entry)
    return {
        "a_id": a_id, "b_id": b_id,
        "groups": {"identity": identity, "stability": stability},
        "features": features,
        "fingerprint_match": {
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Runs + diagnostics (raw sample rows are deliberately excluded)."""
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    results: Dict[int, Any] = {}
    split_results: Dict[int, Any] = {}
    correlation_groups: Dict[int, Any] = {}
    drift_results: Dict[int, Any] = {}
    for r in runs:
        results[r["id"]] = store.list_results(r["id"])
        split_results[r["id"]] = store.list_split_results(r["id"])
        correlation_groups[r["id"]] = store.list_correlation_groups(r["id"])
        drift_results[r["id"]] = store.list_drift_results(r["id"])
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "note": "raw feature samples are not exported",
        "runs": runs,
        "results": results,
        "split_results": split_results,
        "correlation_groups": correlation_groups,
        "drift_results": drift_results,
    }


__all__ = [
    "METHODS", "SPLIT_SOURCES", "INTEGRITY_STATUSES",
    "FeatureDiagnosticsError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "compare_runs", "export",
]
