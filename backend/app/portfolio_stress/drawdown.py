"""
Historical drawdown analysis, episode detection and attribution (v1).

Convention (documented): the wealth index compounds simple per-period
returns, ``W_t = Π_{s<=t} (1 + r_s)`` from 1.0; the running peak uses
TRAILING history only (``peak_t = max_{s<=t} W_s`` — never a future
maximum); ``drawdown_t = W_t / peak_t − 1``.  Recovery is the first
observed index after the trough where wealth returns to (or above) the
episode peak; unrecovered episodes stay visibly unrecovered — no
fabricated recovery dates.  Leading None observations (before the first
effective rebalance) are excluded explicitly, never zero-filled.

Episode rule (deterministic): an episode opens at the first index whose
drawdown goes below zero after a peak, its trough is the minimum drawdown
(first occurrence on ties), and it closes at recovery or at the series
end.  Exact-zero drawdowns are boundaries, not episode members.

Attribution over the below-peak interval (episode start … trough — the
peak-making period's return is NOT part of the decline) uses the
STATIC-WEIGHT linear approximation where flagged, or per-period supplied
weights otherwise: ``contribution_i = Σ_t w_i[t] × r_i[t]``; contributions
reconcile with the summed arithmetic portfolio return of the interval
under that weight policy (NOT the geometric depth, and not the drifting
series the depth is measured on — both gaps are disclosed).  Cost
contributions, when linked, stay separate from market contributions.
Attribution never claims to prove why a drawdown occurred.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

MAX_EPISODES = 40


class DrawdownError(ValueError):
    """Raised for invalid drawdown inputs."""


def drawdown_path(returns: List[Optional[float]],
                  timestamps: List[str]) -> Dict[str, Any]:
    """Wealth index, trailing peak and drawdown series over the observed
    (non-None) span.  Returns index offsets into the ORIGINAL timeline."""
    observed = [(i, r) for i, r in enumerate(returns) if r is not None]
    if len(observed) < 2:
        return {"available": False,
                "reason": "fewer than two observed portfolio returns"}
    start, end = observed[0][0], observed[-1][0]
    if any(returns[i] is None for i in range(start, end + 1)):
        return {"available": False,
                "reason": "portfolio return series has interior gaps; "
                          "drawdown analysis needs a contiguous span"}
    wealth: List[float] = []
    level = 1.0
    for i in range(start, end + 1):
        level *= (1.0 + returns[i])  # type: ignore[operator]
        if not math.isfinite(level) or level <= 0:
            return {"available": False,
                    "reason": "wealth index became non-positive or "
                              "non-finite (a return <= -100%)"}
        wealth.append(level)
    peaks: List[float] = []
    peak = 1.0  # the initial capital IS a peak: an opening decline is a drawdown
    for w in wealth:
        peak = max(peak, w)
        peaks.append(peak)
    drawdowns = [w / p - 1.0 for w, p in zip(wealth, peaks)]
    return {
        "available": True,
        "start_index": start,
        "end_index": end,
        "trailing_unobserved": len(returns) - 1 - end,
        "timestamps": timestamps[start:end + 1],
        "wealth": wealth,
        "peaks": peaks,
        "drawdowns": drawdowns,
        "max_drawdown": min(drawdowns) if drawdowns else 0.0,
        "convention": "wealth compounds simple returns from 1.0; the "
                      "running peak is trailing-only",
    }


def detect_episodes(path: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic drawdown episodes (module doc).

    Returns EVERY episode in chronological order with chronological ids —
    no truncation here.  The caller bounds persistence (keeping the deepest
    ``MAX_EPISODES``) and must disclose any truncation; the deepest episode
    is always selected from the full list.
    """
    if not path.get("available"):
        return []
    drawdowns = path["drawdowns"]
    wealth = path["wealth"]
    peaks = path["peaks"]
    timestamps = path["timestamps"]
    episodes: List[Dict[str, Any]] = []
    open_start: Optional[int] = None
    for t, dd in enumerate(drawdowns):
        if dd < 0 and open_start is None:
            open_start = t
        elif dd >= 0 and open_start is not None:
            episodes.append(_episode(open_start, t, drawdowns, wealth, peaks,
                                     timestamps, recovered=True))
            open_start = None
    if open_start is not None:
        episodes.append(_episode(open_start, len(drawdowns), drawdowns,
                                 wealth, peaks, timestamps, recovered=False))
    for i, e in enumerate(episodes):
        e["episode_id"] = i
    return episodes


