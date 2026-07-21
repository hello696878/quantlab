"""
Deterministic SHA-256 fingerprints for overfitting-diagnostic runs (shared
canonical JSON: sorted keys, NaN/Infinity rejected, no DB ids, no wall-clock
timestamps, no runtime durations, no paths).  Integrity aids only — they
prove what was recorded, never that a strategy works.

Numeric values are quantized to 12 decimal places before hashing (documented
boundary: perturbations below ~5e-13 do not change a fingerprint — the
quantization exists for cross-platform hash stability).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import FingerprintError, sha256_hex

UNIVERSE_FP_VERSION = "overfitting_universe_v1"
CONFIG_FP_VERSION = "overfitting_config_v1"
RESULT_FP_VERSION = "overfitting_result_v1"


def universe_fingerprint(
    *,
    candidate_ids: Sequence[str],
    candidate_config_fps: Sequence[Optional[str]],
    timestamps: Sequence[str],
    returns_matrix: Sequence[Sequence[float]],
    alignment_policy: str,
    nominal_p_values: Optional[Sequence[Optional[float]]] = None,
) -> str:
    """Identity of the candidate universe.

    ``nominal_p_values`` are declared per-candidate inputs that change the
    persisted multiple-testing results, so they belong to the universe
    identity: without them two runs that produce provably different
    Bonferroni/Holm/BH outputs would share a fingerprint and be presented as
    reproducibility evidence for one another.
    """
    payload = {
        "fp_version": UNIVERSE_FP_VERSION,
        "candidate_ids": list(candidate_ids),
        "candidate_configuration_fingerprints": list(candidate_config_fps),
        "timestamps": list(timestamps),
        "returns": [[round(v, 12) for v in row] for row in returns_matrix],
        "alignment_policy": alignment_policy,
        "nominal_p_values": (
            None if nominal_p_values is None
            else [None if p is None else round(float(p), 12) for p in nominal_p_values]
        ),
    }
    return sha256_hex(payload)


def configuration_fingerprint(
    *,
    universe_fp: str,
    metric: str,
    block_count: int,
    cscv_policy: Dict[str, Any],
    tie_policy: str,
    rank_convention: str,
    sharpe_convention: str,
    benchmark_sharpe: float,
    trial_count_policy: Dict[str, Any],
    confidence: float,
    alpha: float,
    multiple_testing_methods: Sequence[str],
    dependence_config: Dict[str, Any],
    periods_per_year: Optional[float],
) -> str:
    payload = {
        "fp_version": CONFIG_FP_VERSION,
        "universe_fingerprint": universe_fp,
        "metric": metric,
        "metric_direction": "higher_is_better",
        "block_count": block_count,
        "cscv_policy": cscv_policy,
        "tie_policy": tie_policy,
        "rank_convention": rank_convention,
        "sharpe_convention": sharpe_convention,
        "annualization": {"periods_per_year": periods_per_year,
                          "policy": "display/calendar conversion only — never silent"},
        "benchmark_sharpe": round(benchmark_sharpe, 12),
        "trial_count_policy": trial_count_policy,
        "confidence": round(confidence, 12),
        "alpha": round(alpha, 12),
        "multiple_testing_methods": list(multiple_testing_methods),
        "dependence": dependence_config,
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    configuration_fp: str,
    split_results: Sequence[Dict[str, Any]],
    pbo_aggregate: Dict[str, Any],
    sharpe_diagnostics: Dict[str, Any],
    multiple_testing: Sequence[Dict[str, Any]],
    dependence: Dict[str, Any],
    warnings: Sequence[str],
    status: str,
) -> str:
    def _round(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 12)
        if isinstance(value, dict):
            return {k: _round(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_round(v) for v in value]
        return value

    payload = {
        "fp_version": RESULT_FP_VERSION,
        "configuration_fingerprint": configuration_fp,
        "split_results": _round([
            {k: s.get(k) for k in (
                "split_id", "status", "is_block_ids", "oos_block_ids",
                "selected_candidate_id", "is_metric", "oos_metric", "oos_rank",
                "relative_rank", "lambda", "degradation", "tie_in_sample",
                "tie_out_of_sample")}
            for s in split_results
        ]),
        "pbo_aggregate": _round(pbo_aggregate),
        "sharpe_diagnostics": _round(sharpe_diagnostics),
        "multiple_testing": _round(list(multiple_testing)),
        "dependence": _round(dependence),
        "warnings": list(warnings),
        "status": status,
    }
    return sha256_hex(payload)


__all__: List[str] = [
    "UNIVERSE_FP_VERSION", "CONFIG_FP_VERSION", "RESULT_FP_VERSION",
    "FingerprintError", "universe_fingerprint", "configuration_fingerprint",
    "result_fingerprint",
]
