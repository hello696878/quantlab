"""
Tree-based option pricing v1 — Cox-Ross-Rubinstein (CRR) binomial lattice with
European **and** American exercise, early-exercise diagnostics, a small-lattice
builder for visualization, and convergence comparison against Black-Scholes.

Educational / deterministic only.  This is a numerical **approximation**, not a
production options risk engine:

* European prices converge to Black-Scholes as the step count grows.
* American prices are handled by taking ``max(intrinsic, continuation)`` at each
  node — a simplified lattice model.  It does **not** model discrete dividends,
  corporate actions, transaction costs, liquidity, smile, or term structure.
* Results depend on the step count, the volatility input, and the (continuous)
  dividend-yield assumption.

CRR construction (``dt = T / N``)::

    u = exp(sigma * sqrt(dt))         # up factor
    d = 1 / u                         # down factor
    p = (exp((r - q) * dt) - d) / (u - d)   # risk-neutral up probability
    discount = exp(-r * dt)

The Black-Scholes helper is reused from :mod:`app.options` so there is no
duplicated closed-form code.  All outputs are finite and rounded for JSON —
never NaN/inf.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.options import black_scholes_price

# Only build the full node lattice for small trees — a readable diagram, not a
# giant payload.  Larger trees return the price only (see ``lattice_note``).
LATTICE_MAX_STEPS = 6
# Keep direct Python callers bounded the same way the API schema is bounded.
MAX_TREE_STEPS = 1000
# Cap how many exercise-boundary points the response carries (downsampled, the
# exact first-exercise step/time are computed before downsampling).
BOUNDARY_MAX_POINTS = 60
# Tolerance for treating the risk-neutral probability as in-bounds / for the
# early-exercise strict-improvement test.
_P_TOL = 1e-9
_EXERCISE_EPS = 1e-9


class TreeInputError(ValueError):
    """Raised when tree parameters are numerically invalid (e.g. p ∉ [0, 1])."""


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def _intrinsic(option_type: str, spot: float, strike: float) -> float:
    if option_type == "call":
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def _risk_neutral_prob(
    r: float, q: float, sigma: float, dt: float
) -> Tuple[float, float, float]:
    """Return ``(p, u, d)`` for the CRR lattice."""
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    if abs(u - d) < 1e-15:
        raise TreeInputError(
            "Volatility and step size make the CRR up/down factors indistinguishable; "
            "increase volatility, time to expiry, or use fewer steps."
        )
    p = (math.exp((r - q) * dt) - d) / (u - d)
    return p, u, d


def validate_tree_inputs(
    S: float, K: float, T: float, r: float, sigma: float, q: float, steps: int
) -> Optional[str]:
    """Numeric (non-schema) validation.

    Schema bounds (S/K/T/sigma > 0, steps ∈ [1, 1000]) are enforced by Pydantic;
    this guards the one condition that depends on the *combination* of inputs:
    the risk-neutral probability ``p`` must lie in ``[0, 1]``.  When extreme
    ``r``/``q`` relative to ``sigma`` and a large ``dt`` push ``p`` outside that
    range the lattice is arbitrageable, so we raise rather than return a
    misleading price.  Returns an optional informational warning otherwise.
    """
    numeric_inputs = {
        "underlying_price": S,
        "strike": K,
        "time_to_expiry": T,
        "risk_free_rate": r,
        "volatility": sigma,
        "dividend_yield": q,
    }
    for name, value in numeric_inputs.items():
        if not math.isfinite(float(value)):
            raise TreeInputError(f"{name} must be finite.")
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        raise TreeInputError("underlying_price, strike, time_to_expiry, and volatility must be positive.")
    if q < 0:
        raise TreeInputError("dividend_yield must be non-negative.")
    if steps < 1:
        raise TreeInputError("steps must be a positive integer.")
    if steps > MAX_TREE_STEPS:
        raise TreeInputError(f"steps must be at most {MAX_TREE_STEPS}.")
    dt = T / steps
    p, _u, _d = _risk_neutral_prob(r, q, sigma, dt)
    if p < -_P_TOL or p > 1.0 + _P_TOL:
        raise TreeInputError(
            f"Risk-neutral probability p={p:.4f} is outside [0, 1] for these "
            f"parameters (r={r}, q={q}, sigma={sigma}, steps={steps}). The CRR "
            "lattice is unstable / arbitrageable here — increase the step count "
            "or adjust the rate, dividend, or volatility."
        )
    if steps <= 3:
        return (
            "Very few steps — the lattice price is a coarse approximation; "
            "increase the step count for a more accurate value."
        )
    return None


def _price_tree(
    option_type: str,
    exercise_style: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    steps: int,
    *,
    record_lattice: bool = False,
) -> Tuple[float, List[dict], Optional[List[dict]], Dict[str, float]]:
    """Backward-induction CRR pricer.

    Returns ``(price, boundary, lattice_nodes_or_None, tree_params)``.  When
    ``record_lattice`` is set the full node grid is captured (small trees only).
    """
    dt = T / steps
    p, u, d = _risk_neutral_prob(r, q, sigma, dt)
    p = min(1.0, max(0.0, p))  # clamp away sub-ulp boundary noise
    discount = math.exp(-r * dt)
    american = exercise_style == "american"

    # Precompute powers so node prices are O(1) lookups (no repeated exp()).
    u_pow = [u**k for k in range(steps + 1)]
    d_pow = [d**k for k in range(steps + 1)]

    def spot(step: int, j: int) -> float:
        # j = number of up moves at this step.
        return S * u_pow[j] * d_pow[step - j]

    # Terminal layer.
    values = [_intrinsic(option_type, spot(steps, j), K) for j in range(steps + 1)]

    nodes: Optional[List[dict]] = None
    if record_lattice:
        nodes = []
        for j in range(steps + 1):
            s = spot(steps, j)
            nodes.append(
                {
                    "step": steps,
                    "index": j,
                    "underlying_price": _clean(s),
                    "option_value": _clean(values[j]),
                    "intrinsic_value": _clean(_intrinsic(option_type, s, K)),
                    "early_exercise": False,  # terminal = exercise/expiry, not "early"
                }
            )

    boundary: List[dict] = []
    for step in range(steps - 1, -1, -1):
        exercised_spots: List[float] = []
        for j in range(step + 1):
            cont = discount * (p * values[j + 1] + (1.0 - p) * values[j])
            value = cont
            early = False
            if american:
                s = spot(step, j)
                intrinsic = _intrinsic(option_type, s, K)
                if intrinsic > cont + _EXERCISE_EPS:
                    value = intrinsic
                    early = True
                    exercised_spots.append(s)
            values[j] = value
            if record_lattice and nodes is not None:
                s = spot(step, j)
                nodes.append(
                    {
                        "step": step,
                        "index": j,
                        "underlying_price": _clean(s),
                        "option_value": _clean(value),
                        "intrinsic_value": _clean(_intrinsic(option_type, s, K)),
                        "early_exercise": early,
                    }
                )
        if american and exercised_spots:
            # Put: exercise region is *below* a critical price → its upper edge
            # (max exercised spot) is the boundary.  Call (with dividends): the
            # region is above a critical price → its lower edge (min spot).
            boundary_price = (
                max(exercised_spots) if option_type == "put" else min(exercised_spots)
            )
            boundary.append(
                {
                    "step": step,
                    "time": _clean(step * dt),
                    "boundary_price": _clean(boundary_price),
                }
            )

    if record_lattice and nodes is not None:
        nodes.sort(key=lambda n: (n["step"], n["index"]))

    tree_params = {
        "dt": _clean(dt),
        "up_factor": _clean(u),
        "down_factor": _clean(d),
        "risk_neutral_prob": _clean(p),
        "discount_per_step": _clean(discount),
    }
    return values[0], boundary, nodes, tree_params


def build_binomial_lattice(
    option_type: str,
    exercise_style: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    steps: int,
) -> Optional[dict]:
    """Full node grid for a **small** tree (``steps <= LATTICE_MAX_STEPS``).

    Returns ``None`` when the tree is too large to visualize — the caller shows
    a "limited to small step counts" message instead of a giant lattice.
    """
    if steps > LATTICE_MAX_STEPS:
        return None
    validate_tree_inputs(S, K, T, r, sigma, q, steps)
    _price, _boundary, nodes, _params = _price_tree(
        option_type, exercise_style, S, K, T, r, sigma, q, steps, record_lattice=True
    )
    return {"steps": steps, "nodes": nodes or []}


def compute_early_exercise_boundary(
    option_type: str,
    exercise_style: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    steps: int,
) -> dict:
    """Early-exercise diagnostic for an American option.

    ``{detected, first_step, first_time, boundary}``.  European options never
    exercise early, so everything is empty/False there.
    """
    if exercise_style != "american":
        return {"detected": False, "first_step": None, "first_time": None, "boundary": []}
    validate_tree_inputs(S, K, T, r, sigma, q, steps)
    _price, boundary, _nodes, _params = _price_tree(
        option_type, exercise_style, S, K, T, r, sigma, q, steps
    )
    return _summarize_boundary(boundary, T, steps)


def _summarize_boundary(boundary: List[dict], T: float, steps: int) -> dict:
    if not boundary:
        return {"detected": False, "first_step": None, "first_time": None, "boundary": []}
    first_step = min(b["step"] for b in boundary)
    dt = T / steps
    # boundary is built from high → low step; present it low → high (time order)
    ordered = sorted(boundary, key=lambda b: b["step"])
    return {
        "detected": True,
        "first_step": first_step,
        "first_time": _clean(first_step * dt),
        "boundary": _downsample(ordered, BOUNDARY_MAX_POINTS),
    }


def _downsample(items: List[dict], max_points: int) -> List[dict]:
    if len(items) <= max_points:
        return items
    step = len(items) / max_points
    picked = [items[min(len(items) - 1, int(i * step))] for i in range(max_points)]
    # always keep the last point
    if picked[-1] is not items[-1]:
        picked[-1] = items[-1]
    return picked


def _convergence_block(
    option_type: str,
    exercise_style: str,
    tree_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
) -> dict:
    """Compare the tree price to Black-Scholes.

    For European options BS is the exact benchmark.  For American options BS is
    only a **European reference** (no early-exercise value), flagged honestly.
    """
    bs = black_scholes_price(option_type, S, K, T, r, sigma, q)
    difference = tree_price - bs
    relative = difference / bs if abs(bs) > 1e-12 else None
    return {
        "black_scholes_price": _clean(bs),
        "difference": _clean(difference),
        "relative_difference": _clean(relative) if relative is not None else None,
        "is_european_reference": exercise_style == "american",
    }


def binomial_tree_price(
    option_type: str,
    exercise_style: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    steps: int = 100,
    *,
    include_lattice: bool = True,
) -> dict:
    """Price a European/American option on a CRR binomial lattice.

    Returns a JSON-ready dict matching ``BinomialTreeResponse``: price, the
    parameter echo, early-exercise diagnostics, Black-Scholes convergence, tree
    parameters, an optional small-tree lattice, and any warnings.
    """
    warning = validate_tree_inputs(S, K, T, r, sigma, q, steps)

    want_lattice = include_lattice and steps <= LATTICE_MAX_STEPS
    price, boundary, nodes, tree_params = _price_tree(
        option_type,
        exercise_style,
        S,
        K,
        T,
        r,
        sigma,
        q,
        steps,
        record_lattice=want_lattice,
    )

    lattice = {"steps": steps, "nodes": nodes or []} if want_lattice else None
    lattice_note = None
    if include_lattice and not want_lattice:
        lattice_note = (
            f"Tree visualization is limited to {LATTICE_MAX_STEPS} steps for "
            f"readability; {steps} steps were priced, so the lattice is hidden."
        )

    warnings: List[str] = []
    if warning:
        warnings.append(warning)

    return {
        "model": "crr_binomial",
        "option_type": option_type,
        "exercise_style": exercise_style,
        "price": _clean(price),
        "steps": steps,
        "parameters": {
            "underlying_price": _clean(S),
            "strike": _clean(K),
            "time_to_expiry": _clean(T),
            "risk_free_rate": _clean(r),
            "volatility": _clean(sigma),
            "dividend_yield": _clean(q),
        },
        "tree_params": tree_params,
        "early_exercise": _summarize_boundary(boundary, T, steps),
        "convergence": _convergence_block(
            option_type, exercise_style, price, S, K, T, r, sigma, q
        ),
        "lattice": lattice,
        "lattice_note": lattice_note,
        "warnings": warnings,
    }


def compare_tree_to_black_scholes(
    option_type: str,
    exercise_style: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    step_values: List[int],
) -> dict:
    """Tree price vs Black-Scholes across a list of step counts (convergence).

    European: convergence *to* Black-Scholes.  American: tree-price convergence,
    with Black-Scholes shown only as a European reference.
    """
    bs = black_scholes_price(option_type, S, K, T, r, sigma, q)
    points: List[dict] = []
    for n in step_values:
        validate_tree_inputs(S, K, T, r, sigma, q, n)
        price, _b, _n, _p = _price_tree(
            option_type, exercise_style, S, K, T, r, sigma, q, n
        )
        points.append(
            {
                "steps": n,
                "price": _clean(price),
                "difference_vs_black_scholes": _clean(price - bs),
            }
        )
    return {
        "points": points,
        "black_scholes_price": _clean(bs),
        "is_european_reference": exercise_style == "american",
    }
