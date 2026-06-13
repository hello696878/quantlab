"""
Options & Volatility Lab v1 — European Black–Scholes pricing, Greeks, an
implied-volatility solver, and expiration-payoff math.

Educational / deterministic only.  This is **not** an options trading system:
no live chains, no American exercise, no discrete dividends, no transaction
costs / liquidity / smile / term structure.  Black–Scholes assumes lognormal
prices with constant volatility and continuous dividend yield ``q``.

Greeks conventions (labelled in the schema/UI):
* delta, gamma — per 1.0 change in the underlying.
* vega, rho    — **raw**, per 1.0 (100%) change in volatility / rate.
* theta        — returned both annualized (per year) and per-day (annual/365).

All outputs are finite and rounded for JSON — never NaN/inf.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

SQRT_2PI = math.sqrt(2.0 * math.pi)
_DAYS_PER_YEAR = 365.0


def normal_cdf(x: float) -> float:
    """Standard normal CDF via the error function (no scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float) -> Tuple[float, float]:
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def black_scholes_price(
    option_type: str, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
) -> float:
    """European Black–Scholes price with continuous dividend yield ``q``."""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_q = math.exp(-q * T)
    disc_r = math.exp(-r * T)
    if option_type == "call":
        return S * disc_q * normal_cdf(d1) - K * disc_r * normal_cdf(d2)
    return K * disc_r * normal_cdf(-d2) - S * disc_q * normal_cdf(-d1)


def black_scholes_greeks(
    option_type: str, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
) -> dict:
    """Price + Greeks for a European option (see module docstring for conventions)."""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_q = math.exp(-q * T)
    disc_r = math.exp(-r * T)
    pdf_d1 = normal_pdf(d1)
    sqrt_t = math.sqrt(T)

    price = black_scholes_price(option_type, S, K, T, r, sigma, q)
    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t  # per 1.0 (100%) vol change

    common_theta = -(S * disc_q * pdf_d1 * sigma) / (2.0 * sqrt_t)
    if option_type == "call":
        delta = disc_q * normal_cdf(d1)
        theta = (
            common_theta
            - r * K * disc_r * normal_cdf(d2)
            + q * S * disc_q * normal_cdf(d1)
        )
        rho = K * T * disc_r * normal_cdf(d2)  # per 1.0 (100%) rate change
    else:
        delta = disc_q * (normal_cdf(d1) - 1.0)
        theta = (
            common_theta
            + r * K * disc_r * normal_cdf(-d2)
            - q * S * disc_q * normal_cdf(-d1)
        )
        rho = -K * T * disc_r * normal_cdf(-d2)

    return {
        "price": _clean(price),
        "delta": _clean(delta),
        "gamma": _clean(gamma),
        "vega": _clean(vega),
        "theta_annual": _clean(theta),
        "theta_daily": _clean(theta / _DAYS_PER_YEAR),
        "rho": _clean(rho),
        "d1": _clean(d1),
        "d2": _clean(d2),
    }


def no_arbitrage_bounds(
    option_type: str, S: float, K: float, T: float, r: float, q: float
) -> Tuple[float, float]:
    """(lower, upper) no-arbitrage price bounds for a European option."""
    disc_q = math.exp(-q * T)
    disc_r = math.exp(-r * T)
    if option_type == "call":
        return max(0.0, S * disc_q - K * disc_r), S * disc_q
    return max(0.0, K * disc_r - S * disc_q), K * disc_r


