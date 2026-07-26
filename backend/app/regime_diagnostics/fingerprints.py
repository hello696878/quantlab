"""
Deterministic SHA-256 fingerprints for regime-diagnostic runs (shared
canonical JSON: sorted keys, NaN/Infinity rejected; no DB ids, creation
timestamps, runtime durations, or paths).  Numeric values are quantized to
12 decimal places for cross-platform hash stability.  Integrity aids only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import FingerprintError, sha256_hex

UNIVERSE_FP_VERSION = "regime_universe_v1"
CONFIG_FP_VERSION = "regime_config_v1"
RESULT_FP_VERSION = "regime_result_v1"


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return value


def universe_fingerprint(
    *,
    candidate_ids: Sequence[str],
    timestamps: Sequence[str],
    frequency: str,
    outcome_matrix: Sequence[Sequence[float]],
    market_features: Dict[str, Sequence[float]],
    sample_ids: Optional[Sequence[str]],
    alignment_policy: str,
) -> str:
    payload = {
        "fp_version": UNIVERSE_FP_VERSION,
        "candidate_ids": list(candidate_ids),
        "timestamps": list(timestamps),
        "frequency": frequency,
        "outcomes": _round([list(row) for row in outcome_matrix]),
        "market_features": {k: _round(list(v))
                            for k, v in sorted(market_features.items())},
        "sample_ids": list(sample_ids) if sample_ids else None,
        "alignment_policy": alignment_policy,
    }
    return sha256_hex(payload)


def configuration_fingerprint(
    *,
    universe_fp: str,
    definition_fps: Sequence[str],
    metric_policy: Dict[str, Any],
    transition_settings: Dict[str, Any],
    validation_run_fp: Optional[str],
    overfitting_universe_fp: Optional[str],
) -> str:
    payload = {
        "fp_version": CONFIG_FP_VERSION,
        "universe_fingerprint": universe_fp,
        "regime_definition_fingerprints": list(definition_fps),
        "metric_policy": _round(metric_policy),
        "transition_settings": _round(transition_settings),
        "validation_run_fingerprint": validation_run_fp,
        "overfitting_universe_fingerprint": overfitting_universe_fp,
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    configuration_fp: str,
    assignments: Dict[str, Sequence[Optional[str]]],
    conditional_results: Sequence[Dict[str, Any]],
    robustness: Sequence[Dict[str, Any]],
    rank_stability: Dict[str, Any],
    concentration: Sequence[Dict[str, Any]],
    transitions: Dict[str, Any],
    warnings: Sequence[str],
    integrity_status: str,
) -> str:
    payload = {
        "fp_version": RESULT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "assignments": {k: list(v) for k, v in sorted(assignments.items())},
        "conditional_results": _round(list(conditional_results)),
        "robustness": _round(list(robustness)),
        "rank_stability": _round(rank_stability),
        "concentration": _round(list(concentration)),
        "transitions": _round(transitions),
        "warnings": list(warnings),
        "integrity_status": integrity_status,
    }
    return sha256_hex(payload)


__all__: List[str] = [
    "UNIVERSE_FP_VERSION", "CONFIG_FP_VERSION", "RESULT_FP_VERSION",
    "FingerprintError", "universe_fingerprint", "configuration_fingerprint",
    "result_fingerprint",
]
