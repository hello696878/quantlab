"""
Short Rate Models Lab v1 — Vasicek and CIR one-factor short-rate models with
risk-neutral Monte Carlo path simulation, a capped path preview, terminal-rate
distribution, and **analytic** zero-coupon bond pricing.

Educational / research only.  These are **simplified mathematical models** — this
is **not** an institutional or production rates engine:

* No live rates feed, no market calibration, no swap-curve bootstrapping.
* No Hull-White (or other multi-factor / time-dependent) models yet.
* Outputs depend on the parameters, the Euler discretization, the simulation
  count, and the random seed.  There is inherent Monte Carlo sampling error.

Dynamics (risk-neutral):

* **Vasicek**  ``dr = kappa·(theta − r) dt + sigma·dW`` — Gaussian, mean
  reverting, and **can produce negative rates** (a known model feature).
* **CIR**      ``dr = kappa·(theta − r) dt + sigma·√r·dW`` — square-root
  diffusion; non-negative under ideal continuous dynamics.  Simulated with a
  **full-truncation Euler** scheme (``r⁺ = max(r, 0)`` wherever ``r`` appears and
  again after each step) so simulated rates stay non-negative.  The **Feller
  condition** ``2·kappa·theta ≥ sigma²`` controls behaviour near zero.

Zero-coupon bond prices use the standard closed-form affine ``P = A·exp(−B·r0)``
solutions (CIR rewritten in a numerically stable form).  ``sigma = 0`` falls back
to the deterministic zero-volatility limit.  All outputs are finite and rounded
for JSON — never NaN/inf; full paths are never returned.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

MODELS = ("vasicek", "cir")

_MIN_STEPS = 1
_MAX_STEPS = 2000
_MIN_SIMULATIONS = 100
_MAX_SIMULATIONS = 200_000
_MAX_SEED = 2**32 - 1
# Path-preview caps — never stream all paths to the frontend.
_PREVIEW_PATHS = 12
_PREVIEW_POINTS = 150
_DISTRIBUTION_BUCKETS = 24

# Defensive bounds (well outside any sensible educational input).
_MAX_RATE = 10.0  # |r0|, |theta| <= 1000%
_MAX_KAPPA = 100.0
_MAX_SIGMA = 10.0
_MAX_HORIZON = 100.0


class ShortRateInputError(ValueError):
    """Raised when short-rate inputs are logically invalid."""


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


def _clean_or_zero(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


# ---------------------------------------------------------------------------
# Feller condition (CIR)
# ---------------------------------------------------------------------------


def feller_condition(kappa: float, theta: float, sigma: float) -> Tuple[bool, float, float]:
    """Return ``(satisfied, 2·kappa·theta, sigma²)``. Satisfied when ``2κθ ≥ σ²``."""
    lhs = 2.0 * kappa * theta
    rhs = sigma * sigma
    return lhs >= rhs, lhs, rhs


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_short_rate_inputs(
    model: str,
    initial_rate: float,
    long_run_rate: float,
    kappa: float,
    sigma: float,
    horizon_years: float,
    steps: int,
    simulations: int,
    seed: Optional[int] = None,
) -> List[str]:
    """Field/combination validation. Returns warnings; raises on fatal problems."""
    if model not in MODELS:
        raise ShortRateInputError("model must be 'vasicek' or 'cir'.")

    numeric = {
        "initial_rate": initial_rate,
        "long_run_rate": long_run_rate,
        "kappa": kappa,
        "sigma": sigma,
        "horizon_years": horizon_years,
    }
    for name, value in numeric.items():
        if not math.isfinite(float(value)):
            raise ShortRateInputError(f"{name} must be finite.")

    if kappa <= 0:
        raise ShortRateInputError("kappa (mean-reversion speed) must be positive.")
    if kappa > _MAX_KAPPA:
        raise ShortRateInputError(f"kappa must be no greater than {_MAX_KAPPA}.")
    if sigma < 0:
        raise ShortRateInputError("sigma (volatility) must be non-negative.")
    if sigma > _MAX_SIGMA:
        raise ShortRateInputError(f"sigma must be no greater than {_MAX_SIGMA}.")
    if horizon_years <= 0:
        raise ShortRateInputError("horizon_years must be positive.")
    if horizon_years > _MAX_HORIZON:
        raise ShortRateInputError(f"horizon_years must be no greater than {_MAX_HORIZON}.")
    if abs(initial_rate) > _MAX_RATE or abs(long_run_rate) > _MAX_RATE:
        raise ShortRateInputError("initial_rate and long_run_rate are out of a sensible range.")

    if not isinstance(steps, (int, np.integer)) or steps < _MIN_STEPS or steps > _MAX_STEPS:
        raise ShortRateInputError(f"steps must be an integer between {_MIN_STEPS} and {_MAX_STEPS}.")
    if (
        not isinstance(simulations, (int, np.integer))
        or simulations < _MIN_SIMULATIONS
        or simulations > _MAX_SIMULATIONS
    ):
        raise ShortRateInputError(
            f"simulations must be an integer between {_MIN_SIMULATIONS} and {_MAX_SIMULATIONS}."
        )
    if seed is not None:
        if not isinstance(seed, (int, np.integer)) or seed < 0 or seed > _MAX_SEED:
            raise ShortRateInputError(f"seed must be an integer between 0 and {_MAX_SEED}.")

    # CIR is defined for non-negative rates; negative inputs are rejected.
    if model == "cir":
        if initial_rate < 0:
            raise ShortRateInputError("CIR requires a non-negative initial_rate.")
        if long_run_rate < 0:
            raise ShortRateInputError("CIR requires a non-negative long_run_rate.")

    warnings: List[str] = []
    if model == "cir":
        satisfied, _lhs, _rhs = feller_condition(kappa, theta=long_run_rate, sigma=sigma)
        if not satisfied:
            warnings.append(
                "CIR Feller condition is violated (2·kappa·theta < sigma^2); simulated rates may "
                "spend more time near zero and Euler discretization bias can increase."
            )
    return warnings


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def _simulate(
    model: str,
    r0: float,
    kappa: float,
    theta: float,
    sigma: float,
    T: float,
    steps: int,
    simulations: int,
    rng: np.random.Generator,
    preview_paths: int = _PREVIEW_PATHS,
) -> dict:
    """Euler simulation shared by Vasicek / CIR.

    Memory is O(simulations) for the live state plus a small
    ``(preview_paths, steps+1)`` preview history and a length-``steps+1`` array
    of cross-sectional means.  Returns terminal rates, the preview history, the
    per-step mean path, and the probability a path ever went negative.
    """
    dt = T / steps
    sqrt_dt = math.sqrt(dt)

    r = np.full(simulations, float(r0))

    n_prev = min(preview_paths, simulations)
    prev = np.empty((n_prev, steps + 1))
    prev[:, 0] = r0

    step_means = np.empty(steps + 1)
    step_means[0] = float(r0)

    path_sum = r.astype(float).copy()  # running sum across time for each sim
    ever_negative = r < 0.0

    for t in range(1, steps + 1):
        z = rng.standard_normal(simulations)
        if model == "vasicek":
            r = r + kappa * (theta - r) * dt + sigma * sqrt_dt * z
        else:  # cir, full-truncation Euler
            r_pos = np.maximum(r, 0.0)
            r = r + kappa * (theta - r_pos) * dt + sigma * np.sqrt(r_pos * dt) * z
            r = np.maximum(r, 0.0)

        path_sum += r
        ever_negative |= r < 0.0
        step_means[t] = float(np.mean(r))
        prev[:, t] = r[:n_prev]

    if not np.all(np.isfinite(r)):
        raise ShortRateInputError(
            "Simulated short-rate paths became non-finite; reduce sigma, the horizon, or the "
            "number of steps."
        )

    mean_path_rate = float(np.mean(path_sum / (steps + 1)))
    return {
        "terminal": r,
        "preview": prev,
        "step_means": step_means,
        "mean_path_rate": mean_path_rate,
        "negative_rate_probability": float(np.mean(ever_negative)),
        "dt": dt,
    }


def simulate_vasicek_paths(
    r0: float,
    kappa: float,
    theta: float,
    sigma: float,
    T: float,
    steps: int,
    simulations: int,
    rng: np.random.Generator,
    preview_paths: int = _PREVIEW_PATHS,
) -> dict:
    """Vasicek Euler simulation. ``dr = kappa·(theta − r) dt + sigma·dW``."""
    return _simulate("vasicek", r0, kappa, theta, sigma, T, steps, simulations, rng, preview_paths)


def simulate_cir_paths(
    r0: float,
    kappa: float,
    theta: float,
    sigma: float,
    T: float,
    steps: int,
    simulations: int,
    rng: np.random.Generator,
    preview_paths: int = _PREVIEW_PATHS,
) -> dict:
    """CIR full-truncation Euler simulation. ``dr = kappa·(theta − r) dt + sigma·√r·dW``."""
    return _simulate("cir", r0, kappa, theta, sigma, T, steps, simulations, rng, preview_paths)


# ---------------------------------------------------------------------------
# Summary / distribution / preview
# ---------------------------------------------------------------------------


def summarize_short_rate_paths(sim: dict) -> dict:
    terminal = sim["terminal"]
    n = int(terminal.shape[0])
    std = float(np.std(terminal, ddof=1)) if n > 1 else 0.0
    return {
        "mean_terminal_rate": _clean_or_zero(float(np.mean(terminal))),
        "median_terminal_rate": _clean_or_zero(float(np.median(terminal))),
        "min_terminal_rate": _clean_or_zero(float(np.min(terminal))),
        "max_terminal_rate": _clean_or_zero(float(np.max(terminal))),
        "negative_rate_probability": _clean_or_zero(sim["negative_rate_probability"]),
        "mean_path_rate": _clean_or_zero(sim["mean_path_rate"]),
        "final_rate_std": _clean_or_zero(std),
    }


def build_terminal_distribution(sim: dict, buckets: int = _DISTRIBUTION_BUCKETS) -> List[dict]:
    """Histogram of terminal rates as probability buckets (sums to 1)."""
    terminal = sim["terminal"]
    n = int(terminal.shape[0])
    if n == 0:
        return []
    lo = float(np.min(terminal))
    hi = float(np.max(terminal))
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        # Degenerate (e.g. sigma = 0): a single bucket at the common value.
        return [
            {
                "lower": _clean_or_zero(lo),
                "upper": _clean_or_zero(lo),
                "mid": _clean_or_zero(lo),
                "count": n,
                "probability": 1.0,
            }
        ]
    counts, edges = np.histogram(terminal, bins=buckets, range=(lo, hi))
    out: List[dict] = []
    for i in range(len(counts)):
        lower = float(edges[i])
        upper = float(edges[i + 1])
        out.append(
            {
                "lower": _clean_or_zero(lower),
                "upper": _clean_or_zero(upper),
                "mid": _clean_or_zero(0.5 * (lower + upper)),
                "count": int(counts[i]),
                "probability": _clean_or_zero(int(counts[i]) / n),
            }
        )
    return out


def _downsample_indices(cols: int, max_points: int) -> List[int]:
    if cols <= max_points:
        return list(range(cols))
    return sorted({round(i * (cols - 1) / (max_points - 1)) for i in range(max_points)})


def build_short_rate_path_preview(
    sim: dict, T: float, steps: int, max_points: int = _PREVIEW_POINTS
) -> Tuple[List[dict], List[dict]]:
    """Return ``(paths, mean_path)`` with column-downsampled time series.

    Each path is ``{path_id, points: [{time, rate}]}``; ``mean_path`` is the
    cross-sectional mean rate at each (downsampled) time.
    """
    prev = sim["preview"]
    step_means = sim["step_means"]
    cols = steps + 1
    dt = T / steps
    indices = _downsample_indices(cols, max_points)
    times = [j * dt for j in indices]

    paths: List[dict] = []
    for pid in range(prev.shape[0]):
        points = [
            {"time": _clean_or_zero(times[k]), "rate": _clean_or_zero(float(prev[pid, j]))}
            for k, j in enumerate(indices)
        ]
        paths.append({"path_id": pid, "points": points})

    mean_path = [
        {"time": _clean_or_zero(times[k]), "rate": _clean_or_zero(float(step_means[j]))}
        for k, j in enumerate(indices)
    ]
    return paths, mean_path


# ---------------------------------------------------------------------------
# Analytic zero-coupon bond pricing
# ---------------------------------------------------------------------------


def _deterministic_zero_coupon(r0: float, kappa: float, theta: float, T: float) -> float:
    """Zero-volatility limit (shared drift) ``P = exp(−∫ r dt)`` for sigma = 0.

    ``r(t) = theta + (r0 − theta)·e^{−κt}`` ⇒
    ``∫₀ᵀ r dt = theta·T + (r0 − theta)·(1 − e^{−κT})/κ``.
    """
    b = (1.0 - math.exp(-kappa * T)) / kappa
    integral = theta * T + (r0 - theta) * b
    return math.exp(-integral)


def price_vasicek_zero_coupon(
    r0: float, kappa: float, theta: float, sigma: float, T: float
) -> dict:
    """Closed-form Vasicek zero-coupon bond price ``P(0,T) = A·exp(−B·r0)``."""
    warnings: List[str] = []
    b = (1.0 - math.exp(-kappa * T)) / kappa
    if sigma <= 1e-12:
        price = _deterministic_zero_coupon(r0, kappa, theta, T)
        formula = "vasicek_zero_volatility_limit"
    else:
        a_exponent = (theta - sigma * sigma / (2.0 * kappa * kappa)) * (b - T) - (
            sigma * sigma * b * b
        ) / (4.0 * kappa)
        price = math.exp(a_exponent) * math.exp(-b * r0)
        formula = "vasicek_affine_closed_form"

    if not math.isfinite(price) or price <= 0:
        return {"price": None, "implied_zero_rate": None, "formula": formula, "warnings": warnings}
    implied = -math.log(price) / T if T > 0 else None
    return {
        "price": _clean(price, 8),
        "implied_zero_rate": _clean(implied),
        "formula": formula,
        "warnings": warnings,
    }


def price_cir_zero_coupon(r0: float, kappa: float, theta: float, sigma: float, T: float) -> dict:
    """Closed-form CIR zero-coupon bond price ``P(0,T) = A·exp(−B·r0)``.

    The standard formula is rewritten with ``h = e^{−γT}`` so the intermediate
    quantities stay bounded (no ``e^{γT}`` overflow).  ``sigma = 0`` uses the
    deterministic limit (the usual formula divides by ``sigma²``).
    """
    warnings: List[str] = []
    if sigma <= 1e-12:
        price = _deterministic_zero_coupon(r0, kappa, theta, T)
        formula = "cir_zero_volatility_limit"
        if not math.isfinite(price) or price <= 0:
            return {"price": None, "implied_zero_rate": None, "formula": formula, "warnings": warnings}
        implied = -math.log(price) / T if T > 0 else None
        return {
            "price": _clean(price, 8),
            "implied_zero_rate": _clean(implied),
            "formula": formula,
            "warnings": warnings,
        }

    gamma = math.sqrt(kappa * kappa + 2.0 * sigma * sigma)
    h = math.exp(-gamma * T)  # in (0, 1]
    denom = (gamma + kappa) * (1.0 - h) + 2.0 * gamma * h
    if denom <= 0 or not math.isfinite(denom):
        return {
            "price": None,
            "implied_zero_rate": None,
            "formula": "cir_affine_closed_form",
            "warnings": warnings,
        }

    b = 2.0 * (1.0 - h) / denom
    exponent = 2.0 * kappa * theta / (sigma * sigma)
    a_base = 2.0 * gamma * math.exp(-(gamma - kappa) * T / 2.0) / denom
    try:
        a = a_base**exponent
    except (OverflowError, ValueError):
        a = float("nan")
    price = a * math.exp(-b * r0)

    if not math.isfinite(price) or price <= 0:
        # Numerically delicate corner — fall back to the deterministic limit.
        price = _deterministic_zero_coupon(r0, kappa, theta, T)
        warnings.append(
            "CIR closed-form price was numerically unstable for these parameters; reporting the "
            "deterministic zero-volatility approximation instead."
        )
        formula = "cir_zero_volatility_limit"
        if not math.isfinite(price) or price <= 0:
            return {"price": None, "implied_zero_rate": None, "formula": formula, "warnings": warnings}
    else:
        formula = "cir_affine_closed_form"

    implied = -math.log(price) / T if T > 0 else None
    return {
        "price": _clean(price, 8),
        "implied_zero_rate": _clean(implied),
        "formula": formula,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_short_rate_model(
    model: str,
    initial_rate: float,
    long_run_rate: float,
    kappa: float,
    sigma: float,
    horizon_years: float,
    steps: int = 252,
    simulations: int = 5000,
    seed: Optional[int] = 42,
) -> dict:
    """Simulate a short-rate model and return a JSON-ready diagnostics dict."""
    warnings = validate_short_rate_inputs(
        model, initial_rate, long_run_rate, kappa, sigma, horizon_years, steps, simulations, seed
    )

    rng = np.random.default_rng(None if seed is None else int(seed))
    if model == "vasicek":
        sim = simulate_vasicek_paths(
            initial_rate, kappa, long_run_rate, sigma, horizon_years, steps, simulations, rng
        )
        zc = price_vasicek_zero_coupon(initial_rate, kappa, long_run_rate, sigma, horizon_years)
    else:
        sim = simulate_cir_paths(
            initial_rate, kappa, long_run_rate, sigma, horizon_years, steps, simulations, rng
        )
        zc = price_cir_zero_coupon(initial_rate, kappa, long_run_rate, sigma, horizon_years)

    summary = summarize_short_rate_paths(sim)
    distribution = build_terminal_distribution(sim)
    path_preview, mean_path = build_short_rate_path_preview(sim, horizon_years, steps)
    satisfied, lhs, rhs = feller_condition(kappa, long_run_rate, sigma)

    warnings = list(warnings)
    warnings.extend(zc.get("warnings", []))
    if model == "vasicek" and summary["negative_rate_probability"] > 0:
        warnings.append(
            "Vasicek can generate negative rates; this is a known feature of the Gaussian model, "
            "not an error."
        )
    warnings.append(
        "Short-rate paths are model scenarios under the chosen parameters and seed — not forecasts. "
        "Results carry Monte Carlo sampling error and are not calibrated to any market curve."
    )

    return {
        "model": model,
        "summary": summary,
        "zero_coupon": {
            "maturity_years": _clean_or_zero(horizon_years),
            "price": zc["price"],
            "implied_zero_rate": zc["implied_zero_rate"],
            "formula": zc["formula"],
        },
        "feller": {
            "satisfied": bool(satisfied),
            "two_kappa_theta": _clean_or_zero(lhs),
            "sigma_squared": _clean_or_zero(rhs),
        },
        "parameters": {
            "initial_rate": _clean_or_zero(initial_rate),
            "long_run_rate": _clean_or_zero(long_run_rate),
            "kappa": _clean_or_zero(kappa),
            "sigma": _clean_or_zero(sigma),
        },
        "horizon_years": _clean_or_zero(horizon_years),
        "steps": int(steps),
        "simulations": int(simulations),
        "seed": seed,
        "long_run_rate": _clean_or_zero(long_run_rate),
        "mean_path": mean_path,
        "path_preview": path_preview,
        "distribution": distribution,
        "warnings": warnings,
    }
