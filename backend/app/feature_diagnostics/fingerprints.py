"""
Deterministic SHA-256 fingerprints for feature-diagnostics runs (shared
canonical JSON: sorted keys, NaN/Infinity rejected, no DB ids, no wall-clock
timestamps, no paths, no serialized model bytes).  Integrity aids only —
not proof of model correctness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import FingerprintError, sha256_hex

CONFIG_FP_VERSION = "feature_diagnostics_config_v1"
RESULT_FP_VERSION = "feature_diagnostics_result_v1"
BASELINE_FP_VERSION = "feature_diagnostics_baseline_v1"


def configuration_fingerprint(
    *,
    method: str,
    model_type: str,
    hyperparameters: Dict[str, Any],
    target_type: str,
    metric: str,
    metric_direction: str,
    feature_names: Sequence[str],
    samples: Sequence[Dict[str, Any]],
    split_source: str,
    validation_run_fp: Optional[str],
    declared_splits: Optional[Sequence[Dict[str, Any]]],
    permutation_repeats: int,
    seed: int,
    correlation_config: Dict[str, Any],
    drift_config: Dict[str, Any],
    missing_value_policy: str,
    encoding_policy: str,
) -> str:
    payload = {
        "fp_version": CONFIG_FP_VERSION,
        "method": method,
        "model_type": model_type,
        "hyperparameters": hyperparameters,
        "target_type": target_type,
        "metric": metric,
        "metric_direction": metric_direction,
        "feature_names": list(feature_names),
        "samples": [
            [s["sample_id"], s["timestamp"],
             [round(s["features"][n], 10) for n in feature_names],
             round(s["target"], 10)]
            for s in samples
        ],
        "split_source": split_source,
        "validation_run_fingerprint": validation_run_fp,
        "declared_splits": [
            [d["split_id"], sorted(d["train_sample_ids"]), sorted(d["test_sample_ids"])]
            for d in declared_splits
        ] if declared_splits else None,
        "permutation_repeats": permutation_repeats,
        "seed": seed,
        "correlation": correlation_config,
        "drift": drift_config,
        "missing_value_policy": missing_value_policy,
        "encoding_policy": encoding_policy,
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    configuration_fp: str,
    split_results: Sequence[Dict[str, Any]],
    aggregates: Sequence[Dict[str, Any]],
    stability: Dict[str, Any],
    correlation: Dict[str, Any],
    distribution_drift: Sequence[Dict[str, Any]],
    importance_drift: Dict[str, Any],
    warnings: Sequence[str],
    integrity_status: str,
) -> str:
    def _round(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 10)
        if isinstance(value, dict):
            return {k: _round(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_round(v) for v in value]
        return value

    payload = {
        "fp_version": RESULT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "split_results": _round([
            {"split_id": s["split_id"], "status": s["status"],
             "baseline_score": s.get("baseline_score"),
             "features": s.get("features")}
            for s in split_results
        ]),
        "aggregates": _round(list(aggregates)),
        "stability": _round(stability),
        "correlation": _round(correlation),
        "distribution_drift": _round(list(distribution_drift)),
        "importance_drift": _round(importance_drift),
        "warnings": list(warnings),
        "integrity_status": integrity_status,
    }
    return sha256_hex(payload)


def baseline_fingerprint(
    *, result_fp: str, scope: Dict[str, Any], notes: str = ""
) -> str:
    payload = {
        "fp_version": BASELINE_FP_VERSION,
        "result_fingerprint": result_fp,
        "scope": scope,
        "notes": notes,
    }
    return sha256_hex(payload)


__all__: List[str] = [
    "CONFIG_FP_VERSION", "RESULT_FP_VERSION", "BASELINE_FP_VERSION",
    "FingerprintError", "configuration_fingerprint", "result_fingerprint",
    "baseline_fingerprint",
]
