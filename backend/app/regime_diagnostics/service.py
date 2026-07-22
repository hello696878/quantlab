"""
Service layer: run lifecycle, no-look-ahead label assignment, conditional
metrics, robustness/rank/concentration/transition diagnostics, baselines,
comparison, and export.

Run-level integrity is the **least-trusted** integrity among the run's valid
definitions (invalid definitions are counted separately and excluded from
diagnostics).  Multiple-comparison corrections are deliberately NOT applied
in v1: the lab implements no hypothesis test, fabricates no p-values, and
reports descriptive effect sizes only with significance marked unavailable —
the Phase 53 corrections remain available for callers who bring genuinely
tested p-values to that lab.
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
from app.meta_labeling import store as meta_store
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import store as overfitting_store
from app.regime_diagnostics import EXPORT_SCHEMA_VERSION
from app.regime_diagnostics import conditional as cond_mod
from app.regime_diagnostics import definitions as def_mod
from app.regime_diagnostics import fingerprints as fp_mod
from app.regime_diagnostics import transitions as trans_mod
from app.regime_diagnostics.core import (
    ALIGNMENT_POLICY, RegimeInputError, build_outcome_matrix,
    normalize_candidates, normalize_market_features, normalize_sample_ids,
    normalize_timeline,
)

_TRUST_ORDER = def_mod._TRUST_ORDER


class RegimeError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


BASELINE_ACCEPTABLE_INTEGRITY = (
    "verified_causal_rule", "verified_from_validation_split", "declared",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.regime_diagnostics import store  # noqa: E402  (after error classes)


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    try:
        timeline = normalize_timeline(payload.get("timestamps") or [],
                                      payload.get("frequency"))
        n_periods = len(timeline["timestamps"])
        candidates = normalize_candidates(payload.get("candidates") or [], n_periods)
        market_features = normalize_market_features(
            payload.get("market_features"), n_periods)
        sample_ids = normalize_sample_ids(payload.get("sample_ids"), n_periods)
    except RegimeInputError as exc:
        raise RegimeError(str(exc))

    raw_definitions = payload.get("definitions") or []
    if not isinstance(raw_definitions, list) or not raw_definitions:
        raise RegimeError("at least one regime definition is required")
    if len(raw_definitions) > def_mod.MAX_DEFINITIONS:
        raise RegimeError(f"at most {def_mod.MAX_DEFINITIONS} definitions are supported")
    definitions: List[Dict[str, Any]] = []
    ids: List[str] = []
    try:
        for d in raw_definitions:
            validated = def_mod.validate_definition(d, list(market_features), ids)
            definitions.append(validated)
            ids.append(validated["definition_id"])
        for d in definitions:
            if d["dimension"] == "combined":
                by_id = {x["definition_id"]: x for x in definitions}
                for source in d["sources"]:
                    if source not in by_id:
                        raise def_mod.RegimeDefinitionError(
                            f"combined definition {d['definition_id']}: unknown "
                            f"source {source!r}")
                    if by_id[source]["dimension"] == "combined":
                        raise def_mod.RegimeDefinitionError(
                            "combined definitions cannot source other combined "
                            "definitions")
    except def_mod.RegimeDefinitionError as exc:
        raise RegimeError(str(exc))

    needs_validation = [d for d in definitions
                        if d.get("threshold_mode") == "training_quantile"]
    if needs_validation:
        if payload.get("validation_run_id") is None:
            raise RegimeError(
                "training_quantile definitions require validation_run_id")
        if sample_ids is None:
            raise RegimeError(
                "training_quantile definitions require per-period sample_ids "
                "mapping to the validation run's memberships")

    window = payload.get("transition_window")
    if window is None:
        window = trans_mod.DEFAULT_TRANSITION_WINDOW
    if isinstance(window, bool) or not isinstance(window, int) \
            or not (trans_mod.MIN_TRANSITION_WINDOW <= window
                    <= trans_mod.MAX_TRANSITION_WINDOW):
        raise RegimeError(
            f"transition_window must be an integer in "
            f"[{trans_mod.MIN_TRANSITION_WINDOW}, {trans_mod.MAX_TRANSITION_WINDOW}]"
        )

    validation_run_fp = None
    if payload.get("validation_run_id") is not None:
        vrun = validation_store.get_run(payload["validation_run_id"])
        if vrun is None:
            raise NotFoundError(f"validation run {payload['validation_run_id']} not found")
        validation_run_fp = vrun["configuration_fingerprint"]
    overfitting_universe_fp = None
    if payload.get("overfitting_run_id") is not None:
        orun = overfitting_store.get_run(payload["overfitting_run_id"])
        if orun is None:
            raise NotFoundError(
                f"overfitting-diagnostic run {payload['overfitting_run_id']} not found")
        overfitting_universe_fp = orun["universe_fingerprint"]
    for field, getter, label in (
        ("dataset_version_id", dataset_store.get_version, "dataset version"),
        ("experiment_id", experiment_store.get_experiment, "experiment"),
        ("feature_diagnostics_run_id", feature_store.get_run, "feature-diagnostics run"),
        ("meta_label_run_id", meta_store.get_run, "meta-label run"),
    ):
        value = payload.get(field)
        if value is not None and getter(value) is None:
            raise NotFoundError(f"{label} {value} not found")

    outcome_matrix = build_outcome_matrix(candidates)
    candidate_ids = [c["candidate_id"] for c in candidates]
    universe_fp = fp_mod.universe_fingerprint(
        candidate_ids=candidate_ids, timestamps=timeline["timestamps"],
        frequency=timeline["frequency"],
        outcome_matrix=[c["outcomes"] for c in candidates],
        market_features=market_features, sample_ids=sample_ids,
        alignment_policy=ALIGNMENT_POLICY,
    )
    definition_records = []
    for d in definitions:
        definition_records.append({
            **d,
            "definition": d,
            "definition_fingerprint": def_mod.definition_fingerprint(d),
        })
    metric_policy = {
        "sharpe_convention": "per-period mean/std(ddof=1); never annualized",
        "cumulative_convention": "compounded for outcome_kind 'return', summed otherwise",
        "max_drawdown": "omitted in v1 — non-contiguous regime observations have "
                        "no honest drawdown semantics",
        "min_observations_default": def_mod.MIN_REGIME_OBSERVATIONS_DEFAULT,
        "multiple_comparisons": (
            "descriptive effect sizes only — no hypothesis test is implemented, "
            "no p-values are fabricated, significance is unavailable in v1"
        ),
    }
    transition_settings = {"window": window,
                           "max_recorded": trans_mod.MAX_RECORDED_TRANSITIONS}
    config_fp = fp_mod.configuration_fingerprint(
        universe_fp=universe_fp,
        definition_fps=[d["definition_fingerprint"] for d in definition_records],
        metric_policy=metric_policy, transition_settings=transition_settings,
        validation_run_fp=validation_run_fp,
        overfitting_universe_fp=overfitting_universe_fp,
    )
    configuration = {
        "alignment_policy": ALIGNMENT_POLICY,
        "metric_policy": metric_policy,
        "transition_settings": transition_settings,
        "no_lookahead_policy": (
            "trailing windows only; effective label at i uses the statistic at "
            "i − lag with lag ≥ 1; centered windows and negative lags rejected"
        ),
        "definitions": [d["definition"] for d in definition_records],
    }

    run = store.insert_run({
        "name": payload["name"], "description": payload.get("description", ""),
        "candidate_count": len(candidates),
        "observation_count": len(candidates) * n_periods,
        "period_count": n_periods, "frequency": timeline["frequency"],
        "regime_definition_count": len(definition_records),
        "universe_fingerprint": universe_fp,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "timestamps": timeline["timestamps"],
        "candidates": candidates,
        "market_features": market_features,
        "sample_ids": sample_ids,
        "dataset_version_id": payload.get("dataset_version_id"),
        "validation_run_id": payload.get("validation_run_id"),
        "overfitting_run_id": payload.get("overfitting_run_id"),
        "feature_diagnostics_run_id": payload.get("feature_diagnostics_run_id"),
        "meta_label_run_id": payload.get("meta_label_run_id"),
        "experiment_id": payload.get("experiment_id"),
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""), "demo_key": demo_key,
    })
    store.replace_definitions(run["id"], [
        {**d, "status": "pending", "integrity_status": "unknown",
         "assignments": [], "thresholds_used": None,
         "threshold_fingerprint": None, "unavailable_count": 0,
         "distinct_label_count": 0, "interval_summary": {}, "transitions": {},
         "warnings": []}
        for d in definition_records
    ])
    return get_run(run["id"])


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"regime-diagnostic run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = None
    run["overfitting_name"] = run["overfitting_pbo"] = None
    run["overfitting_psr"] = run["overfitting_dsr"] = None
    run["overfitting_universe_fp"] = None
    run["feature_run_name"] = run["feature_run_integrity"] = None
    run["meta_label_run_name"] = run["meta_label_oof_status"] = None
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
    if run.get("overfitting_run_id"):
        orun = overfitting_store.get_run(run["overfitting_run_id"])
        if orun:
            run["overfitting_name"] = orun["name"]
            run["overfitting_pbo"] = orun.get("pbo_estimate")
            run["overfitting_psr"] = orun.get("psr")
            run["overfitting_dsr"] = orun.get("dsr")
            run["overfitting_universe_fp"] = orun["universe_fingerprint"]
    if run.get("feature_diagnostics_run_id"):
        frun = feature_store.get_run(run["feature_diagnostics_run_id"])
        if frun:
            run["feature_run_name"] = frun["name"]
            run["feature_run_integrity"] = frun["integrity_status"]
    if run.get("meta_label_run_id"):
        mrun = meta_store.get_run(run["meta_label_run_id"])
        if mrun:
            run["meta_label_run_name"] = mrun["name"]
            run["meta_label_oof_status"] = mrun["oof_status"]
    if run.get("experiment_id"):
        exp = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = exp["name"] if exp else None
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


def _resolve_train_indices(
    run: Dict[str, Any], split_label: str
) -> List[int]:
    """Period indices whose sample ids are in the named split's recorded
    training membership — exact memberships, leakage-clean runs only."""
    vrun = validation_store.get_run(run["validation_run_id"])
    if vrun is None:
        raise RegimeError("linked validation run no longer exists")
    if vrun["status"] != "completed" or vrun.get("leakage_clean") is not True:
        raise RegimeError(
            "verified training-only thresholds require a completed, "
            "leakage-clean validation run"
        )
    splits = validation_store.list_splits(run["validation_run_id"])
    split = next((s for s in splits if s["split_label"] == split_label), None)
    if split is None:
        raise RegimeError(f"validation split {split_label!r} not found")
    if split["status"] != "valid":
        raise RegimeError(
            f"validation split {split_label!r} is invalid — it cannot produce "
            "verified thresholds"
        )
    known: set = set()
    for s in splits:
        known.update(s["train_ids"], s["test_ids"], s["purged_ids"], s["embargoed_ids"])
    sample_ids = run["sample_ids"] or []
    unknown = sorted(set(sample_ids) - known)
    if unknown:
        raise RegimeError(
            f"{len(unknown)} period sample id(s) are not members of the linked "
            f"validation run (e.g. {unknown[:3]})"
        )
    train_set = set(split["train_ids"])
    return [i for i, sid in enumerate(sample_ids) if sid in train_set]


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"regime-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")

    t0 = time.monotonic()
    config = run["configuration"]
    n_periods = run["period_count"]
    candidates = run["candidates"]
    candidate_ids = [c["candidate_id"] for c in candidates]
    outcome_matrix = build_outcome_matrix(candidates)
    warnings: List[str] = []
    try:
        assigned: Dict[str, Dict[str, Any]] = {}
        definition_rows: List[Dict[str, Any]] = []
        for d in config["definitions"]:
            if d["dimension"] == "combined":
                continue
            train_indices = None
            if d.get("threshold_mode") == "training_quantile":
                train_indices = _resolve_train_indices(run, d["threshold_split_label"])
            result = def_mod.assign_labels(d, run["market_features"], n_periods,
                                           train_indices)
            assigned[d["definition_id"]] = result
        for d in config["definitions"]:
            if d["dimension"] != "combined":
                continue
            result = def_mod.combine_labels(
                d, assigned[d["sources"][0]], assigned[d["sources"][1]], n_periods)
            assigned[d["definition_id"]] = result

        valid_defs = [d for d in config["definitions"]
                      if assigned[d["definition_id"]]["status"] == "ok"]
        invalid_defs = [d for d in config["definitions"]
                        if assigned[d["definition_id"]]["status"] == "invalid"]
        for d in invalid_defs:
            warnings.extend(assigned[d["definition_id"]]["warnings"])
        if not valid_defs:
            raise RegimeError(
                "every regime definition is invalid — nothing to condition on "
                "(see the definition warnings)"
            )
        integrity = min(
            (assigned[d["definition_id"]]["integrity_status"] for d in valid_defs),
            key=lambda s: _TRUST_ORDER[s],
        )
        for d in valid_defs:
            warnings.extend(assigned[d["definition_id"]]["warnings"])

        coverage: Dict[str, Any] = {}
        conditional_rows: List[Dict[str, Any]] = []
        robustness: List[Dict[str, Any]] = []
        concentration: List[Dict[str, Any]] = []
        rank_blocks: Dict[str, Any] = {}
        low_coverage = 0
        observed_regimes = 0
        for d in valid_defs:
            def_id = d["definition_id"]
            labels = assigned[def_id]["labels"]
            label_indices: Dict[str, List[int]] = {}
            for i, lb in enumerate(labels):
                if lb is not None:
                    label_indices.setdefault(lb, []).append(i)
            labeled_total = sum(len(v) for v in label_indices.values())
            distinct = sorted(label_indices)
            observed_regimes += len(distinct)
            coverage[def_id] = {
                "labeled_periods": labeled_total,
                "unassigned_periods": n_periods - labeled_total,
                "per_label": {
                    lb: {"observations": len(idx),
                         "share": len(idx) / labeled_total if labeled_total else None}
                    for lb, idx in sorted(label_indices.items())
                },
            }
            min_obs = d["min_observations"]
            means_by_label: Dict[str, Dict[str, Optional[float]]] = {}
            for lb, idx in sorted(label_indices.items()):
                if len(idx) < min_obs:
                    low_coverage += 1
                    warnings.append(
                        f"definition {def_id}: regime {lb!r} has only {len(idx)} "
                        f"observation(s) — below the minimum of {min_obs}; "
                        "performance statistics withheld"
                    )
                means_by_label[lb] = {}
                for col, cid in enumerate(candidate_ids):
                    metrics = cond_mod.conditional_metrics(
                        outcome_matrix[:, col], idx, labeled_total, min_obs,
                        candidates[col]["outcome_kind"])
                    conditional_rows.append({
                        "candidate_id": cid, "definition_id": def_id,
                        "regime_label": lb, "metrics": metrics,
                    })
                    means_by_label[lb][cid] = metrics["mean"]
            for col, cid in enumerate(candidate_ids):
                rows = [r for r in conditional_rows
                        if r["candidate_id"] == cid and r["definition_id"] == def_id]
                rob = cond_mod.candidate_robustness(rows)
                robustness.append({"candidate_id": cid, "definition_id": def_id,
                                   **rob})
                outcomes_by_label = {
                    lb: outcome_matrix[list(idx), col]
                    for lb, idx in sorted(label_indices.items())
                }
                conc = cond_mod.concentration_diagnostics(rows, outcomes_by_label)
                concentration.append({"candidate_id": cid, "definition_id": def_id,
                                      **conc})
            rank_blocks[def_id] = cond_mod.rank_stability(candidate_ids, means_by_label)
            assigned[def_id]["interval_summary"] = trans_mod.interval_summary(labels)
            assigned[def_id]["transitions"] = trans_mod.detect_transitions(
                labels, run["timestamps"], outcome_matrix, candidate_ids,
                config["transition_settings"]["window"])
            assigned[def_id]["distinct_label_count"] = len(distinct)

        assignments_for_fp = {def_id: assigned[def_id]["labels"]
                              for def_id in assigned}
        result_fp = fp_mod.result_fingerprint(
            configuration_fp=run["configuration_fingerprint"],
            assignments=assignments_for_fp,
            conditional_results=[{**r} for r in conditional_rows],
            robustness=robustness, rank_stability=rank_blocks,
            concentration=concentration,
            transitions={d["definition_id"]: assigned[d["definition_id"]]["transitions"]
                         for d in valid_defs},
            warnings=warnings, integrity_status=integrity,
        )
    except (RegimeError, RegimeInputError, def_mod.RegimeDefinitionError) as exc:
        # A failed (re-)execution must not leave the PREVIOUS execution's
        # derived state behind: otherwise a run reported as failed /
        # unknown-integrity would still advertise a result fingerprint, stale
        # coverage/robustness/rank/concentration blocks and definition +
        # conditional child rows, and — worst — remain the active baseline of
        # its scope, a state mark_baseline itself would refuse to create.
        store.update_run(run_id, {
            "status": "failed", "error_message": str(exc),
            "integrity_status": "unknown",
            "result_fingerprint": None,
            "is_baseline": 0, "baseline_scope": None,
            "observed_regime_count": 0, "invalid_definition_count": 0,
            "low_coverage_warning_count": 0,
            # Empty shapes must match the response-model types:
            # coverage/rank_stability are objects, robustness/concentration
            # /warnings are arrays.
            "coverage_json": "{}", "robustness_json": "[]",
            "rank_stability_json": "{}", "concentration_json": "[]",
            "warnings_json": "[]",
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        })
        store.replace_definitions(run_id, [])
        store.replace_conditional_results(run_id, [])
        return get_run(run_id)

    definition_records = []
    for d in config["definitions"]:
        result = assigned[d["definition_id"]]
        definition_records.append({
            **d, "definition": d,
            "definition_fingerprint": def_mod.definition_fingerprint(d),
            "integrity_status": result["integrity_status"],
            "status": result["status"],
            "assignments": result["labels"],
            "thresholds_used": result["thresholds_used"],
            "threshold_fingerprint": result["threshold_fingerprint"],
            "unavailable_count": result["unavailable_count"],
            "distinct_label_count": result.get("distinct_label_count", 0),
            "interval_summary": result.get("interval_summary", {}),
            "transitions": result.get("transitions", {}),
            "warnings": result["warnings"],
        })
    store.replace_definitions(run_id, definition_records)
    store.replace_conditional_results(run_id, conditional_rows)
    store.update_run(run_id, {
        "status": "completed",
        "integrity_status": integrity,
        "observed_regime_count": observed_regimes,
        "invalid_definition_count": len(invalid_defs),
        "low_coverage_warning_count": low_coverage,
        "coverage_json": json.dumps(coverage),
        "robustness_json": json.dumps(robustness),
        "rank_stability_json": json.dumps(rank_blocks),
        "concentration_json": json.dumps(concentration),
        "warnings_json": json.dumps(warnings),
        "result_fingerprint": result_fp,
        "completed_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "error_message": None,
    })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Regime diagnostics: {run['name']}",
            module="regime_diagnostics",
            experiment_type="conditional_performance",
            status="completed",
            parameters={
                "dimensions": sorted({d["dimension"] for d in valid_defs}),
                "integrity_status": integrity,
                "candidate_count": run["candidate_count"],
                "regime_definition_count": run["regime_definition_count"],
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "observed_regimes": observed_regimes,
                "invalid_definitions": len(invalid_defs),
                "low_coverage_warnings": low_coverage,
            },
            tags=["regime-diagnostics"],
            source="regime_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"regime-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any], definition_fps: Sequence[str]) -> str:
    window = (f"{run['timestamps'][0]}..{run['timestamps'][-1]}"
              if run["timestamps"] else "none")
    from app.experiment_registry.fingerprints import sha256_hex
    defs_hash = sha256_hex({"defs": list(definition_fps)})[:16]
    return "|".join([
        f"ds:{run['dataset_version_id'] or 'none'}",
        f"uni:{run['universe_fingerprint'][:16]}",
        f"defs:{defs_hash}", f"win:{window}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"regime-diagnostic run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["invalid_definition_count"] > 0:
        raise ConflictError("baselines require a run with no invalid definitions")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            "baselines require verified or declared regime integrity — "
            f"this run is {run['integrity_status']}"
        )
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    definition_fps = [d["definition_fingerprint"]
                      for d in store.list_definitions(run_id)]
    scope = _baseline_scope(run, definition_fps)
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
        raise RegimeError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    a_defs = store.list_definitions(a_id)
    b_defs = store.list_definitions(b_id)
    comparability: List[str] = []
    if a["universe_fingerprint"] != b["universe_fingerprint"]:
        comparability.append("candidate/observation universes differ — "
                             "conditional statistics are not directly comparable")
    if (a.get("dataset_version_id") or None) != (b.get("dataset_version_id") or None):
        comparability.append("linked dataset versions differ")
    if a["timestamps"][:1] != b["timestamps"][:1] or a["timestamps"][-1:] != b["timestamps"][-1:]:
        comparability.append("observation windows differ")
    if [d["definition_fingerprint"] for d in a_defs] != \
            [d["definition_fingerprint"] for d in b_defs]:
        comparability.append("regime definitions differ")
    if sorted({d.get("threshold_mode") or "" for d in a_defs}) != \
            sorted({d.get("threshold_mode") or "" for d in b_defs}):
        comparability.append("threshold-fitting modes differ")
    if a["integrity_status"] != b["integrity_status"]:
        comparability.append("integrity states differ")
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "candidate_count", "period_count", "frequency",
        "regime_definition_count", "observed_regime_count",
        "invalid_definition_count", "low_coverage_warning_count",
        "integrity_status", "status", "dataset_name")]
    a_rob = {(r["candidate_id"], r["definition_id"]): r for r in a["robustness"]}
    b_rob = {(r["candidate_id"], r["definition_id"]): r for r in b["robustness"]}
    keys = list(a_rob) + [k for k in b_rob if k not in a_rob]
    robustness = [{
        "candidate_id": cid, "definition_id": did,
        "availability": ("both" if (cid, did) in a_rob and (cid, did) in b_rob
                         else ("only_in_a" if (cid, did) in a_rob else "only_in_b")),
        "a_classification": a_rob.get((cid, did), {}).get("classification"),
        "b_classification": b_rob.get((cid, did), {}).get("classification"),
        "a_sign_consistency": a_rob.get((cid, did), {}).get("sign_consistency"),
        "b_sign_consistency": b_rob.get((cid, did), {}).get("sign_consistency"),
    } for cid, did in keys]
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity},
        "robustness": robustness,
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
    definitions: Dict[int, Any] = {}
    conditional: Dict[int, Any] = {}
    for r in runs:
        definitions[r["id"]] = store.list_definitions(r["id"])
        conditional[r["id"]] = store.list_conditional_results(r["id"])
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "runs": runs,
        "definitions": definitions,
        "conditional_results": conditional,
    }


__all__ = [
    "BASELINE_ACCEPTABLE_INTEGRITY", "RegimeError", "NotFoundError",
    "ConflictError", "create_run", "get_run", "list_runs", "lab_summary",
    "execute_run", "invalidate_run", "mark_baseline", "compare_runs", "export",
]
