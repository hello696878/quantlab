"""
Long/short bucket selection + dollar-neutral weighting for the scanner engine.

Convention (v1): **gross exposure target = 1.0**, so the long basket sums to
``+gross/2`` (e.g. +0.5) and the short basket to ``−gross/2`` (e.g. −0.5); net
exposure is ~0 (dollar-neutral) and gross exposure (sum of |weights|) = ``gross``.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def dollar_neutral_weights(
    scores_row: np.ndarray,
    eligible_mask: np.ndarray,
    long_quantile: float,
    short_quantile: float,
    gross_exposure: float,
) -> Tuple[np.ndarray, int, int, bool]:
    """Equal-weight, dollar-neutral long/short weights for one date.

    Returns ``(weights, n_long, n_short, ok)``. ``ok`` is False (and weights are
    all zero) when there are too few eligible names or every score is equal.
    """
    n = scores_row.shape[0]
    weights = np.zeros(n)
    elig_idx = np.where(eligible_mask)[0]
    n_elig = int(elig_idx.size)
    if n_elig < 2:
        return weights, 0, 0, False

    elig_scores = scores_row[elig_idx]
    spread = float(np.nanmax(elig_scores) - np.nanmin(elig_scores))
    if not np.isfinite(spread) or spread <= 1e-12:
        # All eligible scores equal → no cross-sectional information; zero weights.
        return weights, 0, 0, False

    n_long = max(1, int(round(long_quantile * n_elig)))
    n_short = max(1, int(round(short_quantile * n_elig)))
    if n_long + n_short > n_elig:
        return weights, 0, 0, False

    order = elig_idx[np.argsort(-elig_scores, kind="stable")]  # highest score first
    longs = order[:n_long]
    shorts = order[-n_short:]

    weights[longs] = (gross_exposure / 2.0) / n_long
    weights[shorts] = -(gross_exposure / 2.0) / n_short
    return weights, n_long, n_short, True
