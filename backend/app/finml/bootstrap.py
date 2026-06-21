"""
Sequential bootstrap (López de Prado, AFML ch. 4).

Overlapping financial labels are not independent, so a standard (uniform)
bootstrap repeatedly samples highly dependent labels.  The **sequential
bootstrap** draws events one at a time with probability proportional to the
*marginal average uniqueness* they would add, producing a less-overlapping
(higher-uniqueness) sample.

Reuses the existing AFML synthetic path + triple-barrier labels + the inclusive
``[start, end]`` interval convention.  Educational methodology only — this helps
reduce sample dependence but does **not** guarantee a better model or valid
research.  Not investment advice.
"""

from __future__ import annotations

import math
from numbers import Integral
from typing import List, Optional, Tuple

import numpy as np

from app.finml.cusum import cusum_events
from app.finml.labeling import triple_barrier_labels
from app.finml.orchestrator import FinmlInputError, validate_finml_inputs
from app.finml.sample_data import generate_synthetic_path

_MIN_TRIALS = 1
_MAX_TRIALS = 1000
_EVENT_CAP = 2000
_MAX_SAMPLE = 2000
_MAX_SEQUENTIAL_WORK = 50_000_000
_MAX_RANDOM_WORK = 50_000_000


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


# ---------------------------------------------------------------------------
# Indicator matrix + uniqueness
# ---------------------------------------------------------------------------


def build_indicator_matrix(intervals: List[dict], n_bars: int) -> np.ndarray:
    """Return a bar-by-event 0/1 matrix using inclusive intervals.

    Columns preserve the input interval order, so column ``j`` corresponds to
    ``intervals[j]["event_id"]``. Invalid, reversed, duplicate, or out-of-range
    intervals are rejected rather than silently clipped.
    """
    if not isinstance(n_bars, Integral) or isinstance(n_bars, bool) or int(n_bars) < 1:
        raise FinmlInputError("n_bars must be a positive integer.")
    n_bars = int(n_bars)
    n_events = len(intervals)
    ind = np.zeros((n_bars, n_events), dtype=np.uint8)
    seen_event_ids = set()
    for j, iv in enumerate(intervals):
        try:
            event_id, start, end = iv["event_id"], iv["start"], iv["end"]
        except (KeyError, TypeError) as exc:
            raise FinmlInputError(f"Indicator interval {j} is missing event_id, start, or end.") from exc
        if any(isinstance(value, bool) or not isinstance(value, Integral) for value in (event_id, start, end)):
            raise FinmlInputError(f"Indicator interval {j} must contain integer fields.")
        event_id, start, end = int(event_id), int(start), int(end)
        if event_id < 0 or event_id in seen_event_ids:
            raise FinmlInputError("Indicator event_id values must be unique non-negative integers.")
        if start < 0 or end < start or end >= n_bars:
            raise FinmlInputError("Indicator intervals must satisfy 0 <= start <= end < n_bars.")
        seen_event_ids.add(event_id)
        ind[start : end + 1, j] = 1
    return ind


def _validate_indicator(indicator: np.ndarray, require_events: bool = True) -> None:
    if not isinstance(indicator, np.ndarray) or indicator.ndim != 2 or indicator.shape[0] < 1:
        raise FinmlInputError("indicator must be a two-dimensional matrix with at least one row.")
    if require_events and indicator.shape[1] < 1:
        raise FinmlInputError("indicator must contain at least one event column.")
    if not np.all(np.isfinite(indicator)) or not np.all((indicator == 0) | (indicator == 1)):
        raise FinmlInputError("indicator must contain only finite 0/1 values.")
    if require_events and np.any(indicator.sum(axis=0) <= 0):
        raise FinmlInputError("Every indicator column must contain at least one active observation.")


def _validate_positions(indicator: np.ndarray, positions: List[int]) -> List[int]:
    clean: List[int] = []
    for position in positions:
        if isinstance(position, bool) or not isinstance(position, Integral):
            raise FinmlInputError("Selected event positions must be integers.")
        value = int(position)
        if value < 0 or value >= indicator.shape[1]:
            raise FinmlInputError("Selected event position is outside the indicator matrix.")
        clean.append(value)
    return clean


