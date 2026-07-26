"""
Deterministic SHA-256 fingerprints for portfolio stress (v1).

Scenario-definition, causal-observation, configuration, result, stressed-covariance,
stressed-cost-model and per-sensitivity-scenario fingerprints over
canonical JSON with deterministic arrays; floats quantized to 12 decimal
places; NaN/Infinity rejected; no database ids, creation timestamps,
runtime durations or absolute paths.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.experiment_registry.fingerprints import sha256_hex


class FingerprintError(ValueError):
    """Raised when non-finite values reach a fingerprint."""


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
    raise FingerprintError(f"unsupported fingerprint value type {type(obj).__name__}")


def scenario_fingerprint(scenario: Dict[str, Any], integrity: str) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_stress_scenario_v1",
        "scenario_type": scenario["scenario_type"],
        "source": scenario["source"],
        "historical": scenario.get("historical"),
        "asset_shocks": scenario["asset_shocks"],
        "group_shocks": scenario["group_shocks"],
        "global_shock": scenario["global_shock"],
        "volatility_stress": scenario["volatility_stress"],
        "correlation_stress": scenario["correlation_stress"],
        "liquidity_cost_stress": scenario["liquidity_cost_stress"],
        "units_note": scenario["units_note"],
        "precedence": scenario["precedence"],
        "missing_shock_policy": scenario["missing_shock_policy"],
        "integrity": integrity,
    }))


def observation_input_fingerprint(kind: str, asset_ids: List[str],
                                  timestamps: List[str],
                                  returns_matrix: List[List[float]],
                                  start_index: int,
                                  end_index: int) -> str:
    """Hash only the observations permitted for a causal calculation."""
    if start_index < 0 or end_index < start_index \
            or end_index >= len(timestamps):
        raise FingerprintError("invalid observation fingerprint window")
    return sha256_hex(_clean({
        "kind": kind,
        "asset_ids": asset_ids,
        "timestamps": timestamps[start_index:end_index + 1],
        "returns": [row[start_index:end_index + 1]
                    for row in returns_matrix],
    }))


def configuration_fingerprint(scenario_fp: str,
                              portfolio_identity: Dict[str, Any],
                              notional: Optional[float],
                              linked: Dict[str, Any],
                              attribution_policy: str,
                              sensitivity_config: Dict[str, Any],
                              execution_order: List[str]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_stress_configuration_v1",
        "scenario_fingerprint": scenario_fp,
        "portfolio": portfolio_identity,
        "notional": notional,
        "linked": linked,
        "attribution_policy": attribution_policy,
        "sensitivity": sensitivity_config,
        "execution_order": execution_order,
    }))


def matrix_fingerprint(kind: str, matrix: List[List[float]]) -> str:
    return sha256_hex(_clean({"kind": kind, "matrix": matrix}))


def stressed_cost_model_fingerprint(base_fp: Optional[str],
                                    multipliers: Dict[str, Any]) -> str:
    """A NEW fingerprint for the stressed copy of a linked Phase 55 cost
    model — the base model's stored fingerprint is referenced, never
    rewritten."""
    return sha256_hex(_clean({
        "kind": "portfolio_stress_cost_model_v1",
        "base_cost_model_fingerprint": base_fp,
        "multipliers": multipliers,
    }))


def result_fingerprint(configuration_fp: str,
                       material_result: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_stress_result_v1",
        "configuration_fingerprint": configuration_fp,
        "material_result": material_result,
    }))


def sensitivity_fingerprint(configuration_fp: str,
                            scenario: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_stress_sensitivity_v1",
        "configuration_fingerprint": configuration_fp,
        "result": {k: v for k, v in scenario.items()
                   if k != "fingerprint"},
    }))
