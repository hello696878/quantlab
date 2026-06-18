"""
Credit Risk Lab v1 — educational credit-risk analytics: the Merton structural
model, a constant-hazard reduced-form survival model, a simplified CDS par-spread
calculator, and risky (defaultable) bond pricing.

Educational / research only.  This is **not** an institutional credit desk, a
production default model, a rating-agency replacement, or a CVA engine:

* No live CDS spreads, no live bond prices, no paid data.
* No full CVA, no credit-portfolio model, no rating-transition matrix.
* Results depend heavily on assumptions about asset value, asset volatility,
  recovery rate, capital structure, liquidity, seniority, covenants, and
  calibration quality.

All outputs are finite and rounded for JSON — never NaN/inf.  The functions are
pure and deterministic, so the math is fully unit-testable.  Reuses
:func:`app.options.normal_cdf` for the Merton (Black-Scholes) terms.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.options import normal_cdf

# Defensive bounds (well outside any sensible educational input).
_MAX_T = 100.0
_MAX_RATE = 10.0  # |risk-free rate| <= 1000%
_MAX_HAZARD = 10.0
_MAX_VALUE = 1e15
_MAX_FREQ = 365


class CreditInputError(ValueError):
    """Raised when credit inputs are logically invalid."""


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


def _require_finite(name: str, value: float) -> float:
    if not math.isfinite(float(value)):
        raise CreditInputError(f"{name} must be finite.")
    return float(value)


def _check_recovery(recovery_rate: float) -> float:
    _require_finite("recovery_rate", recovery_rate)
    if recovery_rate < 0.0 or recovery_rate > 1.0:
        raise CreditInputError("recovery_rate must be between 0 and 1.")
    return float(recovery_rate)


def _check_hazard(hazard_rate: float) -> float:
    _require_finite("hazard_rate", hazard_rate)
    if hazard_rate < 0.0:
        raise CreditInputError("hazard_rate must be non-negative.")
    if hazard_rate > _MAX_HAZARD:
        raise CreditInputError(f"hazard_rate must be no greater than {_MAX_HAZARD}.")
    return float(hazard_rate)


def _check_maturity(name: str, t: float) -> float:
    _require_finite(name, t)
    if t <= 0:
        raise CreditInputError(f"{name} must be positive.")
    if t > _MAX_T:
        raise CreditInputError(f"{name} must be no greater than {_MAX_T}.")
    return float(t)


def _check_frequency(freq: int) -> int:
    if not isinstance(freq, (int,)) or isinstance(freq, bool):
        raise CreditInputError("payment_frequency must be a positive integer.")
    if freq < 1 or freq > _MAX_FREQ:
        raise CreditInputError(f"payment_frequency must be an integer between 1 and {_MAX_FREQ}.")
    return int(freq)


# ---------------------------------------------------------------------------
# Merton structural model
# ---------------------------------------------------------------------------


def compute_distance_to_default(
    asset_value: float,
    debt_face_value: float,
    asset_volatility: float,
    drift: float,
    time_to_maturity: float,
) -> float:
    """DD = [ln(V/D) + (drift − 0.5σ²)T] / (σ√T).

    ``drift`` is the asset return used for the distance to default — the
    risk-free rate (risk-neutral) or a supplied expected asset return.
    """
    vol_sqrt_t = asset_volatility * math.sqrt(time_to_maturity)
    return (
        math.log(asset_value / debt_face_value)
        + (drift - 0.5 * asset_volatility * asset_volatility) * time_to_maturity
    ) / vol_sqrt_t


def compute_merton_default_probability(
    asset_value: float,
    debt_face_value: float,
    asset_volatility: float,
    drift: float,
    time_to_maturity: float,
) -> float:
    """Default probability ``N(−DD)`` for the given drift (risk-neutral if drift=r)."""
    dd = compute_distance_to_default(
        asset_value, debt_face_value, asset_volatility, drift, time_to_maturity
    )
    return normal_cdf(-dd)


def price_merton_credit(
    asset_value: float,
    debt_face_value: float,
    asset_volatility: float,
    risk_free_rate: float,
    time_to_maturity: float,
    recovery_rate: float = 0.4,
    expected_asset_return: Optional[float] = None,
) -> dict:
    """Merton structural credit model: equity as a call on firm assets.

    ``E = V·N(d1) − D·e^{−rT}·N(d2)``; debt ``= V − E``; risk-neutral default
    probability ``= N(−d2)``; credit spread from the implied risky debt yield.
    """
    V = _require_finite("asset_value", asset_value)
    D = _require_finite("debt_face_value", debt_face_value)
    if V <= 0:
        raise CreditInputError("asset_value must be positive.")
    if D <= 0:
        raise CreditInputError("debt_face_value must be positive.")
    if V > _MAX_VALUE or D > _MAX_VALUE:
        raise CreditInputError("asset_value / debt_face_value are out of a sensible range.")
    sigma = _require_finite("asset_volatility", asset_volatility)
    if sigma <= 0:
        raise CreditInputError("asset_volatility must be positive.")
    if sigma > 100:
        raise CreditInputError("asset_volatility must be no greater than 100 (10000%).")
    r = _require_finite("risk_free_rate", risk_free_rate)
    if abs(r) > _MAX_RATE:
        raise CreditInputError("risk_free_rate is out of a sensible range.")
    T = _check_maturity("time_to_maturity", time_to_maturity)
    R = _check_recovery(recovery_rate)
    if expected_asset_return is not None:
        _require_finite("expected_asset_return", expected_asset_return)
        if abs(expected_asset_return) > _MAX_RATE:
            raise CreditInputError("expected_asset_return is out of a sensible range.")

    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(V / D) + (r + 0.5 * sigma * sigma) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t

    disc = math.exp(-r * T)
    equity = V * normal_cdf(d1) - D * disc * normal_cdf(d2)
    equity = max(0.0, equity)
    debt = V - equity
    pd_q = normal_cdf(-d2)

    # Distance to default — uses the supplied expected asset return if given,
    # otherwise the risk-free rate (risk-neutral DD).
    drift = expected_asset_return if expected_asset_return is not None else r
    dd_drift_used = "expected_asset_return" if expected_asset_return is not None else "risk_free_rate"
    dd = compute_distance_to_default(V, D, sigma, drift, T)

    # Risky debt yield + credit spread (continuously compounded).
    if debt > 0:
        risky_yield = -math.log(debt / D) / T
    else:
        risky_yield = float("inf")
    credit_spread = risky_yield - r
    expected_loss = pd_q * (1.0 - R) * D

    warnings: List[str] = [
        "Merton is a stylized single-debt structural model: one zero-coupon debt maturity, constant "
        "asset volatility, and no intermediate default. Real capital structures, liquidity, "
        "seniority, and covenants are not modeled.",
    ]
    if V <= D:
        warnings.append(
            "Assets are at or below the debt face value (V ≤ D): the firm is deeply distressed in "
            "this model and the default probability is high."
        )

    return {
        "equity_value": _clean(equity),
        "debt_value": _clean(debt),
        "asset_value": _clean(V),
        "debt_face_value": _clean(D),
        "d1": _clean(d1),
        "d2": _clean(d2),
        "distance_to_default": _clean(dd),
        "dd_drift_used": dd_drift_used,
        "risk_neutral_default_probability": _clean(pd_q),
        "risky_debt_yield": _clean(risky_yield),
        "credit_spread": _clean(credit_spread),
        "credit_spread_bps": _clean(credit_spread * 1e4, 2),
        "expected_loss": _clean(expected_loss),
        "recovery_rate": _clean(R),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Reduced-form hazard / survival
# ---------------------------------------------------------------------------


def compute_hazard_survival_curve(
    hazard_rate: float,
    recovery_rate: float,
    maturity_years: float,
    risk_free_rate: float,
    points: int = 0,
) -> dict:
    """Constant-hazard survival / default / expected-loss / risky-DF curve.

    ``Q(t) = e^{−λt}``, ``PD(t) = 1 − Q(t)``, ``EL(t) = (1−R)·PD(t)``,
    ``risky_DF(t) = e^{−(r + λ(1−R))·t}``.
    """
    lam = _check_hazard(hazard_rate)
    R = _check_recovery(recovery_rate)
    T = _check_maturity("maturity_years", maturity_years)
    r = _require_finite("risk_free_rate", risk_free_rate)
    if abs(r) > _MAX_RATE:
        raise CreditInputError("risk_free_rate is out of a sensible range.")

    lgd = 1.0 - R
    n = points if points and points > 0 else min(max(int(round(T * 12)), 12), 240)
    curve: List[dict] = []
    for i in range(n + 1):
        t = T * i / n
        survival = math.exp(-lam * t)
        default = 1.0 - survival
        el = lgd * default
        risky_df = math.exp(-(r + lam * lgd) * t)
        curve.append(
            {
                "time": _clean(t),
                "survival_probability": _clean(survival),
                "default_probability": _clean(default),
                "expected_loss": _clean(el),
                "risky_discount_factor": _clean(risky_df),
            }
        )

    survival_T = math.exp(-lam * T)
    return {
        "hazard_rate": _clean(lam),
        "recovery_rate": _clean(R),
        "maturity_years": _clean(T),
        "survival_probability_at_maturity": _clean(survival_T),
        "default_probability_at_maturity": _clean(1.0 - survival_T),
        "expected_loss_at_maturity": _clean(lgd * (1.0 - survival_T)),
        "simple_cds_spread": _clean(lam * lgd),
        "simple_cds_spread_bps": _clean(lam * lgd * 1e4, 2),
        "curve": curve,
        "warnings": [
            "Constant-hazard (flat) reduced-form model — a real hazard term structure is not flat, "
            "and the hazard rate here is an assumption, not calibrated to market CDS or bond prices.",
        ],
    }


# ---------------------------------------------------------------------------
# CDS spread
# ---------------------------------------------------------------------------


def compute_simple_cds_spread(hazard_rate: float, recovery_rate: float) -> float:
    """The classic credit-triangle approximation ``spread ≈ λ·(1−R)``."""
    lam = _check_hazard(hazard_rate)
    R = _check_recovery(recovery_rate)
    return lam * (1.0 - R)


def compute_cds_spread(
    hazard_rate: float,
    recovery_rate: float,
    maturity_years: float,
    risk_free_rate: float,
    payment_frequency: int = 4,
    notional: float = 1_000_000.0,
) -> dict:
    """Discrete protection-leg / premium-leg fair CDS par spread.

    Protection PV = Σ DF(t_i)·(S(t_{i−1}) − S(t_i))·(1−R)·N;
    risky PV01    = Σ DF(t_i)·S(t_i)·Δt·N;
    fair spread   = protection PV / risky PV01.
    """
    lam = _check_hazard(hazard_rate)
    R = _check_recovery(recovery_rate)
    T = _check_maturity("maturity_years", maturity_years)
    r = _require_finite("risk_free_rate", risk_free_rate)
    if abs(r) > _MAX_RATE:
        raise CreditInputError("risk_free_rate is out of a sensible range.")
    freq = _check_frequency(payment_frequency)
    notional = _require_finite("notional", notional)
    if notional <= 0:
        raise CreditInputError("notional must be positive.")
    if notional > _MAX_VALUE:
        raise CreditInputError("notional is out of a sensible range.")

    lgd = 1.0 - R
    dt = 1.0 / freq
    n = max(1, int(round(T * freq)))
    protection_pv = 0.0
    risky_pv01 = 0.0
    prev_survival = 1.0
    for i in range(1, n + 1):
        t = i * dt
        survival = math.exp(-lam * t)
        df = math.exp(-r * t)
        marginal_default = prev_survival - survival
        protection_pv += df * marginal_default * lgd * notional
        risky_pv01 += df * survival * dt * notional
        prev_survival = survival

    fair_spread = protection_pv / risky_pv01 if risky_pv01 > 0 else 0.0
    survival_T = math.exp(-lam * T)
    expected_loss = lgd * (1.0 - survival_T) * notional

    return {
        "hazard_rate": _clean(lam),
        "recovery_rate": _clean(R),
        "maturity_years": _clean(T),
        "payment_frequency": freq,
        "notional": _clean(notional),
        "fair_spread": _clean(fair_spread),
        "fair_spread_bps": _clean(fair_spread * 1e4, 2),
        "simple_spread_bps": _clean(lam * lgd * 1e4, 2),
        "protection_leg_pv": _clean(protection_pv),
        "risky_pv01": _clean(risky_pv01),
        "expected_loss": _clean(expected_loss),
        "survival_probability_at_maturity": _clean(survival_T),
        "warnings": [
            "Simplified par-spread approximation (flat hazard, end-of-period default, no accrual on "
            "default, no upfront/coupon conventions). Real CDS pricing uses a calibrated hazard term "
            "structure and ISDA conventions. Not a tradable quote.",
        ],
    }


# ---------------------------------------------------------------------------
# Risky bond pricing
# ---------------------------------------------------------------------------


def _solve_flat_yield(cashflows: List[Tuple[float, float]], price: float) -> Optional[float]:
    """Bisection for the continuously-compounded flat yield matching ``price``."""

    def pv(y: float) -> float:
        return sum(cf * math.exp(-y * t) for t, cf in cashflows)

    lo, hi = -0.99, 5.0
    f_lo = pv(lo) - price
    f_hi = pv(hi) - price
    if f_lo * f_hi > 0:
        return None  # price not bracketed
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = pv(mid) - price
        if abs(f_mid) < 1e-10:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return 0.5 * (lo + hi)


def price_risky_bond(
    face_value: float,
    coupon_rate: float,
    maturity_years: float,
    coupon_frequency: int,
    risk_free_rate: float,
    hazard_rate: float,
    recovery_rate: float,
) -> dict:
    """Reduced-form risky bond: survival-weighted promised flows + recovery leg."""
    face = _require_finite("face_value", face_value)
    if face <= 0:
        raise CreditInputError("face_value must be positive.")
    if face > _MAX_VALUE:
        raise CreditInputError("face_value is out of a sensible range.")
    coupon_rate = _require_finite("coupon_rate", coupon_rate)
    if coupon_rate < 0:
        raise CreditInputError("coupon_rate must be non-negative.")
    if coupon_rate > 1.0:
        raise CreditInputError("coupon_rate must be no greater than 1.0 (100%).")
    T = _check_maturity("maturity_years", maturity_years)
    freq = _check_frequency(coupon_frequency)
    r = _require_finite("risk_free_rate", risk_free_rate)
    if abs(r) > _MAX_RATE:
        raise CreditInputError("risk_free_rate is out of a sensible range.")
    lam = _check_hazard(hazard_rate)
    R = _check_recovery(recovery_rate)

    dt = 1.0 / freq
    n = max(1, int(round(T * freq)))
    coupon = face * coupon_rate / freq

    pv_coupons = 0.0
    pv_principal = 0.0
    pv_recovery = 0.0
    rf_price = 0.0
    prev_survival = 1.0
    promised_cf: List[Tuple[float, float]] = []
    rows: List[dict] = []

    for i in range(1, n + 1):
        t = i * dt
        survival = math.exp(-lam * t)
        df = math.exp(-r * t)
        marginal_default = prev_survival - survival
        is_last = i == n
        cash_flow = coupon + (face if is_last else 0.0)

        pv_coupons += coupon * survival * df
        if is_last:
            pv_principal += face * survival * df
        recovery_i = R * face * marginal_default * df
        pv_recovery += recovery_i
        rf_price += cash_flow * df  # risk-free: no default
        promised_cf.append((t, cash_flow))

        survival_weighted_pv = cash_flow * survival * df
        rows.append(
            {
                "time": _clean(t),
                "cash_flow": _clean(cash_flow),
                "survival_probability": _clean(survival),
                "discount_factor": _clean(df),
                "present_value": _clean(survival_weighted_pv),
                "recovery_pv": _clean(recovery_i),
            }
        )
        prev_survival = survival

    risky_price = pv_coupons + pv_principal + pv_recovery
    survival_T = math.exp(-lam * T)
    expected_loss = (1.0 - R) * (1.0 - survival_T) * face

    # Credit spread from a flat yield that reprices the promised flows to the risky price.
    y = _solve_flat_yield(promised_cf, risky_price)
    if y is None:
        credit_spread = None
        risky_yield = None
        warnings_spread: List[str] = [
            "Could not solve a flat risky yield for these inputs; credit spread omitted."
        ]
    else:
        risky_yield = y
        credit_spread = y - r
        warnings_spread = []

    return {
        "risky_bond_price": _clean(risky_price),
        "risk_free_bond_price": _clean(rf_price),
        "pv_coupons": _clean(pv_coupons),
        "pv_principal": _clean(pv_principal),
        "pv_recovery": _clean(pv_recovery),
        "risky_yield": _clean(risky_yield),
        "credit_spread": _clean(credit_spread),
        "credit_spread_bps": _clean(credit_spread * 1e4, 2) if credit_spread is not None else None,
        "expected_loss": _clean(expected_loss),
        "survival_probability_at_maturity": _clean(survival_T),
        "face_value": _clean(face),
        "coupon_rate": _clean(coupon_rate),
        "maturity_years": _clean(T),
        "coupon_frequency": freq,
        "cash_flows": rows,
        "warnings": [
            "Reduced-form risky bond: flat hazard, deterministic recovery, end-of-period default, "
            "no liquidity/tax/optionality. The credit spread is a flat-yield approximation, not an "
            "OAS or a market quote.",
            *warnings_spread,
        ],
    }


# ---------------------------------------------------------------------------
# Credit spread from prices (standalone helper)
# ---------------------------------------------------------------------------


def compute_credit_spread_from_prices(
    promised_cashflows: List[Tuple[float, float]],
    risky_price: float,
    risk_free_rate: float,
) -> Optional[float]:
    """Flat-yield credit spread: solve y from the promised flows, return y − r."""
    y = _solve_flat_yield(promised_cashflows, risky_price)
    if y is None:
        return None
    return y - risk_free_rate