def implied_volatility(
    option_type: str,
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    *,
    lower_vol: float = 1e-6,
    upper_vol: float = 5.0,
    tolerance: float = 1e-6,
    max_iterations: int = 100,
) -> Tuple[Optional[float], bool, int, Optional[str]]:
    """Robust **bisection** IV solver (slower than Newton, but safe + testable).

    Returns ``(iv, converged, iterations, warning)``.  Out-of-bounds prices
    return ``(None, False, 0, warning)`` rather than looping or crashing.
    """
    lower_bound, upper_bound = no_arbitrage_bounds(option_type, S, K, T, r, q)
    if market_price < lower_bound - tolerance or market_price > upper_bound + tolerance:
        return None, False, 0, (
            f"Market price {market_price} is outside the no-arbitrage bounds "
            f"[{round(lower_bound, 6)}, {round(upper_bound, 6)}] for this "
            f"{option_type}; implied volatility is not defined."
        )

    def f(sigma: float) -> float:
        return black_scholes_price(option_type, S, K, T, r, sigma, q) - market_price

    f_lo = f(lower_vol)
    f_hi = f(upper_vol)
    if f_lo > 0:
        # Even near-zero vol overprices the option (price ≈ intrinsic) — treat as
        # ~0 vol rather than failing.
        return _clean(lower_vol), True, 0, (
            "Market price is at or below intrinsic value; implied volatility is "
            "approximately zero."
        )
    if f_hi < 0:
        return None, False, 0, (
            f"Market price exceeds the price at {upper_vol:.0f} volatility; the "
            "implied volatility is above the solver's search range."
        )

    lo, hi = lower_vol, upper_vol
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < tolerance or (hi - lo) < tolerance:
            return _clean(mid), True, iterations, None
        if (fm > 0) == (f_hi > 0):
            hi = mid
        else:
            lo = mid
    return _clean(0.5 * (lo + hi)), False, iterations, (
        "Solver hit the maximum iteration count without full convergence; the "
        "returned value is approximate."
    )


# ---------------------------------------------------------------------------
# Expiration payoff
# ---------------------------------------------------------------------------


def _leg_payoff(leg: dict, S_T: float) -> float:
    """Per-unit expiration payoff for one leg (before quantity)."""
    sign = 1.0 if leg["side"] == "long" else -1.0
    if leg["instrument"] == "stock":
        entry = float(leg["entry_price"])
        return sign * (S_T - entry)
    # option
    strike = float(leg["strike"])
    premium = float(leg.get("premium", 0.0))
    if leg["option_type"] == "call":
        intrinsic = max(S_T - strike, 0.0)
    else:
        intrinsic = max(strike - S_T, 0.0)
    # long: intrinsic - premium ; short: premium - intrinsic
    return sign * intrinsic - sign * premium


def strategy_payoff(
    legs: List[dict], price_min: float, price_max: float, points: int
) -> dict:
    """Total expiration payoff curve + bounded max/min + approximate breakevens."""
    prices = [
        price_min + (price_max - price_min) * i / (points - 1) for i in range(points)
    ]
    payoffs: List[float] = []
    for S_T in prices:
        total = 0.0
        for leg in legs:
            total += _leg_payoff(leg, S_T) * float(leg.get("quantity", 1))
        payoffs.append(total)

    curve = [
        {"underlying_price": _clean(p), "payoff": _clean(v)}
        for p, v in zip(prices, payoffs)
    ]

    # Bounded-ness from the slope at each edge (payoff is piecewise-linear).
    eps = 1e-9
    slope_left = payoffs[1] - payoffs[0]
    slope_right = payoffs[-1] - payoffs[-2]
    profit_unbounded = slope_right > eps or slope_left < -eps
    loss_unbounded = slope_right < -eps or slope_left > eps
    max_profit = None if profit_unbounded else _clean(max(payoffs))
    max_loss = None if loss_unbounded else _clean(min(payoffs))

    # Approximate breakevens: linear-interpolate sign changes of the payoff.
    breakevens: List[float] = []
    for i in range(1, len(payoffs)):
        y0, y1 = payoffs[i - 1], payoffs[i]
        if y0 == 0.0:
            breakevens.append(_clean(prices[i - 1]))
        elif (y0 < 0) != (y1 < 0) and y1 != y0:
            x0, x1 = prices[i - 1], prices[i]
            crossing = x0 + (x1 - x0) * (0.0 - y0) / (y1 - y0)
            breakevens.append(_clean(crossing))
    # De-duplicate near-identical crossings.
    deduped: List[float] = []
    for b in breakevens:
        if not deduped or abs(b - deduped[-1]) > 1e-6:
            deduped.append(b)

    return {
        "payoff_curve": curve,
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakevens": deduped,
    }


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0
