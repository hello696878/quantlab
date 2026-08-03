"""
Observation alignment (Phase 61, v1).

Signals are aligned on explicit (entity_id, timestamp) keys — never by row
number.  Two bounded policies exist:

* **strict_intersection** — keys where EVERY signal in the universe has a
  non-null observation.  This is the only universe combination
  calculations may use.
* **pairwise_complete** — for pairwise diagnostics only, each pair uses
  its own overlap; every pairwise row then carries its own sample count,
  and matrix-level diagnostics (eigenvalues, effective count) still use
  the strict intersection so no matrix pretends its cells share a
  universe.

Nothing is forward-filled, interpolated, zero-imputed, mean-imputed or
fabricated; a missing observation is missing, and the missingness summary
is part of the result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

Key = Tuple[str, str]  # (entity_id, timestamp)


class AlignmentError(ValueError):
    """Invalid alignment input (HTTP 422)."""


def build_grid(observations: Dict[str, List[Dict[str, Any]]]
               ) -> Dict[str, Any]:
    """Aligned value/availability grid over the union of keys.

    Returns:
      ``keys``          sorted union of (entity, timestamp) keys,
      ``values``        {signal_id: {key: raw_value or None}},
      ``available_at``  {signal_id: {key: availability timestamp}},
      ``membership_id`` {signal_id: {key: validation sample id or None}},
      ``assumed``       {signal_id: {key: bool}} (availability assumed),
      ``timestamps``    sorted unique timestamps,
      ``entities``      sorted unique entities.
    """
    values: Dict[str, Dict[Key, Optional[float]]] = {}
    available_at: Dict[str, Dict[Key, str]] = {}
    membership_id: Dict[str, Dict[Key, Optional[str]]] = {}
    assumed: Dict[str, Dict[Key, bool]] = {}
    keys: set = set()
    for signal_id, rows in observations.items():
        v: Dict[Key, Optional[float]] = {}
        a: Dict[Key, str] = {}
        m: Dict[Key, Optional[str]] = {}
        s: Dict[Key, bool] = {}
        for row in rows:
            key = (row["entity_id"], row["source_timestamp"])
            v[key] = row["raw_value"]
            a[key] = row["available_at"]
            m[key] = row.get("universe_membership_id")
            s[key] = bool(row.get("availability_assumed"))
            keys.add(key)
        values[signal_id] = v
        available_at[signal_id] = a
        membership_id[signal_id] = m
        assumed[signal_id] = s
    sorted_keys = sorted(keys)
    return {
        "keys": sorted_keys,
        "values": values,
        "available_at": available_at,
        "membership_id": membership_id,
        "assumed": assumed,
        "timestamps": sorted({k[1] for k in sorted_keys}),
        "entities": sorted({k[0] for k in sorted_keys}),
    }


def strict_intersection(grid: Dict[str, Any],
                        signal_ids: List[str]) -> List[Key]:
    """Keys where every listed signal has a stored, non-null value."""
    out: List[Key] = []
    for key in grid["keys"]:
        if all(grid["values"][s].get(key) is not None for s in signal_ids):
            out.append(key)
    return out


def pairwise_overlap(grid: Dict[str, Any], signal_a: str,
                     signal_b: str) -> List[Key]:
    """Keys where BOTH signals of one pair have non-null values."""
    va = grid["values"][signal_a]
    vb = grid["values"][signal_b]
    return [key for key in grid["keys"]
            if va.get(key) is not None and vb.get(key) is not None]


def missingness_summary(grid: Dict[str, Any], signal_ids: List[str],
                        strict_keys: List[Key]) -> Dict[str, Any]:
    """Per-signal and universe-level missing-data disclosure."""
    total = len(grid["keys"])
    per_signal: List[Dict[str, Any]] = []
    for signal_id in signal_ids:
        v = grid["values"][signal_id]
        present = sum(1 for key in grid["keys"]
                      if v.get(key) is not None)
        stored_null = sum(1 for key in grid["keys"]
                          if key in v and v[key] is None)
        absent = total - present - stored_null
        per_signal.append({
            "signal_id": signal_id,
            "union_keys": total,
            "present": present,
            "stored_null": stored_null,
            "absent": absent,
            "coverage": (present / total) if total else None,
        })
    return {
        "union_keys": total,
        "strict_intersection_keys": len(strict_keys),
        "strict_intersection_coverage": (len(strict_keys) / total
                                         if total else None),
        "per_signal": per_signal,
        "note": ("missing observations are disclosed, never filled: no "
                 "forward fill, no interpolation, no zero or mean "
                 "imputation, no row-number alignment"),
    }


__all__ = ["Key", "AlignmentError", "build_grid", "strict_intersection",
           "pairwise_overlap", "missingness_summary"]