def _episode(start: int, end: int, drawdowns, wealth, peaks, timestamps,
             *, recovered: bool) -> Dict[str, Any]:
    window = drawdowns[start:end]
    trough_offset = min(range(len(window)), key=lambda k: window[k])
    trough_index = start + trough_offset
    # start == 0 means the peak is the initial 1.0 capital BEFORE the first
    # observation; peak_timestamp then labels the first below-peak period.
    peak_index = start - 1 if start > 0 else 0
    return {
        "start_index": start,  # first below-peak observation (attribution start)
        "peak_index": peak_index,
        "peak_timestamp": timestamps[peak_index],
        "peak_is_initial_capital": start == 0,
        "trough_index": trough_index,
        "trough_timestamp": timestamps[trough_index],
        "recovery_index": end if recovered else None,
        "recovery_timestamp": (timestamps[end]
                               if recovered and end < len(timestamps)
                               else None),
        "depth": float(min(window)),
        "duration": trough_index - start + 1,
        "recovery_duration": (end - trough_index) if recovered else None,
        "recovered": recovered,
        "status": "recovered" if recovered else "unrecovered",
    }


def attribute_interval(start_index: int, end_index: int,
                       asset_ids: List[str],
                       weight_series: List[Optional[Dict[str, float]]],
                       returns_matrix: List[List[float]],
                       asset_groups: Dict[str, Optional[str]],
                       *, static_weights: bool) -> Dict[str, Any]:
    """Per-asset contribution over [start_index, end_index] inclusive.

    ``weight_series[t]`` are the weights governing period t on the FULL
    timeline; the linear approximation Σ_t w_i[t]·r_i[t] reconciles with
    the summed portfolio arithmetic return of the interval, not with the
    geometric depth (disclosed).
    """
    rows = []
    portfolio_sum = 0.0
    for k, aid in enumerate(asset_ids):
        contribution = 0.0
        weight_total = 0.0
        count = 0
        for t in range(start_index, end_index + 1):
            w = weight_series[t]
            if w is None:
                return {"available": False,
                        "reason": "weights unavailable inside the interval"}
            contribution += w.get(aid, 0.0) * returns_matrix[k][t]
            weight_total += w.get(aid, 0.0)
            count += 1
        portfolio_sum += contribution
        rows.append({"asset_id": aid, "group": asset_groups.get(aid),
                     "contribution": contribution,
                     "average_weight": weight_total / count if count else None})
    abs_total = sum(abs(r["contribution"]) for r in rows)
    for r in rows:
        r["abs_share"] = (abs(r["contribution"]) / abs_total
                          if abs_total > 0 else None)
    groups: Dict[str, float] = {}
    for r in rows:
        g = r.get("group") or "ungrouped"
        groups[g] = groups.get(g, 0.0) + r["contribution"]
    return {
        "available": True,
        "rows": rows,
        "group_contributions": groups,
        "portfolio_contribution_sum": portfolio_sum,
        "weight_policy": ("static stored target (approximation labelled)"
                          if static_weights else
                          "per-period drifting stored weights"),
        "reconciliation_note": (
            "asset contributions sum to the interval's summed arithmetic "
            "portfolio return UNDER THE STATED WEIGHT POLICY; the geometric "
            "episode depth differs by compounding, and the depth itself is "
            "measured on the recorded drifting-weight series — both gaps "
            "are disclosed, not hidden"),
    }
