"""
Mortgage & MBS prepayment analytics (Phase 22.1) — pure, deterministic.

Mortgage cash flows with scheduled principal/interest, CPR→SMM and a simplified
educational PSA prepayment ramp, MBS cash-flow decomposition, weighted average
life (WAL), price from a discount rate, modified-duration / convexity
approximations, and rate / prepayment-speed stress scenarios.

All outputs are finite by construction (divisions guarded, balances floored at
0), so no NaN/Infinity reaches the API. Educational only — not investment,
lending, legal, tax, or valuation advice.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.real_estate.models import (
    DurationConvexity,
    MbsCashFlowRow,
    MbsCashFlowSummary,
    MbsScenarioResult,
    MortgageMbsAnalysisResponse,
    MortgageMbsRequest,
    MortgagePoolInput,
    PoolSummary,
    PrepaymentAssumption,
    PrepaymentInput,
    PsaPathPoint,
    ValuationAssumption,
    ValuationInput,
)

_EPS = 1e-9
DISCLAIMER = (
    "Static illustrative sample data. Mortgage and MBS analytics are educational "
    "and not investment, lending, legal, tax, or valuation advice."
)

# id, name, description, prepay multiplier (relative to base), rate shock (decimal)
_SCENARIOS = [
    ("base_psa", "Base PSA", "Base prepayment speed and discount rate.", 1.0, 0.0),
    ("fast_prepayment", "Fast prepayment", "Prepayments ~2x base speed.", 2.0, 0.0),
    ("slow_prepayment", "Slow prepayment", "Prepayments ~0.5x base speed.", 0.5, 0.0),
    ("rate_up_100", "Rate up 100 bps", "Discount rate +1.00%.", 1.0, 0.01),
    ("rate_down_100", "Rate down 100 bps", "Discount rate −1.00%.", 1.0, -0.01),
    ("extension_risk", "Extension risk", "Slower prepayments (~0.6x) with rates +1%.", 0.6, 0.01),
    ("refinance_wave", "Refinance wave", "Faster prepayments (~2.5x) with rates −1%.", 2.5, -0.01),
]


# --------------------------------------------------------------------------- #
# CPR / SMM / PSA
# --------------------------------------------------------------------------- #
def cpr_to_smm(cpr: float) -> float:
    """Single monthly mortality from an annual conditional prepayment rate."""
    cpr = min(max(cpr, 0.0), 0.9999)
    return 1.0 - (1.0 - cpr) ** (1.0 / 12.0)


def psa_cpr(pool_age_month: int, psa_speed: float) -> float:
    """Simplified educational PSA: 100 PSA ramps 0.2%→6% over 30 months, then flat."""
    ramp = 0.06 * min(max(pool_age_month, 0), 30) / 30.0  # 100 PSA annual CPR
    return min((psa_speed / 100.0) * ramp, 0.9999)


def _payment(balance: float, monthly_rate: float, months: int) -> float:
    if months <= 0:
        return balance
    if monthly_rate <= _EPS:
        return balance / months
    return balance * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-months))


# --------------------------------------------------------------------------- #
# Cash-flow projection
# --------------------------------------------------------------------------- #
class _Row:
    __slots__ = (
        "month", "beg", "sched_prin", "prepay", "interest", "cf", "end",
        "total_prin", "cpr", "smm", "pool_age",
    )

    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


def project(
    pool: MortgagePoolInput,
    model: str,
    cpr_const: Optional[float],
    psa_speed: Optional[float],
    lag: int,
    stress_mult: float,
) -> List[_Row]:
    coupon = pool.coupon_rate
    net_coupon = coupon - pool.servicing_fee_rate
    r_m = coupon / 12.0
    n = pool.remaining_term_months
    balance = pool.current_balance
    pmt = _payment(balance, r_m, n)

    rows: List[_Row] = []
    for t in range(1, n + 1):
        if balance <= 1e-4:
            break
        gross_interest = balance * r_m
        sched_prin = min(max(pmt - gross_interest, 0.0), balance)

        if t <= lag:
            cpr = 0.0
        elif model == "constant_cpr":
            cpr = (cpr_const if cpr_const is not None else 0.06) * stress_mult
        else:
            age = pool.seasoning_months + t
            cpr = psa_cpr(age, (psa_speed if psa_speed is not None else 100.0)) * stress_mult
        cpr = min(max(cpr, 0.0), 0.9999)
        smm = cpr_to_smm(cpr)

        prepay = smm * max(balance - sched_prin, 0.0)
        total_prin = min(sched_prin + prepay, balance)
        prepay = total_prin - sched_prin
        net_interest = balance * net_coupon / 12.0
        cf = net_interest + total_prin
        end = max(balance - total_prin, 0.0)
        rows.append(
            _Row(
                month=t,
                beg=balance,
                sched_prin=sched_prin,
                prepay=prepay,
                interest=net_interest,
                cf=cf,
                end=end,
                total_prin=total_prin,
                cpr=cpr,
                smm=smm,
                pool_age=pool.seasoning_months + t,
            )
        )
        balance = end
    return rows


def price_of(rows: List[_Row], annual_yield: float) -> float:
    y = annual_yield / 12.0
    total = 0.0
    for row in rows:
        total += row.cf / ((1.0 + y) ** row.month)
    return total


def wal_of(rows: List[_Row]) -> float:
    num = sum((row.month / 12.0) * row.total_prin for row in rows)
    den = sum(row.total_prin for row in rows)
    return float(num / den) if den > _EPS else 0.0


def duration_convexity(rows: List[_Row], y: float, shock_bps: float = 25.0) -> Tuple[float, float, float, float, float]:
    dy = shock_bps / 10000.0
    p0 = price_of(rows, y)
    pu = price_of(rows, y + dy)
    pd = price_of(rows, max(y - dy, 0.0))
    if p0 <= _EPS or dy <= _EPS:
        return p0, pu, pd, 0.0, 0.0
    duration = (pd - pu) / (2.0 * p0 * dy)
    convexity = (pd + pu - 2.0 * p0) / (p0 * dy * dy)
    return p0, pu, pd, float(duration), float(convexity)


def _solve_yield(rows: List[_Row], target_price: float) -> Optional[float]:
    """Bisection for the yield that prices the cash flows to ``target_price``."""
    lo, hi = 0.0, 0.5
    f_lo = price_of(rows, lo) - target_price
    f_hi = price_of(rows, hi) - target_price
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        val = price_of(rows, mid) - target_price
        if abs(val) < 1e-6:
            return float(mid)
        if f_lo * val < 0:
            hi = mid
        else:
            lo, f_lo = mid, val
    return float(0.5 * (lo + hi))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_mbs(req: MortgageMbsRequest) -> MortgageMbsAnalysisResponse:
    pool = req.pool
    prepay = req.prepayment
    val = req.valuation
    net_coupon = pool.coupon_rate - pool.servicing_fee_rate
    base_stress = float(val.prepayment_stress_multiplier)
    base_y = max(val.discount_rate + val.rate_shock_bps / 10000.0, 0.0)
    current = pool.current_balance

    def project_scenario(mult: float, rate_shock: float) -> Tuple[List[_Row], float]:
        rows = project(
            pool, prepay.model, prepay.cpr, prepay.psa_speed,
            prepay.prepayment_lag_months, base_stress * mult,
        )
        y = max(base_y + rate_shock, 0.0)
        return rows, y

    base_rows, base_y_eff = project_scenario(1.0, 0.0)
    base_price = price_of(base_rows, base_y_eff)
    base_price_100 = 100.0 * base_price / current if current > _EPS else 0.0
    base_wal = wal_of(base_rows)

    total_sched = sum(r.sched_prin for r in base_rows)
    total_prepay = sum(r.prepay for r in base_rows)
    total_prin = sum(r.total_prin for r in base_rows)
    total_int = sum(r.interest for r in base_rows)
    total_cf = sum(r.cf for r in base_rows)
    final_balance = base_rows[-1].end if base_rows else current

    p0, pu, pd, dur, conv = duration_convexity(base_rows, base_y_eff)
    yield_estimate = None
    if val.price is not None:
        yield_estimate = _solve_yield(base_rows, val.price)

    # PSA / CPR path — show the ramp + annual points (capped).
    psa_path: List[PsaPathPoint] = []
    for r in base_rows:
        if r.month <= 36 or r.month % 12 == 0:
            psa_path.append(
                PsaPathPoint(month=r.month, pool_age_month=r.pool_age, cpr=r.cpr, smm=r.smm)
            )
        if len(psa_path) >= 70:
            break

    schedule = [
        MbsCashFlowRow(
            month=r.month,
            beginning_balance=r.beg,
            scheduled_principal=r.sched_prin,
            prepayment_principal=r.prepay,
            interest=r.interest,
            total_cash_flow=r.cf,
            ending_balance=r.end,
        )
        for r in base_rows[:24]
    ]

    scenarios: List[MbsScenarioResult] = []
    for sid, name, desc, mult, rate_shock in _SCENARIOS:
        rows, y = project_scenario(mult, rate_shock)
        price = price_of(rows, y)
        price_100 = 100.0 * price / current if current > _EPS else 0.0
        _, _, _, sdur, sconv = duration_convexity(rows, y)
        scenarios.append(
            MbsScenarioResult(
                id=sid,
                name=name,
                description=desc,
                price_100=price_100,
                wal=wal_of(rows),
                duration=sdur,
                convexity=sconv,
                total_interest=sum(r.interest for r in rows),
                total_principal=sum(r.total_prin for r in rows),
                final_balance=rows[-1].end if rows else current,
                notes=["Illustrative deterministic scenario — not a forecast."],
            )
        )

    return MortgageMbsAnalysisResponse(
        pool_summary=PoolSummary(
            pool_name=pool.pool_name,
            original_balance=pool.original_balance,
            current_balance=pool.current_balance,
            pool_factor=pool.current_balance / pool.original_balance if pool.original_balance > _EPS else 0.0,
            coupon_rate=pool.coupon_rate,
            servicing_fee_rate=pool.servicing_fee_rate,
            net_coupon=net_coupon,
            remaining_term_months=pool.remaining_term_months,
            seasoning_months=pool.seasoning_months,
        ),
        prepayment_assumption=PrepaymentAssumption(
            model=prepay.model,
            cpr=prepay.cpr,
            psa_speed=prepay.psa_speed,
            prepayment_lag_months=prepay.prepayment_lag_months,
            prepayment_stress_multiplier=base_stress,
        ),
        valuation_assumption=ValuationAssumption(
            discount_rate=val.discount_rate,
            net_coupon=net_coupon,
            price=val.price,
        ),
        price=base_price,
        price_100=base_price_100,
        wal=base_wal,
        cash_flow_summary=MbsCashFlowSummary(
            num_months=len(base_rows),
            total_interest=total_int,
            total_scheduled_principal=total_sched,
            total_prepayment=total_prepay,
            total_principal=total_prin,
            total_cash_flow=total_cf,
            final_balance=final_balance,
        ),
        cash_flow_schedule=schedule,
        psa_path=psa_path,
        duration_convexity=DurationConvexity(
            shock_bps=25.0,
            price_base=100.0 * p0 / current if current > _EPS else 0.0,
            price_up=100.0 * pu / current if current > _EPS else 0.0,
            price_down=100.0 * pd / current if current > _EPS else 0.0,
            duration=dur,
            convexity=conv,
            yield_estimate=yield_estimate,
        ),
        scenario_results=scenarios,
        notes=[
            "Scheduled payment is computed once from the current balance and "
            "remaining term; scheduled principal = payment − gross interest.",
            "CPR→SMM uses SMM = 1 − (1 − CPR)^(1/12); the PSA ramp is a simplified "
            "educational 100-PSA ramp scaled by the PSA speed and pool age.",
            "MBS interest accrues on the net (pass-through) coupon; price discounts "
            "the projected cash flows; WAL/duration/convexity are educational "
            "approximations that hold the projected cash flows fixed.",
            "Scenario results are deterministic illustrative stresses, not forecasts.",
        ],
        disclaimer=DISCLAIMER,
    )
