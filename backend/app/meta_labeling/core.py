"""
Observation model + meta-label policy.

Primary-side convention (documented): ``-1`` = negative/short direction,
``0`` = no primary action (abstention), ``1`` = positive/long direction.

Meta-label policy (deterministic, fingerprinted):
``meta_label = 1`` iff ``primary_side * realized_outcome > outcome_threshold``
else ``0`` — strict inequality, so an outcome exactly AT the threshold (and
the zero-outcome case at threshold 0) yields meta-label 0.  The threshold is
expressed in the same units as ``realized_outcome`` (e.g. fractional return)
and must be finite; negative thresholds are permitted (they accept small
adverse outcomes as "correct enough" — an explicit research choice).  No
hidden fees or slippage: any cost-style adjustment is the caller's explicit
``outcome_threshold`` configuration.

Side-0 policy (documented): observations with ``primary_side == 0`` are
recorded as **abstained** — ``meta_label`` stays ``None``, they are excluded
from calibration fitting, probability metrics, and threshold confusion
counts, and they are never converted into failed signals.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MAX_OBSERVATIONS = 2000
MIN_OBSERVATIONS = 8

VALID_SIDES = (-1, 0, 1)


class ObservationError(ValueError):
    """Invalid observation payload (HTTP 422)."""


def _parse_ts(value: Any, field: str, sid: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"observation {sid!r}: {field} must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationError(f"observation {sid!r}: {field} is not valid ISO-8601") from exc


def _finite(value: Any, field: str, sid: str, *, optional: bool = True) -> Optional[float]:
    if value is None:
        if optional:
            return None
        raise ObservationError(f"observation {sid!r}: {field} is required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationError(f"observation {sid!r}: {field} must be a finite number")
    v = float(value)
    if not math.isfinite(v):
        raise ObservationError(f"observation {sid!r}: {field} must be finite (no NaN/Infinity)")
    return v


def normalize_observations(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate + deterministically sort meta-label observations."""
    if not isinstance(raw_list, list) or len(raw_list) < MIN_OBSERVATIONS:
        raise ObservationError(f"at least {MIN_OBSERVATIONS} observations are required")
    if len(raw_list) > MAX_OBSERVATIONS:
        raise ObservationError(f"at most {MAX_OBSERVATIONS} observations are supported in v1")

    seen: set[str] = set()
    awareness: Optional[bool] = None
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            raise ObservationError(f"observation {i} must be an object")
        sid = raw.get("sample_id")
        if not isinstance(sid, str) or not sid.strip() or len(sid.strip()) > 100:
            raise ObservationError(f"observation {i}: sample_id must be a 1–100 char string")
        sid = sid.strip()
        if sid in seen:
            raise ObservationError(f"duplicate sample_id {sid!r}")
        seen.add(sid)

        pred_dt = _parse_ts(raw.get("prediction_time"), "prediction_time", sid)
        eval_dt = _parse_ts(raw.get("evaluation_time"), "evaluation_time", sid)
        aware = pred_dt.tzinfo is not None
        if (eval_dt.tzinfo is not None) != aware:
            raise ObservationError(f"observation {sid!r}: mixed naive/aware timestamps")
        if awareness is None:
            awareness = aware
        elif aware != awareness:
            raise ObservationError("all observations must be timezone-consistent")
        if aware:
            pred_dt = pred_dt.astimezone(timezone.utc)
            eval_dt = eval_dt.astimezone(timezone.utc)
        if eval_dt < pred_dt:
            raise ObservationError(f"observation {sid!r}: evaluation_time precedes prediction_time")

        side = raw.get("primary_side")
        if isinstance(side, bool) or not isinstance(side, int) or side not in VALID_SIDES:
            raise ObservationError(
                f"observation {sid!r}: primary_side must be one of {VALID_SIDES}"
            )

        prob = _finite(raw.get("raw_probability"), "raw_probability", sid)
        if prob is not None and not (0.0 <= prob <= 1.0):
            raise ObservationError(f"observation {sid!r}: raw_probability must be in [0, 1]")
        weight = _finite(raw.get("sample_weight"), "sample_weight", sid)
        if weight is not None and weight < 0:
            raise ObservationError(f"observation {sid!r}: sample_weight must be non-negative")

        # Outcomes are never invented: missing stays None and the labeling
        # step decides (side!=0 with no outcome is rejected there).
        outcome = _finite(raw.get("realized_outcome"), "realized_outcome", sid)

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict) or len(str(metadata)) > 2000:
            raise ObservationError(f"observation {sid!r}: metadata must be a small object")

        out.append(
            {
                "sample_id": sid,
                "prediction_time": pred_dt.isoformat(),
                "evaluation_time": eval_dt.isoformat(),
                "primary_side": side,
                "primary_score": _finite(raw.get("primary_score"), "primary_score", sid),
                "raw_probability": prob,
                "realized_outcome": outcome,
                "sample_weight": weight,
                "metadata": metadata,
            }
        )

    out.sort(key=lambda o: (o["prediction_time"], o["evaluation_time"], o["sample_id"]))
    return out


def apply_meta_labels(
    observations: List[Dict[str, Any]], *, outcome_threshold: float = 0.0
) -> Dict[str, Any]:
    """Assign meta-labels in place; returns counts.

    ``meta_label = 1`` iff ``side * outcome > threshold`` (strict).  Side-0
    observations are marked ``abstained`` with ``meta_label = None``.  A
    non-abstained observation without a realized outcome is rejected — the
    outcome is never invented.
    """
    if isinstance(outcome_threshold, bool) or not isinstance(outcome_threshold, (int, float)):
        raise ObservationError("outcome_threshold must be a finite number")
    threshold = float(outcome_threshold)
    if not math.isfinite(threshold):
        raise ObservationError("outcome_threshold must be finite")

    labeled = positives = abstained = 0
    for obs in observations:
        if obs["primary_side"] == 0:
            obs["meta_label"] = None
            obs["abstained"] = True
            abstained += 1
            continue
        obs["abstained"] = False
        if obs["realized_outcome"] is None:
            raise ObservationError(
                f"observation {obs['sample_id']!r}: realized_outcome is required for "
                "a non-zero primary side (outcomes are never inferred)"
            )
        signed = obs["primary_side"] * obs["realized_outcome"]
        obs["meta_label"] = 1 if signed > threshold else 0
        labeled += 1
        if obs["meta_label"] == 1:
            positives += 1
    return {
        "labeled_count": labeled,
        "positive_count": positives,
        "abstained_count": abstained,
        "outcome_threshold": threshold,
    }


__all__ = [
    "MAX_OBSERVATIONS",
    "MIN_OBSERVATIONS",
    "VALID_SIDES",
    "ObservationError",
    "normalize_observations",
    "apply_meta_labels",
]
