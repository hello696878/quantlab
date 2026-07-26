"""
Candidate-universe input model: validated, strictly aligned, deterministic.

Alignment policy (v1, documented): **strict identical alignment** — every
candidate must supply exactly the same ordered observation timestamps.  There
is no intersection alignment, no forward-filling, and no fabricated
timestamps; missing values are rejected, never imputed.  Returns are plain
per-period observations in the caller's stated frequency — the lab never
silently annualizes anything.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

MIN_CANDIDATES = 2
MAX_CANDIDATES = 24
MIN_OBSERVATIONS = 24
MAX_OBSERVATIONS = 2000
MAX_ID_LEN = 64

ALIGNMENT_POLICY = (
    "strict identical alignment — every candidate supplies the same ordered "
    "timestamps; missing values are rejected, never filled"
)
MISSING_VALUE_POLICY = "reject (no forward-filling, no imputation, no fabricated timestamps)"


class CandidateInputError(ValueError):
    """Invalid candidate-universe input (HTTP 422)."""


def _parse_time(value: Any, field: str) -> Tuple[datetime, bool]:
    if not isinstance(value, str) or not value:
        raise CandidateInputError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CandidateInputError(f"{field} {value!r} is not valid ISO-8601")
    return parsed, parsed.tzinfo is not None


def normalize_timestamps(timestamps: Sequence[Any]) -> List[str]:
    """Shared observation timeline: ordered, strictly increasing, one tz style."""
    if not isinstance(timestamps, (list, tuple)):
        raise CandidateInputError("timestamps must be a list of ISO-8601 strings")
    if not (MIN_OBSERVATIONS <= len(timestamps) <= MAX_OBSERVATIONS):
        raise CandidateInputError(
            f"observation count must be between {MIN_OBSERVATIONS} and "
            f"{MAX_OBSERVATIONS} (got {len(timestamps)})"
        )
    parsed: List[datetime] = []
    tz_flags: set[bool] = set()
    for i, t in enumerate(timestamps):
        dt, aware = _parse_time(t, f"timestamps[{i}]")
        tz_flags.add(aware)
        if len(tz_flags) > 1:
            raise CandidateInputError(
                "timestamps mix timezone-aware and naive values — use one convention"
            )
        parsed.append(dt)
    for i in range(1, len(parsed)):
        if parsed[i] <= parsed[i - 1]:
            raise CandidateInputError(
                f"timestamps must be strictly increasing (violation at index {i})"
            )
    return [str(t) for t in timestamps]


def normalize_candidates(
    candidates: Sequence[Dict[str, Any]], n_observations: int
) -> List[Dict[str, Any]]:
    if not isinstance(candidates, (list, tuple)):
        raise CandidateInputError("candidates must be a list")
    if not (MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES):
        raise CandidateInputError(
            f"candidate count must be between {MIN_CANDIDATES} and "
            f"{MAX_CANDIDATES} (got {len(candidates)})"
        )
    seen: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    for c in candidates:
        cid = c.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            raise CandidateInputError("every candidate needs a non-empty candidate_id")
        cid = cid.strip()
        if len(cid) > MAX_ID_LEN:
            raise CandidateInputError(f"candidate_id {cid[:20]!r}… exceeds {MAX_ID_LEN} chars")
        if cid in seen:
            raise CandidateInputError(f"duplicate candidate_id {cid!r}")
        seen.add(cid)
        returns = c.get("returns")
        if not isinstance(returns, (list, tuple)):
            raise CandidateInputError(f"candidate {cid}: returns must be a list")
        if len(returns) != n_observations:
            raise CandidateInputError(
                f"candidate {cid}: {len(returns)} observations do not match the "
                f"shared timeline of {n_observations} ({ALIGNMENT_POLICY})"
            )
        values: List[float] = []
        for i, v in enumerate(returns):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise CandidateInputError(
                    f"candidate {cid}: returns[{i}] must be a finite number "
                    f"({MISSING_VALUE_POLICY})"
                )
            values.append(float(v))
        p_value = c.get("nominal_p_value")
        if p_value is not None:
            if isinstance(p_value, bool) or not isinstance(p_value, (int, float)) \
                    or not math.isfinite(p_value) or not (0.0 <= float(p_value) <= 1.0):
                raise CandidateInputError(
                    f"candidate {cid}: nominal_p_value must be a finite number in [0, 1]"
                )
            p_value = float(p_value)
        provenance = c.get("p_value_provenance")
        if provenance is not None and not isinstance(provenance, dict):
            raise CandidateInputError(f"candidate {cid}: p_value_provenance must be an object")
        name = c.get("name") or cid
        if not isinstance(name, str) or len(name) > 200:
            raise CandidateInputError(f"candidate {cid}: name must be a string ≤ 200 chars")
        group = c.get("candidate_group")
        if group is not None and (not isinstance(group, str) or len(group) > 100):
            raise CandidateInputError(f"candidate {cid}: candidate_group must be ≤ 100 chars")
        normalized.append({
            "candidate_id": cid,
            "name": name,
            "description": c.get("description") or "",
            "candidate_group": group,
            "experiment_id": c.get("experiment_id"),
            "validation_run_id": c.get("validation_run_id"),
            "dataset_version_id": c.get("dataset_version_id"),
            "configuration_fingerprint": c.get("configuration_fingerprint"),
            "result_fingerprint": c.get("result_fingerprint"),
            "returns": values,
            "nominal_p_value": p_value,
            "p_value_provenance": provenance,
            "metadata": c.get("metadata") or {},
        })
    # Deterministic candidate order: stable sort by candidate_id (documented —
    # the matrix, fingerprints, and tie-breaking all use this order).
    normalized.sort(key=lambda c: c["candidate_id"])
    return normalized


def build_matrix(candidates: Sequence[Dict[str, Any]]) -> np.ndarray:
    """(T × N) return matrix in normalized candidate order."""
    return np.column_stack(
        [np.asarray(c["returns"], dtype=np.float64) for c in candidates]
    )


__all__ = [
    "MIN_CANDIDATES", "MAX_CANDIDATES", "MIN_OBSERVATIONS", "MAX_OBSERVATIONS",
    "ALIGNMENT_POLICY", "MISSING_VALUE_POLICY", "CandidateInputError",
    "normalize_timestamps", "normalize_candidates", "build_matrix",
]
