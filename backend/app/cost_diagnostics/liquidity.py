"""
No-look-ahead execution-input policy (v1).

Spread, volatility, ADV and volume values used to estimate the cost of an
execution at timestamp t must have been observable at t under the documented
information-timing policy:

* trailing statistics at series index j use only ``values[j-lag-lookback+1
  .. j-lag]`` with ``lag >= 1`` — the value effective for an execution never
  includes the execution period itself;
* centered windows and negative lags are prohibited (integrity ``invalid``);
* full-sample averages are descriptive only and are never leakage-safe;
* supplied values carry a declared basis; an undeclared basis is honestly
  ``unknown``, never silently upgraded.

Integrity trust order (least to most trusted):
``invalid < unknown < full_sample_descriptive < declared <
verified_from_dataset_lineage < verified_causal_input < supplied_realized``.
A run's integrity is the least trusted state among execution inputs actually
used; a run whose costs come only from declared configuration assumptions is
``declared``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

INTEGRITY_STATES = (
    "supplied_realized",
    "verified_causal_input",
    "verified_from_dataset_lineage",
    "declared",
    "full_sample_descriptive",
    "unknown",
    "invalid",
)

_TRUST_ORDER = {
    "invalid": 0,
    "unknown": 1,
    "full_sample_descriptive": 2,
    "declared": 3,
    "verified_from_dataset_lineage": 4,
    "verified_causal_input": 5,
    "supplied_realized": 6,
}

MIN_LOOKBACK = 1
MAX_LOOKBACK = 250
MIN_LAG = 1
MAX_LAG = 30


class LiquidityInputError(ValueError):
    """Raised when a liquidity-input policy is invalid."""


def least_trusted(states: Sequence[str]) -> str:
    """Return the least trusted state among ``states`` (``declared`` if empty)."""
    pool = [s for s in states if s in _TRUST_ORDER]
    if not pool:
        return "declared"
    return min(pool, key=lambda s: _TRUST_ORDER[s])


def classify_supplied_input(spec: Dict[str, Any],
                            *, dataset_linked: bool,
                            input_key: Optional[str] = None) -> Dict[str, Any]:
    """Classify one per-observation supplied input into an integrity state.

    Returns ``{"integrity": state, "warnings": [...]}``.  Nothing is silently
    upgraded: dataset-lineage claims without a linked dataset version degrade
    to ``declared`` with a warning; centered windows and non-positive lags on
    a trailing claim are ``invalid``.
    """
    warnings: List[str] = []
    basis = spec.get("basis", "unknown")
    window = spec.get("window", "trailing")
    lag = spec.get("lag")
    if lag is not None and lag < 0:
        return {"integrity": "invalid",
                "warnings": ["negative lag on an execution input is prohibited"]}
    if window == "centered":
        return {"integrity": "invalid",
                "warnings": ["centered windows on execution inputs are prohibited"]}
    if basis == "supplied_realized":
        return {"integrity": "supplied_realized", "warnings": warnings}
    if basis == "trailing":
        if lag is None or lag < MIN_LAG:
            return {"integrity": "invalid",
                    "warnings": [
                        "trailing execution inputs require lag >= 1; a value "
                        "computed through the execution period looks ahead"]}
        lookback = spec.get("lookback")
        if lookback is None or lookback < MIN_LOOKBACK:
            return {"integrity": "invalid",
                    "warnings": ["trailing execution inputs require lookback >= 1"]}
        if input_key == "volatility" and lookback < 2:
            return {"integrity": "invalid",
                    "warnings": [
                        "a trailing volatility claim needs lookback >= 2 — a "
                        "sample standard deviation is undefined at n = 1"]}
        return {"integrity": "verified_causal_input", "warnings": warnings}
    if basis == "dataset_lineage":
        if dataset_linked:
            return {"integrity": "verified_from_dataset_lineage", "warnings": warnings}
        warnings.append(
            "input claims dataset lineage but the run links no dataset "
            "version; treated as declared")
        return {"integrity": "declared", "warnings": warnings}
    if basis == "declared":
        return {"integrity": "declared", "warnings": warnings}
    if basis == "full_sample":
        warnings.append(
            "full-sample execution input is descriptive only and never "
            "leakage-safe")
        return {"integrity": "full_sample_descriptive", "warnings": warnings}
    warnings.append("execution input has no declared basis; provenance unknown")
    return {"integrity": "unknown", "warnings": warnings}


def validate_series(series: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a run-level liquidity series used for trailing derivation.

    Ordering is enforced on the PARSED timestamps — a lexicographic string
    comparison could accept chronologically disordered mixed-offset
    timestamps and silently defeat the trailing (no-look-ahead) guarantee.
    """
    if not isinstance(series, dict):
        raise LiquidityInputError("liquidity_series must be an object")
    stamps = series.get("timestamps")
    if not isinstance(stamps, list) or len(stamps) < 3 or len(stamps) > 5000:
        raise LiquidityInputError(
            "liquidity_series.timestamps must be a list of 3..5000 entries")
    clean = []
    parsed = []
    for i, s in enumerate(stamps):
        if not isinstance(s, str) or not s.strip():
            raise LiquidityInputError(f"liquidity_series.timestamps[{i}] invalid")
        text = s.strip()
        try:
            from datetime import datetime as _dt
            parsed.append(_dt.fromisoformat(text))
        except ValueError:
            raise LiquidityInputError(
                f"liquidity_series.timestamps[{i}] is not a valid ISO-8601 "
                "timestamp")
        clean.append(text)
    has_tz = parsed[0].tzinfo is not None
    if any((p.tzinfo is not None) != has_tz for p in parsed):
        raise LiquidityInputError(
            "liquidity_series.timestamps mix timezone-aware and naive values")
    if any(parsed[i] >= parsed[i + 1] for i in range(len(parsed) - 1)):
        raise LiquidityInputError(
            "liquidity_series.timestamps must be strictly increasing in time")
    out: Dict[str, Any] = {"timestamps": clean}
    for key, non_negative in (("volume", True), ("returns", False)):
        if series.get(key) is None:
            continue
        vals = series[key]
        if not isinstance(vals, list) or len(vals) != len(clean):
            raise LiquidityInputError(
                f"liquidity_series.{key} must align with timestamps")
        arr = []
        for i, v in enumerate(vals):
            if isinstance(v, bool):
                raise LiquidityInputError(f"liquidity_series.{key}[{i}] invalid")
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise LiquidityInputError(f"liquidity_series.{key}[{i}] invalid")
            if not math.isfinite(f) or (non_negative and f < 0):
                raise LiquidityInputError(
                    f"liquidity_series.{key}[{i}] must be finite"
                    + (" and >= 0" if non_negative else ""))
            arr.append(f)
        out[key] = arr
    return out


