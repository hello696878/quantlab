"""
Purged K-Fold + Embargo cross-validation (López de Prado, AFML ch. 7).

Financial labels span an interval ``[start, end]`` (the label uses future
information through ``end``).  A standard random/contiguous K-fold leaks because a
training label whose interval overlaps the test fold shares information with it.
**Purging** removes such overlapping training labels; the **embargo** additionally
removes training labels that start just after the test fold.

Reuses the existing AFML synthetic path + triple-barrier labels.  Educational
methodology only — this is **not** Combinatorial Purged CV, not model training,
not investment advice.  Interval convention is **inclusive** ``[start, end]``.
"""

from __future__ import annotations

import math
from datetime import date
from numbers import Integral
from typing import List, Optional, Tuple

import numpy as np

from app.finml.cusum import cusum_events
from app.finml.labeling import triple_barrier_labels
from app.finml.orchestrator import FinmlInputError, validate_finml_inputs
from app.finml.sample_data import generate_synthetic_path

_MIN_SPLITS = 2
_MAX_SPLITS = 20
_MAX_EMBARGO_PCT = 0.2
_EVENT_CAP = 2000  # keep the CV payload bounded


# ---------------------------------------------------------------------------
# Interval helpers
# ---------------------------------------------------------------------------


def intervals_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Inclusive-interval overlap: ``s1 <= e2 and e1 >= s2``."""
    return s1 <= e2 and e1 >= s2


def build_label_intervals(labels: List[dict]) -> List[dict]:
    """Normalize triple-barrier labels into ``{event_id, start, end, label}`` rows,
    sorted by start (time order). Invalid or reversed intervals are rejected."""
    rows: List[dict] = []
    seen_event_ids = set()
    for row_number, label in enumerate(labels):
        try:
            values = {
                "event_id": label["event_id"],
                "start": label["start_index"],
                "end": label["end_index"],
                "label": label["label"],
            }
        except (KeyError, TypeError) as exc:
            raise FinmlInputError(f"Label interval {row_number} is missing a required field.") from exc

        if any(isinstance(value, bool) or not isinstance(value, Integral) for value in values.values()):
            raise FinmlInputError(f"Label interval {row_number} must contain integer fields.")

        event_id = int(values["event_id"])
        start = int(values["start"])
        end = int(values["end"])
        outcome = int(values["label"])
        if event_id < 0 or event_id in seen_event_ids:
            raise FinmlInputError("Label event_id values must be unique non-negative integers.")
        if start < 0 or end < start:
            raise FinmlInputError("Each label interval must satisfy 0 <= start_index <= end_index.")
        if outcome not in (-1, 0, 1):
            raise FinmlInputError("Label values must be -1, 0, or 1.")

        seen_event_ids.add(event_id)
        rows.append({"event_id": event_id, "start": start, "end": end, "label": outcome})

    rows.sort(key=lambda r: (r["start"], r["end"], r["event_id"]))
    return rows


def count_overlaps(train_pos: List[int], test_pos: List[int], intervals: List[dict]) -> int:
    """Count train events whose interval overlaps **any** test event's interval."""
    n = 0
    for p in train_pos:
        ts, te = intervals[p]["start"], intervals[p]["end"]
        if any(intervals_overlap(ts, te, intervals[q]["start"], intervals[q]["end"]) for q in test_pos):
            n += 1
    return n


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------


def split_kfold_by_time(n_events: int, n_splits: int) -> List[List[int]]:
    """Standard time-ordered (no-shuffle) K-fold: contiguous test blocks of positions."""
    if not isinstance(n_events, int) or isinstance(n_events, bool) or n_events < 1:
        raise FinmlInputError("n_events must be a positive integer.")
    validate_cv_inputs(n_splits, 0.0)
    if n_splits > n_events:
        raise FinmlInputError("n_splits cannot exceed the number of labeled events.")
    return [list(map(int, block)) for block in np.array_split(np.arange(n_events), n_splits)]


def purge_train_indices(
    train_pos: List[int], test_pos: List[int], intervals: List[dict]
) -> Tuple[List[int], List[int]]:
    """Split train into (kept, purged); purge any train interval overlapping a test interval."""
    kept: List[int] = []
    purged: List[int] = []
    test_iv = [(intervals[q]["start"], intervals[q]["end"]) for q in test_pos]
    for p in train_pos:
        ts, te = intervals[p]["start"], intervals[p]["end"]
        if any(intervals_overlap(ts, te, qs, qe) for qs, qe in test_iv):
            purged.append(p)
        else:
            kept.append(p)
    return kept, purged


def apply_embargo(
    train_pos: List[int], test_end_bar: int, intervals: List[dict], embargo_bars: int
) -> Tuple[List[int], List[int]]:
    """Split train into (kept, embargoed); embargo train events that *start* in the
    window ``(test_end_bar, test_end_bar + embargo_bars]`` (right after the test fold)."""
    if embargo_bars <= 0:
        return list(train_pos), []
    lo = test_end_bar
    hi = test_end_bar + embargo_bars
    kept: List[int] = []
    embargoed: List[int] = []
    for p in train_pos:
        s = intervals[p]["start"]
        if lo < s <= hi:
            embargoed.append(p)
        else:
            kept.append(p)
    return kept, embargoed


