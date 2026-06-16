"""
Yield Curve Lab v1 — zero rates, discount factors, forward rates, curve shocks,
and basic fixed-rate bond pricing (duration / convexity / DV01).

Educational / research only.  This is **not** an institutional fixed-income
system: no live rates feed, no full swap-curve bootstrapping, no short-rate
models (Vasicek / CIR / Hull-White), no credit curve.

Results depend on the curve construction, the **compounding convention**, the
**interpolation method**, day-count assumptions, and data quality.  All curves
are **synthetic or manually entered** — never claimed to be live market data.

All outputs are finite and rounded for JSON — never NaN/inf.  The functions are
pure and deterministic, so the math is fully unit-testable.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Compounding = str  # "annual" | "semiannual" | "continuous"
Interpolation = str  # "linear_zero" | "linear_discount"

COMPOUNDINGS = ("annual", "semiannual", "continuous")
INTERPOLATIONS = ("linear_zero", "linear_discount")
COUPON_FREQUENCIES = (1, 2, 4, 12)

# Synthetic sample curve for education — NOT current market data.
SAMPLE_CURVE = [
    {"maturity_years": 0.25, "zero_rate": 0.0525},
    {"maturity_years": 0.5, "zero_rate": 0.0515},
    {"maturity_years": 1.0, "zero_rate": 0.0490},
    {"maturity_years": 2.0, "zero_rate": 0.0450},
    {"maturity_years": 5.0, "zero_rate": 0.0410},
    {"maturity_years": 10.0, "zero_rate": 0.0400},
    {"maturity_years": 30.0, "zero_rate": 0.0420},
]


class CurveInputError(ValueError):
    """Raised when curve / bond inputs are structurally invalid."""


def _clean(value: Optional[float], digits: int = 8) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


def generate_sample_yield_curve() -> List[dict]:
    return [dict(p) for p in SAMPLE_CURVE]


# ---------------------------------------------------------------------------
# Validation / sorting
# ---------------------------------------------------------------------------


def validate_curve_points(points: Sequence[dict]) -> List[dict]:
    """Validate, sort by maturity, and reject duplicate maturities."""
    if len(points) < 2:
        raise CurveInputError("At least two curve points are required for interpolation.")
    cleaned = []
    seen = set()
    for p in points:
        try:
            t = float(p["maturity_years"])
            r = float(p["zero_rate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CurveInputError("Each curve point needs maturity_years and zero_rate.") from exc
        if not (math.isfinite(t) and math.isfinite(r)):
            raise CurveInputError("Curve maturities and zero rates must be finite.")
        if t <= 0:
            raise CurveInputError("maturity_years must be positive.")
        key = round(t, 9)
        if key in seen:
            raise CurveInputError(f"Duplicate maturity {t} years; maturities must be unique.")
        seen.add(key)
        cleaned.append({"maturity_years": t, "zero_rate": r})
    cleaned.sort(key=lambda x: x["maturity_years"])
    return cleaned


# ---------------------------------------------------------------------------
# Discount factor <-> zero rate
# ---------------------------------------------------------------------------


def zero_rate_to_discount_factor(rate: float, t: float, compounding: Compounding) -> float:
    if not (math.isfinite(float(rate)) and math.isfinite(float(t))):
        raise CurveInputError("rate and maturity must be finite.")
    if t <= 0:
        raise CurveInputError("maturity must be positive.")
    if compounding == "continuous":
        return math.exp(-rate * t)
    if compounding == "annual":
        if 1.0 + rate <= 0:
            raise CurveInputError("annual compounding requires 1 + rate > 0.")
        return 1.0 / (1.0 + rate) ** t
    if compounding == "semiannual":
        if 1.0 + rate / 2.0 <= 0:
            raise CurveInputError("semiannual compounding requires 1 + rate / 2 > 0.")
        return 1.0 / (1.0 + rate / 2.0) ** (2.0 * t)
    raise CurveInputError(f"Unknown compounding '{compounding}'.")


def discount_factor_to_zero_rate(df: float, t: float, compounding: Compounding) -> float:
    if not (math.isfinite(float(df)) and math.isfinite(float(t))):
        raise CurveInputError("discount factor and maturity must be finite.")
    if t <= 0:
        raise CurveInputError("maturity must be positive.")
    if df <= 0:
        raise CurveInputError("discount factor must be positive.")
    if compounding == "continuous":
        return -math.log(df) / t
    if compounding == "annual":
        return df ** (-1.0 / t) - 1.0
    if compounding == "semiannual":
        return 2.0 * (df ** (-1.0 / (2.0 * t)) - 1.0)
    raise CurveInputError(f"Unknown compounding '{compounding}'.")


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def interpolate_zero_rate(points: Sequence[dict], t: float) -> Tuple[float, bool]:
    """Linear interpolation on zero rates. Returns ``(rate, out_of_range)``.

    Outside the curve range the nearest endpoint rate is clamped (out_of_range
    flagged so callers can warn).
    """
    mats = [p["maturity_years"] for p in points]
    rates = [p["zero_rate"] for p in points]
    if t <= mats[0]:
        return rates[0], t < mats[0]
    if t >= mats[-1]:
        return rates[-1], t > mats[-1]
    for i in range(1, len(mats)):
        if t <= mats[i]:
            t0, t1 = mats[i - 1], mats[i]
            r0, r1 = rates[i - 1], rates[i]
            w = (t - t0) / (t1 - t0)
            return r0 + w * (r1 - r0), False
    return rates[-1], False  # pragma: no cover


def interpolate_discount_factor(
    points: Sequence[dict], t: float, compounding: Compounding
) -> Tuple[float, bool]:
    """Linear interpolation on discount factors → effective zero rate."""
    mats = [p["maturity_years"] for p in points]
    rates = [p["zero_rate"] for p in points]
    dfs = [zero_rate_to_discount_factor(p["zero_rate"], p["maturity_years"], compounding) for p in points]
    if t <= mats[0]:
        return rates[0], t < mats[0]
    if t >= mats[-1]:
        return rates[-1], t > mats[-1]
    for i in range(1, len(mats)):
        if t <= mats[i]:
            t0, t1 = mats[i - 1], mats[i]
            d0, d1 = dfs[i - 1], dfs[i]
            w = (t - t0) / (t1 - t0)
            df = d0 + w * (d1 - d0)
            return discount_factor_to_zero_rate(df, t, compounding), False
    return _df_rate(dfs[-1], t, compounding), False  # pragma: no cover


def _df_rate(df: float, t: float, compounding: Compounding) -> float:
    return discount_factor_to_zero_rate(df, t, compounding)


def _interpolate(
    points: Sequence[dict], t: float, compounding: Compounding, interpolation: Interpolation
) -> Tuple[float, bool]:
    if interpolation == "linear_discount":
        return interpolate_discount_factor(points, t, compounding)
    return interpolate_zero_rate(points, t)


# ---------------------------------------------------------------------------
# Discount curve / forward rates
# ---------------------------------------------------------------------------


def compute_discount_curve(points: Sequence[dict], compounding: Compounding) -> List[dict]:
    out = []
    for p in points:
        df = zero_rate_to_discount_factor(p["zero_rate"], p["maturity_years"], compounding)
        out.append(
            {
                "maturity_years": _clean(p["maturity_years"]),
                "zero_rate": _clean(p["zero_rate"]),
                "discount_factor": _clean(df),
            }
        )
    return out


def compute_forward_rates(points: Sequence[dict], compounding: Compounding) -> List[dict]:
    """Continuously-compounded forward rates implied by the discount factors."""
    out = []
    for i in range(1, len(points)):
        t1, t2 = points[i - 1]["maturity_years"], points[i]["maturity_years"]
        if t2 <= t1:
            continue
        df1 = zero_rate_to_discount_factor(points[i - 1]["zero_rate"], t1, compounding)
        df2 = zero_rate_to_discount_factor(points[i]["zero_rate"], t2, compounding)
        if df1 <= 0 or df2 <= 0:
            continue
        fwd = -math.log(df2 / df1) / (t2 - t1)
        out.append({"start_year": _clean(t1), "end_year": _clean(t2), "forward_rate": _clean(fwd)})
    return out


# ---------------------------------------------------------------------------
# Curve shocks
# ---------------------------------------------------------------------------


def apply_curve_shock(points: Sequence[dict], shock_type: str, shock_bps: float) -> List[dict]:
    """Apply an educational curve shock. Returns new shocked points."""
    shock = shock_bps / 10000.0
    mats = [p["maturity_years"] for p in points]
    t_min, t_max = mats[0], mats[-1]
    span = (t_max - t_min) or 1.0

    out = []
    for p in points:
        t = p["maturity_years"]
        u = (t - t_min) / span  # 0 at short end, 1 at long end
        if shock_type == "parallel":
            shift = shock
        elif shock_type == "steepener":
            shift = shock * (u - 0.5)  # short down, long up
        elif shock_type == "flattener":
            shift = shock * (0.5 - u)  # short up, long down
        elif shock_type == "butterfly":
            shift = shock * (1.0 - 4.0 * abs(u - 0.5))  # belly up, wings down
        else:
            raise CurveInputError(f"Unknown shock_type '{shock_type}'.")
        out.append({"maturity_years": t, "zero_rate": p["zero_rate"] + shift})
    return out


# ---------------------------------------------------------------------------
# Bond pricing
# ---------------------------------------------------------------------------


def _bond_cashflows(
    face_value: float, coupon_rate: float, maturity_years: float, freq: int
) -> List[Tuple[float, float]]:
    periods = maturity_years * freq
    n = int(round(periods))
    if not math.isclose(periods, n, rel_tol=0.0, abs_tol=1e-9):
        raise CurveInputError(
            "maturity_years × coupon_frequency must be an integer number of coupon periods."
        )
    if n < 1:
        raise CurveInputError("maturity_years × coupon_frequency must be at least 1 period.")
    coupon = face_value * coupon_rate / freq
    flows: List[Tuple[float, float]] = []
    for k in range(1, n + 1):
        t = k / freq
        cf = coupon + (face_value if k == n else 0.0)
        flows.append((t, cf))
    return flows


def price_bond_from_ytm(
    face_value: float, coupon_rate: float, maturity_years: float, freq: int, ytm: float
) -> Tuple[float, List[dict]]:
    if 1.0 + ytm / freq <= 0:
        raise CurveInputError("yield_to_maturity is too negative for the coupon frequency.")
    flows = _bond_cashflows(face_value, coupon_rate, maturity_years, freq)
    rows = []
    price = 0.0
    for t, cf in flows:
        df = 1.0 / (1.0 + ytm / freq) ** (freq * t)
        pv = cf * df
        price += pv
        rows.append({"time_years": _clean(t), "cash_flow": _clean(cf), "discount_factor": _clean(df), "present_value": _clean(pv)})
    return price, rows


def price_bond_from_curve(
    face_value: float,
    coupon_rate: float,
    maturity_years: float,
    freq: int,
    points: Sequence[dict],
    compounding: Compounding,
    interpolation: Interpolation,
) -> Tuple[float, List[dict], List[str]]:
    flows = _bond_cashflows(face_value, coupon_rate, maturity_years, freq)
    warnings: List[str] = []
    warned_range = False
    rows = []
    price = 0.0
    for t, cf in flows:
        rate, oor = _interpolate(points, t, compounding, interpolation)
        if oor and not warned_range:
            warnings.append(
                "Some cash flows fall outside the curve's maturity range; the nearest endpoint "
                "rate was clamped."
            )
            warned_range = True
        df = zero_rate_to_discount_factor(rate, t, compounding)
        pv = cf * df
        price += pv
        rows.append({"time_years": _clean(t), "cash_flow": _clean(cf), "discount_factor": _clean(df), "present_value": _clean(pv)})
    return price, rows, warnings


def compute_duration_convexity(
    rows: Sequence[dict], price: float, freq: int, ytm: Optional[float]
) -> dict:
    """Macaulay/modified duration, DV01, and convexity (YTM-mode closed form)."""
    if price <= 0:
        return {"macaulay_duration": None, "modified_duration": None, "dv01": None, "convexity": None}
    macaulay = sum(r["time_years"] * r["present_value"] for r in rows) / price
    if ytm is not None:
        modified = macaulay / (1.0 + ytm / freq)
        convexity = sum(
            r["present_value"] * r["time_years"] * (r["time_years"] + 1.0 / freq) for r in rows
        ) / (price * (1.0 + ytm / freq) ** 2)
        dv01 = modified * price * 1e-4
    else:
        modified = None
        convexity = None
        dv01 = None
    return {
        "macaulay_duration": _clean(macaulay),
        "modified_duration": _clean(modified) if modified is not None else None,
        "dv01": _clean(dv01) if dv01 is not None else None,
        "convexity": _clean(convexity) if convexity is not None else None,
    }


# ---------------------------------------------------------------------------
# Orchestrators (route entry points)
# ---------------------------------------------------------------------------


def build_curve_analytics(
    points: Sequence[dict], compounding: Compounding, interpolation: Interpolation
) -> dict:
    if compounding not in COMPOUNDINGS:
        raise CurveInputError(f"compounding must be one of {COMPOUNDINGS}.")
    if interpolation not in INTERPOLATIONS:
        raise CurveInputError(f"interpolation must be one of {INTERPOLATIONS}.")
    pts = validate_curve_points(points)
    return {
        "compounding": compounding,
        "interpolation": interpolation,
        "curve": compute_discount_curve(pts, compounding),
        "forward_rates": compute_forward_rates(pts, compounding),
        "warnings": [
            "Synthetic / manually-entered curve — not live market data. Forward rates are "
            "continuously compounded, implied by the discount factors, and not guaranteed forecasts.",
        ],
    }


def shock_analytics(
    points: Sequence[dict], shock_type: str, shock_bps: float, compounding: Compounding
) -> dict:
    if compounding not in COMPOUNDINGS:
        raise CurveInputError(f"compounding must be one of {COMPOUNDINGS}.")
    if shock_type not in ("parallel", "steepener", "flattener", "butterfly"):
        raise CurveInputError("shock_type must be parallel, steepener, flattener, or butterfly.")
    if not math.isfinite(float(shock_bps)):
        raise CurveInputError("shock_bps must be finite.")
    pts = validate_curve_points(points)
    shocked = apply_curve_shock(pts, shock_type, shock_bps)
    original_curve = compute_discount_curve(pts, compounding)
    shocked_curve = compute_discount_curve(shocked, compounding)
    changes = []
    for o, s in zip(pts, shocked):
        changes.append(
            {
                "maturity_years": _clean(o["maturity_years"]),
                "original_rate": _clean(o["zero_rate"]),
                "shocked_rate": _clean(s["zero_rate"]),
                "change_bps": _clean((s["zero_rate"] - o["zero_rate"]) * 10000.0, 4),
            }
        )
    return {
        "shock_type": shock_type,
        "shock_bps": _clean(shock_bps, 4),
        "compounding": compounding,
        "original_curve": original_curve,
        "shocked_curve": shocked_curve,
        "changes": changes,
        "warnings": ["Educational curve shock — not a realistic scenario-generation model."],
    }


def bond_analytics(
    face_value: float,
    coupon_rate: float,
    maturity_years: float,
    coupon_frequency: int,
    pricing_mode: str,
    yield_to_maturity: Optional[float],
    curve_points: Optional[Sequence[dict]],
    compounding: Compounding,
    interpolation: Interpolation,
) -> dict:
    if not math.isfinite(face_value) or face_value <= 0:
        raise CurveInputError("face_value must be positive.")
    if not math.isfinite(maturity_years) or maturity_years <= 0:
        raise CurveInputError("maturity_years must be positive.")
    if coupon_frequency not in COUPON_FREQUENCIES:
        raise CurveInputError(f"coupon_frequency must be one of {COUPON_FREQUENCIES}.")
    if not (math.isfinite(coupon_rate) and coupon_rate >= 0):
        raise CurveInputError("coupon_rate must be finite and non-negative.")

    warnings: List[str] = []
    if pricing_mode == "ytm":
        if yield_to_maturity is None or not math.isfinite(yield_to_maturity):
            raise CurveInputError("yield_to_maturity is required for YTM pricing.")
        price, rows = price_bond_from_ytm(
            face_value, coupon_rate, maturity_years, coupon_frequency, yield_to_maturity
        )
        risk = compute_duration_convexity(rows, price, coupon_frequency, yield_to_maturity)
    elif pricing_mode == "curve":
        if not curve_points:
            raise CurveInputError("curve_points are required for curve discounting.")
        if compounding not in COMPOUNDINGS:
            raise CurveInputError(f"compounding must be one of {COMPOUNDINGS}.")
        pts = validate_curve_points(curve_points)
        price, rows, warnings = price_bond_from_curve(
            face_value, coupon_rate, maturity_years, coupon_frequency, pts, compounding, interpolation
        )
        # Macaulay from PV-weighted times; DV01 / convexity via finite-difference reprice.
        risk = compute_duration_convexity(rows, price, coupon_frequency, None)
        bump = 1e-4  # 1 bp parallel
        up = apply_curve_shock(pts, "parallel", 1.0)
        down = apply_curve_shock(pts, "parallel", -1.0)
        p_up, _r1, _w1 = price_bond_from_curve(face_value, coupon_rate, maturity_years, coupon_frequency, up, compounding, interpolation)
        p_down, _r2, _w2 = price_bond_from_curve(face_value, coupon_rate, maturity_years, coupon_frequency, down, compounding, interpolation)
        dv01 = (p_down - p_up) / 2.0  # price change per 1 bp (down minus up) / 2
        modified = dv01 / (price * bump) if price > 0 else None
        convexity = (p_up + p_down - 2.0 * price) / (price * bump * bump) if price > 0 else None
        risk["modified_duration"] = _clean(modified) if modified is not None else None
        risk["dv01"] = _clean(abs(dv01))
        risk["convexity"] = _clean(convexity) if convexity is not None else None
    else:
        raise CurveInputError("pricing_mode must be 'ytm' or 'curve'.")

    warnings.append(
        "Simplified clean-price approximation — no accrued interest, day-count, or settlement "
        "conventions. Educational only."
    )
    return {
        "pricing_mode": pricing_mode,
        "price": _clean(price),
        "face_value": _clean(face_value),
        "coupon_rate": _clean(coupon_rate),
        "maturity_years": _clean(maturity_years),
        "coupon_frequency": coupon_frequency,
        "yield_to_maturity": _clean(yield_to_maturity) if yield_to_maturity is not None else None,
        "macaulay_duration": risk["macaulay_duration"],
        "modified_duration": risk["modified_duration"],
        "dv01": risk["dv01"],
        "convexity": risk["convexity"],
        "cash_flows": rows,
        "warnings": warnings,
    }
