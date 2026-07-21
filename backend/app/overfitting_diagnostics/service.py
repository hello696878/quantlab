"""
Service layer: run lifecycle, CSCV/PBO execution, Sharpe deflation, multiple
testing, dependence, baselines, comparison, and export.

Everything is deterministic and conservatively worded: no candidate is ever
called best, winning, safe, optimal, or recommended; low PBO is a lower
estimated selection-overfitting frequency under one configuration; PSR/DSR
are research statistics under stated assumptions — never probabilities of
future profit.
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
from app.feature_diagnostics import store as feature_store
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import EXPORT_SCHEMA_VERSION
from app.overfitting_diagnostics import cscv as cscv_mod
from app.overfitting_diagnostics import dependence as dep_mod
from app.overfitting_diagnostics import fingerprints as fp_mod
from app.overfitting_diagnostics import metrics as metrics_mod
from app.overfitting_diagnostics import multiple_testing as mt_mod
from app.overfitting_diagnostics import sharpe as sharpe_mod
from app.overfitting_diagnostics.core import (
    ALIGNMENT_POLICY, CandidateInputError, build_matrix, normalize_candidates,
    normalize_timestamps,
)


class OverfittingError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


TIE_POLICY = (
    "exact in-sample ties select the lexicographically smallest candidate_id "
    "and are recorded; out-of-sample ranks use average ties"
)
TRIAL_MODES = ("raw", "manual", "dependence_adjusted")
MULTIPLE_TESTING_METHODS = ("bonferroni", "holm", "benjamini_hochberg")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.overfitting_diagnostics import store  # noqa: E402  (after error classes)


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def _validate_trial_policy(policy: Optional[Dict[str, Any]], n_candidates: int) -> Dict[str, Any]:
    policy = policy or {}
    mode = policy.get("mode", "raw")
    if mode not in TRIAL_MODES:
        raise OverfittingError(f"trial_count_policy.mode must be one of {TRIAL_MODES}")
    manual = policy.get("manual_value")
    if mode == "manual":
        if isinstance(manual, bool) or not isinstance(manual, (int, float)) \
                or not math.isfinite(manual) or not (1.0 <= float(manual) <= n_candidates):
            raise OverfittingError(
                "trial_count_policy.manual_value must be a finite number between 1 "
                f"and the raw candidate count ({n_candidates}) — correlated trials "
                "are never counted as more than the raw total"
            )
        manual = float(manual)
    elif manual is not None:
        raise OverfittingError("manual_value is only valid with mode 'manual'")
    return {"mode": mode, "manual_value": manual}


def _validate_periods_per_year(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) or not (1.0 <= float(value) <= 100_000.0):
        raise OverfittingError("periods_per_year must be a finite number in [1, 100000]")
    return float(value)


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    try:
        timestamps = normalize_timestamps(payload.get("timestamps") or [])
        candidates = normalize_candidates(payload.get("candidates") or [], len(timestamps))
    except CandidateInputError as exc:
        raise OverfittingError(str(exc))

    metric = metrics_mod.validate_metric(payload.get("metric", "sharpe_like"))
    try:
        block_count = cscv_mod.validate_block_count(
            payload.get("block_count", 8), len(timestamps))
        benchmark_sharpe = sharpe_mod.validate_benchmark_sharpe(
            payload.get("benchmark_sharpe", 0.0))
        confidence = sharpe_mod.validate_confidence(payload.get("confidence", 0.95))
        alpha = mt_mod.validate_alpha(payload.get("alpha", 0.05))
        dependence_config = dep_mod.validate_dependence_config(payload.get("dependence"))
    except (cscv_mod.CSCVError, sharpe_mod.SharpeError,
            mt_mod.MultipleTestingError, dep_mod.DependenceError) as exc:
        raise OverfittingError(str(exc))
    trial_policy = _validate_trial_policy(payload.get("trial_count_policy"),
                                          len(candidates))
    periods_per_year = _validate_periods_per_year(payload.get("periods_per_year"))
    if len({c["candidate_id"] for c in candidates
            if c["nominal_p_value"] is not None}) > mt_mod.MAX_HYPOTHESES:
        raise OverfittingError(
            f"at most {mt_mod.MAX_HYPOTHESES} candidates may carry p-values")

    for field, getter, label in (
        ("dataset_version_id", dataset_store.get_version, "dataset version"),
        ("validation_run_id", validation_store.get_run, "validation run"),
        ("experiment_id", experiment_store.get_experiment, "experiment"),
        ("feature_diagnostics_run_id", feature_store.get_run, "feature-diagnostics run"),
    ):
        value = payload.get(field)
        if value is not None and getter(value) is None:
            raise NotFoundError(f"{label} {value} not found")
    for c in candidates:
        for field, getter, label in (
            ("experiment_id", experiment_store.get_experiment, "experiment"),
            ("validation_run_id", validation_store.get_run, "validation run"),
            ("dataset_version_id", dataset_store.get_version, "dataset version"),
        ):
            value = c.get(field)
            if value is not None and getter(value) is None:
                raise NotFoundError(
                    f"candidate {c['candidate_id']}: {label} {value} not found")

    matrix = build_matrix(candidates)
    candidate_ids = [c["candidate_id"] for c in candidates]
    universe_fp = fp_mod.universe_fingerprint(
        candidate_ids=candidate_ids,
        candidate_config_fps=[c.get("configuration_fingerprint") for c in candidates],
        timestamps=timestamps,
        returns_matrix=[c["returns"] for c in candidates],
        alignment_policy=ALIGNMENT_POLICY,
    )
    cscv_policy = {
        "s_min": cscv_mod.S_MIN, "s_max": cscv_mod.S_MAX,
        "max_combinations": cscv_mod.MAX_COMBINATIONS,
        "min_block_observations": cscv_mod.MIN_BLOCK_OBSERVATIONS,
        "combination_order": "itertools.combinations lexicographic",
        "block_sizing": "numpy.array_split (earlier blocks take the extra observation)",
        "approximation": "none — all C(S, S/2) combinations are evaluated",
    }
    configuration = {
        "metric": metric,
        "metric_direction": "higher_is_better",
        "sharpe_convention": metrics_mod.SHARPE_CONVENTION,
        "skew_convention": sharpe_mod.SKEW_CONVENTION,
        "kurtosis_convention": sharpe_mod.KURTOSIS_CONVENTION,
        "alignment_policy": ALIGNMENT_POLICY,
        "block_count": block_count,
        "combination_count": cscv_mod.combination_count(block_count),
        "cscv_policy": cscv_policy,
        "tie_policy": TIE_POLICY,
        "rank_convention": "rank 1 = worst OOS, rank N = strongest OOS; "
                           "omega = rank/(N+1); lambda = ln(omega/(1-omega)); "
                           "PBO counts lambda < 0 (lambda == 0 is not overfit)",
        "benchmark_sharpe": benchmark_sharpe,
        "confidence": confidence,
        "alpha": alpha,
        "trial_count_policy": trial_policy,
        "multiple_testing_methods": list(MULTIPLE_TESTING_METHODS),
        "dependence": dependence_config,
        "periods_per_year": periods_per_year,
    }
    config_fp = fp_mod.configuration_fingerprint(
        universe_fp=universe_fp, metric=metric, block_count=block_count,
        cscv_policy=cscv_policy, tie_policy=TIE_POLICY,
        rank_convention=configuration["rank_convention"],
        sharpe_convention=metrics_mod.SHARPE_CONVENTION,
        benchmark_sharpe=benchmark_sharpe, trial_count_policy=trial_policy,
        confidence=confidence, alpha=alpha,
        multiple_testing_methods=MULTIPLE_TESTING_METHODS,
        dependence_config=dependence_config, periods_per_year=periods_per_year,
    )

    run = store.insert_run({
        "name": payload["name"], "description": payload.get("description", ""),
        "metric": metric, "block_count": block_count,
        "candidate_count": len(candidates),
        "observation_count": len(timestamps),
        "combination_count": cscv_mod.combination_count(block_count),
        "universe_fingerprint": universe_fp,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "timestamps": timestamps,
        "dataset_version_id": payload.get("dataset_version_id"),
        "validation_run_id": payload.get("validation_run_id"),
        "experiment_id": payload.get("experiment_id"),
        "feature_diagnostics_run_id": payload.get("feature_diagnostics_run_id"),
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""), "demo_key": demo_key,
    })
    store.replace_candidates(run["id"], candidates)
    return get_run(run["id"])


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"overfitting-diagnostic run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = run["validation_result_fp"] = None
    run["validation_valid_splits"] = run["validation_invalid_splits"] = None
    run["experiment_name"] = None
    run["feature_run_name"] = run["feature_run_integrity"] = None
    run["feature_run_stable_count"] = run["feature_run_drift_flags"] = None
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
            run["validation_valid_splits"] = vrun.get("valid_split_count")
            run["validation_invalid_splits"] = vrun.get("invalid_split_count")
    if run.get("experiment_id"):
        exp = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = exp["name"] if exp else None
    if run.get("feature_diagnostics_run_id"):
        frun = feature_store.get_run(run["feature_diagnostics_run_id"])
        if frun:
            run["feature_run_name"] = frun["name"]
            run["feature_run_integrity"] = frun["integrity_status"]
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


def _augment_rank_matrices(
    records: List[Dict[str, Any]], matrix: np.ndarray, blocks, metric: str
) -> Dict[str, Any]:
    """Per-candidate mean IS/OOS rank across valid splits (§17) computed from
    the same block partitions the CSCV records used."""
    block_indices = [np.arange(b["start"], b["end"] + 1) for b in blocks]
    n = matrix.shape[1]
    is_rank_sums = np.zeros(n)
    is_rank_counts = np.zeros(n)
    oos_rank_sums = np.zeros(n)
    oos_rank_counts = np.zeros(n)
    from scipy import stats as sp_stats
    for r in records:
        if r["status"] != "valid":
            continue
        for key, sums, counts in (
            ("is_block_ids", is_rank_sums, is_rank_counts),
            ("oos_block_ids", oos_rank_sums, oos_rank_counts),
        ):
            idx = np.concatenate([block_indices[b] for b in r[key]])
            values, _ = metrics_mod.matrix_metrics(metric, matrix[idx])
            defined = ~np.isnan(values)
            if defined.any():
                ranks = sp_stats.rankdata(values[defined], method="average")
                positions = np.where(defined)[0]
                for pos, rank in zip(positions, ranks):
                    sums[pos] += rank
                    counts[pos] += 1
    return {
        "mean_is_rank": [float(is_rank_sums[j] / is_rank_counts[j])
                         if is_rank_counts[j] else None for j in range(n)],
        "mean_oos_rank": [float(oos_rank_sums[j] / oos_rank_counts[j])
                          if oos_rank_counts[j] else None for j in range(n)],
    }


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"overfitting-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")

    t0 = time.monotonic()
    config = run["configuration"]
    metric = run["metric"]
    warnings: List[str] = []
    try:
        candidates = store.list_candidates(run_id)
        candidate_ids = [c["candidate_id"] for c in candidates]
        matrix = build_matrix(candidates)

        blocks = cscv_mod.build_blocks(matrix.shape[0], run["block_count"])
        records = cscv_mod.run_cscv(matrix, blocks, metric, candidate_ids)
        aggregate = cscv_mod.aggregate_pbo(records, candidate_ids)
        if aggregate["valid_split_count"] == 0:
            raise OverfittingError(
                "no valid CSCV splits — every combination had undefined metrics "
                "(see the split warnings)"
            )
        rank_means = _augment_rank_matrices(records, matrix, blocks, metric)
        for entry, mean_is, mean_oos in zip(
                aggregate["selection"], rank_means["mean_is_rank"],
                rank_means["mean_oos_rank"]):
            entry["mean_is_rank"] = mean_is
            entry["mean_oos_rank"] = mean_oos
        if aggregate["tie_in_sample_count"]:
            warnings.append(
                f"{aggregate['tie_in_sample_count']} split(s) had exact in-sample "
                "ties — resolved deterministically by candidate_id and recorded"
            )
        if aggregate["invalid_split_count"]:
            warnings.append(
                f"{aggregate['invalid_split_count']} CSCV split(s) were invalid "
                "and excluded from the PBO denominator"
            )

        dependence = dep_mod.dependence_diagnostics(
            matrix, candidate_ids, config["dependence"]["threshold"])
        if dependence["constant_candidates"]:
            warnings.append(
                f"constant-return candidate(s) {dependence['constant_candidates'][:5]}: "
                "Sharpe and correlation diagnostics are unavailable for them"
            )

        # Per-candidate full-series statistics.
        sharpes: List[Optional[float]] = []
        selection_by_id = {e["candidate_id"]: e for e in aggregate["selection"]}
        for j, c in enumerate(candidates):
            r = matrix[:, j]
            moments = sharpe_mod.sharpe_moments(r)
            psr = sharpe_mod.probabilistic_sharpe(
                moments["sharpe"], config["benchmark_sharpe"],
                moments["observations"], moments["skewness"], moments["kurtosis"],
            ) if moments["status"] == "ok" else {"psr": None, "status": "unavailable",
                                                "note": moments["note"]}
            if moments.get("small_sample_warning"):
                warnings.append(
                    f"candidate {c['candidate_id']}: {moments['small_sample_warning']}")
            sharpes.append(moments["sharpe"])
            sel = selection_by_id[c["candidate_id"]]
            store.update_candidate_stats(run_id, c["candidate_id"], {
                "raw_sharpe": moments["sharpe"],
                "skewness": moments["skewness"], "kurtosis": moments["kurtosis"],
                "psr": psr["psr"], "sharpe_status": moments["status"],
                "sharpe_note": moments["note"] or psr.get("note"),
                "mean_return": float(r.mean()),
                "cumulative_return": metrics_mod.cumulative_return(r),
                "selection_frequency": sel["selection_frequency"],
                "mean_oos_rank": sel["mean_oos_rank"],
                "status": "ok" if moments["status"] == "ok" else "sharpe_unavailable",
            })

        # Run-level Sharpe deflation for the highest observed Sharpe candidate
        # (the value selection bias applies to — a descriptive focus, never a
        # recommendation).
        defined = [(j, s) for j, s in enumerate(sharpes) if s is not None]
        trial_policy = config["trial_count_policy"]
        raw_trials = len(candidates)
        if trial_policy["mode"] == "manual":
            effective_trials: Optional[float] = trial_policy["manual_value"]
        elif trial_policy["mode"] == "dependence_adjusted":
            effective_trials = dependence["effective_trials_estimate"]
        else:
            effective_trials = float(raw_trials)
        sharpe_block: Dict[str, Any] = {
            "sharpe_convention": metrics_mod.SHARPE_CONVENTION,
            "skew_convention": sharpe_mod.SKEW_CONVENTION,
            "kurtosis_convention": sharpe_mod.KURTOSIS_CONVENTION,
            "benchmark_sharpe": config["benchmark_sharpe"],
            "confidence": config["confidence"],
            "trials_raw": raw_trials,
            "trials_effective": effective_trials,
            "trial_policy": trial_policy,
            "periods_per_year": config.get("periods_per_year"),
            "focus_note": (
                "PSR/DSR/MinTRL below are computed for the candidate with the "
                "highest observed Sharpe — the value most affected by selection "
                "bias; this is a descriptive focus, not a recommendation"
            ),
        }
        run_psr = run_dsr = None
        if defined:
            focus_j = max(defined, key=lambda t: (t[1], -t[0]))[0]
            focus = candidates[focus_j]
            r = matrix[:, focus_j]
            moments = sharpe_mod.sharpe_moments(r)
            sharpe_variance = (
                float(np.var([s for _, s in defined], ddof=1))
                if len(defined) > 1 else None
            )
            psr = sharpe_mod.probabilistic_sharpe(
                moments["sharpe"], config["benchmark_sharpe"],
                moments["observations"], moments["skewness"], moments["kurtosis"])
            if effective_trials is None:
                dsr: Dict[str, Any] = {"dsr": None, "status": "unavailable",
                                       "note": dependence["effective_trials_note"],
                                       "expected_max_sharpe": None}
            elif effective_trials < sharpe_mod.MIN_TRIALS_FOR_DSR:
                dsr = {"dsr": None, "status": "unavailable",
                       "note": ("one effective trial — deflation is undefined; "
                                "the PSR against the configured benchmark applies"),
                       "expected_max_sharpe": None}
            elif sharpe_variance is None:
                dsr = {"dsr": None, "status": "unavailable",
                       "note": "cross-trial Sharpe variance needs at least 2 "
                               "candidates with a defined Sharpe",
                       "expected_max_sharpe": None}
            else:
                dsr = sharpe_mod.deflated_sharpe(
                    moments["sharpe"], moments["observations"],
                    moments["skewness"], moments["kurtosis"],
                    effective_trials, sharpe_variance)
            mintrl = sharpe_mod.minimum_track_record_length(
                moments["sharpe"], config["benchmark_sharpe"],
                moments["skewness"], moments["kurtosis"], config["confidence"],
                config.get("periods_per_year"),
            ) if moments["status"] == "ok" else {"min_track_record": None,
                                                "status": "unavailable",
                                                "note": moments["note"]}
            sharpe_block.update({
                "focus_candidate_id": focus["candidate_id"],
                "observed_sharpe": moments["sharpe"],
                "observations": moments["observations"],
                "skewness": moments["skewness"], "kurtosis": moments["kurtosis"],
                "small_sample_warning": moments.get("small_sample_warning"),
                "sharpe_variance": sharpe_variance,
                "psr": psr, "dsr": dsr, "min_track_record": mintrl,
            })
            run_psr, run_dsr = psr["psr"], dsr["dsr"]
        else:
            sharpe_block.update({
                "focus_candidate_id": None, "observed_sharpe": None,
                "observations": None, "skewness": None, "kurtosis": None,
                "sharpe_variance": None,
                "psr": {"psr": None, "status": "unavailable",
                        "note": "no candidate has a defined Sharpe ratio"},
                "dsr": {"dsr": None, "status": "unavailable",
                        "note": "no candidate has a defined Sharpe ratio"},
                "min_track_record": {"min_track_record": None,
                                     "status": "unavailable",
                                     "note": "no candidate has a defined Sharpe ratio"},
            })
            warnings.append("no candidate has a defined Sharpe ratio")

        mt_entries = [{"candidate_id": c["candidate_id"],
                       "raw_p": c["nominal_p_value"],
                       "provenance": c["p_value_provenance"]}
                      for c in candidates]
        mt_rows = mt_mod.adjust_p_values(mt_entries, config["alpha"])

        persisted_records = [
            {k: v for k, v in r.items() if not k.startswith("_")} for r in records
        ]
        result_fp = fp_mod.result_fingerprint(
            configuration_fp=run["configuration_fingerprint"],
            split_results=persisted_records, pbo_aggregate=aggregate,
            sharpe_diagnostics=sharpe_block, multiple_testing=mt_rows,
            dependence=dependence, warnings=warnings, status="completed",
        )
    except (OverfittingError, CandidateInputError, cscv_mod.CSCVError,
            sharpe_mod.SharpeError, mt_mod.MultipleTestingError,
            dep_mod.DependenceError, metrics_mod.MetricError) as exc:
        store.update_run(run_id, {
            "status": "failed", "error_message": str(exc),
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        })
        return get_run(run_id)

    store.replace_splits(run_id, persisted_records)
    store.replace_multiple_testing(run_id, mt_rows)
    store.update_run(run_id, {
        "status": "completed",
        "valid_split_count": aggregate["valid_split_count"],
        "invalid_split_count": aggregate["invalid_split_count"],
        "pbo_estimate": aggregate["pbo_estimate"],
        "psr": run_psr, "dsr": run_dsr,
        "benchmark_sharpe": config["benchmark_sharpe"],
        "effective_trial_count": effective_trials,
        "blocks_json": json.dumps(blocks),
        "pbo_aggregate_json": json.dumps(aggregate),
        "sharpe_diagnostics_json": json.dumps(sharpe_block),
        "dependence_json": json.dumps(dependence),
        "warnings_json": json.dumps(warnings),
        "result_fingerprint": result_fp,
        "completed_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "error_message": None,
    })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Overfitting diagnostics: {run['name']}",
            module="overfitting_diagnostics",
            experiment_type=f"cscv_pbo_{metric}",
            status="completed",
            parameters={
                "metric": metric, "block_count": run["block_count"],
                "candidate_count": run["candidate_count"],
                "trial_count_policy": config["trial_count_policy"],
                "multiple_testing_methods": config["multiple_testing_methods"],
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "pbo_estimate": aggregate["pbo_estimate"],
                "valid_splits": aggregate["valid_split_count"],
                "psr": run_psr, "dsr": run_dsr,
                "effective_trials": effective_trials,
            },
            tags=["overfitting-diagnostics", metric],
            source="overfitting_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"overfitting-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    window = (f"{run['timestamps'][0]}..{run['timestamps'][-1]}"
              if run["timestamps"] else "none")
    return "|".join([
        f"ds:{run['dataset_version_id'] or 'none'}",
        f"uni:{run['universe_fingerprint'][:16]}",
        run["metric"], f"S:{run['block_count']}", f"win:{window}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"overfitting-diagnostic run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["invalid_split_count"] > 0:
        raise ConflictError("baselines require a run with no invalid CSCV splits")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    scope = _baseline_scope(run)
    store.update_run(run_id, {"baseline_scope": scope})
    store.mark_baseline(run_id, scope)
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
        raise OverfittingError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    comparability: List[str] = []
    if a["universe_fingerprint"] != b["universe_fingerprint"]:
        comparability.append(
            "candidate universes differ — PBO values are not directly comparable")
    if a["metric"] != b["metric"]:
        comparability.append("metrics differ — rankings are not directly comparable")
    if a["block_count"] != b["block_count"]:
        comparability.append("CSCV block counts differ")
    if a["timestamps"][:1] != b["timestamps"][:1] or a["timestamps"][-1:] != b["timestamps"][-1:]:
        comparability.append("observation windows differ")
    if (a["configuration"].get("periods_per_year")
            != b["configuration"].get("periods_per_year")):
        comparability.append("annualization declarations differ")
    if (a["configuration"]["trial_count_policy"]
            != b["configuration"]["trial_count_policy"]):
        comparability.append("trial-count assumptions differ")
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "metric", "block_count", "candidate_count", "observation_count",
        "combination_count", "valid_split_count", "invalid_split_count",
        "status", "dataset_name", "benchmark_sharpe", "effective_trial_count")]
    diagnostics = [
        _entry("pbo_estimate", a.get("pbo_estimate"), b.get("pbo_estimate")),
        _entry("psr", a.get("psr"), b.get("psr")),
        _entry("dsr", a.get("dsr"), b.get("dsr")),
        _entry("lambda_mean",
               ((a.get("pbo_aggregate") or {}).get("lambda_stats") or {}).get("mean"),
               ((b.get("pbo_aggregate") or {}).get("lambda_stats") or {}).get("mean")),
        _entry("oos_loss_fraction", (a.get("pbo_aggregate") or {}).get("oos_loss_fraction"),
               (b.get("pbo_aggregate") or {}).get("oos_loss_fraction")),
        _entry("mean_abs_correlation", (a.get("dependence") or {}).get("mean_abs_correlation"),
               (b.get("dependence") or {}).get("mean_abs_correlation")),
    ]
    a_sel = {e["candidate_id"]: e for e in (a.get("pbo_aggregate") or {}).get("selection", [])}
    b_sel = {e["candidate_id"]: e for e in (b.get("pbo_aggregate") or {}).get("selection", [])}
    ordered = list(a_sel) + [cid for cid in b_sel if cid not in a_sel]
    selection = [{
        "candidate_id": cid,
        "availability": ("both" if cid in a_sel and cid in b_sel
                         else ("only_in_a" if cid in a_sel else "only_in_b")),
        "a_selection_frequency": a_sel.get(cid, {}).get("selection_frequency"),
        "b_selection_frequency": b_sel.get(cid, {}).get("selection_frequency"),
        "a_mean_oos_rank": a_sel.get(cid, {}).get("mean_oos_rank"),
        "b_mean_oos_rank": b_sel.get(cid, {}).get("mean_oos_rank"),
    } for cid in ordered]
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity, "diagnostics": diagnostics},
        "selection": selection,
        "fingerprint_match": {
            "universe": a["universe_fingerprint"] == b["universe_fingerprint"],
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    candidates: Dict[int, Any] = {}
    splits: Dict[int, Any] = {}
    multiple_testing: Dict[int, Any] = {}
    for r in runs:
        candidates[r["id"]] = store.list_candidates(r["id"])
        splits[r["id"]] = store.all_splits(r["id"])
        multiple_testing[r["id"]] = store.list_multiple_testing(r["id"])
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "runs": runs,
        "candidates": candidates,
        "pbo_splits": splits,
        "multiple_testing": multiple_testing,
    }


__all__ = [
    "TIE_POLICY", "TRIAL_MODES", "MULTIPLE_TESTING_METHODS",
    "OverfittingError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "compare_runs", "export",
]
