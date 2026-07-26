"""
Deterministic SHA-256 fingerprints for portfolio attribution (v1).

Four kinds — observation-universe, attribution-policy, configuration and
result — over canonical JSON with deterministic arrays.  Floats are
quantized to 12 decimal places; NaN and Infinity are rejected outright.

Fingerprints carry CONTENT-ADDRESSED identity only: no database row ids,
creation timestamps, runtime durations or absolute paths, so a
byte-identical configuration over byte-identical inputs reproduces the same
fingerprint in a different database.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

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


def observation_universe_fingerprint(observations: Dict[str, Any],
                                     benchmark: Dict[str, Any],
                                     dataset_identity: Dict[str, Any],
                                     timing_policy: str) -> str:
    periods = [{
        "period_id": p["period_id"],
        "start": p["period_start"],
        "end": p["period_end"],
        "information_available_at": p["information_available_at"],
        "rows": [{
            "asset_id": r["asset_id"],
            "group_id": r["group_id"],
            "weight": r["portfolio_beginning_weight"],
            "return": r["asset_return"],
        } for r in p["rows"]],
    } for p in observations["periods"]]
    return sha256_hex(_clean({
        "kind": "portfolio_attribution_observation_universe_v1",
        "asset_ids": observations["asset_ids"],
        "groups": observations["groups"],
        "frequency": observations["frequency"],
        "timing_policy": timing_policy,
        "periods": periods,
        "benchmark": {
            "configured": benchmark.get("configured", False),
            "benchmark_id": benchmark.get("benchmark_id"),
            "kind": benchmark.get("kind"),
            "source": benchmark.get("source"),
            "asset_ids": benchmark.get("asset_ids"),
            "groups": benchmark.get("groups"),
            "base_weights": benchmark.get("base_weights"),
            "weights_per_period": benchmark.get("weights_per_period"),
            "returns": benchmark.get("returns"),
            "timing_policy": benchmark.get("timing_policy"),
            "frequency": benchmark.get("frequency"),
            "period_start": benchmark.get("period_start"),
            "period_end": benchmark.get("period_end"),
            "dataset_version_id": benchmark.get("dataset_version_id"),
            "dataset_identity": benchmark.get("dataset_identity"),
            "metadata": benchmark.get("metadata"),
            "period_starts": benchmark.get("period_starts"),
            "information_available_at": benchmark.get(
                "information_available_at"),
        },
        "dataset": dataset_identity,
    }))


def benchmark_definition_fingerprint(benchmark: Dict[str, Any]) -> str:
    """Content identity for an explicit benchmark, excluding display notes."""
    material = {key: value for key, value in benchmark.items()
                if key not in {"note", "fingerprint"}}
    return sha256_hex(_clean({
        "kind": "portfolio_attribution_benchmark_v1",
        "definition": material,
    }))

def attribution_policy_fingerprint(policy: Dict[str, Any],
                                   attribution_method: str,
                                   brinson_variant: Optional[str],
                                   linking_method: str,
                                   cost_policy: str) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_attribution_policy_v1",
        "return_convention": policy["return_convention"],
        "return_frequency": policy["return_frequency"],
        "weight_timing_policy": policy["weight_timing_policy"],
        "benchmark_timing_policy": policy["benchmark_timing_policy"],
        "reconciliation_tolerance": policy["reconciliation_tolerance"],
        "missing_input_policy": policy["missing_input_policy"],
        "attribution_method": attribution_method,
        "brinson_variant": brinson_variant,
        "linking_method": linking_method,
        "cost_policy": cost_policy,
    }))


def configuration_fingerprint(observation_fp: str, policy_fp: str,
                              portfolio_identity: Dict[str, Any],
                              benchmark_identity: Dict[str, Any],
                              linked: Dict[str, Any],
                              filters: Dict[str, Any]) -> str:
    return sha256_hex(_clean({
        "kind": "portfolio_attribution_configuration_v1",
        "observation_universe_fingerprint": observation_fp,
        "attribution_policy_fingerprint": policy_fp,
        "portfolio": portfolio_identity,
        "benchmark": benchmark_identity,
        "linked": linked,
        "filters": filters,
    }))


def result_fingerprint(configuration_fp: str,
                       period_rows: List[Dict[str, Any]],
                       asset_rows: List[Dict[str, Any]],
                       group_rows: List[Dict[str, Any]],
                       brinson_rows: List[Dict[str, Any]],
                       linking: Optional[Dict[str, Any]],
                       cost_block: Optional[Dict[str, Any]],
                       active_risk_block: Optional[Dict[str, Any]],
                       concentration_blocks: Dict[str, Any],
                       regime_rows: List[Dict[str, Any]],
                       drawdown_rows: List[Dict[str, Any]],
                       summary: Dict[str, Any], warnings: List[str],
                       integrity: str, completeness: str,
                       reconciliation: str) -> str:
    """Fingerprint every material result while excluding local row ids."""
    material_drawdowns = [
        {key: value for key, value in row.items()
         if key not in {"id", "run_id", "episode_id"}}
        for row in drawdown_rows
    ]
    return sha256_hex(_clean({
        "kind": "portfolio_attribution_result_v1",
        "configuration_fingerprint": configuration_fp,
        "periods": period_rows,
        "assets": asset_rows,
        "groups": group_rows,
        "brinson": brinson_rows,
        "linking": linking,
        "cost": cost_block,
        "active_risk": active_risk_block,
        "concentration": concentration_blocks,
        "regimes": regime_rows,
        "drawdowns": material_drawdowns,
        "summary": summary,
        "warnings": sorted(warnings),
        "integrity": integrity,
        "completeness": completeness,
        "reconciliation": reconciliation,
    }))

__all__ = ["FingerprintError", "observation_universe_fingerprint",
           "benchmark_definition_fingerprint",
           "attribution_policy_fingerprint", "configuration_fingerprint",
           "result_fingerprint"]
