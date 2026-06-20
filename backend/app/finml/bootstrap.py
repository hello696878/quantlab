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


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


# ---------------------------------------------------------------------------
# Indicator matrix + uniqueness
# ---------------------------------------------------------------------------


def build_indicator_matrix(intervals: List[dict], n_bars: int) -> np.ndarray:
    """``(n_bars × n_events)`` 0/1 matrix; column i is 1 where event i is active."""
    n_events = len(intervals)
    ind = np.zeros((n_bars, n_events), dtype=np.int16)
    for j, iv in enumerate(intervals):
        s = max(0, int(iv["start"]))
        e = min(n_bars - 1, int(iv["end"]))
        if e >= s:
            ind[s : e + 1, j] = 1
    return ind


def _active_rows(indicator: np.ndarray) -> List[np.ndarray]:
    return [np.where(indicator[:, j] > 0)[0] for j in range(indicator.shape[1])]


def sample_average_uniqueness(indicator: np.ndarray, positions: List[int]) -> float:
    """Average uniqueness of a (multiset) sample of event columns.

    Concurrency at each bar = number of selected events active there; each
    selected event's uniqueness is the mean of ``1/concurrency`` over its active
    bars; the sample value is the mean across the selected events.
    """
    if not positions:
        return 1.0
    c = indicator[:, positions].sum(axis=1).astype(float)
    uniq: List[float] = []
    for col in positions:
        active = indicator[:, col] > 0
        cc = c[active]
        cc = cc[cc > 0]
        uniq.append(float(np.mean(1.0 / cc)) if cc.size else 1.0)
    return float(np.mean(uniq)) if uniq else 1.0


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
        avg_u = np.empty(len(candidates))
        for idx, j in enumerate(candidates):
            rows = active_rows[j]
            avg_u[idx] = float(np.mean(1.0 / (c[rows] + 1.0))) if rows.size else 1.0
        total = float(avg_u.sum())
        delta = avg_u / total if total > 0 else np.full(len(candidates), 1.0 / len(candidates))
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
    if len(labels) > _EVENT_CAP:
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

    intervals = [{"event_id": l["event_id"], "start": l["start_index"], "end": l["end_index"]} for l in labels]
    indicator = build_indicator_matrix(intervals, len(dates))

    rng_seq = np.random.default_rng(seed if seed is not None else 42)
    rng_rand = np.random.default_rng((seed if seed is not None else 42) + 10_007)

    # First sequential draw is the representative sample shown in the table/path.
    selected, probs, uniq_path = sequential_bootstrap(indicator, n_events, sample_size, rng_seq, with_replacement)
    seq_sample_uniq = [sample_average_uniqueness(indicator, selected)]
    # For a stable (textbook) comparison, average uniqueness over several sequential
    # draws — but only when cheap (the inner loop is O(sample_size · n_events)).
    extra_trials = 0
    if n_events * sample_size <= 20_000:
        extra_trials = min(random_trials, 30) - 1
    for _ in range(max(0, extra_trials)):
        sel, _p, _path = sequential_bootstrap(indicator, n_events, sample_size, rng_seq, with_replacement)
        seq_sample_uniq.append(sample_average_uniqueness(indicator, sel))
    seq_avg = float(np.mean(seq_sample_uniq))

    rand = random_bootstrap(indicator, n_events, sample_size, random_trials, rng_rand, with_replacement)
    improvement = seq_avg - rand["mean"]

    selected_events = [
        {
            "draw_order": k,
            "event_id": labels[pos]["event_id"],
            "label": labels[pos]["label"],
            "start_date": dates[labels[pos]["start_index"]],
            "end_date": dates[labels[pos]["end_index"]],
            "realized_return": _clean(labels[pos]["realized_return"]),
            "average_uniqueness_after_draw": _clean(uniq_path[k]),
            "selection_probability": _clean(probs[k]),
        }
        for k, pos in enumerate(selected)
    ]

    note = (
        "Sequential bootstrap selected a less-overlapping event sample in this synthetic demo."
        if improvement > 0
        else "Sequential and random bootstrap produced similar uniqueness on this synthetic sample."
    )

    warnings = [
        "Synthetic demo data — not live market data.",
        "Sequential bootstrap reduces sample dependence (overlap) but does NOT guarantee a better "
        "model or valid research by itself. This is methodology only — no features, no model, no "
        "out-of-sample performance. Meta-labeling, fractional differentiation, and CPCV are planned.",
    ]
    if with_replacement:
        warnings.append("Sampling with replacement: an event may be drawn more than once.")

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
            {"draw": k, "sequential_uniqueness": _clean(u)} for k, u in enumerate(uniq_path)
        ],
        "warnings": warnings,
    }
