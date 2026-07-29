"""
Target-series model (v1).

Exactly ONE explicit return series is regressed per run.  A target is either
read READ-ONLY from a stored Phase 58 attribution run (whose periods already
carry ``information_available_at``) or supplied directly as a descriptive
series with declared type, convention, frequency and currency.

No benchmark or factor series is ever mixed into the target vector, no
currency is converted silently, and no return convention is translated
silently: a mismatch is a validation error, not an adjustment.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.factor_diagnostics.observations import (MAX_OBSERVATIONS,
                                                 MIN_OBSERVATIONS,
                                                 ObservationError,
                                                 normalise_timestamp)

TARGET_TYPES = (
    "portfolio_return", "benchmark_return", "active_return", "asset_return",
    "strategy_return", "cost_adjusted_portfolio_return",
    "supplied_descriptive",
)

TARGET_SOURCES = ("attribution_run", "user_supplied")

RETURN_CONVENTIONS = ("simple",)

RETURN_FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "annual",
                      "unspecified")

#: Which stored Phase 58 column backs each attribution-sourced target type.
ATTRIBUTION_COLUMNS = {
    "portfolio_return": "portfolio_market_return",
    "benchmark_return": "benchmark_return",
    "active_return": "active_return",
    "cost_adjusted_portfolio_return": "portfolio_net_return",
}


class TargetError(ValueError):
    """Invalid target-series definition (HTTP 422)."""


def _finite(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(float(value)))


def validate_target(raw: Any) -> Dict[str, Any]:
    """Validate the target envelope (before any stored record is read)."""
    if not isinstance(raw, dict):
        raise TargetError("target must be an object")
    unknown = sorted(set(raw) - {
        "target_id", "target_type", "source", "attribution_run_id",
        "return_convention", "frequency", "currency", "description",
        "timestamps", "period_ends", "information_available_at", "returns",
    })
    if unknown:
        raise TargetError(f"unknown target keys: {unknown}")

    target_id = raw.get("target_id") or "target"
    if not isinstance(target_id, str) or not (1 <= len(target_id) <= 64):
        raise TargetError("target_id must be 1-64 characters")

    target_type = raw.get("target_type")
    if target_type not in TARGET_TYPES:
        raise TargetError(f"target_type must be one of {list(TARGET_TYPES)}")

    source = raw.get("source")
    if source not in TARGET_SOURCES:
        raise TargetError(f"target source must be one of {list(TARGET_SOURCES)}")

    convention = raw.get("return_convention", "simple")
    if convention not in RETURN_CONVENTIONS:
        raise TargetError(
            f"return_convention must be one of {list(RETURN_CONVENTIONS)}; v1 "
            f"never converts between conventions silently")

    frequency = raw.get("frequency", "daily")
    if frequency not in RETURN_FREQUENCIES:
        raise TargetError(f"frequency must be one of {list(RETURN_FREQUENCIES)}")

    currency = raw.get("currency", "USD")
    if not isinstance(currency, str) or not (1 <= len(currency) <= 12):
        raise TargetError("currency must be 1-12 characters")

    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > 1000:
        raise TargetError("target description must be at most 1000 characters")

    if source == "attribution_run":
        run_id = raw.get("attribution_run_id")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise TargetError(
                "attribution_run_id must be a positive integer for an "
                "attribution-sourced target")
        if target_type not in ATTRIBUTION_COLUMNS:
            raise TargetError(
                f"target_type {target_type} cannot be read from an attribution "
                f"run; supported types are "
                f"{sorted(ATTRIBUTION_COLUMNS)}")
        for key in ("timestamps", "period_ends", "returns",
                    "information_available_at"):
            if raw.get(key) is not None:
                raise TargetError(
                    f"{key} is not accepted for an attribution-sourced target; "
                    f"the stored periods are used verbatim")
        return {"target_id": target_id, "target_type": target_type,
                "source": source, "attribution_run_id": run_id,
                "return_convention": convention, "frequency": frequency,
                "currency": currency, "description": description}

    timestamps = raw.get("timestamps")
    returns = raw.get("returns")
    if not isinstance(timestamps, list) or not isinstance(returns, list):
        raise TargetError(
            "a user-supplied target requires timestamps and returns lists")
    if len(timestamps) != len(returns):
        raise TargetError(
            f"timestamps ({len(timestamps)}) and returns ({len(returns)}) must "
            f"have the same length")
    period_ends = raw.get("period_ends")
    if period_ends is not None and not isinstance(period_ends, list):
        raise TargetError("period_ends must be a list when supplied")
    if period_ends is not None and len(period_ends) != len(timestamps):
        raise TargetError("period_ends must have the same length as timestamps")
    cutoffs = raw.get("information_available_at")
    if cutoffs is not None and not isinstance(cutoffs, list):
        raise TargetError(
            "information_available_at must be a list when supplied")
    if cutoffs is not None and len(cutoffs) != len(timestamps):
        raise TargetError(
            "information_available_at must have the same length as timestamps")
    return {"target_id": target_id, "target_type": target_type,
            "source": source, "attribution_run_id": None,
            "return_convention": convention, "frequency": frequency,
            "currency": currency, "description": description,
            "timestamps": timestamps, "period_ends": period_ends,
            "information_available_at": cutoffs, "returns": returns}


def build_supplied_target(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Materialise a user-supplied descriptive target series."""
    timestamps = spec["timestamps"]
    returns = spec["returns"]
    if len(timestamps) < MIN_OBSERVATIONS:
        raise TargetError(
            f"at least {MIN_OBSERVATIONS} target observations are required")
    if len(timestamps) > MAX_OBSERVATIONS:
        raise TargetError(
            f"at most {MAX_OBSERVATIONS} target observations are supported")

    periods: List[Dict[str, Any]] = []
    previous: Optional[str] = None
    for index, stamp in enumerate(timestamps):
        start = normalise_timestamp(stamp, field=f"timestamps[{index}]")
        if previous is not None and start <= previous:
            raise TargetError(
                "target timestamps must be unique and strictly increasing")
        previous = start
        value = returns[index]
        if not _finite(value):
            raise TargetError(
                f"target return at {start} must be a finite number")
        end = start
        if spec.get("period_ends"):
            end = normalise_timestamp(spec["period_ends"][index],
                                      field=f"period_ends[{index}]")
            if end < start:
                raise TargetError(
                    f"period end {end} precedes period start {start}")
        cutoff = start
        if spec.get("information_available_at"):
            cutoff = normalise_timestamp(
                spec["information_available_at"][index],
                field=f"information_available_at[{index}]")
            if cutoff > start:
                raise TargetError(
                    f"information_available_at {cutoff} is after the start of "
                    f"the period it governs ({start}); a period's weights and "
                    f"factor values must be knowable at its start")
        periods.append({
            "period_index": index,
            "period_start": start,
            "period_end": end,
            "information_available_at": cutoff,
            "target_return": float(value),
        })

    return {
        "target_id": spec["target_id"],
        "target_type": spec["target_type"],
        "source": "user_supplied",
        "source_identity": {"kind": "user_supplied"},
        "return_convention": spec["return_convention"],
        "frequency": spec["frequency"],
        "currency": spec["currency"],
        "description": spec["description"],
        "provenance_status": "supplied_descriptive",
        "attribution_run_id": None,
        "periods": periods,
        "observation_start": periods[0]["period_start"],
        "observation_end": periods[-1]["period_end"],
        "observation_count": len(periods),
    }


