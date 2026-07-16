"""
Temporal-event sample model.

Each sample carries an information interval: ``prediction_time`` (when the
signal becomes available) through ``evaluation_time`` (when the outcome is
fully known), interpreted as a **closed** interval ``[prediction_time,
evaluation_time]`` — both boundaries inclusive, matching ``app.finml.cv``.

Normalization rules (all violations raise :class:`EventError`):

* evaluation_time must not precede prediction_time;
* timestamps must be valid ISO-8601 and timezone-consistent (all naive or all
  aware; aware values are normalized to UTC);
* duplicate sample ids rejected;
* labels / predictions / scores / returns / weights must be finite when given;
* missing evaluation_time is **never inferred** — it is an error unless the
  caller sets the explicit ``allow_missing_evaluation="prediction_time"``
  policy, which uses a zero-length interval at prediction_time (documented);
* deterministic stable sort by (prediction_time, evaluation_time, sample_id) —
  equal timestamps tie-break on the id, so ordering is always reproducible.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MAX_SAMPLES = 2000
MIN_SAMPLES = 4


class EventError(ValueError):
    """Invalid sample payload (maps to HTTP 422)."""


def _parse_ts(value: Any, field: str, sample_id: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EventError(f"sample {sample_id!r}: {field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventError(f"sample {sample_id!r}: {field} is not valid ISO-8601") from exc
    return parsed


def _finite_or_none(value: Any, field: str, sample_id: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EventError(f"sample {sample_id!r}: {field} must be a finite number")
    v = float(value)
    if not math.isfinite(v):
        raise EventError(f"sample {sample_id!r}: {field} must be finite (no NaN/Infinity)")
    return v


def normalize_samples(
    raw_samples: List[Dict[str, Any]],
    *,
    allow_missing_evaluation: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Validate + normalize samples; returns them deterministically sorted.

    Output sample shape: ``{sample_id, prediction_time, evaluation_time,
    pred_dt, eval_dt, group, label, prediction, score, ret, weight, metadata}``
    where ``*_dt`` are parsed datetimes (UTC when aware) and the string fields
    are canonical ISO-8601.
    """
    if not isinstance(raw_samples, list) or len(raw_samples) < MIN_SAMPLES:
        raise EventError(f"at least {MIN_SAMPLES} samples are required")
    if len(raw_samples) > MAX_SAMPLES:
        raise EventError(f"at most {MAX_SAMPLES} samples are supported in v1")

    seen: set[str] = set()
    awareness: Optional[bool] = None
    out: List[Dict[str, Any]] = []

    for i, raw in enumerate(raw_samples):
        if not isinstance(raw, dict):
            raise EventError(f"sample {i} must be an object")
        sid = raw.get("sample_id")
        if not isinstance(sid, str) or not sid.strip():
            raise EventError(f"sample {i}: sample_id must be a non-empty string")
        sid = sid.strip()
        if len(sid) > 100:
            raise EventError(f"sample {sid!r}: sample_id exceeds 100 characters")
        if sid in seen:
            raise EventError(f"duplicate sample_id {sid!r}")
        seen.add(sid)

        pred_dt = _parse_ts(raw.get("prediction_time"), "prediction_time", sid)

        eval_raw = raw.get("evaluation_time")
        if eval_raw is None:
            if allow_missing_evaluation == "prediction_time":
                eval_dt = pred_dt
            else:
                raise EventError(
                    f"sample {sid!r}: evaluation_time is missing and no explicit "
                    "missing-evaluation policy was configured (label end times are "
                    "never inferred silently)"
                )
        else:
            eval_dt = _parse_ts(eval_raw, "evaluation_time", sid)

        aware = pred_dt.tzinfo is not None
        if (eval_dt.tzinfo is not None) != aware:
            raise EventError(f"sample {sid!r}: mixed naive/aware timestamps within the sample")
        if awareness is None:
            awareness = aware
        elif aware != awareness:
            raise EventError(
                "all samples must be timezone-consistent (all naive or all timezone-aware)"
            )
        if aware:
            pred_dt = pred_dt.astimezone(timezone.utc)
            eval_dt = eval_dt.astimezone(timezone.utc)

        if eval_dt < pred_dt:
            raise EventError(f"sample {sid!r}: evaluation_time precedes prediction_time")

        group = raw.get("group")
        if group is not None and (not isinstance(group, str) or len(group) > 100):
            raise EventError(f"sample {sid!r}: group must be a string of at most 100 chars")

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict) or len(str(metadata)) > 2000:
            raise EventError(f"sample {sid!r}: metadata must be a small object")

        out.append(
            {
                "sample_id": sid,
                "prediction_time": pred_dt.isoformat(),
                "evaluation_time": eval_dt.isoformat(),
                "pred_dt": pred_dt,
                "eval_dt": eval_dt,
                "group": group,
                "label": _finite_or_none(raw.get("label"), "label", sid),
                "prediction": _finite_or_none(raw.get("prediction"), "prediction", sid),
                "score": _finite_or_none(raw.get("score"), "score", sid),
                "ret": _finite_or_none(raw.get("ret"), "ret", sid),
                "weight": _finite_or_none(raw.get("weight"), "weight", sid),
                "metadata": metadata,
            }
        )

    # Deterministic stable ordering; ties break on sample_id.
    out.sort(key=lambda s: (s["pred_dt"], s["eval_dt"], s["sample_id"]))
    return out


def intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Closed-interval overlap (boundary contact counts): mirrors app.finml.cv."""
    return a_start <= b_end and a_end >= b_start


def strip_datetimes(sample: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe copy of a normalized sample (drops the parsed datetimes)."""
    return {k: v for k, v in sample.items() if k not in ("pred_dt", "eval_dt")}


__all__ = [
    "MAX_SAMPLES",
    "MIN_SAMPLES",
    "EventError",
    "normalize_samples",
    "intervals_overlap",
    "strip_datetimes",
]
