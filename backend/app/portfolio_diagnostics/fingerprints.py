"""
Deterministic SHA-256 fingerprints for portfolio diagnostics (v1).

Universe, covariance, constraint, configuration, result and per-scenario
fingerprints over canonical JSON with deterministic arrays; floats are
quantized to 12 decimal places; NaN/Infinity are rejected; database ids,
creation timestamps, runtime durations and absolute paths are never
hashed.
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


def universe_fingerprint(assets: List[Dict[str, Any]], timestamps: List[str],
                         frequency: str, benchmark: Optional[List[float]],
                         dataset_identity: Optional[Dict[str, Any]],
                         candidate_fingerprints: Optional[List[str]] = None
                         ) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_universe_v1",
        "alignment_policy": "strict identical timestamp alignment",
        "frequency": frequency,
        "timestamps": timestamps,
        "assets": [{"asset_id": a["asset_id"], "asset_type": a["asset_type"],
                    "group": a.get("group"), "currency": a.get("currency"),
                    "returns": a["returns"]} for a in assets],
        "benchmark": benchmark,
        "dataset": dataset_identity or None,
        "candidate_fingerprints": candidate_fingerprints or None,
    }))


def covariance_fingerprint(universe_fp: str, estimation: Dict[str, Any],
                           cov_config: Dict[str, Any],
                           window: Optional[List[int]],
                           matrix: Optional[List[List[float]]]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_covariance_v1",
        "universe_fingerprint": universe_fp,
        "estimation": estimation,
        "covariance_config": cov_config,
        "window": window,
        "matrix": matrix,
    }))


def constraint_fingerprint(constraints: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_constraints_v1",
        "constraints": constraints,
    }))


def configuration_fingerprint(universe_fp: str, method: str,
                              cov_config: Dict[str, Any],
                              estimation: Dict[str, Any],
                              constraint_fp: str,
                              risk_budgets: Optional[Dict[str, float]],
                              rebalance_policy: Dict[str, Any],
                              solver_config: Dict[str, Any],
                              sensitivity_config: Dict[str, Any],
                              linked: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_configuration_v1",
        "universe_fingerprint": universe_fp,
        "method": method,
        "covariance_config": cov_config,
        "estimation": estimation,
        "constraint_fingerprint": constraint_fp,
        "risk_budgets": risk_budgets,
        "rebalance_policy": rebalance_policy,
        "solver_config": solver_config,
        "sensitivity_config": sensitivity_config,
        "linked": linked,
    }))


def result_fingerprint(configuration_fp: str,
                       rebalances: List[Dict[str, Any]],
                       risk: Dict[str, Any],
                       budget: Dict[str, Any],
                       concentration: Dict[str, Any],
                       sensitivity: List[Dict[str, Any]],
                       constraint_checks: List[Dict[str, Any]],
                       warnings: List[str],
                       integrity: str, solver_status: str) -> str:
    rows = [{
        "rebalance_id": r["rebalance_id"],
        "decision_timestamp": r["decision_timestamp"],
        "weights": r.get("weights"),
        "turnover": r.get("turnover"),
        "solver_status": r.get("solver", {}).get("status"),
        "constraint_violations": len(r.get("constraint_violations") or []),
    } for r in rebalances]
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_result_v1",
        "configuration_fingerprint": configuration_fp,
        "rebalances": rows,
        "risk": risk,
        "budget": budget,
        "concentration": concentration,
        "sensitivity": sensitivity,
        "constraint_checks": constraint_checks,
        "warnings": sorted(warnings),
        "integrity_status": integrity,
        "solver_status": solver_status,
    }))


def scenario_fingerprint(configuration_fp: str, scenario: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_diagnostics_scenario_v1",
        "configuration_fingerprint": configuration_fp,
        "scenario": {k: scenario[k] for k in sorted(scenario)
                     if k in ("dimension", "value", "is_base")},
    }))


def weight_fingerprint(weights: Dict[str, float]) -> str:
    return sha256_hex(_clean({"kind": "portfolio_diagnostics_weights_v1",
                              "weights": weights}))
