"""
Bounded, deterministic sensitivity scenarios (v1).

A scenario perturbs ONE stated assumption at a time and re-fits.  The base
scenario appears exactly once, duplicates collapse, ordering is
deterministic (declaration order after the base), and the grid is bounded.

Nothing here selects a preferred specification: no scenario is labelled
best, optimal or recommended, no hyper-parameter is searched, and the
lab never re-runs itself with the "winning" settings.

Supported dimensions
--------------------
``lookback``        use only the most recent N aligned observations
``lag_delta``       add N periods to EVERY factor's declared lag and
                    re-align (the alignment is a pure function, so the
                    scenario is exactly reproducible)
``intercept_policy``  include / exclude the intercept
``ridge_lambda``    re-fit with the explicit ridge reference
``factor_subset``   fit an explicitly listed subset of the factors
``factor_scale``    multiply every factor value by a constant (a unit
                    change: coefficients scale inversely, fitted values do
                    not — a useful check that a reported exposure is
                    expressed in the unit the reader thinks it is)

Deferred dimensions
-------------------
``standardisation_policy`` and ``winsorisation_threshold`` change the factor
DEFINITION and therefore the observation-universe identity: the result is a
different observation universe with a different fingerprint, which belongs
in a separate run compared through the comparison endpoint rather than in a
sensitivity cell that pretends to share this run's inputs.  Winsorisation
itself is not implemented in v1 (see ``definitions.WINSORISATION_POLICIES``).
``missing_input_policy`` has exactly one legal value in v1
(``unavailable``), so a scenario over it would be a single cell.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence

MAX_SCENARIOS = 16
MAX_LAG_DELTA = 12
MIN_FACTOR_SCALE = 1e-6
MAX_FACTOR_SCALE = 1e6

SENSITIVITY_DIMENSIONS = (
    "lookback", "lag_delta", "intercept_policy", "ridge_lambda",
    "factor_subset", "factor_scale",
)

DEFERRED_DIMENSIONS = {
    "standardisation_policy": (
        "DEFERRED: changing the standardisation policy changes the factor "
        "definition and therefore the observation-universe fingerprint; that "
        "is a different run, not a cell of this run's grid"),
    "winsorisation_threshold": (
        "DEFERRED: winsorisation is not implemented in v1, so there is no "
        "threshold to vary"),
    "missing_input_policy": (
        "DEFERRED: v1 supports exactly one missing-input policy "
        "('unavailable'), so a scenario over it would contain a single cell"),
}


class SensitivityError(ValueError):
    """Invalid sensitivity configuration (HTTP 422)."""


def _scenario_key(scenario: Dict[str, Any]) -> str:
    return json.dumps({k: scenario[k] for k in sorted(scenario)
                       if k not in ("label", "is_base")},
                      sort_keys=True, separators=(",", ":"))


def validate_scenarios(raw: Any, *, factor_ids: Sequence[str],
                       observation_count: int) -> List[Dict[str, Any]]:
    """Validate and expand the scenario list; the base is always first."""
    base = {"label": "base", "is_base": True, "lookback": None,
            "lag_delta": 0, "intercept_policy": None, "ridge_lambda": None,
            "factor_subset": None, "factor_scale": None}
    if raw is None:
        return [base]
    if not isinstance(raw, list):
        raise SensitivityError("sensitivity must be a list of scenarios")
    if len(raw) > MAX_SCENARIOS:
        raise SensitivityError(
            f"at most {MAX_SCENARIOS} sensitivity scenarios are supported")

    scenarios: List[Dict[str, Any]] = [base]
    seen = {_scenario_key(base)}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SensitivityError("each sensitivity scenario must be an object")
        for key in item:
            if key in DEFERRED_DIMENSIONS:
                raise SensitivityError(DEFERRED_DIMENSIONS[key])
        unknown = sorted(set(item) - set(SENSITIVITY_DIMENSIONS) - {"label"})
        if unknown:
            raise SensitivityError(f"unknown sensitivity keys: {unknown}")

        scenario = dict(base)
        scenario["is_base"] = False
        scenario["label"] = item.get("label") or f"scenario-{index + 1}"
        if not isinstance(scenario["label"], str) \
                or not (1 <= len(scenario["label"]) <= 80):
            raise SensitivityError("scenario label must be 1-80 characters")

        if "lookback" in item and item["lookback"] is not None:
            lookback = item["lookback"]
            if isinstance(lookback, bool) or not isinstance(lookback, int):
                raise SensitivityError("lookback must be an integer")
            if not (4 <= lookback <= observation_count):
                raise SensitivityError(
                    f"lookback must be between 4 and the aligned observation "
                    f"count ({observation_count})")
            scenario["lookback"] = lookback

        if "lag_delta" in item and item["lag_delta"] is not None:
            delta = item["lag_delta"]
            if isinstance(delta, bool) or not isinstance(delta, int):
                raise SensitivityError("lag_delta must be an integer")
            if not (0 <= delta <= MAX_LAG_DELTA):
                raise SensitivityError(
                    f"lag_delta must be between 0 and {MAX_LAG_DELTA}; a "
                    f"negative delta would move factor values into the future")
            scenario["lag_delta"] = delta

        if "intercept_policy" in item and item["intercept_policy"] is not None:
            policy = item["intercept_policy"]
            if policy not in ("include", "exclude"):
                raise SensitivityError(
                    "intercept_policy must be 'include' or 'exclude'")
            scenario["intercept_policy"] = policy

        if "ridge_lambda" in item and item["ridge_lambda"] is not None:
            lam = item["ridge_lambda"]
            if isinstance(lam, bool) or not isinstance(lam, (int, float)) \
                    or not math.isfinite(float(lam)) or float(lam) < 0.0:
                raise SensitivityError(
                    "ridge_lambda must be a finite non-negative number")
            scenario["ridge_lambda"] = float(lam)

        if "factor_subset" in item and item["factor_subset"] is not None:
            subset = item["factor_subset"]
            if not isinstance(subset, list) or not subset:
                raise SensitivityError(
                    "factor_subset must be a non-empty explicit list")
            unknown_factors = sorted(set(subset) - set(factor_ids))
            if unknown_factors:
                raise SensitivityError(
                    f"factor_subset names unknown factors: {unknown_factors}")
            if len(set(subset)) != len(subset):
                raise SensitivityError("factor_subset contains duplicates")
            # Preserve the run's declared factor order, not the caller's.
            scenario["factor_subset"] = [f for f in factor_ids if f in set(subset)]

        if "factor_scale" in item and item["factor_scale"] is not None:
            scale = item["factor_scale"]
            if isinstance(scale, bool) or not isinstance(scale, (int, float)) \
                    or not math.isfinite(float(scale)) \
                    or not (MIN_FACTOR_SCALE <= abs(float(scale))
                            <= MAX_FACTOR_SCALE):
                raise SensitivityError(
                    f"factor_scale must be a finite non-zero number with "
                    f"magnitude in [{MIN_FACTOR_SCALE}, {MAX_FACTOR_SCALE}]")
            scenario["factor_scale"] = float(scale)

        key = _scenario_key(scenario)
        if key in seen:
            continue  # duplicates (including a restatement of the base) drop
        seen.add(key)
        scenarios.append(scenario)
    return scenarios


def scenario_description(scenario: Dict[str, Any]) -> str:
    """Human-readable statement of exactly what the scenario changed."""
    if scenario.get("is_base"):
        return "base configuration exactly as stored"
    parts: List[str] = []
    if scenario.get("lookback") is not None:
        parts.append(f"most recent {scenario['lookback']} observations")
    if scenario.get("lag_delta"):
        parts.append(f"every factor lag +{scenario['lag_delta']} period(s)")
    if scenario.get("intercept_policy") is not None:
        parts.append(f"intercept {scenario['intercept_policy']}d")
    if scenario.get("ridge_lambda") is not None:
        parts.append(f"ridge lambda {scenario['ridge_lambda']:g}")
    if scenario.get("factor_subset") is not None:
        parts.append(f"factors {', '.join(scenario['factor_subset'])}")
    if scenario.get("factor_scale") is not None:
        parts.append(f"factor values x{scenario['factor_scale']:g}")
    return "; ".join(parts) or "no change"


__all__ = [
    "MAX_SCENARIOS", "MAX_LAG_DELTA", "SENSITIVITY_DIMENSIONS",
    "DEFERRED_DIMENSIONS", "SensitivityError", "validate_scenarios",
    "scenario_description",
]