def _active_rows(indicator: np.ndarray) -> List[np.ndarray]:
    return [np.where(indicator[:, j] > 0)[0] for j in range(indicator.shape[1])]


def event_uniqueness(indicator: np.ndarray, positions: List[int]) -> List[float]:
    """Return one uniqueness value per selected event occurrence.

    Concurrency at each bar = number of selected events active there; each
    selected occurrence's uniqueness is the mean of ``1/concurrency`` over its
    active bars. Duplicate positions are retained for with-replacement samples.
    """
    _validate_indicator(indicator, require_events=bool(positions))
    if not positions:
        return []
    positions = _validate_positions(indicator, positions)
    selected = indicator[:, positions].astype(float)
    concurrency = selected.sum(axis=1)
    inverse = np.zeros_like(concurrency)
    active_rows = concurrency > 0
    inverse[active_rows] = 1.0 / concurrency[active_rows]
    active_counts = selected.sum(axis=0)
    values = (selected.T @ inverse) / active_counts
    return [float(value) for value in values]


def sample_average_uniqueness(indicator: np.ndarray, positions: List[int]) -> float:
    """Average event uniqueness for a selected (possibly repeated) sample."""
    values = event_uniqueness(indicator, positions)
    return float(np.mean(values)) if values else 1.0


def _avg_uniqueness_running(selected: List[int], active_rows: List[np.ndarray], c: np.ndarray) -> float:
    """Average uniqueness of the selected-so-far sample given running concurrency ``c``."""
    if not selected:
        return 1.0
    uniq: List[float] = []
    for j in selected:
        rows = active_rows[j]
        cc = c[rows]
        cc = cc[cc > 0]
        uniq.append(float(np.mean(1.0 / cc)) if cc.size else 1.0)
    return float(np.mean(uniq))


def _candidate_probabilities_from_concurrency(
    active_rows: List[np.ndarray], concurrency: np.ndarray, candidates: List[int]
) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.empty(len(candidates), dtype=float)
    for index, candidate in enumerate(candidates):
        rows = active_rows[candidate]
        scores[index] = float(np.mean(1.0 / (concurrency[rows] + 1.0)))
    scores = np.where(np.isfinite(scores) & (scores >= 0.0), scores, 0.0)
    total = float(scores.sum())
    probabilities = (
        scores / total
        if math.isfinite(total) and total > 0.0
        else np.full(len(candidates), 1.0 / len(candidates), dtype=float)
    )
    return scores, probabilities


def candidate_probabilities(
    indicator: np.ndarray, selected: List[int], candidates: Optional[List[int]] = None
) -> Tuple[List[float], List[float]]:
    """Return canonical candidate uniqueness scores and normalized probabilities.

    A uniform probability fallback is used if all candidate scores become
    degenerate; valid non-empty indicator columns normally make every score
    strictly positive.
    """
    _validate_indicator(indicator)
    selected = _validate_positions(indicator, selected)
    candidate_positions = (
        list(range(indicator.shape[1])) if candidates is None else _validate_positions(indicator, candidates)
    )
    if not candidate_positions:
        raise FinmlInputError("At least one candidate event is required.")
    concurrency = (
        indicator[:, selected].sum(axis=1).astype(float)
        if selected
        else np.zeros(indicator.shape[0], dtype=float)
    )
    scores, probabilities = _candidate_probabilities_from_concurrency(
        _active_rows(indicator), concurrency, candidate_positions
    )
    return scores.tolist(), probabilities.tolist()


# ---------------------------------------------------------------------------
# Random baseline + sequential bootstrap
# ---------------------------------------------------------------------------