# ---------------------------------------------------------------------------
# Fold construction + diagnostics
# ---------------------------------------------------------------------------


def make_purged_kfold_splits(
    intervals: List[dict], n_splits: int, embargo_bars: int, dates: List[str]
) -> List[dict]:
    """Build per-fold purged + embargoed splits with leakage diagnostics."""
    n_events = len(intervals)
    if not isinstance(embargo_bars, int) or isinstance(embargo_bars, bool) or embargo_bars < 0:
        raise FinmlInputError("embargo_bars must be a non-negative integer.")
    if not dates:
        raise FinmlInputError("dates must contain at least one observation.")
    try:
        parsed_dates = [date.fromisoformat(value) for value in dates]
    except (TypeError, ValueError) as exc:
        raise FinmlInputError("dates must contain valid ISO date strings.") from exc
    if any(current <= previous for previous, current in zip(parsed_dates, parsed_dates[1:])):
        raise FinmlInputError("dates must be strictly increasing.")
    if any(iv["start"] < 0 or iv["end"] < iv["start"] or iv["end"] >= len(dates) for iv in intervals):
        raise FinmlInputError("Label intervals must be ordered and fall within the available dates.")
    if intervals != sorted(intervals, key=lambda r: (r["start"], r["end"], r["event_id"])):
        raise FinmlInputError("Label intervals must be sorted by start date.")

    test_blocks = split_kfold_by_time(n_events, n_splits)
    folds: List[dict] = []
    for fold_id, test_pos in enumerate(test_blocks):
        if not test_pos:
            continue
        test_set = set(test_pos)
        train_std = [p for p in range(n_events) if p not in test_set]

        test_min_start = min(intervals[q]["start"] for q in test_pos)
        test_end_bar = max(intervals[q]["end"] for q in test_pos)

        standard_overlap = count_overlaps(train_std, test_pos, intervals)

        kept_after_purge, purged = purge_train_indices(train_std, test_pos, intervals)
        after_purge_overlap = count_overlaps(kept_after_purge, test_pos, intervals)
        kept_after_embargo, embargoed = apply_embargo(kept_after_purge, test_end_bar, intervals, embargo_bars)

        n_bars = len(dates)
        embargo_start = test_end_bar + 1
        embargo_end = min(test_end_bar + embargo_bars, n_bars - 1)

        warnings: List[str] = []
        if train_std and len(kept_after_embargo) / len(train_std) < 0.4:
            warnings.append(
                f"Fold {fold_id}: more than 60% of training events were purged/embargoed — overlapping "
                "labels are long relative to the fold size; consider fewer splits or shorter vertical barriers."
            )

        folds.append(
            {
                "fold_id": fold_id,
                "train_event_ids": [intervals[p]["event_id"] for p in kept_after_embargo],
                "test_event_ids": [intervals[q]["event_id"] for q in test_pos],
                "purged_event_ids": [intervals[p]["event_id"] for p in purged],
                "embargoed_event_ids": [intervals[p]["event_id"] for p in embargoed],
                "test_start_date": dates[test_min_start],
                "test_end_date": dates[test_end_bar],
                "embargo_start_date": dates[embargo_start] if embargo_bars > 0 and embargo_start < n_bars else None,
                "embargo_end_date": dates[embargo_end] if embargo_bars > 0 and embargo_start < n_bars else None,
                "embargo_start_index": embargo_start if embargo_bars > 0 and embargo_start < n_bars else None,
                "embargo_end_index": embargo_end if embargo_bars > 0 and embargo_start < n_bars else None,
                "train_count_before": len(train_std),
                "train_count_after": len(kept_after_embargo),
                "test_count": len(test_pos),
                "purged_count": len(purged),
                "embargoed_count": len(embargoed),
                "standard_train_overlap_count": standard_overlap,
                "purged_overlap_count_after_purge": after_purge_overlap,
                "leakage_reduction": standard_overlap - after_purge_overlap,
                "train_fraction_remaining": round(len(kept_after_embargo) / len(train_std), 6) if train_std else 0.0,
                "warnings": warnings,
            }
        )
    return folds


