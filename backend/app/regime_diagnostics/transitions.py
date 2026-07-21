"""
Regime intervals and transition diagnostics (descriptive only).

Intervals are maximal runs of one effective label; a transition exists where
two consecutive periods carry different defined labels (gaps of unavailable
labels break intervals without creating transitions — documented).  Detection
uses only the effective labels, which are themselves lagged trailing
constructs — no future data can enter.

Per transition and candidate the lab reports the mean outcome over a bounded
event window before and after the boundary and their **measured before/after
difference** — never "the regime caused the change", and no event-study
significance claim exists in v1 (no supported test is implemented).
Overlapping windows (transitions closer together than the window) are
flagged; small windows are warned.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

MIN_TRANSITION_WINDOW = 2
MAX_TRANSITION_WINDOW = 20
DEFAULT_TRANSITION_WINDOW = 5
MAX_RECORDED_TRANSITIONS = 50


def build_intervals(labels: Sequence[Optional[str]]) -> List[Dict[str, Any]]:
    """Maximal runs, INCLUDING unavailable (None) runs — summaries filter them."""
    intervals: List[Dict[str, Any]] = []
    if not labels:
        return intervals
    current = labels[0]
    start = 0
    for i in range(1, len(labels)):
        if labels[i] != current:
            intervals.append({"label": current, "start": start, "end": i - 1,
                              "length": i - start})
            current = labels[i]
            start = i
    intervals.append({"label": current, "start": start,
                      "end": len(labels) - 1, "length": len(labels) - start})
    return intervals


def interval_summary(labels: Sequence[Optional[str]]) -> Dict[str, Any]:
    intervals = [iv for iv in build_intervals(labels) if iv["label"] is not None]
    by_label: Dict[str, List[int]] = {}
    for iv in intervals:
        by_label.setdefault(iv["label"], []).append(iv["length"])
    return {
        "interval_count": len(intervals),
        "per_label": {
            label: {"intervals": len(lengths),
                    "mean_duration": float(np.mean(lengths)),
                    "max_duration": int(max(lengths))}
            for label, lengths in sorted(by_label.items())
        },
    }


def detect_transitions(
    labels: Sequence[Optional[str]],
    timestamps: Sequence[str],
    outcome_matrix: np.ndarray,
    candidate_ids: Sequence[str],
    window: int,
) -> Dict[str, Any]:
    boundaries: List[Dict[str, Any]] = []
    for i in range(1, len(labels)):
        prev, nxt = labels[i - 1], labels[i]
        if prev is not None and nxt is not None and prev != nxt:
            boundaries.append({"index": i, "previous_regime": prev,
                               "next_regime": nxt})
    truncated = len(boundaries) > MAX_RECORDED_TRANSITIONS
    recorded = boundaries[:MAX_RECORDED_TRANSITIONS]
    transitions: List[Dict[str, Any]] = []
    prev_index: Optional[int] = None
    for b in recorded:
        i = b["index"]
        pre_lo = max(0, i - window)
        post_hi = min(len(labels), i + window)
        overlap = prev_index is not None and (i - prev_index) < window
        candidates: List[Dict[str, Any]] = []
        for col, cid in enumerate(candidate_ids):
            pre = outcome_matrix[pre_lo:i, col]
            post = outcome_matrix[i:post_hi, col]
            entry: Dict[str, Any] = {
                "candidate_id": cid,
                "pre_count": int(len(pre)), "post_count": int(len(post)),
                "pre_mean": float(pre.mean()) if len(pre) else None,
                "post_mean": float(post.mean()) if len(post) else None,
            }
            entry["difference"] = (
                entry["post_mean"] - entry["pre_mean"]
                if entry["pre_mean"] is not None and entry["post_mean"] is not None
                else None
            )
            entry["status"] = ("ok" if len(pre) >= window and len(post) >= window
                               else "small_sample")
            candidates.append(entry)
        transitions.append({
            "transition_index": i,
            "timestamp": timestamps[i],
            "previous_regime": b["previous_regime"],
            "next_regime": b["next_regime"],
            "window": window,
            "overlapping_window": overlap,
            "candidates": candidates,
        })
        prev_index = i
    return {
        "transition_count": len(boundaries),
        "recorded_count": len(recorded),
        "truncated": truncated,
        "truncation_note": (
            f"only the first {MAX_RECORDED_TRANSITIONS} transitions carry "
            "event-window detail" if truncated else None),
        "window": window,
        "wording_note": ("differences are measured before/after statistics — "
                         "never causal claims; no significance test exists in v1"),
        "transitions": transitions,
    }


__all__ = [
    "MIN_TRANSITION_WINDOW", "MAX_TRANSITION_WINDOW",
    "DEFAULT_TRANSITION_WINDOW", "MAX_RECORDED_TRANSITIONS",
    "build_intervals", "interval_summary", "detect_transitions",
]
