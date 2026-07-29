"""
Factor definitions, units and transformations (v1).

A factor definition is an explicit contract: what the series is, in which
unit it arrives, how it is transformed, how long it lags the target period,
and when it becomes available.  Nothing is inferred from a factor's NAME —
an unknown factor stays ``custom_descriptive`` and an unknown unit is a
validation error, never a guess.

Transformation formulas (``x`` is the raw source series, ``v`` the
transformed series; the first ``d`` values of a differencing transform are
UNAVAILABLE and are never zero-filled or back-filled):

* ``level``               v_t = x_t                         (d = 0)
* ``simple_return``       v_t = x_t / x_{t-1} - 1           (d = 1)
* ``percent_change``      v_t = 100 * (x_t / x_{t-1} - 1)   (d = 1)
* ``log_change``          v_t = ln(x_t / x_{t-1})           (d = 1)
* ``first_difference``    v_t = x_t - x_{t-1}               (d = 1)
* ``basis_point_change``  v_t = (x_t - x_{t-1}) * s         (d = 1)
      s = 10_000 for a ``rate_fraction`` source, 100 for ``rate_percent``
* ``trailing_zscore``     v_t = (x_t - mean(x_{t-w..t-1})) / sd(x_{t-w..t-1})
      STRICTLY trailing: the window ends one observation BEFORE t, so no
      value of the series at or after t enters its own standardisation.
      Sample standard deviation (ddof=1); a zero or non-finite trailing sd
      leaves that observation unavailable.  (d = w)
* ``supplied_transformed`` v_t = x_t, unit declared by the caller (d = 0)

Centred windows and negative lags are rejected outright.  Winsorisation is
DEFERRED in v1 (see ``WINSORISATION_POLICIES``): every quantile threshold we
could compute over the full sample would be look-ahead, and a trailing
quantile policy is not needed by any v1 analysis mode.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAX_FACTORS = 12
MIN_LAG = 0
MAX_LAG = 60
MIN_STANDARDISATION_WINDOW = 3
MAX_STANDARDISATION_WINDOW = 500
MAX_METADATA_KEYS = 20
MAX_METADATA_CHARS = 2000
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")

FACTOR_CATEGORIES = (
    "market", "style", "sector", "volatility", "liquidity", "macro",
    "custom_descriptive",
)

TRANSFORMATIONS = (
    "level", "simple_return", "percent_change", "log_change",
    "first_difference", "basis_point_change", "trailing_zscore",
    "supplied_transformed",
)

#: Units a RAW supplied series may carry.
SOURCE_UNITS = (
    "return_fraction", "return_percent", "basis_points", "index_level",
    "rate_fraction", "rate_percent", "zscore", "ratio", "count",
)

#: Units an already-transformed supplied series may declare.  Keeping this
#: bounded prevents a typo from becoming a new, apparently valid unit.
TRANSFORMED_UNITS = SOURCE_UNITS + (
    "log_change_fraction",
    "return_fraction_change", "return_percent_change",
    "basis_points_change", "index_level_change", "rate_fraction_change",
    "rate_percent_change", "zscore_change", "ratio_change", "count_change",
)

#: Units that express a period return and can therefore be multiplied by a
#: dimensionless exposure to obtain a return contribution (§ decomposition).
RETURN_LIKE_UNITS: Dict[str, float] = {
    "return_fraction": 1.0,
    "return_percent": 0.01,
    "basis_points": 1e-4,
}

AVAILABILITY_POLICIES = (
    "same_timestamp",          # descriptive: the value carries the period stamp
    "explicit_available_at",   # each observation declares when it was knowable
    "lagged_by_periods",       # availability derived from the declared lag
)

#: v1 never fabricates a factor value.  A missing observation removes its
#: period from the estimation sample and is listed with a reason.
MISSING_POLICIES = ("unavailable",)

STANDARDISATION_POLICIES = ("none", "trailing_zscore")

#: Winsorisation is deferred in v1; only the explicit "none" is accepted.
WINSORISATION_POLICIES = ("none",)

TRANSFORMATION_LOOKBACK = {
    "level": 0,
    "simple_return": 1,
    "percent_change": 1,
    "log_change": 1,
    "first_difference": 1,
    "basis_point_change": 1,
    "supplied_transformed": 0,
}

BASIS_POINT_SCALE = {"rate_fraction": 10_000.0, "rate_percent": 100.0}


class DefinitionError(ValueError):
    """Invalid factor definition or transformation input (HTTP 422)."""


def _finite(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(float(value)))


def result_unit(transformation: str, source_unit: str,
                supplied_unit: Optional[str]) -> str:
    """The unit of the TRANSFORMED series — explicit, never assumed."""
    if transformation == "level":
        return source_unit
    if transformation == "simple_return":
        return "return_fraction"
    if transformation == "percent_change":
        return "return_percent"
    if transformation == "log_change":
        return "log_change_fraction"
    if transformation == "first_difference":
        return f"{source_unit}_change"
    if transformation == "basis_point_change":
        return "basis_points"
    if transformation == "trailing_zscore":
        return "zscore"
    if transformation == "supplied_transformed":
        if supplied_unit is None:
            raise DefinitionError(
                "supplied_transformed requires an explicit transformed_unit")
        if supplied_unit not in TRANSFORMED_UNITS:
            raise DefinitionError(
                f"transformed_unit must be one of {list(TRANSFORMED_UNITS)}")
        return supplied_unit
    raise DefinitionError(f"unknown transformation '{transformation}'")


def validate_definition(raw: Any) -> Dict[str, Any]:
    """Validate one factor definition envelope; return the normalised form."""
    if not isinstance(raw, dict):
        raise DefinitionError("each factor definition must be an object")
    allowed = {
        "factor_id", "name", "description", "category", "source", "unit",
        "frequency", "transformation", "transformed_unit", "lag",
        "availability_policy", "missing_policy", "standardisation_policy",
        "standardisation_window", "winsorisation_policy", "dataset_version_id",
        "observations", "metadata",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise DefinitionError(f"unknown factor definition keys: {unknown}")

    factor_id = raw.get("factor_id")
    if not isinstance(factor_id, str) or not ID_PATTERN.match(factor_id):
        raise DefinitionError(
            "factor_id must be lowercase alphanumeric with '_' or '-' "
            "(max 64 characters)")

    name = raw.get("name") or factor_id
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise DefinitionError("factor name must be 1-200 characters")
    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > 1000:
        raise DefinitionError("factor description must be at most 1000 characters")

    category = raw.get("category", "custom_descriptive")
    if category not in FACTOR_CATEGORIES:
        raise DefinitionError(
            f"category must be one of {list(FACTOR_CATEGORIES)}; an unknown "
            f"factor is never categorised automatically")

    source = raw.get("source", "user_supplied")
    if not isinstance(source, str) or not (1 <= len(source) <= 200):
        raise DefinitionError("factor source must be 1-200 characters")

    unit = raw.get("unit")
    if unit not in SOURCE_UNITS:
        raise DefinitionError(f"unit must be one of {list(SOURCE_UNITS)}")

    frequency = raw.get("frequency", "daily")
    if frequency not in ("daily", "weekly", "monthly", "quarterly", "annual",
                         "unspecified"):
        raise DefinitionError(
            "frequency must be daily, weekly, monthly, quarterly, annual or "
            "unspecified")

    transformation = raw.get("transformation")
    if transformation not in TRANSFORMATIONS:
        raise DefinitionError(
            f"transformation must be one of {list(TRANSFORMATIONS)}")
    if transformation == "basis_point_change" and unit not in BASIS_POINT_SCALE:
        raise DefinitionError(
            "basis_point_change requires a rate_fraction or rate_percent "
            "source unit so the conversion factor is unambiguous")
    if transformation in ("simple_return", "percent_change", "log_change") \
            and unit not in ("index_level", "ratio", "count"):
        raise DefinitionError(
            f"{transformation} requires an index_level, ratio or count source "
            f"unit (a ratio of two rates is not a return)")

    lag = raw.get("lag", 0)
    if isinstance(lag, bool) or not isinstance(lag, int):
        raise DefinitionError("lag must be an integer number of periods")
    if not (MIN_LAG <= lag <= MAX_LAG):
        raise DefinitionError(
            f"lag must be between {MIN_LAG} and {MAX_LAG} periods; negative "
            f"lags (future factor values) are rejected")

    availability_policy = raw.get("availability_policy", "same_timestamp")
    if availability_policy not in AVAILABILITY_POLICIES:
        raise DefinitionError(
            f"availability_policy must be one of {list(AVAILABILITY_POLICIES)}")

    missing_policy = raw.get("missing_policy", "unavailable")
    if missing_policy not in MISSING_POLICIES:
        raise DefinitionError(
            "missing_policy must be 'unavailable' — v1 never forward-fills, "
            "interpolates or zero-fills a missing factor observation")

    standardisation_policy = raw.get("standardisation_policy", "none")
    if standardisation_policy not in STANDARDISATION_POLICIES:
        raise DefinitionError(
            f"standardisation_policy must be one of "
            f"{list(STANDARDISATION_POLICIES)}")
    window = raw.get("standardisation_window")
    needs_window = (transformation == "trailing_zscore"
                    or standardisation_policy == "trailing_zscore")
    if needs_window:
        if isinstance(window, bool) or not isinstance(window, int):
            raise DefinitionError(
                "trailing standardisation requires an integer "
                "standardisation_window")
        if not (MIN_STANDARDISATION_WINDOW <= window
                <= MAX_STANDARDISATION_WINDOW):
            raise DefinitionError(
                f"standardisation_window must be between "
                f"{MIN_STANDARDISATION_WINDOW} and "
                f"{MAX_STANDARDISATION_WINDOW} observations")
    elif window is not None:
        raise DefinitionError(
            "standardisation_window is only valid with a trailing "
            "standardisation policy")

    winsorisation_policy = raw.get("winsorisation_policy", "none")
    if winsorisation_policy not in WINSORISATION_POLICIES:
        raise DefinitionError(
            "winsorisation is deferred in v1: only 'none' is accepted, and no "
            "threshold is applied silently")

    dataset_version_id = raw.get("dataset_version_id")
    if dataset_version_id is not None and (
            isinstance(dataset_version_id, bool)
            or not isinstance(dataset_version_id, int)
            or dataset_version_id <= 0):
        raise DefinitionError("dataset_version_id must be a positive integer")

    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise DefinitionError("factor metadata must be an object")
    if len(metadata) > MAX_METADATA_KEYS:
        raise DefinitionError(
            f"factor metadata is limited to {MAX_METADATA_KEYS} keys")
    if len(str(metadata)) > MAX_METADATA_CHARS:
        raise DefinitionError(
            f"factor metadata is limited to {MAX_METADATA_CHARS} characters")

    transformed_unit = result_unit(transformation, unit,
                                   raw.get("transformed_unit"))
    if transformation != "supplied_transformed" \
            and raw.get("transformed_unit") not in (None, transformed_unit):
        raise DefinitionError(
            f"transformed_unit for {transformation} is {transformed_unit}; it "
            f"cannot be overridden")

    return {
        "factor_id": factor_id,
        "name": name,
        "description": description,
        "category": category,
        "source": source,
        "unit": unit,
        "transformed_unit": transformed_unit,
        "frequency": frequency,
        "transformation": transformation,
        "lag": lag,
        "availability_policy": availability_policy,
        "missing_policy": missing_policy,
        "standardisation_policy": standardisation_policy,
        "standardisation_window": window,
        "winsorisation_policy": winsorisation_policy,
        "dataset_version_id": dataset_version_id,
        "metadata": metadata,
    }


def validate_definitions(raw_list: Any) -> List[Dict[str, Any]]:
    """Validate the ordered factor list (order is part of the design matrix)."""
    if not isinstance(raw_list, list) or not raw_list:
        raise DefinitionError("at least one factor definition is required")
    if len(raw_list) > MAX_FACTORS:
        raise DefinitionError(
            f"at most {MAX_FACTORS} factor definitions are supported")
    definitions = [validate_definition(item) for item in raw_list]
    ids = [d["factor_id"] for d in definitions]
    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise DefinitionError(f"duplicate factor_id values: {duplicates}")
    return definitions


def transform_series(values: Sequence[Optional[float]],
                     definition: Dict[str, Any]) -> List[Optional[float]]:
    """Apply the declared transformation; unavailable stays ``None``.

    The returned list has exactly the length of ``values``.  Leading entries
    that a differencing or trailing-window transform cannot produce are
    ``None`` — never zero, never back-filled.
    """
    transformation = definition["transformation"]
    unit = definition["unit"]
    raw: List[Optional[float]] = []
    for v in values:
        if v is None:
            raw.append(None)
        elif not _finite(v):
            raise DefinitionError(
                f"factor '{definition['factor_id']}' contains a non-finite "
                f"observation")
        else:
            raw.append(float(v))

    out: List[Optional[float]] = [None] * len(raw)
    if transformation in ("level", "supplied_transformed"):
        out = list(raw)
    elif transformation in ("simple_return", "percent_change", "log_change"):
        for t in range(1, len(raw)):
            prev, cur = raw[t - 1], raw[t]
            if prev is None or cur is None or prev == 0.0:
                continue
            ratio = cur / prev
            if transformation == "log_change":
                if prev <= 0.0 or cur <= 0.0:
                    continue
                out[t] = math.log(ratio)
            elif transformation == "simple_return":
                out[t] = ratio - 1.0
            else:
                out[t] = 100.0 * (ratio - 1.0)
    elif transformation == "first_difference":
        for t in range(1, len(raw)):
            if raw[t - 1] is None or raw[t] is None:
                continue
            out[t] = raw[t] - raw[t - 1]
    elif transformation == "basis_point_change":
        scale = BASIS_POINT_SCALE[unit]
        for t in range(1, len(raw)):
            if raw[t - 1] is None or raw[t] is None:
                continue
            out[t] = (raw[t] - raw[t - 1]) * scale
    elif transformation == "trailing_zscore":
        out = _trailing_zscore(raw, int(definition["standardisation_window"]))
    else:  # pragma: no cover - validate_definition rejects anything else
        raise DefinitionError(f"unknown transformation '{transformation}'")

    if definition["standardisation_policy"] == "trailing_zscore" \
            and transformation != "trailing_zscore":
        out = _trailing_zscore(out, int(definition["standardisation_window"]))

    for t, v in enumerate(out):
        if v is not None and not math.isfinite(v):
            out[t] = None
    return out


def _trailing_zscore(values: Sequence[Optional[float]],
                     window: int) -> List[Optional[float]]:
    """(x_t - mean of the ``window`` values BEFORE t) / their sample sd."""
    out: List[Optional[float]] = [None] * len(values)
    for t in range(len(values)):
        if values[t] is None or t < window:
            continue
        history = [v for v in values[t - window:t] if v is not None]
        if len(history) < window or len(history) < 2:
            continue
        mean = sum(history) / len(history)
        variance = sum((h - mean) ** 2 for h in history) / (len(history) - 1)
        sd = math.sqrt(variance) if variance > 0 else 0.0
        if sd <= 1e-15 or not math.isfinite(sd):
            continue
        out[t] = (values[t] - mean) / sd
    return out


def lookback_periods(definition: Dict[str, Any]) -> int:
    """Observations consumed before the first transformed value can exist."""
    transformation = definition["transformation"]
    base = (int(definition["standardisation_window"])
            if transformation == "trailing_zscore"
            else TRANSFORMATION_LOOKBACK[transformation])
    if definition["standardisation_policy"] == "trailing_zscore" \
            and transformation != "trailing_zscore":
        base += int(definition["standardisation_window"])
    return base


def contribution_scale(transformed_unit: str) -> Optional[float]:
    """Factor → return-fraction scale, or ``None`` when the unit is not a
    return (an exposure times a non-return factor is not a return)."""
    return RETURN_LIKE_UNITS.get(transformed_unit)


__all__ = [
    "MAX_FACTORS", "MIN_LAG", "MAX_LAG", "MIN_STANDARDISATION_WINDOW",
    "MAX_STANDARDISATION_WINDOW", "FACTOR_CATEGORIES", "TRANSFORMATIONS",
    "SOURCE_UNITS", "TRANSFORMED_UNITS", "RETURN_LIKE_UNITS",
    "AVAILABILITY_POLICIES",
    "MISSING_POLICIES", "STANDARDISATION_POLICIES", "WINSORISATION_POLICIES",
    "BASIS_POINT_SCALE", "DefinitionError", "result_unit",
    "validate_definition", "validate_definitions", "transform_series",
    "lookback_periods", "contribution_scale",
]
