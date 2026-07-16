"""
Deterministic SHA-256 fingerprints for validation runs, over the shared
canonical JSON (sorted keys, NaN/Infinity rejected — ``app.experiment_registry
.fingerprints``).  No database ids, no wall-clock timestamps, no paths.
Integrity aids only — they do not prove financial validity or correctness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import FingerprintError, sha256_hex

CONFIG_FP_VERSION = "model_validation_config_v1"
SPLIT_FP_VERSION = "model_validation_split_v1"
RESULT_FP_VERSION = "model_validation_result_v1"


def configuration_fingerprint(
    *,
    method: str,
    samples: Sequence[Dict[str, Any]],
    configuration: Dict[str, Any],
    random_seed: Optional[int] = None,
) -> str:
    """Identity of the split problem: method + ordered sample identity
    (id + information interval) + full split configuration (+ seed when set)."""
    payload = {
        "fp_version": CONFIG_FP_VERSION,
        "method": method,
        "samples": [
            [s["sample_id"], s["prediction_time"], s["evaluation_time"]] for s in samples
        ],
        "configuration": configuration,
        "random_seed": random_seed,
    }
    return sha256_hex(payload)


def split_fingerprint(
    *,
    configuration_fp: str,
    split_label: str,
    train_ids: List[str],
    test_ids: List[str],
    purged_ids: List[str],
    embargoed_ids: List[str],
) -> str:
    payload = {
        "fp_version": SPLIT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "split_label": split_label,
        "train_ids": sorted(train_ids),
        "test_ids": sorted(test_ids),
        "purged_ids": sorted(purged_ids),
        "embargoed_ids": sorted(embargoed_ids),
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    configuration_fp: str,
    split_fps: List[str],
    aggregate_metrics: Dict[str, Any],
    leakage_summary: Dict[str, Any],
    dataset_identity: Optional[str] = None,
    experiment_identity: Optional[str] = None,
) -> str:
    payload = {
        "fp_version": RESULT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "split_fingerprints": list(split_fps),
        "aggregate_metrics": aggregate_metrics,
        "leakage_summary": leakage_summary,
        "dataset_identity": dataset_identity,
        "experiment_identity": experiment_identity,
    }
    return sha256_hex(payload)


__all__ = [
    "CONFIG_FP_VERSION",
    "SPLIT_FP_VERSION",
    "RESULT_FP_VERSION",
    "FingerprintError",
    "configuration_fingerprint",
    "split_fingerprint",
    "result_fingerprint",
]
