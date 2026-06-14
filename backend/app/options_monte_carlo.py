"""
Monte Carlo option pricing v1 — risk-neutral Geometric Brownian Motion path
simulation for European, arithmetic-average **Asian**, and simple **barrier**
options, with a reproducible seed, standard error, and a 95% confidence
interval.

Educational / illustrative only.  This is **not** a production derivatives
pricing system:

* Geometric Brownian Motion with **constant** volatility and a continuous
  dividend yield — no stochastic / local volatility, no smile, no surface.
* Barrier monitoring is **discrete** over the simulated time steps (it can
  differ from continuous monitoring), and Asian averaging is **arithmetic**
  (no closed form).
* Results depend on the random seed, the number of simulations, the number of
  time steps (for path-dependent payoffs), the volatility input, and the payoff
  definition — there is inherent Monte Carlo sampling error (reported as the
  standard error / confidence interval).

The Black-Scholes helper is reused from :mod:`app.options` for the European
reference.  All outputs are finite and rounded for JSON — never NaN/inf.  Full
simulated paths are never returned — only a small, capped ``path_preview``.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from app.options import black_scholes_price

# Per-batch element cap keeps peak memory bounded for large simulations × steps.
_MAX_BATCH_ELEMENTS = 4_000_000
# Path-preview caps — never stream all paths to the frontend.
_PREVIEW_PATHS = 12
_PREVIEW_POINTS = 150

_BARRIER_TYPES = {
    "up_and_out_call",
    "down_and_out_put",
    "up_and_in_call",
    "down_and_in_put",
}
_UP_BARRIER_TYPES = {"up_and_out_call", "up_and_in_call"}
_EUROPEAN_TYPES = {"european_call", "european_put"}
_ASIAN_TYPES = {"asian_call", "asian_put"}
_ALL_PAYOFFS = _EUROPEAN_TYPES | _ASIAN_TYPES | _BARRIER_TYPES


class MonteCarloInputError(ValueError):
    """Raised when Monte Carlo inputs are logically invalid (e.g. missing barrier)."""


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def _is_barrier(payoff_type: str) -> bool:
    return payoff_type in _BARRIER_TYPES


def validate_monte_carlo_inputs(
    payoff_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    steps: int,
    simulations: int,
    barrier: Optional[float],
) -> List[str]:
    """Numeric / combination validation beyond the schema's field ranges.

    Returns a list of (non-fatal) warnings; raises :class:`MonteCarloInputError`
    for fatal problems (unknown payoff, missing/invalid barrier).
    """
    if payoff_type not in _ALL_PAYOFFS:
        raise MonteCarloInputError(f"Unknown payoff_type '{payoff_type}'.")

    warnings: List[str] = []
    if _is_barrier(payoff_type):
        if barrier is None:
            raise MonteCarloInputError(
                "barrier_price is required for barrier payoff types."
            )
        if barrier <= 0:
            raise MonteCarloInputError("barrier_price must be positive.")
        warnings.append(
            "Barrier monitoring is discrete over simulated time steps and may "
            "differ from continuous monitoring."
        )
        if payoff_type in _UP_BARRIER_TYPES and barrier <= S:
            warnings.append(
                f"Up-barrier {barrier:g} is at or below the spot {S:g}; the path "
                "starts breached, so up-and-out payoff is ~0 (up-and-in ~vanilla)."
            )
        if payoff_type not in _UP_BARRIER_TYPES and barrier >= S:
            warnings.append(
                f"Down-barrier {barrier:g} is at or above the spot {S:g}; the path "
                "starts breached, so down-and-out payoff is ~0 (down-and-in ~vanilla)."
            )
    return warnings


def _draw_normals(
    rng: np.random.Generator, n_paths: int, steps: int, antithetic: bool
) -> np.ndarray:
    """Standard-normal increments, shape ``(n_paths, steps)``.

    With ``antithetic`` the batch is built from ``ceil(n/2)`` independent draws
    and their negatives — a variance-reduction technique.  The first ``n/2`` rows
    are always the independent draws (so a path-preview slice has no mirror twins).
    """
    if not antithetic:
        return rng.standard_normal((n_paths, steps))
    half = (n_paths + 1) // 2
    z = rng.standard_normal((half, steps))
    return np.concatenate([z, -z], axis=0)[:n_paths]


def simulate_gbm_paths(
    S: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    steps: int,
    n_paths: int,
    rng: np.random.Generator,
    antithetic: bool = False,
) -> np.ndarray:
    """Risk-neutral GBM paths, shape ``(n_paths, steps + 1)`` including ``S`` at t=0.

    ``S_{t+dt} = S_t · exp((r − q − ½σ²)dt + σ√dt · Z)``.  Caller is responsible
    for keeping ``n_paths × steps`` bounded (see :func:`_run_simulation`).
    """
    dt = T / steps
    drift = (r - q - 0.5 * sigma * sigma) * dt
    vol = sigma * math.sqrt(dt)
    z = _draw_normals(rng, n_paths, steps, antithetic)
    log_increments = drift + vol * z
    cumulative = np.cumsum(log_increments, axis=1)
    paths = np.empty((n_paths, steps + 1), dtype=float)
    paths[:, 0] = S
    paths[:, 1:] = S * np.exp(cumulative)
    return paths


def _raw_payoffs(
    payoff_type: str, paths: np.ndarray, K: float, barrier: Optional[float]
) -> np.ndarray:
    """Undiscounted payoff per path (vectorised)."""
    S_T = paths[:, -1]
    if payoff_type == "european_call":
        return np.maximum(S_T - K, 0.0)
    if payoff_type == "european_put":
        return np.maximum(K - S_T, 0.0)
    if payoff_type in _ASIAN_TYPES:
        # Arithmetic average over all path points, including the initial price.
        average = paths.mean(axis=1)
        if payoff_type == "asian_call":
            return np.maximum(average - K, 0.0)
        return np.maximum(K - average, 0.0)
    if payoff_type in _UP_BARRIER_TYPES:
        breached = paths.max(axis=1) >= barrier
        vanilla = np.maximum(S_T - K, 0.0)
        if payoff_type == "up_and_out_call":
            return np.where(breached, 0.0, vanilla)
        return np.where(breached, vanilla, 0.0)  # up_and_in_call
    # down barriers
    breached = paths.min(axis=1) <= barrier
    vanilla = np.maximum(K - S_T, 0.0)
    if payoff_type == "down_and_out_put":
        return np.where(breached, 0.0, vanilla)
    return np.where(breached, vanilla, 0.0)  # down_and_in_put


def _run_simulation(
    payoff_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    steps: int,
    simulations: int,
    seed: Optional[int],
    antithetic: bool,
    barrier: Optional[float],
) -> Tuple[np.ndarray, np.ndarray]:
    """Batched simulation → ``(discounted_payoffs, preview_paths)``.

    Paths are simulated in batches sized so each matrix stays under
    ``_MAX_BATCH_ELEMENTS`` (bounded peak memory).  The path preview is the first
    ``_PREVIEW_PATHS`` paths of the first batch (a true, reproducible subset).
    """
    rng = np.random.default_rng(seed)
    discount = math.exp(-r * T)
    discounted = np.empty(simulations, dtype=float)
    preview: Optional[np.ndarray] = None

    cols = steps + 1
    batch_size = max(1, min(simulations, _MAX_BATCH_ELEMENTS // cols))
    done = 0
    while done < simulations:
        b = min(batch_size, simulations - done)
        paths = simulate_gbm_paths(S, T, r, q, sigma, steps, b, rng, antithetic)
        discounted[done : done + b] = discount * _raw_payoffs(
            payoff_type, paths, K, barrier
        )
        if preview is None:
            preview = paths[: min(_PREVIEW_PATHS, b)].copy()
        done += b

    if preview is None:  # pragma: no cover — simulations >= 100 by schema
        preview = np.empty((0, cols))
    return discounted, preview


def summarize_monte_carlo_payoffs(discounted: np.ndarray) -> dict:
    """Price, standard error, and 95% confidence interval from discounted payoffs."""
    n = int(discounted.shape[0])
    price = float(np.mean(discounted))
    std = float(np.std(discounted, ddof=1)) if n > 1 else 0.0
    standard_error = std / math.sqrt(n) if n > 0 else 0.0
    half_width = 1.96 * standard_error
    return {
        "price": _clean(price),
        "standard_error": _clean(standard_error),
        "confidence_interval_95": {
            "lower": _clean(price - half_width),
            "upper": _clean(price + half_width),
        },
    }


def build_path_preview(
    preview_paths: np.ndarray, T: float, steps: int, max_points: int = _PREVIEW_POINTS
) -> List[dict]:
    """A small, column-downsampled set of paths for visualization (never all paths)."""
    if preview_paths is None or preview_paths.shape[0] == 0:
        return []
    cols = preview_paths.shape[1]
    dt = T / steps
    if cols <= max_points:
        indices = list(range(cols))
    else:
        indices = sorted(
            {round(i * (cols - 1) / (max_points - 1)) for i in range(max_points)}
        )
    out: List[dict] = []
    for path_id in range(preview_paths.shape[0]):
        points = [
            {"time": _clean(j * dt), "price": _clean(float(preview_paths[path_id, j]))}
            for j in indices
        ]
        out.append({"path_id": path_id, "points": points})
    return out


# Thin, named wrappers (per the design spec) — all delegate to the shared engine.


def monte_carlo_european_price(
    option_type: str, S, K, T, r, q, sigma, steps, simulations, seed, antithetic=False
) -> Tuple[np.ndarray, np.ndarray]:
    return _run_simulation(
        f"european_{option_type}", S, K, T, r, q, sigma, steps, simulations, seed, antithetic, None
    )


def monte_carlo_asian_price(
    option_type: str, S, K, T, r, q, sigma, steps, simulations, seed, antithetic=False
) -> Tuple[np.ndarray, np.ndarray]:
    return _run_simulation(
        f"asian_{option_type}", S, K, T, r, q, sigma, steps, simulations, seed, antithetic, None
    )


def monte_carlo_barrier_price(
    payoff_type: str, S, K, T, r, q, sigma, steps, simulations, seed, barrier, antithetic=False
) -> Tuple[np.ndarray, np.ndarray]:
    return _run_simulation(
        payoff_type, S, K, T, r, q, sigma, steps, simulations, seed, antithetic, barrier
    )


def price_monte_carlo(
    payoff_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    steps: int = 252,
    simulations: int = 10000,
    seed: Optional[int] = 42,
    antithetic: bool = False,
    barrier: Optional[float] = None,
) -> dict:
    """Monte Carlo price + diagnostics as a JSON-ready dict (``MonteCarloResponse``)."""
    warnings = validate_monte_carlo_inputs(
        payoff_type, S, K, T, r, sigma, q, steps, simulations, barrier
    )

    discounted, preview = _run_simulation(
        payoff_type, S, K, T, r, q, sigma, steps, simulations, seed, antithetic, barrier
    )
    summary = summarize_monte_carlo_payoffs(discounted)

    # Black-Scholes reference only for vanilla European payoffs.
    bs_ref: Optional[float] = None
    difference: Optional[float] = None
    relative: Optional[float] = None
    if payoff_type in _EUROPEAN_TYPES:
        option_type = "call" if payoff_type.endswith("call") else "put"
        bs_ref = black_scholes_price(option_type, S, K, T, r, sigma, q)
        difference = summary["price"] - bs_ref
        relative = difference / bs_ref if abs(bs_ref) > 1e-12 else None

    return {
        "model": "gbm_monte_carlo",
        "payoff_type": payoff_type,
        "price": summary["price"],
        "standard_error": summary["standard_error"],
        "confidence_interval_95": summary["confidence_interval_95"],
        "simulations": simulations,
        "steps": steps,
        "seed": seed,
        "antithetic": antithetic,
        "average_type": "arithmetic" if payoff_type in _ASIAN_TYPES else None,
        "barrier_price": _clean(barrier) if barrier is not None else None,
        "black_scholes_reference": _clean(bs_ref) if bs_ref is not None else None,
        "difference_vs_black_scholes": _clean(difference) if difference is not None else None,
        "relative_difference_vs_black_scholes": (
            _clean(relative) if relative is not None else None
        ),
        "path_preview": build_path_preview(preview, T, steps),
        "warnings": warnings,
    }
