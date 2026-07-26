"""
Split generation, purging, embargo, and the leakage audit.

All splitters take the deterministically-sorted output of
:func:`app.model_validation.events.normalize_samples` and return split dicts
of **sample ids** (never bare row indices).  Purging is interval-based under
the closed-interval convention; the embargo removes training samples whose
information interval *starts* inside the configured window after each disjoint
test block (mirroring ``app.finml.cv.apply_embargo``, generalized to
timestamps and multiple blocks).  Purge and embargo results are always
reported separately.

Every split then passes through :func:`audit_split`, which recomputes the
remaining train/test interval overlap from scratch — a split with any
remaining overlap is marked ``invalid`` with diagnostics, never silently kept.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.model_validation.events import EventError, intervals_overlap

MIN_FOLDS = 2
MAX_FOLDS = 20
MAX_CPCV_GROUPS = 12
MAX_CPCV_COMBINATIONS = 100
MAX_EMBARGO_FRACTION = 0.2
MAX_WALK_FORWARD_FOLDS = 50

Sample = Dict[str, Any]


class SplitConfigError(ValueError):
    """Invalid split configuration (maps to HTTP 422)."""


def _blocks(n: int, k: int) -> List[List[int]]:
    """Contiguous, time-ordered position blocks (same shape as np.array_split)."""
    base, extra = divmod(n, k)
    blocks: List[List[int]] = []
    start = 0
    for i in range(k):
        size = base + (1 if i < extra else 0)
        blocks.append(list(range(start, start + size)))
        start += size
    return [b for b in blocks if b]


def _ids(samples: Sequence[Sample], positions: Sequence[int]) -> List[str]:
    return [samples[p]["sample_id"] for p in positions]


# ---------------------------------------------------------------------------
# Purge + embargo (timestamp domain)
# ---------------------------------------------------------------------------


def purge_positions(
    samples: Sequence[Sample], train_pos: Sequence[int], test_pos: Sequence[int]
) -> Tuple[List[int], List[int], Dict[str, str]]:
    """Interval-overlap purge.  Returns (kept, purged, purged_reason_by_id).

    A training sample is purged iff its closed information interval overlaps
    ANY test sample's interval — never by row adjacency or index arithmetic.
    """
    test_iv = [(samples[q]["pred_dt"], samples[q]["eval_dt"], samples[q]["sample_id"]) for q in test_pos]
    kept: List[int] = []
    purged: List[int] = []
    reasons: Dict[str, str] = {}
    for p in train_pos:
        ts, te = samples[p]["pred_dt"], samples[p]["eval_dt"]
        hit = next((sid for qs, qe, sid in test_iv if intervals_overlap(ts, te, qs, qe)), None)
        if hit is not None:
            purged.append(p)
            reasons[samples[p]["sample_id"]] = f"overlaps test sample {hit}"
        else:
            kept.append(p)
    return kept, purged, reasons


def _test_blocks_time(
    samples: Sequence[Sample], test_pos: Sequence[int]
) -> List[Tuple[datetime, datetime]]:
    """Merge test positions into disjoint (start, end) time blocks."""
    ivs = sorted((samples[q]["pred_dt"], samples[q]["eval_dt"]) for q in test_pos)
    blocks: List[Tuple[datetime, datetime]] = []
    for s, e in ivs:
        if blocks and s <= blocks[-1][1]:
            blocks[-1] = (blocks[-1][0], max(blocks[-1][1], e))
        else:
            blocks.append((s, e))
    return blocks


def resolve_embargo_delta(
    samples: Sequence[Sample], embargo: Optional[Dict[str, Any]]
) -> Optional[timedelta]:
    """Resolve the embargo configuration into a timedelta (or None for no embargo).

    Modes (exactly one): ``{"mode": "none"}``, ``{"mode": "duration_days",
    "value": d}`` (d ≥ 0 days, fractional allowed), or ``{"mode": "fraction",
    "value": f}`` (0 ≤ f ≤ 0.2 of the total observation span).
    """
    if not embargo or embargo.get("mode") in (None, "none"):
        return None
    mode = embargo.get("mode")
    value = embargo.get("value")
    if mode not in ("duration_days", "fraction"):
        raise SplitConfigError("embargo mode must be one of: none, duration_days, fraction")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise SplitConfigError("embargo value must be a finite number")
    value = float(value)
    if value < 0:
        raise SplitConfigError("embargo value must not be negative")
    if mode == "duration_days":
        return timedelta(days=value)
    if value > MAX_EMBARGO_FRACTION:
        raise SplitConfigError(f"embargo fraction must be at most {MAX_EMBARGO_FRACTION}")
    # Documented span: earliest prediction time → latest evaluation time. The
    # sort orders by prediction_time, so the last sample's eval_dt is NOT
    # necessarily the maximum under irregular label horizons — take the true max.
    earliest_pred = min(s["pred_dt"] for s in samples)
    latest_eval = max(s["eval_dt"] for s in samples)
    span = latest_eval - earliest_pred
    return timedelta(seconds=span.total_seconds() * value)


def apply_embargo_positions(
    samples: Sequence[Sample],
    train_pos: Sequence[int],
    test_pos: Sequence[int],
    delta: Optional[timedelta],
) -> Tuple[List[int], List[int], List[Dict[str, str]]]:
    """Embargo training samples that START inside ``(block_end, block_end+delta]``
    after EACH disjoint test block.  Endpoint inclusive; start exclusive
    (a sample starting exactly at block_end is already purged by overlap).
    Returns (kept, embargoed, effective_windows)."""
    if delta is None or delta.total_seconds() <= 0 or not test_pos:
        return list(train_pos), [], []
    raw_windows = sorted((end, end + delta) for _, end in _test_blocks_time(samples, test_pos))
    # Merge overlapping/adjacent windows so each disjoint test block reports
    # one effective embargo interval (the membership union is identical).
    windows: List[Tuple[datetime, datetime]] = []
    for lo, hi in raw_windows:
        if windows and lo <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], hi))
        else:
            windows.append((lo, hi))
    kept: List[int] = []
    embargoed: List[int] = []
    for p in train_pos:
        s = samples[p]["pred_dt"]
        if any(lo < s <= hi for lo, hi in windows):
            embargoed.append(p)
        else:
            kept.append(p)
    effective = [{"start": lo.isoformat(), "end": hi.isoformat()} for lo, hi in windows]
    return kept, embargoed, effective


# ---------------------------------------------------------------------------
# Splitters (each returns a list of raw split dicts of positions)
# ---------------------------------------------------------------------------


def _validate_folds(n_samples: int, n_folds: Any) -> int:
    if isinstance(n_folds, bool) or not isinstance(n_folds, int):
        raise SplitConfigError("n_folds must be an integer")
    if n_folds < MIN_FOLDS or n_folds > MAX_FOLDS:
        raise SplitConfigError(f"n_folds must be between {MIN_FOLDS} and {MAX_FOLDS}")
    if n_folds > n_samples:
        raise SplitConfigError("n_folds cannot exceed the number of samples")
    return n_folds


def standard_kfold(samples: Sequence[Sample], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reference-only K-fold.  Shuffle is OFF by default; enabling it requires
    an explicit seed and the result carries a leakage warning either way."""
    n = len(samples)
    n_folds = _validate_folds(n, config.get("n_folds", 5))
    positions = list(range(n))
    shuffled = bool(config.get("shuffle", False))
    if shuffled:
        seed = config.get("random_seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise SplitConfigError("shuffled K-fold requires an explicit integer random_seed")
        random.Random(seed).shuffle(positions)
    blocks = _blocks(n, n_folds)
    splits = []
    for i, block in enumerate(blocks):
        test_pos = sorted(positions[p] for p in block)
        test_set = set(test_pos)
        train_pos = [p for p in range(n) if p not in test_set]
        splits.append(
            {
                "split_label": f"fold-{i}",
                "train_pos": train_pos,
                "test_pos": test_pos,
                "purged_pos": [],
                "embargoed_pos": [],
                "purge_reasons": {},
                "embargo_windows": [],
                "method_note": "reference only — no purging; overlapping-label leakage is expected",
            }
        )
    return splits


def walk_forward(samples: Sequence[Sample], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Chronological walk-forward: expanding (default) or rolling training window.

    ``min_train_size`` and ``test_size`` are sample counts on the
    time-sorted axis; optional ``step_size`` defaults to ``test_size``;
    ``window="rolling"`` keeps only the trailing ``rolling_size`` samples.
    No sample after a test block's start ever enters that block's training set.

    Chronology alone does not remove label-horizon leakage: the last training
    samples' information intervals can extend INTO the test window.  Boundary
    purging is therefore ON by default (``"purge": false`` disables it for
    educational comparison — those folds will audit as invalid).  A configured
    embargo is applied the same way as for purged K-fold.
    """
    n = len(samples)
    min_train = config.get("min_train_size", max(MIN_FOLDS, n // 5))
    test_size = config.get("test_size", max(1, n // 10))
    step = config.get("step_size", test_size)
    window = config.get("window", "expanding")
    rolling_size = config.get("rolling_size", min_train)
    for name, v in (("min_train_size", min_train), ("test_size", test_size), ("step_size", step)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise SplitConfigError(f"{name} must be a positive integer")
    if window not in ("expanding", "rolling"):
        raise SplitConfigError("window must be 'expanding' or 'rolling'")
    if isinstance(rolling_size, bool) or not isinstance(rolling_size, int) or rolling_size < 1:
        raise SplitConfigError("rolling_size must be a positive integer")
    if min_train + test_size > n:
        raise SplitConfigError("min_train_size + test_size exceeds the sample count")

    do_purge = bool(config.get("purge", True))
    delta = resolve_embargo_delta(samples, config.get("embargo"))

    splits = []
    start = min_train
    i = 0
    while start + 1 <= n and len(splits) < MAX_WALK_FORWARD_FOLDS:
        test_pos = list(range(start, min(start + test_size, n)))
        if not test_pos:
            break
        train_lo = 0 if window == "expanding" else max(0, start - rolling_size)
        train_pos = list(range(train_lo, start))
        purged: List[int] = []
        embargoed: List[int] = []
        reasons: Dict[str, str] = {}
        windows: List[Dict[str, str]] = []
        if do_purge:
            train_pos, purged, reasons = purge_positions(samples, train_pos, test_pos)
            train_pos, embargoed, windows = apply_embargo_positions(
                samples, train_pos, test_pos, delta
            )
        splits.append(
            {
                "split_label": f"wf-{i}",
                "train_pos": train_pos,
                "test_pos": test_pos,
                "purged_pos": purged,
                "embargoed_pos": embargoed,
                "purge_reasons": reasons,
                "embargo_windows": windows,
                "method_note": f"{window} window"
                + ("" if do_purge else " — boundary purge disabled (reference)"),
            }
        )
        start += step
        i += 1
    if not splits:
        raise SplitConfigError("walk-forward configuration produced no folds")
    return splits


def purged_kfold(samples: Sequence[Sample], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Purged K-fold: contiguous time-ordered test blocks; interval purge +
    configured embargo on the complement."""
    n = len(samples)
    n_folds = _validate_folds(n, config.get("n_folds", 5))
    delta = resolve_embargo_delta(samples, config.get("embargo"))
    splits = []
    for i, test_pos in enumerate(_blocks(n, n_folds)):
        test_set = set(test_pos)
        train_candidates = [p for p in range(n) if p not in test_set]
        kept, purged, reasons = purge_positions(samples, train_candidates, test_pos)
        kept, embargoed, windows = apply_embargo_positions(samples, kept, test_pos, delta)
        splits.append(
            {
                "split_label": f"purged-fold-{i}",
                "train_pos": kept,
                "test_pos": list(test_pos),
                "purged_pos": purged,
                "embargoed_pos": embargoed,
                "purge_reasons": reasons,
                "embargo_windows": windows,
                "method_note": "interval purge + embargo",
            }
        )
    return splits


def cpcv(samples: Sequence[Sample], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Combinatorial Purged CV: N contiguous time-ordered groups, all C(N,k)
    deterministic test-group combinations, purge + embargo per combination.

    Conservative v1 limits: ``2 <= N <= 12``, ``1 <= k < N``, and
    ``C(N,k) <= 100`` — configurations beyond these raise a clear error.
    """
    n = len(samples)
    N = config.get("n_groups", 6)
    k = config.get("test_groups", 2)
    for name, v in (("n_groups", N), ("test_groups", k)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise SplitConfigError(f"{name} must be an integer")
    if N < MIN_FOLDS or N > MAX_CPCV_GROUPS:
        raise SplitConfigError(f"n_groups must be between {MIN_FOLDS} and {MAX_CPCV_GROUPS}")
    if k < 1 or k >= N:
        raise SplitConfigError("test_groups must satisfy 1 <= test_groups < n_groups")
    if N > n:
        raise SplitConfigError("n_groups cannot exceed the number of samples")
    combo_count = math.comb(N, k)
    if combo_count > MAX_CPCV_COMBINATIONS:
        raise SplitConfigError(
            f"C({N},{k}) = {combo_count} combinations exceeds the v1 limit of "
            f"{MAX_CPCV_COMBINATIONS}; reduce n_groups or test_groups"
        )
    groups = _blocks(n, N)
    delta = resolve_embargo_delta(samples, config.get("embargo"))
    splits = []
    for combo in combinations(range(N), k):  # itertools order is deterministic
        test_pos = sorted(p for g in combo for p in groups[g])
        test_set = set(test_pos)
        train_candidates = [p for p in range(n) if p not in test_set]
        kept, purged, reasons = purge_positions(samples, train_candidates, test_pos)
        kept, embargoed, windows = apply_embargo_positions(samples, kept, test_pos, delta)
        label = "cpcv-" + "-".join(f"g{g}" for g in combo)
        splits.append(
            {
                "split_label": label,
                "train_pos": kept,
                "test_pos": test_pos,
                "purged_pos": purged,
                "embargoed_pos": embargoed,
                "purge_reasons": reasons,
                "embargo_windows": windows,
                "method_note": f"test groups {list(combo)} of {N}",
                "test_group_indices": list(combo),
            }
        )
    return splits


SPLITTERS = {
    "standard_kfold": standard_kfold,
    "walk_forward": walk_forward,
    "purged_kfold": purged_kfold,
    "cpcv": cpcv,
}


def validate_config(method: str, samples: Sequence[Sample], config: Dict[str, Any]) -> None:
    """Cheap eager validation of a split configuration (no split construction).

    Mirrors the guard clauses at the top of each splitter so an invalid
    configuration is rejected with a 422 at run **creation**, not only as a
    failed execution.  Execution re-validates regardless.
    """
    n = len(samples)
    if method == "standard_kfold":
        _validate_folds(n, config.get("n_folds", 5))
        if config.get("shuffle"):
            seed = config.get("random_seed")
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise SplitConfigError("shuffled K-fold requires an explicit integer random_seed")
    elif method == "walk_forward":
        min_train = config.get("min_train_size", max(MIN_FOLDS, n // 5))
        test_size = config.get("test_size", max(1, n // 10))
        step = config.get("step_size", test_size)
        for name, v in (("min_train_size", min_train), ("test_size", test_size), ("step_size", step)):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise SplitConfigError(f"{name} must be a positive integer")
        if config.get("window", "expanding") not in ("expanding", "rolling"):
            raise SplitConfigError("window must be 'expanding' or 'rolling'")
        if min_train + test_size > n:
            raise SplitConfigError("min_train_size + test_size exceeds the sample count")
        resolve_embargo_delta(samples, config.get("embargo"))
    elif method == "purged_kfold":
        _validate_folds(n, config.get("n_folds", 5))
        resolve_embargo_delta(samples, config.get("embargo"))
    elif method == "cpcv":
        N, k = config.get("n_groups", 6), config.get("test_groups", 2)
        for name, v in (("n_groups", N), ("test_groups", k)):
            if isinstance(v, bool) or not isinstance(v, int):
                raise SplitConfigError(f"{name} must be an integer")
        if N < MIN_FOLDS or N > MAX_CPCV_GROUPS:
            raise SplitConfigError(f"n_groups must be between {MIN_FOLDS} and {MAX_CPCV_GROUPS}")
        if k < 1 or k >= N:
            raise SplitConfigError("test_groups must satisfy 1 <= test_groups < n_groups")
        if N > n:
            raise SplitConfigError("n_groups cannot exceed the number of samples")
        combo_count = math.comb(N, k)
        if combo_count > MAX_CPCV_COMBINATIONS:
            raise SplitConfigError(
                f"C({N},{k}) = {combo_count} combinations exceeds the v1 limit of "
                f"{MAX_CPCV_COMBINATIONS}; reduce n_groups or test_groups"
            )
        resolve_embargo_delta(samples, config.get("embargo"))
    else:
        raise SplitConfigError(f"unknown method {method!r}")


# ---------------------------------------------------------------------------
# Leakage audit
# ---------------------------------------------------------------------------


def _time_range(samples: Sequence[Sample], positions: Sequence[int], field: str) -> Optional[Dict[str, str]]:
    if not positions:
        return None
    values = [samples[p][field] for p in positions]
    return {"min": min(values).isoformat(), "max": max(values).isoformat()}


def audit_split(
    samples: Sequence[Sample], split: Dict[str, Any], method: str
) -> Dict[str, Any]:
    """Recompute leakage diagnostics from scratch for one split.

    The critical invariant: after purge + embargo, **no retained training
    interval may overlap any test interval**.  Any remaining overlap marks the
    split ``invalid`` — expected for the standard K-fold reference, fatal for
    purged methods.

    A required set being empty is also fatal: an all-purged training set has no
    remaining overlap simply because nothing is left to overlap, so emptiness is
    checked explicitly rather than being read as "leakage-clean".
    """
    train_pos, test_pos = split["train_pos"], split["test_pos"]
    remaining_overlaps: List[Dict[str, str]] = []
    for p in train_pos:
        ts, te = samples[p]["pred_dt"], samples[p]["eval_dt"]
        for q in test_pos:
            if intervals_overlap(ts, te, samples[q]["pred_dt"], samples[q]["eval_dt"]):
                remaining_overlaps.append(
                    {"train": samples[p]["sample_id"], "test": samples[q]["sample_id"]}
                )
                break

    assigned = set()
    duplicates = 0
    for bucket in ("train_pos", "test_pos", "purged_pos", "embargoed_pos"):
        for p in split[bucket]:
            if p in assigned:
                duplicates += 1
            assigned.add(p)
    unassigned = len(samples) - len(assigned)

    chronology_violations = 0
    if method == "walk_forward" and test_pos:
        first_test = min(samples[q]["pred_dt"] for q in test_pos)
        chronology_violations = sum(
            1 for p in train_pos if samples[p]["pred_dt"] >= first_test
        )

    labels = [samples[p]["label"] for p in test_pos if samples[p]["label"] is not None]
    label_balance: Optional[Dict[str, int]] = None
    if labels:
        label_balance = {}
        for v in labels:
            key = str(int(v)) if float(v).is_integer() else str(v)
            label_balance[key] = label_balance.get(key, 0) + 1

    spans = [
        (samples[p]["eval_dt"] - samples[p]["pred_dt"]).total_seconds() / 86_400.0
        for p in list(train_pos) + list(test_pos)
    ]
    span_stats = (
        {
            "min_days": round(min(spans), 6),
            "max_days": round(max(spans), 6),
            "mean_days": round(sum(spans) / len(spans), 6),
        }
        if spans
        else None
    )

    groups = {samples[p]["group"] for p in test_pos if samples[p]["group"]}

    # A degenerate split proves nothing: with no retained training samples the
    # overlap scan trivially finds nothing, so emptiness must never read as
    # leakage-clean.
    empty_train = not train_pos
    empty_test = not test_pos

    valid = (
        not remaining_overlaps
        and duplicates == 0
        and chronology_violations == 0
        and not empty_train
        and not empty_test
    )
    return {
        "train_count": len(train_pos),
        "test_count": len(test_pos),
        "empty_train": empty_train,
        "empty_test": empty_test,
        "purged_count": len(split["purged_pos"]),
        "embargoed_count": len(split["embargoed_pos"]),
        "train_prediction_range": _time_range(samples, train_pos, "pred_dt"),
        "train_evaluation_range": _time_range(samples, train_pos, "eval_dt"),
        "test_prediction_range": _time_range(samples, test_pos, "pred_dt"),
        "test_evaluation_range": _time_range(samples, test_pos, "eval_dt"),
        "remaining_overlap_count": len(remaining_overlaps),
        "remaining_overlap_examples": remaining_overlaps[:10],
        "chronological_violations": chronology_violations,
        "duplicate_assignments": duplicates,
        "unassigned_samples": unassigned,
        "test_label_balance": label_balance,
        "test_group_coverage": sorted(groups),
        "interval_span_stats": span_stats,
        "valid": valid,
    }


__all__ = [
    "MIN_FOLDS",
    "MAX_FOLDS",
    "MAX_CPCV_GROUPS",
    "MAX_CPCV_COMBINATIONS",
    "MAX_EMBARGO_FRACTION",
    "SplitConfigError",
    "SPLITTERS",
    "standard_kfold",
    "walk_forward",
    "purged_kfold",
    "cpcv",
    "purge_positions",
    "apply_embargo_positions",
    "resolve_embargo_delta",
    "audit_split",
]
