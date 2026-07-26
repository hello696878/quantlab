"""
Period/asset observation model, weight timing and integrity (v1).

An attribution observation set is derived from a STORED Phase 56 portfolio
run: its parsed chronological timeline supplies the periods, its validated
universe supplies the asset returns and explicit group labels, and its
stored rebalances supply the weights.  Nothing is fetched, inferred or
fabricated here.

Period convention (documented): period ``t`` spans ``timestamps[t]`` to
``timestamps[t+1]`` — its return is the stored ``returns[t]``, and the
weights that govern it are the weights **known at its start**.  Periods are
strictly increasing and non-overlapping by construction.

Weight timing (the no-look-ahead contract):

* a rebalance with decision index ``i`` produces weights that govern period
  ``i`` onward — the Phase 56 estimation contract already guarantees those
  weights were estimated from returns through ``i − lag`` with ``lag ≥ 1``,
  so period ``i`` never informs its own weights;
* between rebalances the book **drifts** by the identical recursion Phase 56
  uses for its realized return series (``rebalance.drift_weights``), so the
  beginning-of-period weight of period ``t`` is a pure function of periods
  strictly before ``t``;
* ``end_of_period`` weight timing is accepted only as an explicitly
  INVALID descriptive declaration — it is never silently treated as a
  beginning-of-period weight;
* a future rebalance can never alter an earlier period's weights, and a
  future return can never alter an earlier contribution (both are
  adversarially tested).

Integrity states: ``verified_from_stored_rebalance`` (weights come from a
stored Phase 56 rebalance whose estimation window is causal),
``verified_causal_weights`` (explicitly supplied weights with a declared
causal basis), ``supplied_descriptive`` (supplied weights without a causal
basis — never called verified), ``full_sample_descriptive`` (the linked
portfolio estimated on the whole sample), ``unknown``, ``invalid``.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

MIN_PERIODS = 1
MAX_PERIODS = 2000
MIN_ASSETS = 1
MAX_ASSETS = 20
MAX_GROUPS = 8
MAX_ID_LENGTH = 64
MAX_METADATA_KEYS = 20

RETURN_CONVENTIONS = ("simple",)          # log returns deferred in v1
RETURN_FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "annual",
                      "unspecified")
WEIGHT_TIMINGS = ("beginning_of_period", "end_of_period")
BENCHMARK_TIMINGS = ("beginning_of_period",)
INTEGRITY_STATES = ("verified_from_stored_rebalance", "verified_causal_weights",
                    "supplied_descriptive", "full_sample_descriptive",
                    "unknown", "invalid")

# periods per year used ONLY when the caller declares a known frequency
PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12,
                    "quarterly": 4, "annual": 1}

UNCLASSIFIED_GROUP = "unclassified"


class ObservationError(ValueError):
    """Raised for invalid observation inputs."""


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationError(f"{field} must be a finite number")
    f = float(value)
    if not math.isfinite(f):
        raise ObservationError(f"{field} must be a finite number")
    return f


def _timestamp(value: Any, field: str) -> Tuple[datetime, bool]:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"{field} must be a non-empty ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationError(f"{field} must be a valid ISO timestamp") from exc
    return parsed, parsed.tzinfo is not None


def validate_policy(raw: Any) -> Dict[str, Any]:
    """The explicit attribution policy (every field stated, none inferred)."""
    cfg = dict(raw or {})
    unknown = set(cfg) - {"return_convention", "return_frequency",
                          "weight_timing_policy", "benchmark_timing_policy",
                          "reconciliation_tolerance", "missing_input_policy"}
    if unknown:
        raise ObservationError(
            "unsupported policy keys (a typo is never silently ignored): "
            + ", ".join(sorted(unknown)))
    convention = cfg.get("return_convention", "simple")
    if convention not in RETURN_CONVENTIONS:
        raise ObservationError(
            "return_convention must be 'simple' in v1 (log-return "
            "attribution is deferred: contributions are not additive under "
            "log returns without a documented conversion)")
    frequency = cfg.get("return_frequency", "unspecified")
    if frequency not in RETURN_FREQUENCIES:
        raise ObservationError(
            f"return_frequency must be one of {', '.join(RETURN_FREQUENCIES)}")
    weight_timing = cfg.get("weight_timing_policy", "beginning_of_period")
    if weight_timing not in WEIGHT_TIMINGS:
        raise ObservationError(
            f"weight_timing_policy must be one of {', '.join(WEIGHT_TIMINGS)}")
    bench_timing = cfg.get("benchmark_timing_policy", "beginning_of_period")
    if bench_timing not in BENCHMARK_TIMINGS:
        raise ObservationError(
            "benchmark_timing_policy must be 'beginning_of_period' in v1")
    tolerance = cfg.get("reconciliation_tolerance", 1e-9)
    tolerance = _finite(tolerance, "reconciliation_tolerance")
    if not (0 < tolerance <= 1e-2):
        raise ObservationError(
            "reconciliation_tolerance must be in (0, 1e-2]")
    missing = cfg.get("missing_input_policy", "unavailable")
    if missing != "unavailable":
        raise ObservationError(
            "missing_input_policy must be 'unavailable' in v1 — a missing "
            "weight, return or benchmark period is never zero-filled")
    return {
        "return_convention": convention,
        "return_frequency": frequency,
        "weight_timing_policy": weight_timing,
        "benchmark_timing_policy": bench_timing,
        "reconciliation_tolerance": tolerance,
        "missing_input_policy": missing,
        "period_convention": ("period t spans timestamps[t]..timestamps[t+1]; "
                              "its return is returns[t] and its weights are "
                              "those known at timestamps[t]"),
        "contribution_formula": ("contribution_i,t = "
                                 "portfolio_beginning_weight_i,t x return_i,t"),
    }


def periods_per_year(frequency: str) -> Optional[int]:
    """Annualization factor — None when the frequency is unspecified, so
    annualized figures stay honestly unavailable rather than assumed."""
    return PERIODS_PER_YEAR.get(frequency)


def beginning_weight_path(rebalances: List[Dict[str, Any]],
                          asset_ids: List[str],
                          returns_matrix: List[List[float]],
                          n_periods: int) -> List[Optional[Dict[str, float]]]:
    """Beginning-of-period weights for every period, or None where no book
    exists yet.

    Identical recursion to ``portfolio_diagnostics.rebalance.drift_weights``
    / ``portfolio_returns``: the target weights of the rebalance whose
    decision index is t become the beginning weights of period t, and
    otherwise the previous period's book drifts by its own realized return.
    A non-positive or non-finite book value ends the path honestly (the
    remaining periods are unavailable) instead of renormalizing.

    ``rebalances`` rows must already carry ``decision_index``.
    """
    targets = {r["decision_index"]: r["weights"] for r in rebalances
               if r.get("weights") is not None
               and r.get("decision_index") is not None}
    out: List[Optional[Dict[str, float]]] = [None] * n_periods
    current: Optional[Dict[str, float]] = None
    for t in range(n_periods):
        if t in targets:
            current = {a: float(targets[t].get(a, 0.0)) for a in asset_ids}
        if current is None:
            continue
        out[t] = dict(current)
        period_return = sum(current[a] * returns_matrix[k][t]
                            for k, a in enumerate(asset_ids))
        next_value = 1.0 + period_return
        if not math.isfinite(next_value) or next_value <= 0:
            current = None            # book wiped out: later periods unavailable
            continue
        current = {a: current[a] * (1.0 + returns_matrix[k][t]) / next_value
                   for k, a in enumerate(asset_ids)}
        if any(not math.isfinite(v) for v in current.values()):
            current = None
    return out


def build_observations(prun: Dict[str, Any],
                       rebalances: List[Dict[str, Any]],
                       policy: Dict[str, Any],
                       *, window: Optional[Tuple[str, str]] = None
                       ) -> Dict[str, Any]:
    """Assemble the period/asset observation set from stored Phase 56 data.

    Returns periods (with start/end/information_available_at), the ordered
    asset ids, their explicit groups, the beginning weights and returns per
    period, plus the periods that are honestly unavailable.
    """
    universe = prun["universe"]
    timestamps: List[str] = universe["timestamps"]
    assets = universe["assets"]
    if not assets:
        raise ObservationError("the linked portfolio run has no assets")
    if len(assets) > MAX_ASSETS:
        raise ObservationError(f"at most {MAX_ASSETS} assets are supported")
    asset_ids = [a["asset_id"] for a in assets]
    if any(not isinstance(a, str) or not a.strip() or len(a) > MAX_ID_LENGTH
           for a in asset_ids):
        raise ObservationError(
            f"asset ids must be non-empty strings up to {MAX_ID_LENGTH} chars")
    if len(set(asset_ids)) != len(asset_ids):
        raise ObservationError("duplicate asset ids in the linked universe")
    groups: Dict[str, str] = {}
    for asset in assets:
        group = asset.get("group") or UNCLASSIFIED_GROUP
        if not isinstance(group, str) or not group.strip() \
                or len(group.strip()) > MAX_ID_LENGTH:
            raise ObservationError(
                f"group for asset {asset['asset_id']!r} must be a non-empty "
                f"string up to {MAX_ID_LENGTH} chars")
        groups[asset["asset_id"]] = group.strip()
    distinct_groups = sorted(set(groups.values()))
    if len(distinct_groups) > MAX_GROUPS:
        raise ObservationError(f"at most {MAX_GROUPS} groups are supported")
    returns_matrix = [a["returns"] for a in assets]

    n = len(timestamps)
    if n < 2:
        raise ObservationError(
            "attribution needs at least two timeline observations")
    parsed_timestamps = [
        _timestamp(ts, f"timestamps[{i}]")
        for i, ts in enumerate(timestamps)]
    if len({aware for _, aware in parsed_timestamps}) > 1:
        raise ObservationError(
            "timestamps must use one timezone convention; naive and "
            "timezone-aware values cannot be mixed")
    for i in range(1, len(parsed_timestamps)):
        if parsed_timestamps[i][0] <= parsed_timestamps[i - 1][0]:
            raise ObservationError(
                "timestamps must be unique and strictly increasing")
    # the last timeline observation opens no complete period
    period_count_all = n - 1
    for k, series in enumerate(returns_matrix):
        if not isinstance(series, list) or len(series) != n:
            raise ObservationError(
                f"returns for asset {asset_ids[k]!r} must contain exactly "
                f"{n} observations aligned to timestamps")
        returns_matrix[k] = [
            _finite(value, f"returns[{asset_ids[k]}][{t}]")
            for t, value in enumerate(series)]

    index = {ts: i for i, ts in enumerate(timestamps)}
    lo, hi = 0, period_count_all - 1
    if window is not None:
        start_ts, end_ts = window
        if start_ts not in index or end_ts not in index:
            raise ObservationError(
                "the observation window must reference stored timestamps "
                "(no fabricated period boundaries)")
        lo, hi = index[start_ts], index[end_ts] - 1
        if hi < lo:
            raise ObservationError(
                "the observation window must contain at least one period")
    if hi - lo + 1 > MAX_PERIODS:
        raise ObservationError(f"at most {MAX_PERIODS} periods are supported")

    weight_path = beginning_weight_path(rebalances, asset_ids,
                                        returns_matrix, period_count_all)

    periods: List[Dict[str, Any]] = []
    unavailable: List[Dict[str, Any]] = []
    for t in range(lo, hi + 1):
        weights = weight_path[t]
        if weights is None:
            unavailable.append({
                "period_id": t,
                "period_start": timestamps[t],
                "period_end": timestamps[t + 1],
                "reason": ("no stored book governs this period (it precedes "
                           "the first solved rebalance, or the book was "
                           "wiped out); weights are never back-filled"),
            })
            continue
        rows = []
        for k, aid in enumerate(asset_ids):
            rows.append({
                "asset_id": aid,
                "group_id": groups[aid],
                "portfolio_beginning_weight": weights.get(aid, 0.0),
                "asset_return": float(returns_matrix[k][t]),
            })
        periods.append({
            "period_id": t,
            "period_start": timestamps[t],
            "period_end": timestamps[t + 1],
            # weights are known at the period start; the Phase 56 estimation
            # contract guarantees they used data through decision - lag
            "information_available_at": timestamps[t],
            "rows": rows,
        })
    if not periods:
        raise ObservationError(
            "no period in the requested window has stored beginning-of-period "
            "weights")
    return {
        "asset_ids": asset_ids,
        "groups": groups,
        "distinct_groups": distinct_groups,
        "periods": periods,
        "unavailable_periods": unavailable,
        "period_count": len(periods),
        "observation_start": periods[0]["period_start"],
        "observation_end": periods[-1]["period_end"],
        "frequency": policy["return_frequency"],
        "timeline_length": n,
    }


def classify_integrity(prun: Dict[str, Any], policy: Dict[str, Any],
                       rebalances: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Integrity of the weight provenance (module doc)."""
    warnings: List[str] = []
    if policy["weight_timing_policy"] == "end_of_period":
        return {"integrity": "invalid", "warnings": [
            "end-of-period weights were declared: a weight formed at the END "
            "of a period already embeds that period's return, so it is never "
            "used as a beginning-of-period weight and this run cannot be "
            "verified or become a baseline"]}
    estimation = (prun.get("configuration") or {}).get("estimation") or {}
    mode = estimation.get("mode")
    if mode == "full_sample":
        warnings.append(
            "the linked portfolio estimated its weights on the FULL sample; "
            "attribution of those weights is descriptive only and is never "
            "called leakage-safe")
        return {"integrity": "full_sample_descriptive", "warnings": warnings}
    solved = [r for r in rebalances if r.get("weights")]
    if not solved:
        return {"integrity": "invalid", "warnings": [
            "the linked portfolio run has no rebalance with solved weights"]}
    method = prun.get("method")
    if method == "user_supplied":
        # the Phase 56 provenance vocabulary is authoritative here; Phase 56
        # stores the validated block as ``user_provenance``
        basis = ((prun.get("configuration") or {})
                 .get("user_provenance") or {}).get("basis")
        if basis == "causal_rolling":
            return {"integrity": "verified_causal_weights", "warnings": warnings}
        if basis == "centered":
            return {"integrity": "invalid", "warnings": [
                "the linked portfolio declares a CENTERED weight basis, which "
                "uses data from after each decision; attribution of those "
                "weights can never be verified"]}
        if basis == "full_sample":
            warnings.append(
                "the linked portfolio declares a full-sample weight basis; "
                "attribution of those weights is descriptive only")
            return {"integrity": "full_sample_descriptive", "warnings": warnings}
        return {"integrity": "supplied_descriptive", "warnings": [
            f"user-supplied weights with a {basis or 'unknown'!s} basis: "
            "descriptive, never independently verified"]}
    return {"integrity": "verified_from_stored_rebalance", "warnings": warnings}


__all__ = [
    "MIN_PERIODS", "MAX_PERIODS", "MAX_ASSETS", "MAX_GROUPS",
    "RETURN_CONVENTIONS", "RETURN_FREQUENCIES", "WEIGHT_TIMINGS",
    "BENCHMARK_TIMINGS", "INTEGRITY_STATES", "PERIODS_PER_YEAR",
    "UNCLASSIFIED_GROUP", "ObservationError", "validate_policy",
    "periods_per_year", "beginning_weight_path", "build_observations",
    "classify_integrity",
]