def build_attribution_target(spec: Dict[str, Any], run: Dict[str, Any],
                             period_rows: List[Dict[str, Any]]
                             ) -> Dict[str, Any]:
    """Materialise a target from a stored Phase 58 attribution run.

    The stored rows are used verbatim — nothing is recomputed, rewritten or
    re-fingerprinted in the attribution lab.
    """
    column = ATTRIBUTION_COLUMNS[spec["target_type"]]
    if run.get("status") != "completed":
        raise TargetError(
            "an attribution-sourced target requires a completed attribution "
            "run")
    if run.get("return_convention") != spec["return_convention"]:
        raise TargetError(
            f"attribution run uses the {run.get('return_convention')} return "
            f"convention but the target declares {spec['return_convention']}; "
            f"v1 never converts conventions silently")
    if run.get("return_frequency") != spec["frequency"]:
        raise TargetError(
            f"attribution run frequency {run.get('return_frequency')} does not "
            f"match the declared target frequency {spec['frequency']}")

    periods: List[Dict[str, Any]] = []
    missing = 0
    previous_start: Optional[str] = None
    for index, row in enumerate(period_rows):
        value = row.get(column)
        if value is None or not _finite(value):
            missing += 1
            continue
        start = normalise_timestamp(row["period_start"],
                                    field="period_start")
        end = normalise_timestamp(row["period_end"] or row["period_start"],
                                  field="period_end")
        cutoff = normalise_timestamp(
            row.get("information_available_at") or row["period_start"],
            field="information_available_at")
        if previous_start is not None and start <= previous_start:
            raise TargetError(
                "stored attribution periods must be unique and strictly "
                "increasing")
        if end < start:
            raise TargetError(
                f"stored attribution period end {end} precedes start {start}")
        if cutoff > start:
            raise TargetError(
                f"stored attribution information cutoff {cutoff} is after "
                f"period start {start}")
        previous_start = start
        periods.append({
            "period_index": len(periods),
            "period_start": start,
            "period_end": end,
            "information_available_at": cutoff,
            "target_return": float(value),
            "attribution_period_id": row["period_id"],
        })
    if len(periods) < MIN_OBSERVATIONS:
        raise TargetError(
            f"attribution run {run['id']} supplies only {len(periods)} usable "
            f"'{column}' observation(s); at least {MIN_OBSERVATIONS} are "
            f"required")

    return {
        "target_id": spec["target_id"],
        "target_type": spec["target_type"],
        "source": "attribution_run",
        "source_identity": {
            "kind": "portfolio_attribution_run",
            "attribution_run_id": run["id"],
            "attribution_run_name": run["name"],
            "column": column,
            "attribution_integrity_status": run.get("integrity_status"),
            "attribution_configuration_fingerprint":
                run.get("configuration_fingerprint"),
            "attribution_result_fingerprint": run.get("result_fingerprint"),
        },
        "return_convention": spec["return_convention"],
        "frequency": spec["frequency"],
        "currency": spec["currency"],
        "description": spec["description"],
        "provenance_status": run.get("integrity_status") or "unknown",
        "attribution_run_id": run["id"],
        "periods": periods,
        "observation_start": periods[0]["period_start"],
        "observation_end": periods[-1]["period_end"],
        "observation_count": len(periods),
        "skipped_periods": missing,
    }


__all__ = [
    "TARGET_TYPES", "TARGET_SOURCES", "RETURN_CONVENTIONS",
    "RETURN_FREQUENCIES", "ATTRIBUTION_COLUMNS", "TargetError",
    "validate_target", "build_supplied_target", "build_attribution_target",
]
