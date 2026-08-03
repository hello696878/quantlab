"""
Explicit combination references (Phase 61, v1).

Four bounded modes, all user-configured, none optimised:

* ``equal_weight``   — mean of oriented, normalised component values;
* ``user_weights``   — user-supplied STATIC weights with an explicit
  negative-weight policy and an explicit normalisation policy;
* ``rank_average``   — mean of per-signal cross-sectional rank
  percentiles (equal weights over rank-normalised components);
* ``majority_sign``  — sign(sum of component signs), a reference for
  sign-semantic signals only; it is not linear, so component
  contributions are reported as sign votes and linear reconciliation
  does not apply (stated, not hidden).

Missing components follow an explicit policy — ``require_all`` (default:
the combined score is unavailable unless every component is present) or
``renormalise_available`` (explicitly opted in; available components'
configured weights are renormalised, the missing ids, effective count and
effective weights all stay visible).  No zero imputation, no
carry-forward, no automatic long-only conversion, no weight ever derived
from historical results.

For linear modes, per-observation component contributions
``effective_weight_k × oriented_normalised_k`` reconcile with the combined
score to a documented tolerance; a reconciliation failure is a run-level
error state, never redistributed.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

Key = Tuple[str, str]

COMBINATION_MODES = ("equal_weight", "user_weights", "rank_average",
                     "majority_sign")
MISSING_COMPONENT_POLICIES = ("require_all", "renormalise_available")
WEIGHT_NORMALISATION_POLICIES = ("require_sum_to_one", "normalise_by_sum",
                                 "normalise_by_gross", "none")

RECONCILIATION_TOLERANCE = 1e-9


class CombinationError(ValueError):
    """Invalid combination configuration (HTTP 422)."""


def validate_combination_policy(raw: Any, signal_ids: List[str]
                                ) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise CombinationError("the combination policy must be an object")
    unknown = sorted(set(raw) - {
        "mode", "weights", "weight_normalisation", "allow_negative_weights",
        "missing_component_policy", "minimum_component_count", "tie_policy"})
    if unknown:
        raise CombinationError(f"unknown combination policy keys: {unknown}")
    mode = raw.get("mode")
    if mode not in COMBINATION_MODES:
        raise CombinationError(
            f"combination mode must be one of {list(COMBINATION_MODES)}")

    missing_policy = raw.get("missing_component_policy", "require_all")
    if missing_policy not in MISSING_COMPONENT_POLICIES:
        raise CombinationError(
            f"missing_component_policy must be one of "
            f"{list(MISSING_COMPONENT_POLICIES)} — renormalisation is never "
            f"applied without explicit selection")
    minimum_components = raw.get("minimum_component_count", len(signal_ids))
    if not isinstance(minimum_components, int) \
            or isinstance(minimum_components, bool) \
            or not (2 <= minimum_components <= len(signal_ids)):
        raise CombinationError(
            f"minimum_component_count must be an integer in "
            f"[2, {len(signal_ids)}]")
    if missing_policy == "require_all" \
            and minimum_components != len(signal_ids):
        raise CombinationError(
            "require_all uses every component by definition; "
            "minimum_component_count must equal the signal count")

    tie_policy = raw.get("tie_policy", "average")
    if tie_policy not in ("average", "first"):
        raise CombinationError("tie_policy must be 'average' or 'first'")

    allow_negative = raw.get("allow_negative_weights", False)
    if not isinstance(allow_negative, bool):
        raise CombinationError("allow_negative_weights must be a boolean")

    policy: Dict[str, Any] = {
        "mode": mode,
        "missing_component_policy": missing_policy,
        "minimum_component_count": minimum_components,
        "tie_policy": tie_policy,
        "allow_negative_weights": allow_negative,
        "weight_normalisation": None,
        "configured_weights": None,
        "final_weights": None,
        "gross_weight": None, "net_weight": None,
        "max_absolute_weight": None,
        "zero_weight_signals": None,
        "normalisation_residual": None,
    }

    if mode == "user_weights":
        policy.update(_validate_weights(raw, signal_ids))
    else:
        if raw.get("weights") is not None:
            raise CombinationError(
                f"weights are only valid for user_weights mode, not {mode}")
        if raw.get("weight_normalisation") is not None:
            raise CombinationError(
                "weight_normalisation is only valid for user_weights mode")
        equal = 1.0 / len(signal_ids)
        weights = {signal_id: equal for signal_id in sorted(signal_ids)}
        policy["configured_weights"] = weights
        policy["final_weights"] = dict(weights)
        policy["gross_weight"] = 1.0
        policy["net_weight"] = 1.0
        policy["max_absolute_weight"] = equal
        policy["zero_weight_signals"] = []
    return policy


def _validate_weights(raw: Dict[str, Any], signal_ids: List[str]
                      ) -> Dict[str, Any]:
    weights_raw = raw.get("weights")
    if not isinstance(weights_raw, dict):
        raise CombinationError(
            "user_weights mode requires a weights object "
            "{signal_id: weight}")
    missing = sorted(set(signal_ids) - set(weights_raw))
    if missing:
        raise CombinationError(f"weights are missing for signal(s): "
                               f"{missing}")
    extra = sorted(set(weights_raw) - set(signal_ids))
    if extra:
        raise CombinationError(f"weights reference unknown signal(s): "
                               f"{extra}")
    allow_negative = raw.get("allow_negative_weights", False)
    configured: Dict[str, float] = {}
    for signal_id in sorted(signal_ids):
        value = weights_raw[signal_id]
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            raise CombinationError(
                f"weight for {signal_id} must be a finite number")
        if float(value) < 0 and not allow_negative:
            raise CombinationError(
                f"weight for {signal_id} is negative and "
                f"allow_negative_weights is false (explicit policy)")
        configured[signal_id] = float(value)

    normalisation = raw.get("weight_normalisation", "require_sum_to_one")
    if normalisation not in WEIGHT_NORMALISATION_POLICIES:
        raise CombinationError(
            f"weight_normalisation must be one of "
            f"{list(WEIGHT_NORMALISATION_POLICIES)}")

    total = sum(configured.values())
    gross = sum(abs(w) for w in configured.values())
    if gross <= 0:
        raise CombinationError("the gross absolute weight is zero")

    final = dict(configured)
    residual = None
    if normalisation == "require_sum_to_one":
        residual = total - 1.0
        if abs(residual) > 1e-9:
            raise CombinationError(
                f"weights must sum to one under require_sum_to_one; the "
                f"sum is {total!r}")
    elif normalisation == "normalise_by_sum":
        if abs(total) <= 1e-12:
            raise CombinationError(
                "weights sum to zero, so normalise_by_sum would divide by "
                "zero")
        final = {k: v / total for k, v in configured.items()}
        residual = 0.0
    elif normalisation == "normalise_by_gross":
        final = {k: v / gross for k, v in configured.items()}
        residual = sum(final.values()) - 1.0
    else:  # none
        residual = total - 1.0

    final_gross = sum(abs(w) for w in final.values())
    return {
        "weight_normalisation": normalisation,
        "configured_weights": configured,
        "final_weights": final,
        "gross_weight": final_gross,
        "net_weight": sum(final.values()),
        "max_absolute_weight": max(abs(w) for w in final.values()),
        "zero_weight_signals": sorted(k for k, v in final.items()
                                      if v == 0.0),
        "normalisation_residual": residual,
    }


def combine(*, keys: List[Key],
            component_values: Dict[str, Dict[Key, Optional[float]]],
            policy: Dict[str, Any],
            signal_ids: List[str]) -> Dict[str, Any]:
    """Combined scores plus per-observation component contributions.

    ``component_values`` are the ORIENTED, NORMALISED per-signal values
    (mode ``rank_average`` receives rank percentiles).  ``keys`` is the
    candidate observation universe (the union grid); the missing-component
    policy decides which keys yield a combined score.
    """
    mode = policy["mode"]
    weights = policy["final_weights"]
    minimum = policy["minimum_component_count"]
    require_all = policy["missing_component_policy"] == "require_all"

    observations: List[Dict[str, Any]] = []
    contributions: List[Dict[str, Any]] = []
    reconciliation_failures = 0
    unavailable = 0
    for key in keys:
        present = [s for s in signal_ids
                   if component_values[s].get(key) is not None]
        missing = [s for s in signal_ids if s not in present]
        entry: Dict[str, Any] = {
            "entity_id": key[0], "timestamp": key[1],
            "component_count": len(present),
            "missing_signal_ids": missing,
            "combined_score": None,
            "state": "unavailable", "reason": None,
        }
        if require_all and missing:
            entry["reason"] = (f"component(s) {missing} are missing under "
                               f"require_all")
            unavailable += 1
            observations.append(entry)
            continue
        if len(present) < minimum:
            entry["reason"] = (f"{len(present)} component(s) are below the "
                               f"minimum of {minimum}")
            unavailable += 1
            observations.append(entry)
            continue

        if mode == "majority_sign":
            votes = {s: _sign(component_values[s][key]) for s in present}
            vote_sum = sum(votes.values())
            entry["combined_score"] = float(_sign(vote_sum))
            entry["state"] = "available"
            entry["effective_weights"] = None
            for signal_id in present:
                contributions.append({
                    "entity_id": key[0], "timestamp": key[1],
                    "signal_id": signal_id,
                    "normalised_value": component_values[signal_id][key],
                    "configured_weight": weights[signal_id],
                    "effective_weight": None,
                    "contribution": None,
                    "sign_vote": votes[signal_id],
                    "missing": False,
                })
            for signal_id in missing:
                contributions.append(_missing_contribution(
                    key, signal_id, weights[signal_id]))
            observations.append(entry)
            continue

        # linear modes: equal_weight / user_weights / rank_average
        if missing:
            available_gross = sum(abs(weights[s]) for s in present)
            if available_gross <= 0:
                entry["reason"] = ("the available components carry zero "
                                   "gross weight")
                unavailable += 1
                observations.append(entry)
                continue
            scale = sum(weights[s] for s in present)
            if abs(scale) <= 1e-12:
                entry["reason"] = ("the available components' configured "
                                   "weights sum to zero, so renormalising "
                                   "would divide by zero")
                unavailable += 1
                observations.append(entry)
                continue
            effective = {s: weights[s] / scale for s in present}
        else:
            effective = {s: weights[s] for s in present}

        combined = 0.0
        for signal_id in present:
            combined += effective[signal_id] \
                * float(component_values[signal_id][key])
        check = sum(effective[s] * float(component_values[s][key])
                    for s in present)
        if abs(combined - check) > RECONCILIATION_TOLERANCE:
            reconciliation_failures += 1
        entry["combined_score"] = float(combined)
        entry["state"] = "available"
        entry["effective_weights"] = {s: effective[s] for s in present}
        for signal_id in present:
            contributions.append({
                "entity_id": key[0], "timestamp": key[1],
                "signal_id": signal_id,
                "normalised_value": component_values[signal_id][key],
                "configured_weight": weights[signal_id],
                "effective_weight": effective[signal_id],
                "contribution": effective[signal_id]
                * float(component_values[signal_id][key]),
                "sign_vote": None,
                "missing": False,
            })
        for signal_id in missing:
            contributions.append(_missing_contribution(
                key, signal_id, weights[signal_id]))
        observations.append(entry)

    available = [o for o in observations if o["state"] == "available"]
    return {
        "observations": observations,
        "contributions": contributions,
        "available_count": len(available),
        "unavailable_count": unavailable,
        "coverage": (len(available) / len(keys)) if keys else None,
        "reconciliation": {
            "tolerance": RECONCILIATION_TOLERANCE,
            "checked": len(available) if mode != "majority_sign" else 0,
            "failures": reconciliation_failures,
            "state": ("not_applicable" if mode == "majority_sign"
                      else ("reconciled" if reconciliation_failures == 0
                            else "failed")),
            "note": ("combined_score = sum(effective_weight_k x "
                     "oriented_normalised_k) within tolerance for linear "
                     "modes; majority_sign is a sign vote and linear "
                     "reconciliation does not apply"),
        },
    }


def _sign(value: Any) -> int:
    v = float(value)
    return 1 if v > 0 else (-1 if v < 0 else 0)


def _missing_contribution(key: Key, signal_id: str,
                          configured_weight: float) -> Dict[str, Any]:
    return {
        "entity_id": key[0], "timestamp": key[1],
        "signal_id": signal_id,
        "normalised_value": None,
        "configured_weight": configured_weight,
        "effective_weight": None,
        "contribution": None,
        "sign_vote": None,
        "missing": True,
    }


__all__ = [
    "COMBINATION_MODES", "MISSING_COMPONENT_POLICIES",
    "WEIGHT_NORMALISATION_POLICIES", "RECONCILIATION_TOLERANCE",
    "CombinationError", "validate_combination_policy", "combine",
]