def summarize_cv_splits(folds: List[dict], n_events: int, n_splits: int, embargo_bars: int) -> dict:
    total_purged = sum(f["purged_count"] for f in folds)
    total_embargoed = sum(f["embargoed_count"] for f in folds)
    total_overlap_before = sum(f["standard_train_overlap_count"] for f in folds)
    total_overlap_after = sum(f["purged_overlap_count_after_purge"] for f in folds)
    before = sum(1 for f in folds if f["standard_train_overlap_count"] > 0)
    after = sum(1 for f in folds if f["purged_overlap_count_after_purge"] > 0)
    fracs = [f["train_fraction_remaining"] for f in folds]
    avg_frac = float(np.mean(fracs)) if fracs else 0.0
    return {
        "n_events": int(n_events),
        "n_splits": int(n_splits),
        "embargo_bars": int(embargo_bars),
        "total_purged": int(total_purged),
        "total_embargoed": int(total_embargoed),
        "total_overlap_before_purge": int(total_overlap_before),
        "total_overlap_after_purge": int(total_overlap_after),
        "folds_with_overlap_before_purge": int(before),
        "folds_with_overlap_after_purge": int(after),
        "average_train_fraction_remaining": round(avg_frac, 6) if math.isfinite(avg_frac) else 0.0,
    }


# ---------------------------------------------------------------------------
# Validation + orchestrator
# ---------------------------------------------------------------------------


def validate_cv_inputs(n_splits: int, embargo_pct: float) -> None:
    if not isinstance(n_splits, int) or isinstance(n_splits, bool) or n_splits < _MIN_SPLITS or n_splits > _MAX_SPLITS:
        raise FinmlInputError(f"n_splits must be an integer between {_MIN_SPLITS} and {_MAX_SPLITS}.")
    if not math.isfinite(embargo_pct) or embargo_pct < 0 or embargo_pct > _MAX_EMBARGO_PCT:
        raise FinmlInputError(f"embargo_pct must be between 0 and {_MAX_EMBARGO_PCT}.")


def run_purged_cv_demo(
    n_days: int = 500,
    start_price: float = 100.0,
    drift: float = 0.0002,
    volatility: float = 0.015,
    seed: Optional[int] = 42,
    cusum_threshold: float = 0.02,
    threshold_mode: str = "fixed",
    volatility_window: int = 20,
    profit_take_multiple: float = 1.5,
    stop_loss_multiple: float = 1.0,
    vertical_barrier_days: int = 10,
    n_splits: int = 5,
    embargo_pct: float = 0.01,
) -> dict:
    """Run the purged K-fold + embargo CV demo on synthetic labels as a JSON-ready dict."""
    validate_finml_inputs(
        n_days, start_price, drift, volatility, seed, cusum_threshold, threshold_mode,
        volatility_window, profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )
    validate_cv_inputs(n_splits, embargo_pct)

    path = generate_synthetic_path(
        n_days, start_price, drift, volatility, seed if seed is not None else 42, volatility_window
    )
    dates = path["dates"]
    raw_events = cusum_events(path["returns"], cusum_threshold, threshold_mode, path["rolling_vol"])
    labels = triple_barrier_labels(
        path["close"], [e["index"] for e in raw_events], path["rolling_vol"],
        profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )

    intervals = build_label_intervals(labels)
    generated_event_count = len(intervals)
    n_events = generated_event_count
    if n_events < n_splits:
        raise FinmlInputError(
            "Not enough labeled events to form the requested number of folds. Lower n_splits, lower "
            "the CUSUM threshold, or increase n_days."
        )
    if n_events > _EVENT_CAP:
        intervals = intervals[:_EVENT_CAP]
        n_events = _EVENT_CAP

    # Embargo is a fraction of the full synthetic observation history. Round up
    # so any positive fraction represents at least one trading observation.
    embargo_bars = int(math.ceil(embargo_pct * n_days)) if embargo_pct > 0 else 0

    folds = make_purged_kfold_splits(intervals, n_splits, embargo_bars, dates)
    summary = summarize_cv_splits(folds, n_events, n_splits, embargo_bars)

    timeline = [
        {
            "event_id": iv["event_id"],
            "start_date": dates[iv["start"]],
            "end_date": dates[iv["end"]],
            "start_index": iv["start"],
            "end_index": iv["end"],
            "label": iv["label"],
        }
        for iv in intervals
    ]

    warnings = [
        "Synthetic demo data — not live market data.",
        "Purged K-fold + embargo reduce leakage from overlapping labels but do not guarantee a good "
        "model or remove all research bias. This is methodology only — no features, no model, no "
        "out-of-sample performance. Combinatorial Purged CV (CPCV) and model training are planned.",
        "Embargo is applied after purging; intervals are inclusive [start, end] in trading observations.",
        f"embargo_pct is applied to the full {n_days}-observation synthetic history and rounded up "
        f"to {embargo_bars} trading observation(s).",
    ]
    if generated_event_count > _EVENT_CAP:
        warnings.append(
            f"The CV demo is capped at the first {_EVENT_CAP} time-ordered labels; "
            f"{generated_event_count - _EVENT_CAP} later label(s) were omitted from split construction."
        )
    if threshold_mode == "vol_scaled":
        warnings.append(
            "Vol-scaled CUSUM mode interprets cusum_threshold as a multiplier of the rolling "
            "volatility estimate, not as a fixed percentage return."
        )
    for f in folds:
        for w in f["warnings"]:
            warnings.append(w)

    return {"summary": summary, "folds": folds, "timeline": timeline, "warnings": warnings}
