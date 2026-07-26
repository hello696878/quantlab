"""
Explicit benchmark definitions (v1).

A benchmark is never selected automatically, never downloaded, and never
falls back to an implicit equal-weight book.  The caller states the
benchmark identity in full and the lab validates it:

* ``fixed_weights`` — an explicit weight vector, restored at the beginning
  of EVERY period (a documented periodic-rebalancing benchmark).  The
  weights must be supplied; "equal weight" is only ever a benchmark the
  caller writes out explicitly.
* ``supplied_per_period`` — an explicit weight vector per period, in the
  benchmark's own asset order.
* ``buy_and_hold`` — an explicit initial weight vector that then DRIFTS
  with benchmark returns (no periodic restoration), by the same recursion
  the portfolio uses.

Benchmark asset returns default to the linked portfolio universe's stored
returns **only for assets shared with that universe** — an exact reuse of
stored data, never a fabrication.  Benchmark-only assets must supply their
own returns explicitly; a benchmark-only asset without returns is rejected
rather than silently dropped.

Benchmark weights are validated (finite, bounded, and their sum disclosed);
they are never renormalized silently.  The benchmark's asset and group
universe is compared with the portfolio's and every difference is
disclosed.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.portfolio_attribution.observations import (
    MAX_ASSETS,
    MAX_GROUPS,
    MAX_ID_LENGTH,
    UNCLASSIFIED_GROUP,
    ObservationError,
)

BENCHMARK_KINDS = ("fixed_weights", "supplied_per_period", "buy_and_hold")
BENCHMARK_SOURCES = ("user_supplied", "demo_fixture", "linked_dataset",
                     "custom_descriptive")
MAX_ABS_WEIGHT = 10.0
WEIGHT_SUM_TOLERANCE = 1e-9
MAX_METADATA_KEYS = 20


class BenchmarkError(ValueError):
    """Raised for invalid benchmark definitions."""


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkError(f"{field} must be a non-empty string")
    text = value.strip()
    if len(text) > MAX_ID_LENGTH:
        raise BenchmarkError(f"{field} must be at most {MAX_ID_LENGTH} chars")
    return text


def _bounded_text(value: Any, field: str, *, maximum: int,
                  default: str, allow_empty: bool = False) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise BenchmarkError(f"{field} must be a string")
    text = value.strip()
    if not text and not allow_empty:
        raise BenchmarkError(f"{field} must be a non-empty string")
    if len(text) > maximum:
        raise BenchmarkError(f"{field} must be at most {maximum} chars")
    return text

def _weight(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkError(f"{field} must be a finite number")
    f = float(value)
    if not math.isfinite(f):
        raise BenchmarkError(f"{field} must be a finite number")
    if abs(f) > MAX_ABS_WEIGHT:
        raise BenchmarkError(f"{field} exceeds the ±{MAX_ABS_WEIGHT:g} bound")
    return f


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkError(f"{field} must be a non-empty ISO timestamp")
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkError(f"{field} must be a valid ISO timestamp") from exc


def _metadata(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > MAX_METADATA_KEYS:
        raise BenchmarkError(
            f"benchmark metadata must be an object with at most "
            f"{MAX_METADATA_KEYS} keys")
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key or len(key) > MAX_ID_LENGTH:
            raise BenchmarkError(
                "benchmark metadata keys must be non-empty bounded strings")
        if isinstance(value, bool) or value is None or isinstance(value, str):
            out[key] = value
        elif isinstance(value, (int, float)) and math.isfinite(float(value)):
            out[key] = value
        else:
            raise BenchmarkError(
                f"benchmark metadata[{key!r}] must be a finite scalar")
    return out


def validate_benchmark(raw: Any, *, portfolio_asset_ids: List[str],
                       portfolio_groups: Dict[str, str],
                       period_count: int,
                       period_starts: Optional[List[str]] = None
                       ) -> Dict[str, Any]:
    """Validate an explicit benchmark definition against the observation set."""
    if raw is None:
        return {"configured": False,
                "note": ("no benchmark configured: benchmark-relative "
                         "measurements are unavailable — a benchmark is "
                         "never selected automatically")}
    if not isinstance(raw, dict):
        raise BenchmarkError("benchmark definition must be an object")
    known = {"benchmark_id", "name", "description", "source", "kind",
             "asset_ids", "weights", "weights_per_period", "returns",
             "groups", "return_convention", "timing_policy",
             "dataset_version_id", "metadata", "period_starts",
             "information_available_at"}
    unknown = set(raw) - known
    if unknown:
        raise BenchmarkError(
            "unsupported benchmark keys (a typo is never silently ignored): "
            + ", ".join(sorted(unknown)))

    kind = raw.get("kind")
    if kind not in BENCHMARK_KINDS:
        raise BenchmarkError(
            f"benchmark kind must be one of {', '.join(BENCHMARK_KINDS)}")
    source = raw.get("source", "user_supplied")
    if source not in BENCHMARK_SOURCES:
        raise BenchmarkError(
            f"benchmark source must be one of {', '.join(BENCHMARK_SOURCES)}")
    convention = raw.get("return_convention", "simple")
    if convention != "simple":
        raise BenchmarkError(
            "benchmark return_convention must be 'simple' and must match the "
            "portfolio convention (mismatched conventions are never mixed)")
    timing = raw.get("timing_policy", "beginning_of_period")
    if timing != "beginning_of_period":
        raise BenchmarkError(
            "benchmark timing_policy must be 'beginning_of_period' in v1")

    asset_ids_raw = raw.get("asset_ids")
    if not isinstance(asset_ids_raw, list) or not asset_ids_raw:
        raise BenchmarkError(
            "the benchmark must declare an ordered, non-empty asset_ids list")
    asset_ids = [_identifier(a, "benchmark asset_id") for a in asset_ids_raw]
    if len(set(asset_ids)) != len(asset_ids):
        raise BenchmarkError("duplicate benchmark asset ids")
    if len(asset_ids) > MAX_ASSETS:
        raise BenchmarkError(
            f"at most {MAX_ASSETS} benchmark assets are supported")

    # groups: explicit only; shared assets inherit the portfolio's stored group
    groups: Dict[str, str] = {}
    supplied_groups = raw.get("groups") or {}
    if not isinstance(supplied_groups, dict):
        raise BenchmarkError("benchmark groups must be an object")
    for key in supplied_groups:
        if key not in asset_ids:
            raise BenchmarkError(
                f"benchmark group references unknown benchmark asset {key!r}")
    for aid in asset_ids:
        if aid in supplied_groups:
            groups[aid] = _identifier(supplied_groups[aid],
                                      f"benchmark group[{aid}]")
        elif aid in portfolio_groups:
            groups[aid] = portfolio_groups[aid]
        else:
            raise BenchmarkError(
                f"benchmark-only asset {aid!r} needs an explicit group — "
                "groups are never inferred from asset names")
    if len(set(groups.values())) > MAX_GROUPS:
        raise BenchmarkError(f"at most {MAX_GROUPS} benchmark groups")

    n = len(asset_ids)
    weights_per_period: List[List[float]]
    supplied_period_starts: List[str] = []
    information_available_at: List[str] = []
    if kind == "supplied_per_period":
        rows = raw.get("weights_per_period")
        if not isinstance(rows, list) or len(rows) != period_count:
            raise BenchmarkError(
                "supplied_per_period requires one weight row per attribution "
                f"period ({period_count} expected)")
        weights_per_period = []
        for t, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != n:
                raise BenchmarkError(
                    f"benchmark weight row {t} must have {n} entries in the "
                    "declared asset order")
            weights_per_period.append(
                [_weight(v, f"benchmark weight[{t}][{i}]")
                 for i, v in enumerate(row)])
        base_weights = list(weights_per_period[0])
        supplied_period_starts = raw.get("period_starts")
        information_available_at = raw.get("information_available_at")
        if not isinstance(supplied_period_starts, list) \
                or len(supplied_period_starts) != period_count:
            raise BenchmarkError(
                "supplied_per_period requires one period_start per "
                "attribution period")
        if not isinstance(information_available_at, list) \
                or len(information_available_at) != period_count:
            raise BenchmarkError(
                "supplied_per_period requires one information_available_at "
                "timestamp per attribution period")
        if period_starts is None or supplied_period_starts != period_starts:
            raise BenchmarkError(
                "supplied benchmark period_starts must exactly match the "
                "portfolio attribution periods")
        for t, (available, start) in enumerate(zip(
                information_available_at, supplied_period_starts)):
            available_dt = _timestamp(
                available, f"information_available_at[{t}]")
            start_dt = _timestamp(start, f"period_starts[{t}]")
            if (available_dt.tzinfo is None) != (start_dt.tzinfo is None):
                raise BenchmarkError(
                    "benchmark availability and period timestamps must use "
                    "the same timezone convention")
            if available_dt > start_dt:
                raise BenchmarkError(
                    f"benchmark weights for period {t} were not available at "
                    "the beginning of the period")
    else:
        base = raw.get("weights")
        if not isinstance(base, list) or len(base) != n:
            raise BenchmarkError(
                f"the benchmark must declare {n} weights in its asset order "
                "(an equal-weight benchmark must be written out explicitly)")
        base_weights = [_weight(v, f"benchmark weight[{i}]")
                        for i, v in enumerate(base)]
        weights_per_period = []      # filled at evaluation time for both kinds

    # explicit benchmark-only returns
    supplied_returns = raw.get("returns") or {}
    if not isinstance(supplied_returns, dict):
        raise BenchmarkError("benchmark returns must be an object")
    for key in supplied_returns:
        if key not in asset_ids:
            raise BenchmarkError(
                f"benchmark returns reference unknown benchmark asset {key!r}")
    returns: Dict[str, List[float]] = {}
    for aid, series in supplied_returns.items():
        if not isinstance(series, list) or len(series) != period_count:
            raise BenchmarkError(
                f"benchmark returns[{aid}] must have {period_count} values "
                "(one per attribution period)")
        clean = []
        for t, v in enumerate(series):
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or not math.isfinite(float(v)):
                raise BenchmarkError(
                    f"benchmark returns[{aid}][{t}] must be a finite number")
            clean.append(float(v))
        returns[aid] = clean
    missing = [a for a in asset_ids
               if a not in returns and a not in portfolio_asset_ids]
    if missing:
        raise BenchmarkError(
            "benchmark-only assets need explicit returns (never fabricated): "
            + ", ".join(sorted(missing)))

    metadata = _metadata(raw.get("metadata"))
    weight_sum = sum(base_weights)
    dataset_version_id = raw.get("dataset_version_id")
    if dataset_version_id is not None and (
            isinstance(dataset_version_id, bool)
            or not isinstance(dataset_version_id, int)
            or dataset_version_id <= 0):
        raise BenchmarkError(
            "benchmark dataset_version_id must be a positive integer")
    portfolio_only = sorted(set(portfolio_asset_ids) - set(asset_ids))
    benchmark_only = sorted(set(asset_ids) - set(portfolio_asset_ids))
    if benchmark_only and not metadata.get("currency"):
        raise BenchmarkError(
            "benchmark-only assets require explicit metadata.currency; "
            "currency conversion is never inferred or performed")
    return {
        "configured": True,
        "benchmark_id": _identifier(raw.get("benchmark_id") or "benchmark",
                                    "benchmark_id"),
        "name": _bounded_text(raw.get("name"), "benchmark name",
                              maximum=200, default="Benchmark"),
        "description": _bounded_text(
            raw.get("description"), "benchmark description", maximum=2000,
            default="", allow_empty=True),
        "source": source,
        "kind": kind,
        "asset_ids": asset_ids,
        "groups": groups,
        "base_weights": base_weights,
        "weights_per_period": weights_per_period,
        "returns": returns,
        "return_convention": convention,
        "timing_policy": timing,
        "dataset_version_id": dataset_version_id,
        "metadata": metadata,
        "period_starts": supplied_period_starts,
        "information_available_at": information_available_at,
        "weight_sum": weight_sum,
        "weight_sum_is_one": abs(weight_sum - 1.0) <= WEIGHT_SUM_TOLERANCE,
        "portfolio_only_assets": portfolio_only,
        "benchmark_only_assets": benchmark_only,
        "shared_asset_count": len(set(asset_ids) & set(portfolio_asset_ids)),
        "note": ("benchmark weights are used as declared and are never "
                 "silently renormalized; a weight sum other than 1 is "
                 "disclosed, not corrected"),
    }


def benchmark_weight_path(benchmark: Dict[str, Any],
                          returns_by_period: List[Dict[str, float]]
                          ) -> List[Optional[Dict[str, float]]]:
    """Beginning-of-period benchmark weights for every period.

    ``fixed_weights`` restores the declared vector each period;
    ``supplied_per_period`` uses the declared rows; ``buy_and_hold`` drifts
    the declared vector by realized benchmark returns using the same
    recursion as the portfolio (a wiped-out book ends the path honestly).
    """
    asset_ids = benchmark["asset_ids"]
    base = {a: benchmark["base_weights"][i] for i, a in enumerate(asset_ids)}
    n_periods = len(returns_by_period)
    out: List[Optional[Dict[str, float]]] = []
    if benchmark["kind"] == "supplied_per_period":
        for t in range(n_periods):
            row = benchmark["weights_per_period"][t]
            out.append({a: row[i] for i, a in enumerate(asset_ids)})
        return out
    if benchmark["kind"] == "fixed_weights":
        return [dict(base) for _ in range(n_periods)]
    current: Optional[Dict[str, float]] = dict(base)
    for t in range(n_periods):
        if current is None:
            out.append(None)
            continue
        out.append(dict(current))
        rets = returns_by_period[t]
        period_return = sum(current[a] * rets[a] for a in asset_ids)
        next_value = 1.0 + period_return
        if not math.isfinite(next_value) or next_value <= 0:
            current = None
            continue
        current = {a: current[a] * (1.0 + rets[a]) / next_value
                   for a in asset_ids}
        if any(not math.isfinite(v) for v in current.values()):
            current = None
    return out


def benchmark_returns_by_period(benchmark: Dict[str, Any],
                                portfolio_returns_by_period: List[Dict[str, float]]
                                ) -> List[Dict[str, float]]:
    """Per-period benchmark asset returns: explicit supplied series where
    given, otherwise the STORED portfolio-universe return of the same asset
    (exact reuse, never a fabrication)."""
    asset_ids = benchmark["asset_ids"]
    supplied = benchmark["returns"]
    out: List[Dict[str, float]] = []
    for t, port_rets in enumerate(portfolio_returns_by_period):
        row: Dict[str, float] = {}
        for aid in asset_ids:
            if aid in supplied:
                row[aid] = supplied[aid][t]
            else:
                row[aid] = port_rets[aid]
        out.append(row)
    return out


__all__ = [
    "BENCHMARK_KINDS", "BENCHMARK_SOURCES", "MAX_ABS_WEIGHT",
    "WEIGHT_SUM_TOLERANCE", "BenchmarkError", "validate_benchmark",
    "benchmark_weight_path", "benchmark_returns_by_period",
]
