"""
Deterministic SHA-256 fingerprints for cost diagnostics (v1).

Four fingerprints: observation universe, cost model, configuration and
result.  All hashing uses the shared canonical-JSON SHA-256 helper; floats
are quantized to 12 decimal places before hashing (documented — differences
below 1e-12 are treated as identical); NaN and Infinity are rejected.
Database ids, created timestamps, runtime durations and absolute paths are
never part of any fingerprint.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.experiment_registry.fingerprints import sha256_hex


class FingerprintError(ValueError):
    """Raised when non-finite values reach a fingerprint."""


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise FingerprintError("non-finite value in fingerprint payload")
        return round(obj, 12)
    raise FingerprintError(f"unsupported fingerprint value type {type(obj).__name__}")


def observation_universe_fingerprint(observations: List[Dict[str, Any]],
                                     observation_type: str,
                                     currency: Optional[str],
                                     dataset_identity: Optional[Dict[str, Any]],
                                     liquidity_series: Optional[Dict[str, Any]] = None
                                     ) -> str:
    rows = []
    for o in observations:
        row = {
            "id": o["observation_id"],
            "candidate_id": o["candidate_id"],
            "timestamp": o.get("timestamp"),
            "gross": o.get("gross_pnl", o.get("gross_return")),
            # per-observation supplied execution inputs (realized slippage,
            # supplied spread/ADV/volume/volatility) are result-changing
            # observed data — omitting them would let two materially different
            # runs collide on the universe fingerprint (and thus baseline scope)
            "cost_inputs": o.get("cost_inputs"),
        }
        if observation_type == "trade":
            row.update({
                "entry_timestamp": o["entry_timestamp"],
                "exit_timestamp": o["exit_timestamp"],
                "side": o["side"],
                "quantity": o["quantity"],
                "contract_multiplier": o["contract_multiplier"],
                "entry_price": o["entry_price"],
                "exit_price": o["exit_price"],
            })
        else:
            row.update({
                "turnover": o.get("turnover"),
                "traded_notional": o.get("traded_notional"),
            })
        rows.append(row)
    return sha256_hex(_clean({
        "kind": "cost_diagnostics_observation_universe_v1",
        "observation_type": observation_type,
        "currency": currency,
        "observations": rows,
        "dataset": dataset_identity or None,
        # the run-level liquidity series (trailing ADV / volatility source the
        # liquidity policy consumes) is observed market data that changes
        # results; hashing it here keeps two runs over different liquidity
        # series from colliding on the universe fingerprint / baseline scope
        "liquidity_series": liquidity_series or None,
    }))


def cost_model_fingerprint(commission: Dict[str, Any], spread: Dict[str, Any],
                           slippage: Dict[str, Any], impact: Dict[str, Any],
                           liquidity_policy: Dict[str, Any],
                           tick_size: Optional[float] = None) -> str:
    return sha256_hex(_clean({
        "kind": "cost_diagnostics_cost_model_v1",
        "commission": commission,
        "spread": spread,
        "slippage": slippage,
        "impact": impact,
        "liquidity_policy": liquidity_policy,
        # tick_size converts a tick-denominated slippage/spread into currency,
        # so it is a cost-model parameter — two models differing only in
        # tick_size must not share a fingerprint (they price ticks differently)
        "tick_size": tick_size,
    }))


def configuration_fingerprint(universe_fp: str, cost_model_fp: str,
                              sensitivity_grid: Dict[str, Any],
                              capacity_scales: List[float],
                              integer_contracts: bool,
                              participation_threshold: float,
                              tick_size: Optional[float],
                              linked: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "cost_diagnostics_configuration_v1",
        "universe_fingerprint": universe_fp,
        "cost_model_fingerprint": cost_model_fp,
        "sensitivity_grid": sensitivity_grid,
        "capacity_scales": capacity_scales,
        "integer_contracts": integer_contracts,
        "participation_threshold": participation_threshold,
        "tick_size": tick_size,
        "linked": linked,
    }))


def result_fingerprint(configuration_fp: str,
                       observation_results: List[Dict[str, Any]],
                       aggregates: Dict[str, Any],
                       breakeven: Dict[str, Any],
                       sensitivity: List[Dict[str, Any]],
                       capacity: List[Dict[str, Any]],
                       warnings: List[str],
                       completeness: str,
                       integrity: str) -> str:
    rows = [{
        "id": r["observation_id"],
        "gross": r["gross_value"],
        "components": r["component_values"],
        "total_cost": r["total_cost"],
        "net": r["net_value"],
        "completeness": r["completeness"],
        "participation": r.get("participation"),
    } for r in observation_results]
    return sha256_hex(_clean({
        "kind": "cost_diagnostics_result_v1",
        "configuration_fingerprint": configuration_fp,
        "observations": rows,
        "aggregates": aggregates,
        "breakeven": breakeven,
        "sensitivity": sensitivity,
        "capacity": capacity,
        "warnings": sorted(warnings),
        "completeness_status": completeness,
        "integrity_status": integrity,
    }))


def scenario_fingerprint(configuration_fp: str,
                         scenario: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "cost_diagnostics_scenario_v1",
        "configuration_fingerprint": configuration_fp,
        "commission_multiplier": scenario["commission_multiplier"],
        "spread_multiplier": scenario["spread_multiplier"],
        "slippage_multiplier": scenario["slippage_multiplier"],
        "impact_multiplier": scenario["impact_multiplier"],
    }))
