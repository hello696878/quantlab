"""
Deterministic SHA-256 fingerprints for signal-decay diagnostics (v1).

Six kinds — signal definition, observation universe, horizon policy,
analysis policy, configuration and result — over canonical JSON with
deterministic arrays.  Floats are quantized to 12 decimal places; NaN and
Infinity are rejected outright.  Content-addressed identity only: no
database ids, creation timestamps, runtime durations or paths.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import sha256_hex


class FingerprintError(ValueError):
    """Raised when non-finite or unsupported values reach a fingerprint."""


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean(v)
                for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise FingerprintError("non-finite value in fingerprint payload")
        return round(obj, 12)
    raise FingerprintError(
        f"unsupported fingerprint value type {type(obj).__name__}")


def signal_definition_fingerprint(definition: Dict[str, Any],
                                  dataset_identity: Optional[Dict[str, Any]]
                                  = None) -> str:
    return sha256_hex(_clean({
        "kind": "signal_definition_v1",
        "signal_id": definition["signal_id"],
        "signal_type": definition["signal_type"],
        "unit": definition["unit"],
        "frequency": definition["frequency"],
        "direction": definition["direction"],
        "transformation": definition["transformation"],
        "availability_policy": definition["availability_policy"],
        "tie_policy": definition["tie_policy"],
        "missing_policy": definition["missing_policy"],
        "source": definition["source"],
        "dataset_identity": dataset_identity or {},
    }))


def outcome_definition_fingerprint(outcome: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_outcome_definition_v1",
        "outcome_id": outcome["outcome_id"],
        "target_type": outcome["target_type"],
        "return_convention": outcome["return_convention"],
        "unit": outcome["unit"],
        "price_field": outcome.get("price_field"),
        "extreme_loss_policy": outcome["extreme_loss_policy"],
        "source": outcome["source"],
    }))


def observation_universe_fingerprint(observations: Sequence[Dict[str, Any]],
                                     *, prices: Optional[Dict[Any, float]],
                                     supplied: Optional[Sequence[Dict[str, Any]]],
                                     signal_fp: str,
                                     outcome_fp: str) -> str:
    return sha256_hex(_clean({
        "kind": "signal_observation_universe_v1",
        "signal_definition_fingerprint": signal_fp,
        "outcome_definition_fingerprint": outcome_fp,
        "observations": [{
            "entity_id": o["entity_id"],
            "source_timestamp": o["source_timestamp"],
            "available_at": o["available_at"],
            "value": o["raw_value"],
            "universe_membership_id": o.get("universe_membership_id"),
        } for o in observations],
        "prices": ([[entity, stamp, value]
                    for (entity, stamp), value in sorted((prices or {}).items())]
                   if prices is not None else None),
        "supplied_outcomes": ([{
            "entity_id": s["entity_id"],
            "signal_timestamp": s["signal_timestamp"],
            "period_start": s["period_start"],
            "period_end": s["period_end"],
            "available_at": s["available_at"],
            "value": s["value"],
        } for s in supplied] if supplied is not None else None),
    }))


def horizon_policy_fingerprint(horizons: Dict[str, Any],
                               bucket_config: Dict[str, Any],
                               turnover_config: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_horizon_policy_v1",
        "horizons": [str(h) for h in horizons["horizons"]],
        "unit": horizons["unit"],
        "entry_lags": list(horizons["entry_lags"]),
        "overlap_policy": horizons["overlap_policy"],
        "minimum_observations": horizons["minimum_observations"],
        "bucket": bucket_config,
        "turnover": turnover_config,
    }))


def analysis_policy_fingerprint(policy: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_analysis_policy_v1",
        "correlation_methods": list(policy["correlation_methods"]),
        "minimum_cross_section_entities":
            policy["minimum_cross_section_entities"],
        "decay": policy["decay"],
        "multiple_testing_methods": list(policy.get("multiple_testing_methods")
                                         or []),
        "multiple_testing_alpha": policy.get("multiple_testing_alpha"),
        "multiple_testing_family": policy.get("multiple_testing_family"),
        "bootstrap": policy.get("bootstrap"),
        "reference_notional": policy.get("reference_notional"),
    }))


def configuration_fingerprint(universe_fp: str, horizon_fp: str,
                              analysis_fp: str,
                              linked: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "signal_configuration_v1",
        "observation_universe_fingerprint": universe_fp,
        "horizon_policy_fingerprint": horizon_fp,
        "analysis_policy_fingerprint": analysis_fp,
        "linked": {
            "dataset_identity": linked.get("dataset_identity"),
            "feature_identity": linked.get("feature_identity"),
            "meta_label_identity": linked.get("meta_label_identity"),
            "validation_identity": linked.get("validation_identity"),
            "regime_identity": linked.get("regime_identity"),
            "cost_identity": linked.get("cost_identity"),
            "factor_identity": linked.get("factor_identity"),
        },
    }))


def result_fingerprint(*, horizon_rows: Sequence[Dict[str, Any]],
                       bucket_rows: Sequence[Dict[str, Any]],
                       turnover: Optional[Dict[str, Any]],
                       overlap: Sequence[Dict[str, Any]],
                       cost: Optional[Dict[str, Any]],
                       regimes: Sequence[Dict[str, Any]],
                       held_out: Optional[Dict[str, Any]],
                       bootstrap_rows: Sequence[Dict[str, Any]],
                       decay: Sequence[Dict[str, Any]],
                       warnings: Sequence[str],
                       integrity_status: str,
                       completeness_status: str,
                       overlap_status: str) -> str:
    return sha256_hex(_clean({
        "kind": "signal_result_v1",
        "horizon_rows": [dict(r) for r in horizon_rows],
        "bucket_rows": [dict(r) for r in bucket_rows],
        "turnover": turnover,
        "overlap": [dict(r) for r in overlap],
        "cost": ({k: v for k, v in cost.items() if k != "rows"}
                 if cost else None),
        "regimes": [dict(r) for r in regimes],
        "held_out": held_out,
        "bootstrap": [dict(r) for r in bootstrap_rows],
        "decay": [dict(r) for r in decay],
        "warnings": list(warnings),
        "integrity_status": integrity_status,
        "completeness_status": completeness_status,
        "overlap_status": overlap_status,
    }))


__all__ = [
    "FingerprintError", "signal_definition_fingerprint",
    "outcome_definition_fingerprint", "observation_universe_fingerprint",
    "horizon_policy_fingerprint", "analysis_policy_fingerprint",
    "configuration_fingerprint", "result_fingerprint",
]
