"""
Input model: one shared strictly-increasing timeline, per-candidate aligned
outcome series, and a market-feature matrix on the same timeline.

Alignment policy (v1, documented): **strict identical alignment** — every
candidate outcome series and every market feature series supplies exactly one
finite value per timeline period.  There is no forward-filling, no fabricated
timestamps, and no imputation; regimes are formed from the market features
(never from candidate outcomes), and observation ids derive deterministically
as ``{candidate_id}:{period_index:04d}``.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

MIN_PERIODS = 24
MAX_PERIODS = 2000
MIN_CANDIDATES = 1
MAX_CANDIDATES = 16
MAX_FEATURES = 8
MAX_ID_LEN = 64

OUTCOME_KINDS = ("return", "score")
ALIGNMENT_POLICY = (
    "strict identical alignment — one finite value per timeline period for "
    "every candidate outcome and market feature; no filling, no imputation"
)
MISSING_VALUE_POLICY = "reject (no forward-filling, no fabricated timestamps)"


class RegimeInputError(ValueError):
    """Invalid observation/feature input (HTTP 422)."""


def _parse_time(value: Any, field: str) -> Tuple[datetime, bool]:
    if not isinstance(value, str) or not value:
        raise RegimeInputError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RegimeInputError(f"{field} {value!r} is not valid ISO-8601")
    return parsed, parsed.tzinfo is not None


def normalize_timeline(timestamps: Sequence[Any], frequency: Any) -> Dict[str, Any]:
    if not isinstance(frequency, str) or not frequency.strip() or len(frequency) > 40:
        raise RegimeInputError(
            "frequency must be an explicit non-empty string (e.g. 'daily') — "
            "nothing is ever annualized without it being declared"
        )
    if not isinstance(timestamps, (list, tuple)):
        raise RegimeInputError("timestamps must be a list of ISO-8601 strings")
    if not (MIN_PERIODS <= len(timestamps) <= MAX_PERIODS):
        raise RegimeInputError(
            f"period count must be between {MIN_PERIODS} and {MAX_PERIODS} "
            f"(got {len(timestamps)})"
        )
    parsed: List[datetime] = []
    tz_flags: set[bool] = set()
    for i, t in enumerate(timestamps):
        dt, aware = _parse_time(t, f"timestamps[{i}]")
        tz_flags.add(aware)
        if len(tz_flags) > 1:
            raise RegimeInputError(
                "timestamps mix timezone-aware and naive values — use one convention"
            )
        parsed.append(dt)
    for i in range(1, len(parsed)):
        if parsed[i] <= parsed[i - 1]:
            raise RegimeInputError(
                f"timestamps must be strictly increasing (violation at index {i})"
            )
    return {"timestamps": [str(t) for t in timestamps],
            "frequency": frequency.strip()}


def normalize_candidates(
    candidates: Sequence[Dict[str, Any]], n_periods: int
) -> List[Dict[str, Any]]:
    if not isinstance(candidates, (list, tuple)):
        raise RegimeInputError("candidates must be a list")
    if not (MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES):
        raise RegimeInputError(
            f"candidate count must be between {MIN_CANDIDATES} and "
            f"{MAX_CANDIDATES} (got {len(candidates)})"
        )
    seen: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, dict):
            raise RegimeInputError("every candidate must be an object")
        cid = c.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            raise RegimeInputError("every candidate needs a non-empty candidate_id")
        cid = cid.strip()
        if len(cid) > MAX_ID_LEN:
            raise RegimeInputError(f"candidate_id {cid[:20]!r}… exceeds {MAX_ID_LEN} chars")
        if cid in seen:
            raise RegimeInputError(f"duplicate candidate_id {cid!r}")
        seen.add(cid)
        outcomes = c.get("outcomes")
        if not isinstance(outcomes, (list, tuple)) or len(outcomes) != n_periods:
            raise RegimeInputError(
                f"candidate {cid}: outcomes must supply exactly one value per "
                f"timeline period ({n_periods}) — {ALIGNMENT_POLICY}"
            )
        values: List[float] = []
        for i, v in enumerate(outcomes):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise RegimeInputError(
                    f"candidate {cid}: outcomes[{i}] must be a finite number "
                    f"({MISSING_VALUE_POLICY})"
                )
            values.append(float(v))
        kind = c.get("outcome_kind", "return")
        if kind not in OUTCOME_KINDS:
            raise RegimeInputError(
                f"candidate {cid}: outcome_kind must be one of {OUTCOME_KINDS}"
            )
        name = c.get("name") or cid
        if not isinstance(name, str) or len(name) > 200:
            raise RegimeInputError(f"candidate {cid}: name must be a string ≤ 200 chars")
        normalized.append({
            "candidate_id": cid,
            "name": name,
            "description": c.get("description") or "",
            "outcome_kind": kind,
            "outcomes": values,
            "experiment_id": c.get("experiment_id"),
            "dataset_version_id": c.get("dataset_version_id"),
            "metadata": c.get("metadata") or {},
        })
    normalized.sort(key=lambda c: c["candidate_id"])
    return normalized


def normalize_market_features(
    features: Optional[Dict[str, Any]], n_periods: int
) -> Dict[str, List[float]]:
    features = features or {}
    if not isinstance(features, dict):
        raise RegimeInputError("market_features must be an object of named series")
    if len(features) > MAX_FEATURES:
        raise RegimeInputError(f"at most {MAX_FEATURES} market features are supported")
    out: Dict[str, List[float]] = {}
    for name, series in features.items():
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_ID_LEN:
            raise RegimeInputError("market feature names must be strings ≤ 64 chars")
        if name.strip() in out:
            raise RegimeInputError(
                f"duplicate market feature name {name.strip()!r} "
                "(names are compared after trimming whitespace)"
            )
        if not isinstance(series, (list, tuple)) or len(series) != n_periods:
            raise RegimeInputError(
                f"market feature {name!r}: must supply exactly one value per "
                f"timeline period ({n_periods})"
            )
        values: List[float] = []
        for i, v in enumerate(series):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise RegimeInputError(
                    f"market feature {name!r}: values[{i}] must be a finite number"
                )
            values.append(float(v))
        out[name.strip()] = values
    return out


def normalize_sample_ids(
    sample_ids: Optional[Sequence[Any]], n_periods: int
) -> Optional[List[str]]:
    """Optional per-period mapping to Model Validation sample ids."""
    if sample_ids is None:
        return None
    if not isinstance(sample_ids, (list, tuple)) or len(sample_ids) != n_periods:
        raise RegimeInputError(
            f"sample_ids must supply exactly one id per timeline period ({n_periods})"
        )
    out: List[str] = []
    seen: set[str] = set()
    for i, sid in enumerate(sample_ids):
        if not isinstance(sid, str) or not sid.strip() or len(sid) > MAX_ID_LEN:
            raise RegimeInputError(f"sample_ids[{i}] must be a non-empty string ≤ 64 chars")
        sid = sid.strip()
        if sid in seen:
            raise RegimeInputError(f"duplicate sample id {sid!r}")
        seen.add(sid)
        out.append(sid)
    return out


def build_outcome_matrix(candidates: Sequence[Dict[str, Any]]) -> np.ndarray:
    """(T × N) outcome matrix in normalized candidate order."""
    return np.column_stack(
        [np.asarray(c["outcomes"], dtype=np.float64) for c in candidates]
    )


__all__ = [
    "MIN_PERIODS", "MAX_PERIODS", "MIN_CANDIDATES", "MAX_CANDIDATES",
    "MAX_FEATURES", "OUTCOME_KINDS", "ALIGNMENT_POLICY", "MISSING_VALUE_POLICY",
    "RegimeInputError", "normalize_timeline", "normalize_candidates",
    "normalize_market_features", "normalize_sample_ids", "build_outcome_matrix",
]
