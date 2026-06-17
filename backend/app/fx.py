"""
FX Lab v1 — educational foreign-exchange analytics: spot/forward via interest
rate parity, FX carry, purchasing-power-parity (PPP) deviation, currency
exposure with a simple stress, and Garman-Kohlhagen FX option pricing.

Educational / research only.  This is **not** a live FX trading system, an FX
arbitrage engine, or a production currency-risk system:

* No live FX rates / quotes, no broker integration, no paid data.
* No FX volatility surface, no real-time arbitrage, no execution.
* Results depend on the rate conventions, funding/transaction costs, capital
  controls, liquidity, inflation-data quality, and whether the quoted rates are
  actually investable.

Quote convention used throughout: the spot/forward rate ``S`` is **domestic
currency per 1 unit of foreign currency** (e.g. ``S = 150`` means 150 JPY per
1 USD, so domestic = JPY and foreign = USD).

All outputs are finite and rounded for JSON — never NaN/inf.  The functions are
pure and deterministic, so the math is fully unit-testable.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence

from app.options import normal_cdf, normal_pdf

FxCompounding = str  # "continuous" | "annual"
COMPOUNDINGS = ("continuous", "annual")
CARRY_DIRECTIONS = ("long_foreign", "long_domestic")
OPTION_TYPES = ("call", "put")

QUOTE_CONVENTION = "domestic currency per 1 unit of foreign currency"

# Defensive bounds (well outside any sensible educational input).
_MAX_RATE = 10.0  # |interest rate| <= 1000%
_MAX_T = 100.0
_MAX_NOTIONAL = 1e15


class FxInputError(ValueError):
    """Raised when FX inputs are logically invalid."""


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


def _require_finite(name: str, value: float) -> float:
    if not math.isfinite(float(value)):
        raise FxInputError(f"{name} must be finite.")
    return float(value)


def _check_rate(name: str, value: float) -> float:
    _require_finite(name, value)
    if abs(value) > _MAX_RATE:
        raise FxInputError(f"{name} is out of a sensible range.")
    return float(value)


# ---------------------------------------------------------------------------
# Forward / interest rate parity
# ---------------------------------------------------------------------------


def compute_fx_forward(
    spot_rate: float,
    domestic_rate: float,
    foreign_rate: float,
    time_to_maturity: float,
    compounding: FxCompounding = "continuous",
) -> dict:
    """Covered interest rate parity forward rate.

    continuous: ``F = S·exp((r_d − r_f)·T)``;
    annual:     ``F = S·((1+r_d)/(1+r_f))^T``.
    """
    if spot_rate <= 0:
        raise FxInputError("spot_rate must be positive.")
    if time_to_maturity <= 0:
        raise FxInputError("time_to_maturity must be positive.")
    if time_to_maturity > _MAX_T:
        raise FxInputError(f"time_to_maturity must be no greater than {_MAX_T}.")
    if compounding not in COMPOUNDINGS:
        raise FxInputError("compounding must be 'continuous' or 'annual'.")
    r_d = _check_rate("domestic_rate", domestic_rate)
    r_f = _check_rate("foreign_rate", foreign_rate)
    _require_finite("spot_rate", spot_rate)

    if compounding == "continuous":
        forward = spot_rate * math.exp((r_d - r_f) * time_to_maturity)
    else:  # annual
        if r_d <= -1.0 or r_f <= -1.0:
            raise FxInputError("annual compounding requires rates greater than -100%.")
        forward = spot_rate * ((1.0 + r_d) / (1.0 + r_f)) ** time_to_maturity

    if not math.isfinite(forward):
        raise FxInputError("Forward rate is not finite for these inputs.")

    differential = r_d - r_f
    warnings: List[str] = []
    if differential < 0:
        warnings.append(
            "Domestic rate is below the foreign rate, so the foreign currency trades at a forward "
            "discount (forward < spot) — covered interest rate parity, not a free profit."
        )
    elif differential > 0:
        warnings.append(
            "Domestic rate is above the foreign rate, so the foreign currency trades at a forward "
            "premium (forward > spot) under covered interest rate parity."
        )
    warnings.append(
        "Theoretical parity forward — ignores bid/ask, funding/transaction costs, credit, and "
        "capital controls; assumes the quoted rates are actually investable."
    )

    return {
        "spot_rate": _clean(spot_rate),
        "forward_rate": _clean(forward),
        "forward_points": _clean(forward - spot_rate),
        "rate_differential": _clean(differential),
        "compounding": compounding,
        "convention": QUOTE_CONVENTION,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# FX carry
# ---------------------------------------------------------------------------


def compute_fx_carry(
    spot_rate: float,
    domestic_rate: float,
    foreign_rate: float,
    expected_spot: float,
    horizon_years: float,
    notional: float,
    direction: str = "long_foreign",
) -> dict:
    """Simplified FX carry decomposition: interest differential + expected FX move.

    ``long_foreign``  = long foreign currency, funded by borrowing domestic
    (earn r_f, pay r_d); a rise in the spot (more domestic per foreign) is a gain.
    ``long_domestic`` is the mirror image.
    """
    if spot_rate <= 0:
        raise FxInputError("spot_rate must be positive.")
    if expected_spot <= 0:
        raise FxInputError("expected_spot must be positive.")
    if horizon_years <= 0:
        raise FxInputError("horizon_years must be positive.")
    if horizon_years > _MAX_T:
        raise FxInputError(f"horizon_years must be no greater than {_MAX_T}.")
    if direction not in CARRY_DIRECTIONS:
        raise FxInputError("direction must be 'long_foreign' or 'long_domestic'.")
    r_d = _check_rate("domestic_rate", domestic_rate)
    r_f = _check_rate("foreign_rate", foreign_rate)
    _require_finite("notional", notional)
    if abs(notional) > _MAX_NOTIONAL:
        raise FxInputError("notional is out of a sensible range.")

    spot_move = (expected_spot - spot_rate) / spot_rate
    if direction == "long_foreign":
        interest_differential = r_f - r_d  # earn foreign, pay domestic
        expected_fx_return = spot_move  # foreign appreciation (spot up) is a gain
    else:  # long_domestic
        interest_differential = r_d - r_f
        expected_fx_return = -spot_move

    carry_return = interest_differential * horizon_years
    total_expected_return = carry_return + expected_fx_return
    pnl_estimate = notional * total_expected_return

    for name, val in (
        ("expected_fx_return", expected_fx_return),
        ("carry_return", carry_return),
        ("total_expected_return", total_expected_return),
        ("pnl_estimate", pnl_estimate),
    ):
        if not math.isfinite(val):
            raise FxInputError(f"{name} is not finite for these inputs.")

    warnings = [
        "Carry is not free money: currency moves can offset or exceed the interest differential "
        "(this is the carry-trade risk).",
        "Simplified annualized decomposition — ignores compounding, funding/transaction costs, "
        "rollover, liquidity, and capital controls. The expected spot is an assumption, not a forecast.",
    ]

    return {
        "direction": direction,
        "interest_differential": _clean(interest_differential),
        "carry_return": _clean(carry_return),
        "expected_fx_return": _clean(expected_fx_return),
        "total_expected_return": _clean(total_expected_return),
        "pnl_estimate": _clean(pnl_estimate),
        "notional": _clean(notional),
        "horizon_years": _clean(horizon_years),
        "convention": QUOTE_CONVENTION,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# PPP deviation
# ---------------------------------------------------------------------------


def compute_ppp_deviation(
    current_spot: float,
    base_spot: float,
    domestic_price_index: float,
    foreign_price_index: float,
) -> dict:
    """Relative PPP-implied spot and deviation.

    ``S_ppp = S_base · (domestic_price_index / foreign_price_index)``;
    ``deviation = (current_spot − S_ppp) / S_ppp``.
    """
    if current_spot <= 0:
        raise FxInputError("current_spot must be positive.")
    if base_spot <= 0:
        raise FxInputError("base_spot must be positive.")
    if domestic_price_index <= 0 or foreign_price_index <= 0:
        raise FxInputError("price indexes must be positive.")

    ppp_implied = base_spot * (domestic_price_index / foreign_price_index)
    if ppp_implied <= 0 or not math.isfinite(ppp_implied):
        raise FxInputError("PPP-implied spot is not finite for these inputs.")
    deviation = (current_spot - ppp_implied) / ppp_implied
    if not math.isfinite(deviation):
        raise FxInputError("PPP deviation is not finite for these inputs.")

    # Wording is from the foreign currency's perspective (the base of the quote).
    if deviation > 0.01:
        valuation = "foreign currency appears overvalued vs domestic (simplified PPP)"
    elif deviation < -0.01:
        valuation = "foreign currency appears undervalued vs domestic (simplified PPP)"
    else:
        valuation = "near PPP fair value (simplified)"

    warnings = [
        "PPP deviation suggests relative valuation under this simplified input, not a timing signal.",
        "Sensitive to the base period, the price-index basket, and data quality; PPP gaps can "
        "persist for years and are not tradable on their own.",
    ]

    return {
        "current_spot": _clean(current_spot),
        "ppp_implied_spot": _clean(ppp_implied),
        "deviation": _clean(deviation),
        "valuation": valuation,
        "convention": QUOTE_CONVENTION,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Currency exposure + stress
# ---------------------------------------------------------------------------


def compute_currency_exposure(
    exposures: Sequence[dict],
    base_currency: str,
    shock_pct: float = 0.1,
) -> dict:
    """Translate exposures to a base currency and apply a symmetric FX shock.

    Each exposure is ``{currency, amount, spot_to_base}`` where ``spot_to_base``
    is units of base currency per 1 unit of the exposure currency
    (so ``base_value = amount · spot_to_base``). The base currency carries no FX
    risk under the shock.
    """
    if not exposures:
        raise FxInputError("At least one exposure row is required.")
    if len(exposures) > 100:
        raise FxInputError("Exposure input is capped at 100 rows.")
    if not isinstance(base_currency, str) or not base_currency.strip():
        raise FxInputError("base_currency is required.")
    _require_finite("shock_pct", shock_pct)
    if shock_pct < 0 or shock_pct > 1.0:
        raise FxInputError("shock_pct must be between 0 and 1 (a decimal fraction).")

    base = base_currency.strip().upper()
    rows: List[dict] = []
    total = 0.0
    gross = 0.0
    for i, e in enumerate(exposures):
        currency = str(e.get("currency", "")).strip().upper()
        if not currency:
            raise FxInputError(f"exposure row {i} is missing a currency.")
        amount = _require_finite(f"exposure row {i} amount", e.get("amount", float("nan")))
        spot_to_base = _require_finite(f"exposure row {i} spot_to_base", e.get("spot_to_base", float("nan")))
        if spot_to_base <= 0:
            raise FxInputError(f"exposure row {i} spot_to_base must be positive.")
        if abs(amount) > _MAX_NOTIONAL:
            raise FxInputError(f"exposure row {i} amount is out of a sensible range.")
        base_value = amount * spot_to_base
        if not math.isfinite(base_value):
            raise FxInputError(f"exposure row {i} base_value is not finite.")
        total += base_value
        gross += abs(base_value)
        rows.append({"currency": currency, "amount": amount, "spot_to_base": spot_to_base, "base_value": base_value})

    if not math.isfinite(total) or not math.isfinite(gross):
        raise FxInputError("Exposure totals are not finite for these inputs.")

    near_zero_net = gross > 0 and abs(total) <= gross * 1e-6

    out_rows: List[dict] = []
    stress_up = 0.0
    stress_down = 0.0
    for r in rows:
        is_base = r["currency"] == base
        weight = 0.0 if near_zero_net else ((r["base_value"] / total) if total != 0 else 0.0)
        gross_weight = (abs(r["base_value"]) / gross) if gross > 0 else 0.0
        # Base currency has no FX risk under a foreign-vs-base shock.
        pnl_up = 0.0 if is_base else r["base_value"] * shock_pct
        pnl_down = 0.0 if is_base else -r["base_value"] * shock_pct
        if not math.isfinite(pnl_up) or not math.isfinite(pnl_down):
            raise FxInputError("Exposure stress P&L is not finite for these inputs.")
        stress_up += pnl_up
        stress_down += pnl_down
        out_rows.append(
            {
                "currency": r["currency"],
                "amount": _clean(r["amount"]),
                "spot_to_base": _clean(r["spot_to_base"]),
                "base_value": _clean(r["base_value"]),
                "weight_pct": _clean(weight),
                "gross_weight_pct": _clean(gross_weight),
                "stress_pnl_up": _clean(pnl_up),
                "stress_pnl_down": _clean(pnl_down),
            }
        )

    if not math.isfinite(stress_up) or not math.isfinite(stress_down):
        raise FxInputError("Aggregate exposure stress P&L is not finite for these inputs.")

    warnings = [
        "Educational translation + a uniform symmetric shock (all non-base currencies move "
        "together) — not a covariance-based risk model. No live FX rates.",
    ]
    if near_zero_net:
        warnings.append(
            "Net exposure is near zero relative to gross exposure; net percentage weights are "
            "suppressed to avoid misleading large ratios. Use gross exposure for scale."
        )

    return {
        "base_currency": base,
        "shock_pct": _clean(shock_pct),
        "total_exposure": _clean(total),
        "gross_exposure": _clean(gross),
        "rows": out_rows,
        "stress_pnl_up": _clean(stress_up),
        "stress_pnl_down": _clean(stress_down),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Garman-Kohlhagen FX option pricing
# ---------------------------------------------------------------------------


def price_garman_kohlhagen(
    option_type: str,
    spot_rate: float,
    strike: float,
    domestic_rate: float,
    foreign_rate: float,
    volatility: float,
    time_to_expiry: float,
) -> dict:
    """Garman-Kohlhagen (Black-Scholes for FX) price + d1/d2 + Greeks.

    Equivalent to Black-Scholes with ``r = r_d`` and dividend yield ``q = r_f``.
    """
    if option_type not in OPTION_TYPES:
        raise FxInputError("option_type must be 'call' or 'put'.")
    if spot_rate <= 0:
        raise FxInputError("spot_rate must be positive.")
    if strike <= 0:
        raise FxInputError("strike must be positive.")
    if volatility <= 0:
        raise FxInputError("volatility must be positive.")
    if time_to_expiry <= 0:
        raise FxInputError("time_to_expiry must be positive.")
    if time_to_expiry > _MAX_T:
        raise FxInputError(f"time_to_expiry must be no greater than {_MAX_T}.")
    if volatility > 100.0:
        raise FxInputError("volatility must be no greater than 100 (10000%).")
    r_d = _check_rate("domestic_rate", domestic_rate)
    r_f = _check_rate("foreign_rate", foreign_rate)

    sqrt_t = math.sqrt(time_to_expiry)
    vol_sqrt_t = volatility * sqrt_t
    d1 = (math.log(spot_rate / strike) + (r_d - r_f + 0.5 * volatility * volatility) * time_to_expiry) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t

    disc_f = math.exp(-r_f * time_to_expiry)
    disc_d = math.exp(-r_d * time_to_expiry)
    pdf_d1 = normal_pdf(d1)

    if option_type == "call":
        price = spot_rate * disc_f * normal_cdf(d1) - strike * disc_d * normal_cdf(d2)
        delta = disc_f * normal_cdf(d1)
        rho_domestic = strike * time_to_expiry * disc_d * normal_cdf(d2)
        rho_foreign = -time_to_expiry * spot_rate * disc_f * normal_cdf(d1)
        theta = (
            -(spot_rate * disc_f * pdf_d1 * volatility) / (2.0 * sqrt_t)
            + r_f * spot_rate * disc_f * normal_cdf(d1)
            - r_d * strike * disc_d * normal_cdf(d2)
        )
    else:  # put
        price = strike * disc_d * normal_cdf(-d2) - spot_rate * disc_f * normal_cdf(-d1)
        delta = -disc_f * normal_cdf(-d1)
        rho_domestic = -strike * time_to_expiry * disc_d * normal_cdf(-d2)
        rho_foreign = time_to_expiry * spot_rate * disc_f * normal_cdf(-d1)
        theta = (
            -(spot_rate * disc_f * pdf_d1 * volatility) / (2.0 * sqrt_t)
            - r_f * spot_rate * disc_f * normal_cdf(-d1)
            + r_d * strike * disc_d * normal_cdf(-d2)
        )

    gamma = disc_f * pdf_d1 / (spot_rate * vol_sqrt_t)
    vega = spot_rate * disc_f * pdf_d1 * sqrt_t  # per 1.00 (100%) vol change

    if price < -1e-12:
        raise FxInputError("Garman-Kohlhagen price is negative for these inputs.")
    price = max(price, 0.0)

    for name, val in (
        ("price", price),
        ("d1", d1),
        ("d2", d2),
        ("delta", delta),
        ("gamma", gamma),
        ("vega", vega),
        ("theta", theta),
        ("rho_domestic", rho_domestic),
        ("rho_foreign", rho_foreign),
    ):
        if not math.isfinite(val):
            raise FxInputError(f"Garman-Kohlhagen {name} is not finite for these inputs.")

    return {
        "option_type": option_type,
        "price": _clean(price),
        "d1": _clean(d1),
        "d2": _clean(d2),
        "delta": _clean(delta),
        "gamma": _clean(gamma),
        "vega": _clean(vega),
        "theta_annual": _clean(theta),
        "theta_daily": _clean(theta / 365.0),
        "rho_domestic": _clean(rho_domestic),
        "rho_foreign": _clean(rho_foreign),
        "convention": QUOTE_CONVENTION,
        "warnings": [
            "Garman-Kohlhagen assumes constant volatility and lognormal spot — no FX volatility "
            "surface, smile, or skew; educational pricing only.",
        ],
    }
