"""
Service layer: run lifecycle, OOF calibration via Model Validation splits,
metrics/bins/threshold analysis, threshold policies with baselines,
comparison, and export.

OOF statuses (documented): ``verified_from_validation_run`` (calibrators fitted
per split on recorded train memberships, applied only to held-out test
observations of a completed, leakage-clean validation run),
``declared_out_of_fold`` (the caller explicitly declared the supplied raw
probabilities as already out-of-fold — recorded as a declaration, NOT
independently verified), ``not_out_of_fold`` (calibration fitted on all
observations without split evidence), ``unknown``.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.meta_labeling import EXPORT_SCHEMA_VERSION
from app.meta_labeling import calibration as cal_mod
from app.meta_labeling import fingerprints as fp_mod
from app.meta_labeling import thresholds as thr_mod
from app.meta_labeling.core import ObservationError, apply_meta_labels, normalize_observations
from app.model_validation import store as validation_store


class MetaLabelError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.meta_labeling import store  # noqa: E402  (after error classes for clarity)


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    try:
        observations = normalize_observations(payload["observations"])
    except ObservationError as exc:
        raise MetaLabelError(str(exc))

    method = payload.get("calibration_method", "none")
    if method not in cal_mod.CALIBRATION_METHODS:
        raise MetaLabelError(f"calibration_method must be one of {cal_mod.CALIBRATION_METHODS}")

    label_policy = {
        "rule": "meta_label = 1 iff primary_side * realized_outcome > outcome_threshold",
        "outcome_threshold": float(payload.get("outcome_threshold", 0.0)),
        "side_zero": "abstained (no binary label)",
    }
    if not math.isfinite(label_policy["outcome_threshold"]):
        raise MetaLabelError("outcome_threshold must be finite")

    # Eager grid/abstention validation so bad configs 422 at creation.
    grid_config = payload.get("threshold_grid") or {}
    thr_mod.build_grid(grid_config)
    thr_mod.validate_abstention(payload.get("abstention"))

    n_bins = payload.get("n_bins", 10)
    binning = payload.get("binning", "equal_width")
    if binning not in ("equal_width", "equal_frequency"):
        raise MetaLabelError("binning must be 'equal_width' or 'equal_frequency'")
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or not (2 <= n_bins <= cal_mod.MAX_BINS):
        raise MetaLabelError(f"n_bins must be an integer between 2 and {cal_mod.MAX_BINS}")

    validation_run_fp = None
    validation_run_id = payload.get("validation_run_id")
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None:
            raise NotFoundError(f"validation run {validation_run_id} not found")
        validation_run_fp = vrun["configuration_fingerprint"]
    dataset_version_id = payload.get("dataset_version_id")
    if dataset_version_id is not None and dataset_store.get_version(dataset_version_id) is None:
        raise NotFoundError(f"dataset version {dataset_version_id} not found")
    if payload.get("experiment_id") is not None:
        if experiment_store.get_experiment(payload["experiment_id"]) is None:
            raise NotFoundError(f"experiment {payload['experiment_id']} not found")

    declared_oof = bool(payload.get("declared_out_of_fold", False))
    oof_policy = (
        "validation_run" if validation_run_id is not None
        else ("declared" if declared_oof else "none")
    )
    configuration = {
        "calibration_method": method,
        "n_bins": n_bins,
        "binning": binning,
        "threshold_grid": grid_config,
        "abstention": payload.get("abstention"),
        "declared_out_of_fold": declared_oof,
    }
    config_fp = fp_mod.configuration_fingerprint(
        label_policy=label_policy,
        observations=observations,
        calibration_method=method,
        calibration_settings={"n_bins": n_bins, "binning": binning},
        oof_policy=oof_policy,
        threshold_grid=grid_config,
        validation_run_fp=validation_run_fp,
        random_seed=payload.get("random_seed"),
    )

    run = store.insert_run(
        {
            "name": payload["name"],
            "description": payload.get("description", ""),
            "label_policy": label_policy,
            "calibration_method": method,
            "oof_status": "unknown",
            "validation_run_id": validation_run_id,
            "dataset_version_id": dataset_version_id,
            "experiment_id": payload.get("experiment_id"),
            "configuration": configuration,
            "configuration_fingerprint": config_fp,
            "observation_count": len(observations),
            "app_version": get_app_version(),
            "git_commit": get_git_commit(),
            "notes": payload.get("notes", ""),
            "demo_key": demo_key,
        }
    )
    store.replace_observations(run["id"], observations)
    return get_run(run["id"])


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"meta-label run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = run["validation_result_fp"] = None
    run["experiment_name"] = None
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
    brier = (run.get("calibrated_metrics") or {}).get("metrics", {}).get("brier")
    ece = (run.get("calibrated_metrics") or {}).get("ece")
    run["brier_preview"] = brier
    run["ece_preview"] = ece
    prevalence = (run.get("calibrated_metrics") or {}).get("positive_prevalence")
    run["positive_prevalence"] = prevalence
    return run


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_runs(**kwargs)
    result["items"] = [_hydrate(r) for r in result["items"]]
    return result


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _oof_calibrate(
    run: Dict[str, Any], labeled: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Per-split OOF calibration using the linked validation run's memberships."""
    vrun = validation_store.get_run(run["validation_run_id"])
    if vrun is None:
        raise MetaLabelError("linked validation run no longer exists")
    if vrun["status"] != "completed" or vrun.get("leakage_clean") is not True:
        raise MetaLabelError(
            "verified OOF calibration requires a completed, leakage-clean validation run"
        )
    splits = validation_store.list_splits(run["validation_run_id"])
    valid_splits = [s for s in splits if s["status"] == "valid"]
    if not valid_splits:
        raise MetaLabelError("the linked validation run has no valid splits")

    by_id = {o["sample_id"]: o for o in labeled}
    known: set[str] = set()
    for s in splits:
        known.update(s["train_ids"])
        known.update(s["test_ids"])
        known.update(s["purged_ids"])
        known.update(s["embargoed_ids"])
    unknown = [sid for sid in by_id if sid not in known]
    if unknown:
        raise MetaLabelError(
            f"{len(unknown)} observation(s) are not members of the linked validation "
            f"run (e.g. {unknown[:3]})"
        )

    method = run["calibration_method"]
    calibrated: Dict[str, float] = {}
    fitted_params: List[Dict[str, Any]] = []
    for s in valid_splits:
        overlap = set(s["train_ids"]) & set(s["test_ids"])
        if overlap:
            raise MetaLabelError(f"split {s['split_label']} has train/test overlap")
        train_obs = [by_id[sid] for sid in s["train_ids"] if sid in by_id]
        test_obs = [by_id[sid] for sid in s["test_ids"] if sid in by_id]
        if not test_obs:
            continue
        if method == "none":
            for o in test_obs:
                calibrated[o["sample_id"]] = o["raw_probability"]
                o["split_label"] = s["split_label"]
            continue
        train_p = [o["raw_probability"] for o in train_obs]
        train_y = [o["meta_label"] for o in train_obs]
        params = cal_mod.FITTERS[method](train_p, train_y)  # raises CalibrationError
        fitted_params.append(
            {"split_label": s["split_label"], "params": params,
             "fitted_on": len(train_obs), "applied_to": len(test_obs)}
        )
        out = cal_mod.APPLIERS[method](params, [o["raw_probability"] for o in test_obs])
        for o, p in zip(test_obs, out):
            calibrated[o["sample_id"]] = p
            o["split_label"] = s["split_label"]

    missing = [sid for sid in by_id if sid not in calibrated]
    if missing:
        raise MetaLabelError(
            f"{len(missing)} observation(s) never appear in a valid test set "
            f"(e.g. {missing[:3]}) — cannot produce out-of-fold probabilities"
        )
    return {"calibrated": calibrated, "fitted_params": fitted_params,
            "oof_status": "verified_from_validation_run"}


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"meta-label run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")

    t0 = time.monotonic()
    observations = store.all_observations(run_id)
    try:
        counts = apply_meta_labels(
            observations, outcome_threshold=run["label_policy"]["outcome_threshold"]
        )
        labeled = [o for o in observations if not o["abstained"]]
        with_prob = [o for o in labeled if o["raw_probability"] is not None]
        if len(with_prob) < cal_mod.MIN_CALIBRATION_SAMPLES:
            raise MetaLabelError(
                "meta-labeling requires raw probabilities on at least "
                f"{cal_mod.MIN_CALIBRATION_SAMPLES} non-abstained observations"
            )

        method = run["calibration_method"]
        config = run["configuration"]
        if run.get("validation_run_id"):
            oof = _oof_calibrate(run, with_prob)
            for o in with_prob:
                o["calibrated_probability"] = oof["calibrated"][o["sample_id"]]
            oof_status = oof["oof_status"]
            calibration_params: Any = {"per_split": oof["fitted_params"], "method": method}
        elif method == "none":
            for o in with_prob:
                o["calibrated_probability"] = o["raw_probability"]
            oof_status = (
                "declared_out_of_fold" if config.get("declared_out_of_fold") else "unknown"
            )
            calibration_params = {"method": "none"}
        else:
            # Fit on ALL observations — explicitly not out-of-fold.
            probs = [o["raw_probability"] for o in with_prob]
            ys = [o["meta_label"] for o in with_prob]
            params = cal_mod.FITTERS[method](probs, ys)
            out = cal_mod.APPLIERS[method](params, probs)
            for o, p in zip(with_prob, out):
                o["calibrated_probability"] = p
            oof_status = "not_out_of_fold"
            calibration_params = {"method": method, "params": params,
                                  "fitted_on": len(with_prob)}

        raw_probs = [o["raw_probability"] for o in with_prob]
        cal_probs = [o["calibrated_probability"] for o in with_prob]
        ys = [o["meta_label"] for o in with_prob]
        outcomes = [o["realized_outcome"] for o in with_prob]

        n_bins, binning = config["n_bins"], config["binning"]
        raw_metrics = cal_mod.probability_metrics(raw_probs, ys)
        cal_metrics = cal_mod.probability_metrics(cal_probs, ys)
        raw_bins = cal_mod.reliability_bins(raw_probs, ys, n_bins=n_bins, binning=binning)
        cal_bins = cal_mod.reliability_bins(cal_probs, ys, n_bins=n_bins, binning=binning)
        raw_metrics.update(cal_mod.calibration_errors(raw_bins, len(raw_probs)))
        cal_metrics.update(cal_mod.calibration_errors(cal_bins, len(cal_probs)))

        analysis = thr_mod.threshold_table(
            cal_probs, ys, outcomes,
            grid_config=config.get("threshold_grid"),
            abstention=config.get("abstention"),
        )

        result_fp = fp_mod.result_fingerprint(
            configuration_fp=run["configuration_fingerprint"],
            calibration_params=calibration_params,
            raw_probabilities=raw_probs,
            calibrated_probabilities=cal_probs,
            labels=ys,
            metrics={"raw": raw_metrics["metrics"], "calibrated": cal_metrics["metrics"]},
            bins=cal_bins,
        )
    except (ObservationError, cal_mod.CalibrationError, thr_mod.ThresholdError,
            MetaLabelError) as exc:
        store.update_run(run_id, {
            "status": "failed", "error_message": str(exc),
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        })
        return get_run(run_id)

    store.replace_observations(run_id, observations)
    store.replace_bins(run_id, "raw", raw_bins)
    store.replace_bins(run_id, "calibrated", cal_bins)
    store.update_run(run_id, {
        "status": "completed",
        "oof_status": oof_status,
        "labeled_count": counts["labeled_count"],
        "positive_count": counts["positive_count"],
        "abstained_count": counts["abstained_count"],
        "raw_metrics_json": json.dumps(raw_metrics),
        "calibrated_metrics_json": json.dumps(cal_metrics),
        "calibration_params_json": json.dumps(calibration_params),
        "threshold_analysis_json": json.dumps(analysis),
        "result_fingerprint": result_fp,
        "completed_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "error_message": None,
    })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Meta-labeling: {run['name']}",
            module="meta_labeling",
            experiment_type=f"calibration_{run['calibration_method']}",
            status="completed",
            parameters={
                "label_policy": run["label_policy"],
                "calibration_method": run["calibration_method"],
                "oof_status": oof_status,
                "configuration": run["configuration"],
            },
            metrics={
                "brier_calibrated": cal_metrics["metrics"].get("brier"),
                "ece_calibrated": cal_metrics.get("ece"),
                "valid_observations": cal_metrics.get("valid_count"),
                "positive_prevalence": cal_metrics.get("positive_prevalence"),
            },
            tags=["meta-labeling", run["calibration_method"]],
            source="meta_labeling",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"meta-label run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Threshold policies
