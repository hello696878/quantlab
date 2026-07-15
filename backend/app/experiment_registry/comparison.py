"""
Neutral two-experiment comparison.

Compares exactly two records and reports differences grouped by category
(identity, parameters, dataset, seed, provenance, metrics, fingerprints,
status/timing).  For numeric metrics it reports A, B, the absolute difference,
and a percentage difference **only when it is mathematically valid** (finite
values and a non-zero A denominator).

This is a factual diff.  It never labels a change as good or bad and never
recommends one experiment over another — a larger metric is not "better".
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

SAME = "same"
CHANGED = "changed"
ONLY_A = "only_in_a"
ONLY_B = "only_in_b"


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _numeric_delta(a: Any, b: Any) -> Dict[str, Any]:
    """Absolute + (guarded) percentage difference for two numeric values."""
    out: Dict[str, Any] = {}
    if _is_finite_number(a) and _is_finite_number(b):
        out["abs_diff"] = b - a
        # Percentage change relative to A; only when A is a non-zero denominator.
        if a != 0:
            out["pct_diff"] = (b - a) / abs(a) * 100.0
        else:
            out["pct_diff"] = None
    return out


def _diff_field(key: str, a_has: bool, a_val: Any, b_has: bool, b_val: Any) -> Dict[str, Any]:
    if a_has and not b_has:
        return {"key": key, "state": ONLY_A, "a": a_val, "b": None}
    if b_has and not a_has:
        return {"key": key, "state": ONLY_B, "a": None, "b": b_val}
    same = a_val == b_val
    entry: Dict[str, Any] = {
        "key": key,
        "state": SAME if same else CHANGED,
        "a": a_val,
        "b": b_val,
    }
    if not same:
        entry.update(_numeric_delta(a_val, b_val))
    return entry


def _diff_maps(a: Dict[str, Any], b: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys = sorted(set(a.keys()) | set(b.keys()))
    return [_diff_field(k, k in a, a.get(k), k in b, b.get(k)) for k in keys]


def _diff_scalars(a: Dict[str, Any], b: Dict[str, Any], fields: List[str]) -> List[Dict[str, Any]]:
    return [_diff_field(f, f in a, a.get(f), f in b, b.get(f)) for f in fields]


def _summarize(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {SAME: 0, CHANGED: 0, ONLY_A: 0, ONLY_B: 0}
    for e in entries:
        counts[e["state"]] = counts.get(e["state"], 0) + 1
    return counts


def compare_experiments(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Return a grouped, neutral diff of two full experiment records."""
    identity = _diff_scalars(
        a, b, ["name", "module", "experiment_type", "status", "reproducibility_status", "is_baseline"]
    )
    dataset = _diff_scalars(a, b, ["dataset_name", "dataset_version", "dataset_fingerprint"])
    seed = _diff_scalars(a, b, ["random_seed"])
    fingerprints = _diff_scalars(a, b, ["configuration_fingerprint", "result_fingerprint"])
    timing = _diff_scalars(
        a, b, ["created_at", "started_at", "completed_at", "duration_ms", "git_commit", "app_version"]
    )
    parameters = _diff_maps(a.get("parameters", {}) or {}, b.get("parameters", {}) or {})
    metrics = _diff_maps(a.get("metrics", {}) or {}, b.get("metrics", {}) or {})
    provenance = _diff_maps(_flatten(a.get("provenance", {}) or {}), _flatten(b.get("provenance", {}) or {}))

    groups = {
        "identity": identity,
        "parameters": parameters,
        "dataset": dataset,
        "seed": seed,
        "provenance": provenance,
        "metrics": metrics,
        "fingerprints": fingerprints,
        "status_timing": timing,
    }

    fingerprint_match = {
        "configuration": bool(
            a.get("configuration_fingerprint")
            and a.get("configuration_fingerprint") == b.get("configuration_fingerprint")
        ),
        "result": bool(
            a.get("result_fingerprint")
            and a.get("result_fingerprint") == b.get("result_fingerprint")
        ),
    }

    return {
        "a_id": a.get("id"),
        "b_id": b.get("id"),
        "groups": groups,
        "summary": {name: _summarize(entries) for name, entries in groups.items()},
        "fingerprint_match": fingerprint_match,
    }


def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten a nested provenance dict into dotted keys for a readable diff."""
    flat: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flat.update(_flatten(v, key))
            else:
                flat[key] = v
    else:
        flat[prefix or "value"] = obj
    return flat


__all__ = ["compare_experiments", "SAME", "CHANGED", "ONLY_A", "ONLY_B"]

# Keep Optional import meaningful for type-checkers of downstream callers.
_ = Optional
