"""
Signal turnover, membership change and holding-period overlap (v1).

All measures describe a NEUTRAL equal-weight reference built from the
bucket assignments — never an executed or recommended portfolio.

One-way turnover of the equal-weight top bucket at rebalance ``t``:

    one_way_turnover_t = 0.5 · Σ_i |w_i,t − w_i,t−1|

with ``w_i,t = 1/n_t`` for members and 0 otherwise.  The first rebalance
has NO prior book: under the default ``no_prior_unavailable`` policy its
turnover is null with that reason (never silently treated as a full
build), and under the explicit ``zero_prior_full_build`` policy it counts
the signed long/short build from zero — the choice is a
declared configuration, not a hidden default.

Holding-period overlap: with horizon ``k`` steps and a rebalance every
step, ``k`` cohorts are open at once.  Gross exposure under overlapping
cohorts is reported (cohort gross × concurrent cohorts) and is NEVER
normalised silently: the normalisation policy is declared
(``none_disclosed`` or ``per_cohort_equal_split``).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

INITIAL_TURNOVER_POLICIES = ("no_prior_unavailable", "zero_prior_full_build")
COHORT_NORMALISATION_POLICIES = ("none_disclosed", "per_cohort_equal_split")


class TurnoverError(ValueError):
    """Invalid turnover configuration (HTTP 422)."""


def validate_turnover_config(raw: Any) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {"initial_policy", "cohort_normalisation"})
    if unknown:
        raise TurnoverError(f"unknown turnover keys: {unknown}")
    initial = cfg.get("initial_policy", "no_prior_unavailable")
    if initial not in INITIAL_TURNOVER_POLICIES:
        raise TurnoverError(
            f"initial_policy must be one of {list(INITIAL_TURNOVER_POLICIES)}")
    normalisation = cfg.get("cohort_normalisation", "none_disclosed")
    if normalisation not in COHORT_NORMALISATION_POLICIES:
        raise TurnoverError(
            f"cohort_normalisation must be one of "
            f"{list(COHORT_NORMALISATION_POLICIES)}")
    return {"initial_policy": initial, "cohort_normalisation": normalisation}


def _weights(members: Set[str]) -> Dict[str, float]:
    if not members:
        return {}
    weight = 1.0 / len(members)
    return {entity: weight for entity in sorted(members)}


def one_way_turnover(previous: Optional[Set[str]],
                     current: Set[str], *,
                     initial_policy: str) -> Optional[float]:
    if previous is None:
        if initial_policy == "zero_prior_full_build":
            return 1.0 if current else 0.0
        return None
    w_prev = _weights(previous)
    w_cur = _weights(current)
    entities = set(w_prev) | set(w_cur)
    return 0.5 * sum(abs(w_cur.get(e, 0.0) - w_prev.get(e, 0.0))
                     for e in sorted(entities))


def reference_one_way_turnover(previous_top: Optional[Set[str]],
                               previous_bottom: Optional[Set[str]],
                               current_top: Set[str],
                               current_bottom: Set[str], *,
                               initial_policy: str) -> Optional[float]:
    """Turnover of the gross-2 long-top / short-bottom reference.

    Signed reference weights are +1 across the top leg and -1 across the
    bottom leg.  The result is 0.5 * sum(abs(delta weight)) across both legs,
    so asymmetric changes are measured rather than assuming both legs turn
    over at the top leg's rate.
    """
    if previous_top is None or previous_bottom is None:
        if initial_policy != "zero_prior_full_build":
            return None
        previous_top = set()
        previous_bottom = set()

    def signed(top: Set[str], bottom: Set[str]) -> Dict[str, float]:
        weights = _weights(top)
        for entity, weight in _weights(bottom).items():
            weights[entity] = weights.get(entity, 0.0) - weight
        return weights

    before = signed(previous_top, previous_bottom)
    after = signed(current_top, current_bottom)
    entities = set(before) | set(after)
    return 0.5 * sum(abs(after.get(entity, 0.0)
                         - before.get(entity, 0.0))
                     for entity in sorted(entities))

def membership_timeline(pairs: List[Dict[str, Any]],
                        assignments: Sequence[int], *,
                        bucket_count: int,
                        initial_policy: str) -> Dict[str, Any]:
    """Per-rebalance membership change of the top and bottom buckets."""
    by_stamp: Dict[str, Dict[str, int]] = {}
    for i, pair in enumerate(pairs):
        by_stamp.setdefault(pair["signal_timestamp"], {})[
            pair["entity_id"]] = assignments[i]
    stamps = sorted(by_stamp)

    rows: List[Dict[str, Any]] = []
    previous_top: Optional[Set[str]] = None
    previous_bottom: Optional[Set[str]] = None
    holding_runs: Dict[str, int] = {}
    completed_runs: List[int] = []
    for stamp in stamps:
        members = by_stamp[stamp]
        top = {e for e, b in members.items() if b == bucket_count}
        bottom = {e for e, b in members.items() if b == 1}

        top_entries = sorted(top - (previous_top or set())) \
            if previous_top is not None else sorted(top)
        top_exits = sorted((previous_top or set()) - top) \
            if previous_top is not None else []
        bottom_entries = sorted(bottom - (previous_bottom or set())) \
            if previous_bottom is not None else sorted(bottom)
        bottom_exits = sorted((previous_bottom or set()) - bottom) \
            if previous_bottom is not None else []

        union = top | (previous_top or set())
        jaccard = (len(top & (previous_top or set())) / len(union)
                   if previous_top is not None and union else None)

        for entity in list(holding_runs):
            if entity not in top:
                completed_runs.append(holding_runs.pop(entity))
        for entity in top:
            holding_runs[entity] = holding_runs.get(entity, 0) + 1

        rows.append({
            "timestamp": stamp,
            "universe_size": len(members),
            "top_size": len(top), "bottom_size": len(bottom),
            "top_entries": len(top_entries), "top_exits": len(top_exits),
            "bottom_entries": len(bottom_entries),
            "bottom_exits": len(bottom_exits),
            "jaccard_top": jaccard,
            "one_way_turnover": reference_one_way_turnover(
                previous_top, previous_bottom, top, bottom,
                initial_policy=initial_policy),
            "top_members": sorted(top),
        })
        previous_top = top
        previous_bottom = bottom

    completed_runs.extend(holding_runs.values())
    turnovers = [r["one_way_turnover"] for r in rows
                 if r["one_way_turnover"] is not None]
    summary: Dict[str, Any] = {
        "rebalance_count": len(stamps),
        "mean_one_way_turnover": (sum(turnovers) / len(turnovers)
                                  if turnovers else None),
        "max_one_way_turnover": max(turnovers) if turnovers else None,
        "mean_jaccard_top": None,
        "average_holding_duration": (sum(completed_runs) / len(completed_runs)
                                     if completed_runs else None),
        "holding_duration_unit": "rebalances",
        "initial_policy": initial_policy,
        "turnover_convention": (
            "0.5 × sum(abs(delta signed weight)) across the long top and "
            "short bottom legs (gross exposure 2.0)"),
        "initial_policy_note": (
            "the first rebalance has no prior book; combined reference "
            "turnover is null under no_prior_unavailable, or a declared "
            "gross-2 full build under zero_prior_full_build — never a "
            "hidden zero prior"),
    }
    jaccards = [r["jaccard_top"] for r in rows if r["jaccard_top"] is not None]
    if jaccards:
        summary["mean_jaccard_top"] = sum(jaccards) / len(jaccards)
    return {"rows": rows, "summary": summary}


def holding_overlap(rebalance_count: int, horizon: Any, *,
                    cohort_normalisation: str) -> Dict[str, Any]:
    """Concurrent-cohort accounting for a hold-to-horizon reference."""
    out: Dict[str, Any] = {
        "open_cohort_model": ("one cohort opens per rebalance and stays open "
                              "for the horizon length"),
        "cohort_normalisation": cohort_normalisation,
        "max_concurrent_cohorts": None,
        "average_concurrent_cohorts": None,
        "gross_exposure_overlapping": None,
        "gross_exposure_note": None,
        "warning": None,
        "state": "unavailable",
    }
    if not isinstance(horizon, int) or horizon <= 0 or rebalance_count <= 0:
        out["gross_exposure_note"] = (
            "supplied outcomes carry their own intervals, so the cohort "
            "count is not defined by a horizon step")
        return out
    concurrent = [min(i + 1, horizon) for i in range(rebalance_count)]
    maximum = max(concurrent)
    average = sum(concurrent) / len(concurrent)
    per_cohort_gross = 2.0  # long top + short bottom, equal weight
    if cohort_normalisation == "per_cohort_equal_split":
        gross = per_cohort_gross
        note = ("each cohort is allocated 1/k of the reference capital, so "
                "total gross stays at the per-cohort gross by construction "
                "(declared policy)")
    else:
        gross = per_cohort_gross * maximum
        note = ("cohorts are NOT normalised (declared policy none_disclosed): "
                "at the maximum overlap the reference carries "
                f"{maximum} concurrent cohorts and gross exposure "
                f"{gross:g}; this leverage is disclosed, never hidden")
    out.update({
        "max_concurrent_cohorts": maximum,
        "average_concurrent_cohorts": average,
        "gross_exposure_overlapping": gross,
        "gross_exposure_note": note,
        "state": "available",
    })
    if maximum > 1:
        out["warning"] = (
            f"up to {maximum} holding cohorts are open simultaneously; "
            f"portfolio-level and cohort-level returns are different objects "
            f"and are kept separate")
    return out


__all__ = [
    "INITIAL_TURNOVER_POLICIES", "COHORT_NORMALISATION_POLICIES",
    "TurnoverError", "validate_turnover_config", "one_way_turnover",
    "reference_one_way_turnover", "membership_timeline",
    "holding_overlap",
]
