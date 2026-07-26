"""
Deterministic SHA-256 fingerprints for factor diagnostics (v1).

Five kinds — factor-definition, observation-universe, model-policy,
configuration and result — over canonical JSON with deterministic arrays.
Floats are quantized to 12 decimal places; NaN and Infinity are rejected
outright rather than serialised.

Fingerprints carry CONTENT-ADDRESSED identity only: no database row ids, no
creation timestamps, no runtime durations and no local paths, so the same
inputs under the same policy reproduce the same fingerprint in a different
database on a different machine.
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


def factor_definition_fingerprint(definition: Dict[str, Any],
                                  dataset_identity: Optional[Dict[str, Any]]
                                  = None) -> str:
    """Identity of ONE factor definition: what it is and how it is built."""
    return sha256_hex(_clean({
        "kind": "factor_definition_v1",
        "factor_id": definition["factor_id"],
        "category": definition["category"],
        "unit": definition["unit"],
        "transformed_unit": definition["transformed_unit"],
        "frequency": definition["frequency"],
        "transformation": definition["transformation"],
        "lag": definition["lag"],
        "availability_policy": definition["availability_policy"],
        "missing_policy": definition["missing_policy"],
        "standardisation_policy": definition["standardisation_policy"],
        "standardisation_window": definition["standardisation_window"],
        "winsorisation_policy": definition["winsorisation_policy"],
        "source": definition["source"],
        "dataset_identity": dataset_identity or {},
    }))


def target_fingerprint(target: Dict[str, Any]) -> str:
    """Identity of the analysed return series (values included)."""
    return sha256_hex(_clean({
        "kind": "factor_target_series_v1",
        "target_id": target["target_id"],
        "target_type": target["target_type"],
        "source": target["source"],
        "source_identity": target.get("source_identity") or {},
        "return_convention": target["return_convention"],
        "frequency": target["frequency"],
        "currency": target["currency"],
        "periods": [{
            "period_start": p["period_start"],
            "period_end": p["period_end"],
            "information_available_at": p["information_available_at"],
            "target_return": p["target_return"],
        } for p in target["periods"]],
    }))


def observation_universe_fingerprint(alignment: Dict[str, Any],
                                     target: Dict[str, Any],
                                     definition_fingerprints: Dict[str, str],
                                     ) -> str:
    """Identity of the ALIGNED sample actually used, timing included."""
    return sha256_hex(_clean({
        "kind": "factor_observation_universe_v1",
        "target_fingerprint": target_fingerprint(target),
        "factor_ids": list(alignment["factor_ids"]),
        "factor_definition_fingerprints": dict(definition_fingerprints),
        "timing_policy": alignment["timing_policy"],
        "vintage_policy": alignment["vintage_policy"],
        "lead_periods": alignment["lead_periods"],
        "excluded_periods": [{
            "period_start": e["period_start"], "reason": e["reason"],
        } for e in alignment["excluded_periods"]],
        "rows": [{
            "period_start": r["period_start"],
            "period_end": r["period_end"],
            "information_available_at": r["information_available_at"],
            "target_return": r["target_return"],
            "factor_values": list(r["factor_values"]),
            "knowable_at": [s["knowable_at"] for s in r["factor_sources"]],
        } for r in alignment["rows"]],
    }))


def model_policy_fingerprint(policy: Dict[str, Any]) -> str:
    """Identity of the estimator and every switch that shapes it."""
    return sha256_hex(_clean({
        "kind": "factor_model_policy_v1",
        "analysis_mode": policy["analysis_mode"],
        "regression_method": policy["regression_method"],
        "intercept_policy": policy["intercept_policy"],
        "ridge_lambda": policy.get("ridge_lambda"),
        "ridge_scaling": policy.get("ridge_scaling"),
        "rank_policy": policy["rank_policy"],
        "standard_error_method": policy.get("standard_error_method"),
        "multiple_testing_methods": list(policy.get("multiple_testing_methods")
                                         or []),
        "multiple_testing_alpha": policy.get("multiple_testing_alpha"),
        "multiple_testing_family": policy.get("multiple_testing_family"),
        "confidence_level": policy.get("confidence_level"),
        "reconciliation_tolerance": policy["reconciliation_tolerance"],
        "rolling": policy.get("rolling"),
        "estimation_scope": policy.get("estimation_scope"),
    }))


def configuration_fingerprint(observation_fp: str, policy_fp: str,
                              linked: Dict[str, Any],
                              sensitivity: Sequence[Dict[str, Any]]) -> str:
    """Identity of the whole decision: inputs, policy, linkage, scenarios."""
    return sha256_hex(_clean({
        "kind": "factor_configuration_v1",
        "observation_fingerprint": observation_fp,
        "model_policy_fingerprint": policy_fp,
        "linked": {
            "attribution_configuration_fingerprint":
                linked.get("attribution_configuration_fingerprint"),
            "portfolio_configuration_fingerprint":
                linked.get("portfolio_configuration_fingerprint"),
            "benchmark_identity": linked.get("benchmark_identity"),
            "validation_configuration_fingerprint":
                linked.get("validation_configuration_fingerprint"),
            "regime_identity": linked.get("regime_identity"),
            "stress_identity": linked.get("stress_identity"),
            "dataset_identity": linked.get("dataset_identity"),
        },
        "sensitivity": [{
            "label": s["label"], "is_base": s["is_base"],
            "lookback": s["lookback"], "lag_delta": s["lag_delta"],
            "intercept_policy": s["intercept_policy"],
            "ridge_lambda": s["ridge_lambda"],
            "factor_subset": s["factor_subset"],
            "factor_scale": s["factor_scale"],
        } for s in sensitivity],
    }))


def result_fingerprint(*, coefficients: Sequence[Dict[str, Any]],
                       fit: Dict[str, Any],
                       period_rows: Sequence[Dict[str, Any]],
                       exposure_comparison: Sequence[Dict[str, Any]],
                       rolling: Sequence[Dict[str, Any]],
                       stability: Sequence[Dict[str, Any]],
                       multicollinearity: Dict[str, Any],
                       residuals: Dict[str, Any],
                       held_out: Optional[Dict[str, Any]],
                       regimes: Sequence[Dict[str, Any]],
                       sensitivity_rows: Sequence[Dict[str, Any]],
                       warnings: Sequence[str],
                       integrity_status: str,
                       completeness_status: str,
                       rank_status: str) -> str:
    """Identity of everything the run measured."""
    return sha256_hex(_clean({
        "kind": "factor_result_v1",
        "coefficients": [{
            "factor_id": c["factor_id"],
            "coefficient": c["coefficient"],
            "standard_error": c.get("standard_error"),
            "t_statistic": c.get("t_statistic"),
            "p_value": c.get("p_value"),
            "confidence_lower": c.get("confidence_lower"),
            "confidence_upper": c.get("confidence_upper"),
            "adjusted_p_values": c.get("adjusted_p_values"),
        } for c in coefficients],
        "fit": {
            "observations": fit["observations"],
            "parameters": fit["parameters"],
            "degrees_of_freedom": fit["degrees_of_freedom"],
            "r_squared": fit["r_squared"],
            "adjusted_r_squared": fit["adjusted_r_squared"],
            "root_mean_squared_error": fit["root_mean_squared_error"],
            "residual_sum_of_squares": fit["residual_sum_of_squares"],
            "total_sum_of_squares": fit["total_sum_of_squares"],
            "rank": fit["rank"],
            "condition_number": fit["condition_number"],
            "fitted": fit["fitted"],
            "residuals": fit["residuals"],
        },
        "periods": [{
            "period_start": r["period_start"],
            "measured_return": r["measured_return"],
            "intercept_contribution": r["intercept_contribution"],
            "factor_contributions": r["factor_contributions"],
            "modelled_return": r["modelled_return"],
            "residual": r["residual"],
            "reconciliation_difference": r["reconciliation_difference"],
            "reconciliation_state": r["reconciliation_state"],
        } for r in period_rows],
        "exposure_comparison": [dict(row) for row in exposure_comparison],
        "rolling": [{
            "window_start": r["window_start"], "window_end": r["window_end"],
            "coefficients": r["coefficients"], "intercept": r["intercept"],
            "r_squared": r["r_squared"], "status": r["status"],
        } for r in rolling],
        "stability": [dict(row) for row in stability],
        "multicollinearity": multicollinearity,
        "residual_diagnostics": residuals,
        "held_out": held_out,
        "regimes": [dict(row) for row in regimes],
        "sensitivity": [dict(row) for row in sensitivity_rows],
        "warnings": list(warnings),
        "integrity_status": integrity_status,
        "completeness_status": completeness_status,
        "rank_status": rank_status,
    }))


__all__ = [
    "FingerprintError", "factor_definition_fingerprint", "target_fingerprint",
    "observation_universe_fingerprint", "model_policy_fingerprint",
    "configuration_fingerprint", "result_fingerprint",
]