def random_bootstrap(
    indicator: np.ndarray,
    n_events: int,
    sample_size: int,
    n_trials: int,
    rng: np.random.Generator,
    with_replacement: bool,
) -> dict:
    """Uniform-sampling baseline: average uniqueness over ``n_trials`` random samples."""
    _validate_indicator(indicator)
    if n_events != indicator.shape[1]:
        raise FinmlInputError("n_events must match the indicator matrix column count.")
    validate_bootstrap_inputs(sample_size, n_trials)
    if not isinstance(with_replacement, bool):
        raise FinmlInputError("with_replacement must be boolean.")
    if not with_replacement and sample_size > n_events:
        raise FinmlInputError("sample_size cannot exceed n_events without replacement.")
    vals = np.empty(n_trials)
    for t in range(n_trials):
        if with_replacement:
            positions = rng.integers(0, n_events, size=sample_size).tolist()
        else:
            positions = rng.choice(n_events, size=sample_size, replace=False).tolist()
        vals[t] = sample_average_uniqueness(indicator, positions)
    return {
        "values": vals,
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
        "p25": float(np.percentile(vals, 25)),
        "p75": float(np.percentile(vals, 75)),
        "n_trials": int(n_trials),
    }


def sequential_bootstrap(
    indicator: np.ndarray,
    n_events: int,
    sample_size: int,
    rng: np.random.Generator,
    with_replacement: bool,
) -> Tuple[List[int], List[float], List[float]]:
    """Draw events with probability ∝ marginal average uniqueness.

    Returns ``(selected_positions, selection_probabilities, uniqueness_path)``.
    """
    _validate_indicator(indicator)
    if n_events != indicator.shape[1]:
        raise FinmlInputError("n_events must match the indicator matrix column count.")
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1 or sample_size > _MAX_SAMPLE:
        raise FinmlInputError(f"sample_size must be an integer between 1 and {_MAX_SAMPLE}.")
    if not isinstance(with_replacement, bool):
        raise FinmlInputError("with_replacement must be boolean.")
    if not with_replacement and sample_size > n_events:
        raise FinmlInputError("sample_size cannot exceed n_events without replacement.")

    active_rows = _active_rows(indicator)
    c = np.zeros(indicator.shape[0])
    selected: List[int] = []
    probs: List[float] = []
    path: List[float] = []
    available = list(range(n_events))

    for _ in range(sample_size):
        candidates = list(range(n_events)) if with_replacement else available
        if not candidates:
            break
        _scores, delta = _candidate_probabilities_from_concurrency(active_rows, c, candidates)
        choice = int(rng.choice(len(candidates), p=delta))
        j = candidates[choice]
        selected.append(j)
        probs.append(float(delta[choice]))
        c[active_rows[j]] += 1.0
        if not with_replacement:
            available.remove(j)
        path.append(_avg_uniqueness_running(selected, active_rows, c))

    return selected, probs, path


# ---------------------------------------------------------------------------
# Validation + orchestrator
# ---------------------------------------------------------------------------


def validate_bootstrap_inputs(sample_size: int, random_trials: int) -> None:
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1 or sample_size > _MAX_SAMPLE:
        raise FinmlInputError(f"sample_size must be an integer between 1 and {_MAX_SAMPLE}.")
    if not isinstance(random_trials, int) or isinstance(random_trials, bool) or random_trials < _MIN_TRIALS or random_trials > _MAX_TRIALS:
        raise FinmlInputError(f"random_trials must be an integer between {_MIN_TRIALS} and {_MAX_TRIALS}.")


