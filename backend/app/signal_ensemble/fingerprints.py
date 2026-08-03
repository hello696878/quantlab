"""
Deterministic SHA-256 fingerprints for signal-ensemble diagnostics (v1).

Six kinds — signal universe, combination policy, similarity policy,
analysis policy, configuration and result — over canonical JSON with
12-decimal float quantisation (the Phase 60 ``_clean`` helper is reused,
not duplicated).  NaN and Infinity are rejected; no database ids, creation
timestamps, runtime durations or local paths ever enter a fingerprint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import sha256_hex
from app.signal_decay.fingerprints import FingerprintError, _clean

__all__ = [
    "FingerprintError", "universe_fingerprint",
    "combination_policy_fingerprint", "similarity_policy_fingerprint",
    "analysis_policy_fingerprint", "configuration_fingerprint",
    "result_fingerprint",
]


def universe_fingerprint(universe: Dict[str, Any],
                         definition_fingerprints: Dict[str, str],
                         dataset_identity: Optional[Dict[str, Any]]
                         ) -> str:
    observations = universe["observations"]
    return sha256_hex(_clean({
        "kind": "signal_universe_v1",
        "signal_ids": universe["signal_ids"],
        "signal_definition_fingerprints": definition_fingerprints,
        "entities": universe["entities"],
        "frequency": universe["frequency"],
        "alignment_policy": universe["alignment_policy"],
        "missing_policy": universe["missing_policy"],
        "dataset_identity": dataset_identity or {},
        "observations": {
            signal_id: [{
                "entity_id": row["entity_id"],
                "source_timestamp": row["source_timestamp"],
                "available_at": row["available_at"],
                "value": row["raw_value"],
                "universe_membership_id":
                    row.get("universe_membership_id"),
            } for row in rows]
            for signal_id, rows in observations.items()},
    }))


def combination_policy_fingerprint(policy: Dict[str, Any],
                                   orientations: Dict[str, str],
                                   normalisation: Dict[str, Dict[str, Any]]
                                   ) -> str:
    return sha256_hex(_clean({
        "kind": "signal_combination_policy_v1",
        "mode": policy["mode"],
        "orientations": orientations,
        "normalisation": normalisation,
        "configured_weights": policy["configured_weights"],
        "weight_normalisation": policy["weight_normalisation"],
        "allow_negative_weights": policy["allow_negative_weights"],
        "missing_component_policy": policy["missing_component_policy"],
        "minimum_component_count": policy["minimum_component_count"],
        "tie_policy": policy["tie_policy"],
    }))


def similarity_policy_fingerprint(policy: Dict[str, Any],
                                  alignment_policy: str) -> str:
    return sha256_hex(_clean({
        "kind": "signal_similarity_policy_v1",
        "correlation_methods": list(policy["correlation_methods"]),
        "matrix_method": policy["matrix_method"],
        "alignment_policy": alignment_policy,
        "minimum_pair_overlap": policy["minimum_pair_overlap"],
        "tail_quantile": policy["tail_quantile"],
        "agreement_bucket_count": policy["agreement_bucket_count"],
        "distance_formula": policy["distance_formula"],
        "clustering": policy.get("clustering"),
    }))


def analysis_policy_fingerprint(policy: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_ensemble_analysis_policy_v1",
        "horizons": [str(h) for h in policy.get("horizons") or []],
        "entry_lags": list(policy.get("entry_lags") or []),
        "outcome": policy.get("outcome"),
        "bucket": policy.get("bucket"),
        "turnover": policy.get("turnover"),
        "reference_notional": policy.get("reference_notional"),
        "regime_policy": policy.get("regime_policy"),
        "validation_policy": policy.get("validation_policy"),
        "factor_residual_policy": policy.get("factor_residual_policy"),
        "multiple_testing": policy.get("multiple_testing"),
        "bootstrap": policy.get("bootstrap"),
        "sensitivity": policy.get("sensitivity"),
        "reconciliation_tolerance": policy["reconciliation_tolerance"],
        "leave_one_out": policy.get("leave_one_out", True),
    }))


def configuration_fingerprint(universe_fp: str, combination_fp: str,
                              similarity_fp: str, analysis_fp: str,
                              linked: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_ensemble_configuration_v1",
        "universe_fingerprint": universe_fp,
        "combination_policy_fingerprint": combination_fp,
        "similarity_policy_fingerprint": similarity_fp,
        "analysis_policy_fingerprint": analysis_fp,
        "linked": {
            "dataset_identity": linked.get("dataset_identity"),
            "signal_decay_identity": linked.get("signal_decay_identity"),
            "feature_identity": linked.get("feature_identity"),
            "meta_label_identity": linked.get("meta_label_identity"),
            "validation_identity": linked.get("validation_identity"),
            "regime_identity": linked.get("regime_identity"),
            "cost_identity": linked.get("cost_identity"),
            "factor_identity": linked.get("factor_identity"),
        },
    }))


def result_fingerprint(*, aligned_keys: Sequence[Sequence[str]],
                       pairwise_rows: Sequence[Dict[str, Any]],
                       distance: Optional[Dict[str, Any]],
                       clustering: Optional[Dict[str, Any]],
                       matrix_diagnostics: Optional[Dict[str, Any]],
                       redundancy: Optional[Dict[str, Any]],
                       combined_observations: Sequence[Dict[str, Any]],
                       component_rows: Sequence[Dict[str, Any]],
                       horizon_rows: Sequence[Dict[str, Any]],
                       leave_one_out: Sequence[Dict[str, Any]],
                       turnover: Optional[Dict[str, Any]],
                       cost: Optional[Dict[str, Any]],
                       regimes: Sequence[Dict[str, Any]],
                       held_out: Optional[Dict[str, Any]],
                       bootstrap_rows: Sequence[Dict[str, Any]],
                       sensitivity_rows: Sequence[Dict[str, Any]],
                       warnings: Sequence[str],
                       integrity_status: str,
                       completeness_status: str) -> str:
    return sha256_hex(_clean({
        "kind": "signal_ensemble_result_v1",
        "aligned_keys": [list(k) for k in aligned_keys],
        "pairwise_rows": [dict(r) for r in pairwise_rows],
        "distance": distance,
        "clustering": clustering,
        "matrix_diagnostics": matrix_diagnostics,
        "redundancy": redundancy,
        "combined_observations": [dict(r) for r in combined_observations],
        "component_rows": [dict(r) for r in component_rows],
        "horizon_rows": [dict(r) for r in horizon_rows],
        "leave_one_out": [dict(r) for r in leave_one_out],
        "turnover": turnover,
        "cost": cost,
        "regimes": [dict(r) for r in regimes],
        "held_out": held_out,
        "bootstrap": [dict(r) for r in bootstrap_rows],
        "sensitivity": [dict(r) for r in sensitivity_rows],
        "warnings": list(warnings),
        "integrity_status": integrity_status,
        "completeness_status": completeness_status,
    }))