def derive_trailing(values: Sequence[float], lookback: int, lag: int,
                    stat: str) -> List[Optional[float]]:
    """Trailing statistic with an explicit information lag.

    ``derived[j]`` uses ``values[j-lag-lookback+1 .. j-lag]`` only; indices
    with insufficient history are ``None`` (honestly unavailable, never
    zero-filled).  ``stat`` is ``mean`` (ADV) or ``std`` (sample volatility,
    ddof=1, requiring lookback >= 2).
    """
    if not (MIN_LOOKBACK <= lookback <= MAX_LOOKBACK):
        raise LiquidityInputError(
            f"lookback must be in [{MIN_LOOKBACK}, {MAX_LOOKBACK}]")
    if not (MIN_LAG <= lag <= MAX_LAG):
        raise LiquidityInputError(f"lag must be in [{MIN_LAG}, {MAX_LAG}]")
    if stat not in ("mean", "std"):
        raise LiquidityInputError("stat must be 'mean' or 'std'")
    if stat == "std" and lookback < 2:
        raise LiquidityInputError("std requires lookback >= 2")
    arr = np.asarray(values, dtype=float)
    out: List[Optional[float]] = []
    for j in range(len(arr)):
        end = j - lag            # inclusive end of the permitted window
        start = end - lookback + 1
        if start < 0:
            out.append(None)
            continue
        window = arr[start:end + 1]
        if stat == "mean":
            value = float(np.mean(window))
        else:
            value = float(np.std(window, ddof=1))
        if not math.isfinite(value):
            raise LiquidityInputError(
                "trailing statistic is not finite; liquidity series values "
                "are too extreme")
        out.append(value)
    return out


def map_series_to_observations(series_timestamps: Sequence[str],
                               derived: Sequence[Optional[float]],
                               obs_timestamps: Sequence[str]
                               ) -> List[Optional[float]]:
    """Exact-match alignment of a derived series to observation timestamps.

    No interpolation and no nearest-neighbour fallback: an observation whose
    timestamp is not present in the series is honestly unavailable.
    """
    index = {ts: i for i, ts in enumerate(series_timestamps)}
    out: List[Optional[float]] = []
    for ts in obs_timestamps:
        i = index.get(ts)
        out.append(derived[i] if i is not None else None)
    return out
