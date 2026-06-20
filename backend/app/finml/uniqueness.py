"""
Sample concurrency and uniqueness weights (López de Prado, AFML ch. 4).

Overlapping labels are not independent.  Concurrency at a bar = how many label
intervals are active there; an event's *average uniqueness* is the mean of
``1/concurrency`` over its interval; the sample weight is that uniqueness
(normalized so the mean weight is 1).

Interval convention: **inclusive** ``[start_index, end_index]``.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def compute_concurrency(n_bars: int, intervals: List[Tuple[int, int]]) -> np.ndarray:
    """Number of active label intervals at each bar (inclusive intervals)."""
    conc = np.zeros(n_bars)
    for s, e in intervals:
        s = max(0, int(s))
        e = min(n_bars - 1, int(e))
        if n_bars <= 0 or e < s:
            continue
        conc[s : e + 1] += 1.0
    return conc


def average_uniqueness(intervals: List[Tuple[int, int]], concurrency: np.ndarray) -> List[float]:
    """Mean of ``1/concurrency`` over each event's interval."""
    out: List[float] = []
    for s, e in intervals:
        n = int(concurrency.shape[0])
        s = max(0, int(s))
        e = min(n - 1, int(e))
        if n <= 0 or e < s:
            out.append(1.0)
            continue
        window = concurrency[s : e + 1]
        safe = window[window > 0]
        out.append(float(np.mean(1.0 / safe)) if safe.size else 1.0)
    return out


def sample_weights(uniqueness: List[float]) -> List[float]:
    """Normalize uniqueness so the mean weight is 1 (raw uniqueness if mean ≤ 0)."""
    arr = np.asarray(uniqueness, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.0)
    mean = float(np.mean(arr)) if arr.size else 0.0
    if mean <= 0:
        return [float(x) for x in arr]
    return [float(x / mean) for x in arr]
