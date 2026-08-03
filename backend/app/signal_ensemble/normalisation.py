"""
Signal normalisation and orientation (Phase 61, v1).

Normalisation is an EXPLICIT per-signal configuration — signals are never
normalised automatically merely because their units differ.  Modes:

* ``none``                             — supplied values unchanged;
* ``cross_sectional_rank_percentile`` — at each timestamp, rank that
  signal's eligible entities (documented tie method), percentile
  ``(rank - 0.5) / n`` in (0, 1);
* ``cross_sectional_zscore``          — ``(x - mean_t) / std_t`` over the
  contemporaneous eligible universe (explicit ddof);
* ``trailing_zscore``                 — per entity,
  ``(x_t - trailing_mean) / trailing_std`` over the last ``window`` stored
  observations, STRICTLY before ``t`` unless ``include_current`` is
  explicitly true.

Orientation (``as_supplied`` / ``multiply_by_negative_one``) is applied to
the raw value BEFORE normalisation, is never inferred from performance, and
both the original and the oriented/normalised values are retained.  Zero
variance, thin universes and short histories yield ``None`` with a counted
reason — never a fabricated 0.  Centred windows and negative lags do not
exist here, and future observations cannot change earlier values by
construction.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

Key = Tuple[str, str]

NORMALISATION_MODES = ("none", "cross_sectional_rank_percentile",
                       "cross_sectional_zscore", "trailing_zscore")

MIN_WINDOW = 2
MAX_WINDOW = 250
DEFAULT_MIN_OBSERVATIONS = 3


class NormalisationError(ValueError):
    """Invalid normalisation configuration (HTTP 422)."""


def validate_normalisation(raw: Any, signal_ids: List[str]
                           ) -> Dict[str, Dict[str, Any]]:
    """Per-signal normalisation config; default mode ``none``."""
    config = dict(raw or {})
    unknown = sorted(set(config) - set(signal_ids))
    if unknown:
        raise NormalisationError(
            f"normalisation references unknown signal(s): {unknown}")
    out: Dict[str, Dict[str, Any]] = {}
    for signal_id in signal_ids:
        entry = config.get(signal_id) or {}
        if not isinstance(entry, dict):
            raise NormalisationError(
                f"normalisation for {signal_id} must be an object")
        bad = sorted(set(entry) - {"mode", "ddof", "minimum_observations",
                                   "window", "include_current"})
        if bad:
            raise NormalisationError(
                f"unknown normalisation keys for {signal_id}: {bad}")
        mode = entry.get("mode", "none")
        if mode not in NORMALISATION_MODES:
            raise NormalisationError(
                f"normalisation mode for {signal_id} must be one of "
                f"{list(NORMALISATION_MODES)}")
        ddof = entry.get("ddof", 1)
        if ddof not in (0, 1):
            raise NormalisationError(
                f"ddof for {signal_id} must be 0 or 1 (explicit convention)")
        minimum = entry.get("minimum_observations", DEFAULT_MIN_OBSERVATIONS)
        if not isinstance(minimum, int) or isinstance(minimum, bool) \
                or minimum < 2:
            raise NormalisationError(
                f"minimum_observations for {signal_id} must be an integer "
                f">= 2")
        window = entry.get("window")
        include_current = entry.get("include_current", False)
        if not isinstance(include_current, bool):
            raise NormalisationError(
                f"include_current for {signal_id} must be a boolean")
        if mode == "trailing_zscore":
            if not isinstance(window, int) or isinstance(window, bool) \
                    or not (MIN_WINDOW <= window <= MAX_WINDOW):
                raise NormalisationError(
                    f"trailing_zscore for {signal_id} requires an integer "
                    f"window in [{MIN_WINDOW}, {MAX_WINDOW}]")
            if minimum > window:
                raise NormalisationError(
                    f"minimum_observations for {signal_id} cannot exceed "
                    f"its trailing_zscore window ({window})")
        elif window is not None:
            raise NormalisationError(
                f"window is only valid for trailing_zscore ({signal_id})")
        out[signal_id] = {
            "mode": mode, "ddof": ddof,
            "minimum_observations": minimum,
            "window": window,
            "include_current": include_current,
        }
    return out


def _oriented(value: Optional[float], orientation: str) -> Optional[float]:
    if value is None:
        return None
    return -float(value) if orientation == "multiply_by_negative_one" \
        else float(value)


def orient_values(grid_values: Dict[str, Dict[Key, Optional[float]]],
                  orientations: Dict[str, str]
                  ) -> Dict[str, Dict[Key, Optional[float]]]:
    """Oriented raw values; originals remain untouched in the grid."""
    return {signal_id: {key: _oriented(value, orientations[signal_id])
                        for key, value in values.items()}
            for signal_id, values in grid_values.items()}


def _rank_percentiles(values: List[float], tie_policy: str,
                      entities: List[str]) -> List[float]:
    """Percentile (rank - 0.5)/n with average or deterministic-first ties."""
    n = len(values)
    order = sorted(range(n), key=lambda i: (values[i], entities[i]))
    ranks = [0.0] * n
    if tie_policy == "first":
        for position, index in enumerate(order):
            ranks[index] = float(position + 1)
    else:  # average
        position = 0
        while position < n:
            j = position
            while j + 1 < n and values[order[j + 1]] == values[order[position]]:
                j += 1
            average = (position + 1 + j + 1) / 2.0
            for k in range(position, j + 1):
                ranks[order[k]] = average
            position = j + 1
    return [(rank - 0.5) / n for rank in ranks]


def normalise_signal(*, oriented: Dict[Key, Optional[float]],
                     stored_keys: List[Key],
                     config: Dict[str, Any],
                     tie_policy: str) -> Dict[str, Any]:
    """Normalised values for one signal plus a reason breakdown.

    ``stored_keys`` is the signal's own stored (entity, timestamp) grid in
    sorted order; only stored keys can produce a normalised value.
    """
    mode = config["mode"]
    normalised: Dict[Key, Optional[float]] = {}
    reasons: Dict[str, int] = {}

    def unavailable(key: Key, reason: str) -> None:
        normalised[key] = None
        reasons[reason] = reasons.get(reason, 0) + 1

    if mode == "none":
        for key in stored_keys:
            normalised[key] = oriented.get(key)
            if oriented.get(key) is None:
                reasons["stored value is null"] = \
                    reasons.get("stored value is null", 0) + 1
        return {"values": normalised, "reasons": reasons}

    if mode in ("cross_sectional_rank_percentile", "cross_sectional_zscore"):
        by_stamp: Dict[str, List[Key]] = {}
        for key in stored_keys:
            by_stamp.setdefault(key[1], []).append(key)
        minimum = config["minimum_observations"]
        ddof = config["ddof"]
        for stamp in sorted(by_stamp):
            eligible = [key for key in by_stamp[stamp]
                        if oriented.get(key) is not None]
            missing = [key for key in by_stamp[stamp]
                       if oriented.get(key) is None]
            for key in missing:
                unavailable(key, "stored value is null")
            if len(eligible) < minimum:
                for key in eligible:
                    unavailable(key, f"fewer than {minimum} eligible "
                                     f"entities at the timestamp")
                continue
            values = [float(oriented[key]) for key in eligible]
            if mode == "cross_sectional_rank_percentile":
                percentiles = _rank_percentiles(
                    values, tie_policy, [key[0] for key in eligible])
                for key, percentile in zip(eligible, percentiles):
                    normalised[key] = float(percentile)
            else:
                array = np.asarray(values, dtype=np.float64)
                if array.size <= ddof:
                    for key in eligible:
                        unavailable(key, "not enough entities for the "
                                         "declared ddof")
                    continue
                std = float(np.std(array, ddof=ddof))
                if std <= 1e-15:
                    for key in eligible:
                        unavailable(key, "zero cross-sectional variance")
                    continue
                mean = float(np.mean(array))
                for key, value in zip(eligible, values):
                    normalised[key] = float((value - mean) / std)
        return {"values": normalised, "reasons": reasons}

    # trailing_zscore
    window = config["window"]
    minimum = config["minimum_observations"]
    ddof = config["ddof"]
    include_current = config["include_current"]
    by_entity: Dict[str, List[Key]] = {}
    for key in stored_keys:
        by_entity.setdefault(key[0], []).append(key)
    for entity in sorted(by_entity):
        series = by_entity[entity]  # sorted by construction
        for index, key in enumerate(series):
            value = oriented.get(key)
            if value is None:
                unavailable(key, "stored value is null")
                continue
            end = index + 1 if include_current else index
            start = max(0, end - window)
            history = [oriented[series[j]] for j in range(start, end)
                       if oriented.get(series[j]) is not None]
            if len(history) < minimum:
                unavailable(key, f"fewer than {minimum} trailing "
                                 f"observations in the window")
                continue
            array = np.asarray(history, dtype=np.float64)
            if array.size <= ddof:
                unavailable(key, "not enough trailing observations for the "
                                 "declared ddof")
                continue
            std = float(np.std(array, ddof=ddof))
            if std <= 1e-15:
                unavailable(key, "zero trailing variance")
                continue
            mean = float(np.mean(array))
            z = (float(value) - mean) / std
            if not math.isfinite(z):
                unavailable(key, "non-finite trailing z-score")
                continue
            normalised[key] = float(z)
    return {"values": normalised, "reasons": reasons}


__all__ = ["NORMALISATION_MODES", "MIN_WINDOW", "MAX_WINDOW",
           "DEFAULT_MIN_OBSERVATIONS", "NormalisationError",
           "validate_normalisation", "orient_values", "normalise_signal"]
