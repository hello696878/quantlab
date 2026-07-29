"""
Signal and outcome definitions (v1).

A signal definition is an explicit contract: what the series is, which unit
it arrives in, which DIRECTION its configured score runs (larger values are
declared to represent a higher or a lower configured score — economic
direction is **never inferred from the name**), how it becomes available,
and how missing values and ties are treated.  There are no user-supplied
expressions of any kind, no silent sign inversion, no silent winsorisation
and no silent standardisation: the transformation is chosen from a closed
list and `none` is the default.

An outcome definition states what the paired later measurement is — a
forward return built from explicit prices, or a supplied outcome value used
verbatim — with its convention, unit and availability.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

MAX_METADATA_KEYS = 20
MAX_METADATA_CHARS = 2000
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")

SIGNAL_TYPES = ("continuous_score", "probability", "rank",
                "ordinal_category", "binary_indicator",
                "user_supplied_descriptive")

SIGNAL_UNITS = ("score", "probability", "rank", "category", "indicator",
                "zscore", "return_fraction", "basis_points", "ratio")

DIRECTIONS = ("higher_is_higher_score", "higher_is_lower_score")

#: v1 transformations.  ``rank_cross_sectional`` ranks within each
#: timestamp's eligible universe only; ``rank_full_sample`` ranks over the
#: whole sample and therefore FORCES a descriptive integrity state.
TRANSFORMATIONS = ("none", "rank_cross_sectional", "rank_full_sample")

AVAILABILITY_POLICIES = ("explicit_available_at", "same_timestamp")

MISSING_POLICIES = ("unavailable",)

#: Deterministic tie handling for ranks and buckets.  ``average`` is the
#: scipy default for Spearman; ``first`` breaks ties by entity order and is
#: only used where an ordering (bucket membership) needs to be total.
TIE_POLICIES = ("average", "first")

FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "annual",
               "unspecified")

OUTCOME_TARGET_TYPES = ("forward_return", "supplied_outcome")

RETURN_CONVENTIONS = ("simple",)

OUTCOME_UNITS = ("return_fraction", "return_percent", "basis_points",
                 "score", "binary")


class DefinitionError(ValueError):
    """Invalid signal or outcome definition (HTTP 422)."""


def _finite(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(float(value)))


def _metadata(raw: Any, label: str) -> Dict[str, Any]:
    metadata = raw or {}
    if not isinstance(metadata, dict):
        raise DefinitionError(f"{label} metadata must be an object")
    if len(metadata) > MAX_METADATA_KEYS:
        raise DefinitionError(
            f"{label} metadata is limited to {MAX_METADATA_KEYS} keys")
    if len(str(metadata)) > MAX_METADATA_CHARS:
        raise DefinitionError(
            f"{label} metadata is limited to {MAX_METADATA_CHARS} characters")
    return metadata


def validate_signal_definition(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise DefinitionError("the signal definition must be an object")
    allowed = {
        "signal_id", "name", "description", "signal_type", "source", "unit",
        "frequency", "direction", "availability_policy", "transformation",
        "missing_policy", "tie_policy", "dataset_version_id",
        "feature_run_id", "meta_label_run_id", "factor_run_id", "metadata",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise DefinitionError(f"unknown signal definition keys: {unknown}")

    signal_id = raw.get("signal_id")
    if not isinstance(signal_id, str) or not ID_PATTERN.match(signal_id):
        raise DefinitionError(
            "signal_id must be lowercase alphanumeric with '_' or '-' "
            "(max 64 characters)")
    name = raw.get("name") or signal_id
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise DefinitionError("signal name must be 1-200 characters")
    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > 1000:
        raise DefinitionError("signal description must be <= 1000 characters")

    signal_type = raw.get("signal_type")
    if signal_type not in SIGNAL_TYPES:
        raise DefinitionError(
            f"signal_type must be one of {list(SIGNAL_TYPES)}")
    source = raw.get("source", "user_supplied")
    if not isinstance(source, str) or not (1 <= len(source) <= 200):
        raise DefinitionError("signal source must be 1-200 characters")
    unit = raw.get("unit")
    if unit not in SIGNAL_UNITS:
        raise DefinitionError(f"signal unit must be one of {list(SIGNAL_UNITS)}")
    frequency = raw.get("frequency", "daily")
    if frequency not in FREQUENCIES:
        raise DefinitionError(f"frequency must be one of {list(FREQUENCIES)}")

    direction = raw.get("direction")
    if direction not in DIRECTIONS:
        raise DefinitionError(
            f"direction must be one of {list(DIRECTIONS)}: whether a larger "
            f"value represents a higher or a lower configured score is an "
            f"explicit declaration, never inferred from the signal's name")

    availability = raw.get("availability_policy", "explicit_available_at")
    if availability not in AVAILABILITY_POLICIES:
        raise DefinitionError(
            f"availability_policy must be one of {list(AVAILABILITY_POLICIES)}")

    transformation = raw.get("transformation", "none")
    if transformation not in TRANSFORMATIONS:
        raise DefinitionError(
            f"transformation must be one of {list(TRANSFORMATIONS)}; no "
            f"formula execution, sign inversion, winsorisation or "
            f"standardisation happens silently")

    missing_policy = raw.get("missing_policy", "unavailable")
    if missing_policy not in MISSING_POLICIES:
        raise DefinitionError(
            "missing_policy must be 'unavailable' — a missing signal is never "
            "forward-filled or fabricated")

    tie_policy = raw.get("tie_policy", "average")
    if tie_policy not in TIE_POLICIES:
        raise DefinitionError(f"tie_policy must be one of {list(TIE_POLICIES)}")

    for field in ("dataset_version_id", "feature_run_id", "meta_label_run_id",
                  "factor_run_id"):
        value = raw.get(field)
        if value is not None and (isinstance(value, bool)
                                  or not isinstance(value, int) or value <= 0):
            raise DefinitionError(f"{field} must be a positive integer")

    return {
        "signal_id": signal_id, "name": name, "description": description,
        "signal_type": signal_type, "source": source, "unit": unit,
        "frequency": frequency, "direction": direction,
        "availability_policy": availability, "transformation": transformation,
        "missing_policy": missing_policy, "tie_policy": tie_policy,
        "dataset_version_id": raw.get("dataset_version_id"),
        "feature_run_id": raw.get("feature_run_id"),
        "meta_label_run_id": raw.get("meta_label_run_id"),
        "factor_run_id": raw.get("factor_run_id"),
        "metadata": _metadata(raw.get("metadata"), "signal"),
    }


def validate_outcome_definition(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise DefinitionError("the outcome definition must be an object")
    allowed = {
        "outcome_id", "name", "target_type", "return_convention", "unit",
        "price_field", "source", "dataset_version_id",
        "extreme_loss_policy", "metadata",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise DefinitionError(f"unknown outcome definition keys: {unknown}")

    outcome_id = raw.get("outcome_id")
    if not isinstance(outcome_id, str) or not ID_PATTERN.match(outcome_id):
        raise DefinitionError(
            "outcome_id must be lowercase alphanumeric with '_' or '-' "
            "(max 64 characters)")
    name = raw.get("name") or outcome_id
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise DefinitionError("outcome name must be 1-200 characters")

    target_type = raw.get("target_type")
    if target_type not in OUTCOME_TARGET_TYPES:
        raise DefinitionError(
            f"target_type must be one of {list(OUTCOME_TARGET_TYPES)}")

    convention = raw.get("return_convention", "simple")
    if convention not in RETURN_CONVENTIONS:
        raise DefinitionError(
            "return_convention must be 'simple' in v1; nothing is converted "
            "silently")

    unit = raw.get("unit", "return_fraction")
    if unit not in OUTCOME_UNITS:
        raise DefinitionError(f"outcome unit must be one of {list(OUTCOME_UNITS)}")
    if target_type == "forward_return" and unit != "return_fraction":
        raise DefinitionError(
            "a forward_return outcome is always a return_fraction: "
            "exit_price / entry_price - 1")

    price_field = raw.get("price_field")
    if target_type == "forward_return":
        if not isinstance(price_field, str) or not (1 <= len(price_field) <= 40):
            raise DefinitionError(
                "forward_return requires an explicit price_field naming which "
                "supplied price is used (e.g. 'close')")
    elif price_field is not None:
        raise DefinitionError(
            "price_field only applies to forward_return outcomes")

    extreme = raw.get("extreme_loss_policy", "report_verbatim")
    if extreme not in ("report_verbatim", "mark_unavailable"):
        raise DefinitionError(
            "extreme_loss_policy must be 'report_verbatim' (a return <= -100% "
            "is reported as measured) or 'mark_unavailable'")

    source = raw.get("source", "user_supplied")
    if not isinstance(source, str) or not (1 <= len(source) <= 200):
        raise DefinitionError("outcome source must be 1-200 characters")

    dataset_version_id = raw.get("dataset_version_id")
    if dataset_version_id is not None and (
            isinstance(dataset_version_id, bool)
            or not isinstance(dataset_version_id, int)
            or dataset_version_id <= 0):
        raise DefinitionError("dataset_version_id must be a positive integer")

    return {
        "outcome_id": outcome_id, "name": name, "target_type": target_type,
        "return_convention": convention, "unit": unit,
        "price_field": price_field, "extreme_loss_policy": extreme,
        "source": source, "dataset_version_id": dataset_version_id,
        "metadata": _metadata(raw.get("metadata"), "outcome"),
    }


def oriented(values: List[Optional[float]],
             direction: str) -> List[Optional[float]]:
    """Map raw values onto the CONFIGURED score orientation.

    Under ``higher_is_lower_score`` the configured score is the negated raw
    value.  The inversion is this explicit, declared step — never a silent
    one — and every stored raw value keeps its original sign.
    """
    if direction == "higher_is_higher_score":
        return list(values)
    return [None if v is None else -float(v) for v in values]


__all__ = [
    "SIGNAL_TYPES", "SIGNAL_UNITS", "DIRECTIONS", "TRANSFORMATIONS",
    "AVAILABILITY_POLICIES", "MISSING_POLICIES", "TIE_POLICIES",
    "FREQUENCIES", "OUTCOME_TARGET_TYPES", "RETURN_CONVENTIONS",
    "OUTCOME_UNITS", "DefinitionError", "validate_signal_definition",
    "validate_outcome_definition", "oriented",
]