def run_sequential_bootstrap_demo(
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
    sample_size: int = 25,
    random_trials: int = 200,
    with_replacement: bool = False,
) -> dict:
    """Run the sequential vs random bootstrap demo on synthetic labels (JSON-ready)."""
    validate_finml_inputs(
        n_days, start_price, drift, volatility, seed, cusum_threshold, threshold_mode,
        volatility_window, profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )
    validate_bootstrap_inputs(sample_size, random_trials)

    path = generate_synthetic_path(
        n_days, start_price, drift, volatility, seed if seed is not None else 42, volatility_window
    )
    dates = path["dates"]
    raw_events = cusum_events(path["returns"], cusum_threshold, threshold_mode, path["rolling_vol"])
    labels = triple_barrier_labels(
        path["close"], [e["index"] for e in raw_events], path["rolling_vol"],
        profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )
    generated_event_count = len(labels)
    if generated_event_count > _EVENT_CAP:
        labels = labels[:_EVENT_CAP]
    n_events = len(labels)

    if n_events < 1:
        raise FinmlInputError(
            "Not enough labeled events for the bootstrap. Lower the CUSUM threshold or increase n_days."
        )
    if not with_replacement and sample_size > n_events:
        raise FinmlInputError(
            "Not enough labeled events for the requested bootstrap sample size (without replacement). "
            "Lower sample_size, enable replacement, or generate more events."
        )

    sequential_work = n_days * n_events * sample_size
    random_work = n_days * sample_size * random_trials
    if sequential_work > _MAX_SEQUENTIAL_WORK or random_work > _MAX_RANDOM_WORK:
        raise FinmlInputError(
            "Requested bootstrap workload is too large for the interactive demo. Reduce n_days, "
            "sample_size, random_trials, or the number of CUSUM events."
        )

    intervals = [{"event_id": l["event_id"], "start": l["start_index"], "end": l["end_index"]} for l in labels]
    indicator = build_indicator_matrix(intervals, len(dates))

    rng_seq = np.random.default_rng(seed if seed is not None else 42)
    rng_rand = np.random.default_rng((seed if seed is not None else 42) + 10_007)

    # First sequential draw is the representative sample shown in the table/path.
    selected, probs, uniq_path = sequential_bootstrap(indicator, n_events, sample_size, rng_seq, with_replacement)
    seq_avg = sample_average_uniqueness(indicator, selected)

    rand = random_bootstrap(indicator, n_events, sample_size, random_trials, rng_rand, with_replacement)
    improvement = seq_avg - rand["mean"]

    selected_events = [
        {
            "draw_order": k + 1,
            "event_id": labels[pos]["event_id"],
            "label": labels[pos]["label"],
            "start_date": dates[labels[pos]["start_index"]],
            "end_date": dates[labels[pos]["end_index"]],
            "start_index": labels[pos]["start_index"],
            "end_index": labels[pos]["end_index"],
            "realized_return": _clean(labels[pos]["realized_return"]),
            "average_uniqueness_after_draw": _clean(uniq_path[k]),
            "selection_probability": _clean(probs[k]),
        }
        for k, pos in enumerate(selected)
    ]

    note = (
        "This seeded sequential draw had higher uniqueness than the random-bootstrap mean."
        if improvement > 0
        else "This seeded sequential draw did not exceed the random-bootstrap mean; results vary by seed and overlap."
    )

    warnings = [
        "Synthetic demo data — not live market data.",
        "Sequential bootstrap reduces sample dependence (overlap) but does NOT guarantee a better "
        "model or valid research by itself. This is methodology only — no features, no model, no "
        "out-of-sample performance. Meta-labeling, fractional differentiation, and CPCV are planned.",
        f"Comparison uses one seeded sequential sample against the mean of {random_trials} uniform "
        "random-bootstrap samples; it is a sampling diagnostic, not a performance estimate.",
    ]
    if generated_event_count > _EVENT_CAP:
        warnings.append(
            f"The bootstrap demo is capped at the first {_EVENT_CAP} time-ordered labels; "
            f"{generated_event_count - _EVENT_CAP} later label(s) were omitted."
        )
    if with_replacement:
        warnings.append("Sampling with replacement: an event may be drawn more than once.")
    if threshold_mode == "vol_scaled":
        warnings.append(
            "Vol-scaled CUSUM mode interprets cusum_threshold as a multiplier of rolling volatility, "
            "not as a fixed percentage return."
        )

    return {
        "summary": {
            "n_events": int(n_events),
            "sample_size": int(sample_size),
            "with_replacement": bool(with_replacement),
            "sequential_average_uniqueness": _clean(seq_avg),
            "random_average_uniqueness": _clean(rand["mean"]),
            "improvement_vs_random": _clean(improvement),
            "overlap_reduction_note": note,
        },
        "selected_events": selected_events,
        "random_baseline": {
            "mean": _clean(rand["mean"]),
            "median": _clean(rand["median"]),
            "min": _clean(rand["min"]),
            "max": _clean(rand["max"]),
            "p25": _clean(rand["p25"]),
            "p75": _clean(rand["p75"]),
            "n_trials": rand["n_trials"],
        },
        "uniqueness_path": [
            {"draw": k + 1, "sequential_uniqueness": _clean(u)} for k, u in enumerate(uniq_path)
        ],
        "warnings": warnings,
    }