# ---------------------------------------------------------------------------


def create_policy(run_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    run = get_run(run_id)
    if run["status"] != "completed":
        raise ConflictError("threshold policies require a completed run")
    threshold = payload.get("threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
            or not math.isfinite(float(threshold)) or not (0.0 <= float(threshold) <= 1.0):
        raise MetaLabelError("threshold must be a finite number in [0, 1]")
    band = thr_mod.validate_abstention(payload.get("abstention"))

    observations = [o for o in store.all_observations(run_id)
                    if not o["abstained"] and o["calibrated_probability"] is not None]
    row = thr_mod.analyze_threshold(
        [o["calibrated_probability"] for o in observations],
        [o["meta_label"] for o in observations],
        [o["realized_outcome"] for o in observations],
        float(threshold), band,
    )
    policy_fp = fp_mod.policy_fingerprint(
        result_fp=run["result_fingerprint"] or "",
        threshold=float(threshold),
        abstention=band,
        observed_metrics={k: row[k] for k in ("coverage", "precision", "recall", "f1")},
    )
    return store.insert_policy({
        "run_id": run_id,
        "name": payload.get("name") or f"threshold {threshold}",
        "threshold": float(threshold),
        "abstention": band,
        "configuration_fingerprint": policy_fp,
        "observed_coverage": row["coverage"],
        "observed_precision": row["precision"],
        "observed_recall": row["recall"],
        "observed_f1": row["f1"],
        "notes": payload.get("notes", ""),
    })


def mark_policy_baseline(policy_id: int) -> Dict[str, Any]:
    policy = store.get_policy(policy_id)
    if policy is None:
        raise NotFoundError(f"threshold policy {policy_id} not found")
    run = get_run(policy["run_id"])
    if run["status"] != "completed":
        raise ConflictError("baseline policies require a completed run")
    if run["oof_status"] == "not_out_of_fold":
        raise ConflictError(
            "baseline policies require out-of-fold evidence (verified or declared)"
        )
    store.mark_policy_baseline(policy_id, policy["run_id"])
    refreshed = store.get_policy(policy_id)
    assert refreshed is not None
    return refreshed


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
        raise MetaLabelError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "calibration_method", "oof_status", "status", "dataset_name",
        "validation_method", "observation_count", "labeled_count",
        "positive_prevalence")]
    metric_entries = []
    for name in ("brier", "log_loss", "roc_auc", "pr_auc"):
        for src in ("raw", "calibrated"):
            ma = (a.get(f"{src}_metrics") or {}).get("metrics", {}).get(name)
            mb = (b.get(f"{src}_metrics") or {}).get("metrics", {}).get(name)
            if ma is None and mb is None:
                continue
            metric_entries.append(_entry(f"{src}_{name}", ma, mb))
    for name in ("ece", "mce"):
        for src in ("raw", "calibrated"):
            ma = (a.get(f"{src}_metrics") or {}).get(name)
            mb = (b.get(f"{src}_metrics") or {}).get(name)
            if ma is None and mb is None:
                continue
            metric_entries.append(_entry(f"{src}_{name}", ma, mb))
    label_policy = [_entry("outcome_threshold",
                           a["label_policy"].get("outcome_threshold"),
                           b["label_policy"].get("outcome_threshold"))]
    return {
        "a_id": a_id, "b_id": b_id,
        "groups": {"identity": identity, "label_policy": label_policy,
                   "probability_metrics": metric_entries},
        "fingerprint_match": {
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    bins: Dict[int, Any] = {}
    policies: List[Dict[str, Any]] = []
    for r in runs:
        bins[r["id"]] = store.list_bins(r["id"])
        policies.extend(store.list_policies(r["id"]))
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "runs": runs,
        "bins": bins,
        "threshold_policies": policies,
    }


__all__ = [
    "MetaLabelError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "create_policy", "mark_policy_baseline",
    "compare_runs", "export",
]
