"""
Deterministic SHA-256 fingerprints for meta-label runs (shared canonical JSON:
sorted keys, NaN/Infinity rejected, no DB ids, no wall-clock timestamps, no
paths).  Integrity aids only — not proof of model correctness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import FingerprintError, sha256_hex

CONFIG_FP_VERSION = "meta_labeling_config_v1"
RESULT_FP_VERSION = "meta_labeling_result_v1"
POLICY_FP_VERSION = "meta_labeling_policy_v1"


def configuration_fingerprint(
    *,
    label_policy: Dict[str, Any],
    observations: Sequence[Dict[str, Any]],
    calibration_method: str,
    calibration_settings: Dict[str, Any],
    oof_policy: str,
    threshold_grid: Dict[str, Any],
    validation_run_fp: Optional[str] = None,
    random_seed: Optional[int] = None,
) -> str:
    payload = {
        "fp_version": CONFIG_FP_VERSION,
        "label_policy": label_policy,
        "side_convention": {"-1": "negative/short", "0": "abstain", "1": "positive/long"},
        "observations": [
            [o["sample_id"], o["prediction_time"], o["evaluation_time"],
             o["primary_side"], o.get("raw_probability")]
            for o in observations
        ],
        "calibration_method": calibration_method,
        "calibration_settings": calibration_settings,
        "oof_policy": oof_policy,
        "threshold_grid": threshold_grid,
        "validation_run_fingerprint": validation_run_fp,
        "random_seed": random_seed,
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    configuration_fp: str,
    calibration_params: Optional[Dict[str, Any]],
    raw_probabilities: Sequence[float],
    calibrated_probabilities: Sequence[float],
    labels: Sequence[int],
    metrics: Dict[str, Any],
    bins: List[Dict[str, Any]],
) -> str:
    payload = {
        "fp_version": RESULT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "calibration_params": calibration_params,
        "raw_probabilities": [round(p, 10) for p in raw_probabilities],
        "calibrated_probabilities": [round(p, 10) for p in calibrated_probabilities],
        "labels": list(labels),
        "metrics": metrics,
        "bins": bins,
    }
    return sha256_hex(payload)


def policy_fingerprint(
    *,
    result_fp: str,
    threshold: float,
    abstention: Optional[Dict[str, float]],
    observed_metrics: Dict[str, Any],
) -> str:
    payload = {
        "fp_version": POLICY_FP_VERSION,
        "result_fingerprint": result_fp,
        "threshold": round(threshold, 10),
        "abstention": abstention,
        "observed_metrics": observed_metrics,
    }
    return sha256_hex(payload)


__all__ = [
    "CONFIG_FP_VERSION", "RESULT_FP_VERSION", "POLICY_FP_VERSION",
    "FingerprintError", "configuration_fingerprint", "result_fingerprint",
    "policy_fingerprint",
]
