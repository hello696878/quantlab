"""
Heston stochastic-volatility research v1 — risk-neutral Heston Monte Carlo with a
**full-truncation Euler** scheme, European call/put pricing, a Black-Scholes
reference, and a capped path preview (underlying + variance + volatility).

Educational / research only.  This is **not** a production Heston engine and is
**not** calibrated to any market surface:

* Risk-neutral dynamics ``dS = (r−q)S dt + √v · S dW1`` and
  ``dv = κ(θ−v) dt + ξ√v dW2`` with ``corr(dW1, dW2) = ρ``.
* **Full-truncation Euler** discretization (``v⁺ = max(v, 0)`` wherever variance
  appears) — simple and robust but **biased**; finer steps reduce the bias.
* Results depend on the parameters, the discretization, the simulation count,
  the random seed, and the variance-process handling.  There is inherent Monte
  Carlo sampling error (reported as the standard error / confidence interval).

Reuses :func:`app.options.black_scholes_price` for the constant-volatility
reference.  Variance is never reported negative (truncated for output).  All
outputs are finite and rounded for JSON; full paths are never returned.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from app.options import black_scholes_price

_MIN_STEPS = 1
_MAX_STEPS = 2000
_MIN_SIMULATIONS = 100
_MAX_SIMULATIONS = 200_000
_MAX_SEED = 2**32 - 1
# Path-preview caps — never stream all paths to the frontend.
_PREVIEW_PATHS = 12
_PREVIEW_POINTS = 150

MODEL_NAME = "heston_mc_full_truncation_euler"


class HestonInputError(ValueError):
    """Raised when Heston inputs are logically invalid (e.g. rho out of range)."""


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def feller_condition(kappa: float, theta: float, xi: float) -> Tuple[bool, float, float]:
    """Return ``(satisfied, 2·κ·θ, ξ²)``. Satisfied when ``2κθ ≥ ξ²``."""
    lhs = 2.0 * kappa * theta
    rhs = xi * xi
    return lhs >= rhs, lhs, rhs


def validate_heston_inputs(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    v0: float,
    theta: float,
    kappa: float,
    xi: float,
    rho: float,
    steps: int,
    simulations: int,
    seed: Optional[int] = None,
) -> List[str]:
    """Field/combination validation. Returns warnings; raises on fatal problems."""
    numeric = {
        "underlying_price": S,
        "strike": K,
        "time_to_expiry": T,
        "risk_free_rate": r,
        "dividend_yield": q,
        "initial_variance": v0,
        "long_run_variance": theta,
        "kappa": kappa,
        "vol_of_vol": xi,
        "rho": rho,
    }
    for name, value in numeric.items():
        if not math.isfinite(float(value)):
            raise HestonInputError(f"{name} must be finite.")
    if S <= 0 or K <= 0 or T <= 0:
        raise HestonInputError("underlying_price, strike, and time_to_expiry must be positive.")
    if S > 1e12 or K > 1e12:
        raise HestonInputError("underlying_price and strike must be no greater than 1e12.")
    if T > 100:
        raise HestonInputError("time_to_expiry must be no greater than 100 years.")
    if r < -1.0 or r > 1.0:
        raise HestonInputError("risk_free_rate must be between -1.0 and 1.0.")
    if v0 <= 0 or theta <= 0:
        raise HestonInputError("initial_variance and long_run_variance must be positive.")
    if v0 > 100 or theta > 100:
        raise HestonInputError("initial_variance and long_run_variance must be no greater than 100.")
    if kappa <= 0:
        raise HestonInputError("kappa (mean-reversion speed) must be positive.")
    if kappa > 100:
        raise HestonInputError("kappa (mean-reversion speed) must be no greater than 100.")
    if xi < 0:
        raise HestonInputError("vol_of_vol must be non-negative.")
    if xi > 100:
        raise HestonInputError("vol_of_vol must be no greater than 100.")
    if q < 0:
        raise HestonInputError("dividend_yield must be non-negative.")
    if q > 1.0:
        raise HestonInputError("dividend_yield must be no greater than 1.0.")
    if rho < -0.999 or rho > 0.999:
        raise HestonInputError("rho must be between -0.999 and 0.999.")
    if not isinstance(steps, (int, np.integer)) or steps < _MIN_STEPS or steps > _MAX_STEPS:
        raise HestonInputError(f"steps must be an integer between {_MIN_STEPS} and {_MAX_STEPS}.")
    if (
        not isinstance(simulations, (int, np.integer))
        or simulations < _MIN_SIMULATIONS
        or simulations > _MAX_SIMULATIONS
    ):
        raise HestonInputError(
            f"simulations must be an integer between {_MIN_SIMULATIONS} and {_MAX_SIMULATIONS}."
        )
    if seed is not None:
        if not isinstance(seed, (int, np.integer)) or seed < 0 or seed > _MAX_SEED:
            raise HestonInputError(f"seed must be an integer between 0 and {_MAX_SEED}.")

    warnings: List[str] = []
    satisfied, _lhs, _rhs = feller_condition(kappa, theta, xi)
    if not satisfied:
        warnings.append(
            "Feller condition is violated (2·kappa·theta < vol_of_vol^2); variance may spend "
            "more time near zero and Euler simulation bias can increase."
        )
    warnings.append(
        "Full-truncation Euler discretization is approximate and can introduce bias; "
        "increase the step count to reduce it."
    )
    return warnings


def simulate_heston_paths(
    S0: float,
    T: float,
    r: float,
    q: float,
    v0: float,
    theta: float,
    kappa: float,
    xi: float,
    rho: float,
    steps: int,
    simulations: int,
    rng: np.random.Generator,
    preview_paths: int = _PREVIEW_PATHS,
) -> dict:
    """Full-truncation Euler Heston simulation.

    Memory is O(simulations) — only the current ``S``/``v`` vectors are kept,
    plus a small ``(preview_paths, steps+1)`` history for the preview.  Returns
    terminal arrays, the preview history, and min/max observed (truncated)
    variance.
    """
    dt = T / steps
    sqrt_dt = math.sqrt(dt)
    rho_comp = math.sqrt(max(0.0, 1.0 - rho * rho))

    S = np.full(simulations, float(S0))
    v = np.full(simulations, float(v0))

    n_prev = min(preview_paths, simulations)
    prev_S = np.empty((n_prev, steps + 1))
    prev_v = np.empty((n_prev, steps + 1))
    prev_S[:, 0] = S0
    prev_v[:, 0] = v0

    min_var = float(v0)
    max_var = float(v0)

    for t in range(1, steps + 1):
        z1 = rng.standard_normal(simulations)
        z_ind = rng.standard_normal(simulations)
        z2 = rho * z1 + rho_comp * z_ind

        v_pos = np.maximum(v, 0.0)
        sqrt_v_dt = np.sqrt(v_pos * dt)
        S = S * np.exp((r - q - 0.5 * v_pos) * dt + sqrt_v_dt * z1)
        v = v + kappa * (theta - v_pos) * dt + xi * sqrt_v_dt * z2

        v_trunc = np.maximum(v, 0.0)
        min_var = min(min_var, float(v_trunc.min()))
        max_var = max(max_var, float(v_trunc.max()))
        prev_S[:, t] = S[:n_prev]
        prev_v[:, t] = v_trunc[:n_prev]

    if not np.all(np.isfinite(S)) or not np.all(np.isfinite(v)):
        raise HestonInputError(
            "Simulated paths became non-finite; reduce vol_of_vol, variance, or time to expiry, "
            "or increase the step count."
        )

    return {
        "terminal_price": S,
        "terminal_variance": np.maximum(v, 0.0),
        "preview_S": prev_S,
        "preview_v": prev_v,
        "min_variance": max(0.0, min_var),
        "max_variance": max(0.0, max_var),
        "dt": dt,
    }


def summarize_heston_paths(sim: dict) -> dict:
    terminal_vol = np.sqrt(sim["terminal_variance"])
    return {
        "mean_terminal_price": _clean(float(np.mean(sim["terminal_price"]))),
        "mean_terminal_volatility": _clean(float(np.mean(terminal_vol))),
        "min_variance_observed": _clean(sim["min_variance"]),
        "max_variance_observed": _clean(sim["max_variance"]),
    }


def build_heston_path_preview(
    sim: dict, T: float, steps: int, max_points: int = _PREVIEW_POINTS
) -> Tuple[List[float], List[dict]]:
    """Return ``(preview_times, paths)`` with column-downsampled arrays per path."""
    prev_S = sim["preview_S"]
    prev_v = sim["preview_v"]
    cols = steps + 1
    dt = T / steps
    if cols <= max_points:
        indices = list(range(cols))
    else:
        indices = sorted({round(i * (cols - 1) / (max_points - 1)) for i in range(max_points)})
    times = [_clean(j * dt) for j in indices]
    paths: List[dict] = []
    for pid in range(prev_S.shape[0]):
        underlying = [_clean(float(prev_S[pid, j])) for j in indices]
        variance = [_clean(float(prev_v[pid, j])) for j in indices]
        volatility = [_clean(math.sqrt(max(0.0, float(prev_v[pid, j])))) for j in indices]
        paths.append(
            {"path_id": pid, "underlying": underlying, "variance": variance, "volatility": volatility}
        )
    return times, paths


def _black_scholes_reference(
    option_type: str, heston_price: float, S: float, K: float, T: float, r: float, q: float, theta: float
) -> dict:
    """Constant-volatility reference using sqrt(long_run_variance) (primary)."""
    vol = math.sqrt(theta)
    bs = black_scholes_price(option_type, S, K, T, r, vol, q)
    difference = heston_price - bs
    relative = difference / bs if abs(bs) > 1e-12 else None
    return {
        "volatility_source": "sqrt(long_run_variance)",
        "volatility_used": _clean(vol),
        "price": _clean(bs),
        "difference": _clean(difference),
        "relative_difference": _clean(relative) if relative is not None else None,
    }


def price_heston_european_mc(
    option_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    v0: float,
    theta: float,
    kappa: float,
    xi: float,
    rho: float,
    steps: int = 252,
    simulations: int = 10000,
    seed: Optional[int] = 42,
) -> dict:
    """Heston Monte Carlo European price + diagnostics as a JSON-ready dict."""
    if option_type not in {"call", "put"}:
        raise HestonInputError("option_type must be 'call' or 'put'.")

    warnings = validate_heston_inputs(
        S, K, T, r, q, v0, theta, kappa, xi, rho, steps, simulations, seed
    )

    rng = np.random.default_rng(None if seed is None else int(seed))
    sim = simulate_heston_paths(S, T, r, q, v0, theta, kappa, xi, rho, steps, simulations, rng)

    S_T = sim["terminal_price"]
    if option_type == "call":
        payoff = np.maximum(S_T - K, 0.0)
    else:
        payoff = np.maximum(K - S_T, 0.0)
    discounted = math.exp(-r * T) * payoff
    if not np.all(np.isfinite(discounted)):
        raise HestonInputError(
            "Discounted payoffs became non-finite; reduce extreme inputs or increase the step count."
        )

    n = int(discounted.shape[0])
    price = float(np.mean(discounted))
    std = float(np.std(discounted, ddof=1)) if n > 1 else 0.0
    standard_error = std / math.sqrt(n) if n > 0 else 0.0
    half_width = 1.96 * standard_error

    satisfied, lhs, rhs = feller_condition(kappa, theta, xi)
    preview_times, path_preview = build_heston_path_preview(sim, T, steps)

    return {
        "model": MODEL_NAME,
        "option_type": option_type,
        "price": _clean(price),
        "standard_error": _clean(standard_error),
        "confidence_interval_95": {
            "lower": _clean(price - half_width),
            "upper": _clean(price + half_width),
        },
        "black_scholes_reference": _black_scholes_reference(
            option_type, price, S, K, T, r, q, theta
        ),
        "parameters": {
            "initial_variance": _clean(v0),
            "long_run_variance": _clean(theta),
            "initial_volatility": _clean(math.sqrt(v0)),
            "long_run_volatility": _clean(math.sqrt(theta)),
            "kappa": _clean(kappa),
            "vol_of_vol": _clean(xi),
            "rho": _clean(rho),
        },
        "feller": {
            "satisfied": bool(satisfied),
            "two_kappa_theta": _clean(lhs),
            "xi_squared": _clean(rhs),
        },
        "simulations": simulations,
        "steps": steps,
        "seed": seed,
        "preview_times": preview_times,
        "path_preview": path_preview,
        "summary": summarize_heston_paths(sim),
        "warnings": warnings,
    }
