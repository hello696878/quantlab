"""
Real Estate Lab analytics (Phase 22.0) — pure, deterministic computation.

Income-property valuation (NOI, cap rate), mortgage amortization, leverage
(LTV, DSCR), levered cash flow (cash-on-cash, IRR, equity multiple), six
deterministic stress scenarios, and a simple REIT NAV discount/premium example.

All outputs are finite by construction (divisions are guarded and the IRR solver
returns ``None`` with a note when it cannot bracket a root), so no NaN/Infinity
reaches the API. Educational only — not investment / tax / legal / lending advice.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.real_estate.models import (
    AmortRow,
    CashFlowYear,
    DebtInput,
    DebtMetrics,
    IncomeStatement,
    LeveredReturns,
    PropertyInput,
    PropertySummary,
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
    ReitInput,
    ReitNavAnalysis,
    ScenarioResult,
    Valuation,
)
from app.real_estate.sample import DISCLAIMER

_EPS = 1e-9

# id, name, description, rent_growth, expense_growth, exit_cap_change,
# vacancy_shock, interest_rate_shock
_SCENARIOS = [
    ("base", "Base case", "Modest rent and expense growth, no shocks.", 0.03, 0.025, 0.0, 0.0, 0.0),
    ("rent_upside", "Rent upside", "Stronger rent growth, expenses steady.", 0.06, 0.025, 0.0, 0.0, 0.0),
    ("vacancy_shock", "Vacancy shock", "Occupancy weakens (+5% vacancy).", 0.03, 0.025, 0.0, 0.05, 0.0),
    ("cap_rate_expansion", "Cap-rate expansion", "Exit cap rate widens by 1%.", 0.03, 0.025, 0.01, 0.0, 0.0),
    ("interest_rate_shock", "Interest-rate shock", "Financing rate rises by 1.5%.", 0.03, 0.025, 0.0, 0.0, 0.015),
    ("downside_combo", "Downside combo", "Flat rent, higher expenses, vacancy + cap + rate stress.", 0.0, 0.04, 0.0125, 0.05, 0.015),
]


# --------------------------------------------------------------------------- #
# Mortgage amortization
# --------------------------------------------------------------------------- #
def _amort_payment(principal: float, monthly_rate: float, months: int) -> float:
    if months <= 0:
        return 0.0
    if monthly_rate <= _EPS:
        return principal / months
    return principal * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-months))


def amortization_schedule(
    principal: float, annual_rate: float, amort_years: int, io_years: int
) -> Tuple[List[AmortRow], float]:
    """Month-by-month schedule (handles an optional interest-only period)."""
    r = annual_rate / 12.0
    n = amort_years * 12
    io = min(io_years * 12, n - 1) if n > 0 else 0
    amort_months = n - io
    payment = _amort_payment(principal, r, amort_months)

    rows: List[AmortRow] = []
    balance = principal
    for m in range(1, n + 1):
        interest = balance * r
        if m <= io:
            principal_paid = 0.0
            pay = interest
        else:
            pay = payment
            principal_paid = pay - interest
            if principal_paid > balance:
                principal_paid = balance
                pay = interest + principal_paid
        balance = max(balance - principal_paid, 0.0)
        rows.append(
            AmortRow(
                month=m,
                payment=float(pay),
                interest=float(interest),
                principal=float(principal_paid),
                balance=float(balance),
            )
        )
    return rows, float(payment)


def _balance_at_month(rows: List[AmortRow], month: int, principal: float) -> float:
    if month <= 0:
        return principal
    if month >= len(rows):
        return rows[-1].balance if rows else 0.0
    return rows[month - 1].balance


def _annual_debt_service(rows: List[AmortRow], year: int) -> float:
    """Sum of the 12 monthly payments in a given (1-based) year."""
    start = (year - 1) * 12
    window = rows[start : start + 12]
    if not window:
        return 0.0
    # If the schedule ran out (loan repaid), the remaining months pay nothing.
    return float(sum(row.payment for row in window))


# --------------------------------------------------------------------------- #
# IRR (deterministic bracket + bisection)
# --------------------------------------------------------------------------- #
def _npv(rate: float, cashflows: List[float]) -> float:
    total = 0.0
    for i, cf in enumerate(cashflows):
        total += cf / ((1.0 + rate) ** i)
    return total


def irr(cashflows: List[float]) -> Optional[float]:
    """Deterministic IRR via sign-change bracketing + bisection; None if unsolvable."""
    if not cashflows or all(abs(cf) < _EPS for cf in cashflows):
        return None
    lo, hi = -0.99, 5.0
    f_lo, f_hi = _npv(lo, cashflows), _npv(hi, cashflows)
    if not (math.isfinite(f_lo) and math.isfinite(f_hi)):
        return None
    if f_lo * f_hi > 0:
        prev_r, prev = lo, f_lo
        found = False
        for k in range(1, 601):
            r = lo + (hi - lo) * k / 600.0
            val = _npv(r, cashflows)
            if prev * val <= 0:
                lo, hi = prev_r, r
                found = True
                break
            prev_r, prev = r, val
        if not found:
            return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        val = _npv(mid, cashflows)
        if abs(val) < 1e-7:
            return float(mid)
        if _npv(lo, cashflows) * val < 0:
            hi = mid
        else:
            lo = mid
    result = 0.5 * (lo + hi)
    return float(result) if math.isfinite(result) else None


# --------------------------------------------------------------------------- #
# Property projection for one scenario
# --------------------------------------------------------------------------- #
class _Projection:
    def __init__(self) -> None:
        self.noi1 = 0.0
        self.dscr = 0.0
        self.coc = 0.0
        self.exit_value = 0.0
        self.equity_multiple = 0.0
        self.irr: Optional[float] = None
        self.cash_flows: List[CashFlowYear] = []
        self.initial_equity = 0.0
        self.year1_btcf = 0.0
        self.remaining_balance = 0.0
        self.selling_costs = 0.0
        self.sale_proceeds = 0.0
        self.total_distributions = 0.0
        self.amort: List[AmortRow] = []
        self.monthly_payment = 0.0


def _project(
    prop: PropertyInput,
    debt: DebtInput,
    selling_cost_rate: float,
    rent_growth: float,
    expense_growth: float,
    exit_cap_change: float,
    vacancy_shock: float,
    rate_shock: float,
) -> _Projection:
    p = _Projection()
    vacancy = min(max(prop.vacancy_rate + vacancy_shock, 0.0), 0.99)
    rate = max(debt.interest_rate + rate_shock, 0.0)
    exit_cap = max(prop.exit_cap_rate + exit_cap_change, 0.001)

    amort, monthly_payment = amortization_schedule(
        debt.loan_amount, rate, debt.amortization_years, debt.interest_only_years
    )
    p.amort = amort
    p.monthly_payment = monthly_payment

    p.initial_equity = (
        prop.purchase_price + prop.purchase_costs + debt.points_or_fees - debt.loan_amount
    )

    def noi_for_year(t: int) -> Tuple[float, float]:
        """(noi, egi) for 1-based year t with growth applied from year 1."""
        g = (1.0 + rent_growth) ** (t - 1)
        gross = prop.gross_rent_annual * g
        other = prop.other_income_annual * g
        egi = gross * (1.0 - vacancy) + other
        opex = prop.operating_expenses_annual * ((1.0 + expense_growth) ** (t - 1))
        return egi - opex, egi

    horizon = prop.holding_period_years
    equity_cfs: List[float] = [-p.initial_equity]
    cash_years: List[CashFlowYear] = [
        CashFlowYear(
            year=0,
            effective_gross_income=0.0,
            net_operating_income=0.0,
            annual_debt_service=0.0,
            before_tax_cash_flow=0.0,
            equity_cash_flow=float(-p.initial_equity),
        )
    ]
    distributions = 0.0
    for t in range(1, horizon + 1):
        noi, egi = noi_for_year(t)
        noi_after = noi - prop.capex_reserve_annual
        ads = _annual_debt_service(amort, t)
        btcf = noi_after - ads
        equity_cf = btcf
        if t == horizon:
            exit_noi, _ = noi_for_year(horizon + 1)  # forward NOI for exit value
            p.exit_value = exit_noi / exit_cap if exit_cap > _EPS else 0.0
            p.remaining_balance = _balance_at_month(amort, horizon * 12, debt.loan_amount)
            p.selling_costs = p.exit_value * selling_cost_rate
            p.sale_proceeds = p.exit_value - p.remaining_balance - p.selling_costs
            equity_cf = btcf + p.sale_proceeds
        distributions += btcf
        equity_cfs.append(equity_cf)
        cash_years.append(
            CashFlowYear(
                year=t,
                effective_gross_income=float(egi),
                net_operating_income=float(noi),
                annual_debt_service=float(ads),
                before_tax_cash_flow=float(btcf),
                equity_cash_flow=float(equity_cf),
            )
        )
        if t == 1:
            p.noi1 = float(noi)
            p.year1_btcf = float(btcf)
            p.dscr = float(noi / ads) if ads > _EPS else 0.0
            p.coc = float(btcf / p.initial_equity) if abs(p.initial_equity) > _EPS else 0.0

    p.total_distributions = float(distributions + p.sale_proceeds)
    p.equity_multiple = (
        float(p.total_distributions / p.initial_equity)
        if abs(p.initial_equity) > _EPS
        else 0.0
    )
    p.irr = irr(equity_cfs)
    p.cash_flows = cash_years
    return p


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_real_estate(req: RealEstateAnalysisRequest) -> RealEstateAnalysisResponse:
    prop = req.property
    debt = req.debt
    reit = req.reit

    base = _SCENARIOS[0]
    base_proj = _project(
        prop, debt, req.selling_cost_rate, base[3], base[4], base[5], base[6], base[7]
    )

    # In-place (year-1) income statement.
    vacancy = prop.vacancy_rate
    gross = prop.gross_rent_annual
    vacancy_loss = gross * vacancy
    egi = gross - vacancy_loss + prop.other_income_annual
    noi = egi - prop.operating_expenses_annual
    noi_after = noi - prop.capex_reserve_annual
    income = IncomeStatement(
        gross_rent=gross,
        vacancy_loss=vacancy_loss,
        other_income=prop.other_income_annual,
        effective_gross_income=egi,
        operating_expenses=prop.operating_expenses_annual,
        net_operating_income=noi,
        capex_reserve=prop.capex_reserve_annual,
        noi_after_reserves=noi_after,
    )

    in_place_cap = noi / prop.purchase_price if prop.purchase_price > _EPS else 0.0
    ltv = debt.loan_amount / prop.purchase_price if prop.purchase_price > _EPS else 0.0
    ads1 = _annual_debt_service(base_proj.amort, 1)
    dscr = noi / ads1 if ads1 > _EPS else 0.0

    summary = PropertySummary(
        property_name=prop.property_name,
        property_type=prop.property_type,
        market=prop.market,
        purchase_price=prop.purchase_price,
        purchase_costs=prop.purchase_costs,
        initial_equity=base_proj.initial_equity,
        holding_period_years=prop.holding_period_years,
        loan_to_value=ltv,
    )
    valuation = Valuation(
        net_operating_income=noi,
        in_place_cap_rate=in_place_cap,
        exit_cap_rate=prop.exit_cap_rate,
        purchase_price=prop.purchase_price,
        value_at_exit_cap=base_proj.exit_value,
    )
    debt_metrics = DebtMetrics(
        loan_amount=debt.loan_amount,
        loan_to_value=ltv,
        interest_rate=debt.interest_rate,
        amortization_years=debt.amortization_years,
        term_years=debt.term_years,
        monthly_payment=base_proj.monthly_payment,
        annual_debt_service=ads1,
        dscr=dscr,
        remaining_balance_at_exit=base_proj.remaining_balance,
    )

    irr_note = None if base_proj.irr is not None else "IRR could not be solved for these cash flows."
    levered = LeveredReturns(
        initial_equity=base_proj.initial_equity,
        year1_before_tax_cash_flow=base_proj.year1_btcf,
        cash_on_cash=base_proj.coc,
        exit_value=base_proj.exit_value,
        remaining_loan_balance=base_proj.remaining_balance,
        selling_costs=base_proj.selling_costs,
        sale_proceeds=base_proj.sale_proceeds,
        total_distributions=base_proj.total_distributions,
        equity_multiple=base_proj.equity_multiple,
        irr=base_proj.irr,
        irr_note=irr_note,
    )

    # Scenario results.
    scenarios: List[ScenarioResult] = []
    for sid, name, desc, rg, eg, ecc, vs, rs in _SCENARIOS:
        proj = _project(prop, debt, req.selling_cost_rate, rg, eg, ecc, vs, rs)
        scenarios.append(
            ScenarioResult(
                id=sid,
                name=name,
                description=desc,
                rent_growth_rate=rg,
                vacancy_rate=min(max(prop.vacancy_rate + vs, 0.0), 0.99),
                exit_cap_rate=max(prop.exit_cap_rate + ecc, 0.001),
                interest_rate=max(debt.interest_rate + rs, 0.0),
                noi=proj.noi1,
                dscr=proj.dscr,
                cash_on_cash=proj.coc,
                exit_value=proj.exit_value,
                equity_multiple=proj.equity_multiple,
                irr=proj.irr,
                notes=["Illustrative deterministic scenario — not a forecast."],
            )
        )

    # REIT NAV analysis.
    nav_equity = reit.property_nav - reit.net_debt
    nav_per_share = nav_equity / reit.shares_outstanding if reit.shares_outstanding > _EPS else 0.0
    premium_discount = (
        reit.share_price / nav_per_share - 1.0 if abs(nav_per_share) > _EPS else 0.0
    )
    ffo_per_share = (
        reit.funds_from_operations / reit.shares_outstanding
        if reit.shares_outstanding > _EPS
        else 0.0
    )
    p_ffo = reit.share_price / ffo_per_share if ffo_per_share > _EPS else None
    dividend_yield = reit.dividend_per_share / reit.share_price if reit.share_price > _EPS else 0.0
    reit_nav = ReitNavAnalysis(
        property_nav=reit.property_nav,
        net_debt=reit.net_debt,
        shares_outstanding=reit.shares_outstanding,
        nav_per_share=nav_per_share,
        share_price=reit.share_price,
        premium_discount=premium_discount,
        ffo_per_share=ffo_per_share,
        p_ffo=p_ffo,
        dividend_per_share=reit.dividend_per_share,
        dividend_yield=dividend_yield,
    )

    return RealEstateAnalysisResponse(
        property_summary=summary,
        income_statement=income,
        valuation=valuation,
        debt_metrics=debt_metrics,
        amortization_schedule=base_proj.amort[:12],
        levered_returns=levered,
        cash_flow_projection=base_proj.cash_flows,
        scenario_results=scenarios,
        reit_nav_analysis=reit_nav,
        notes=[
            "In-place income statement and metrics use year-1 figures; the levered "
            "returns and cash-flow projection use the base scenario over the holding period.",
            "Exit value uses forward (year H+1) NOI divided by the exit cap rate; "
            "sale proceeds net the remaining loan balance and selling costs.",
            "IRR is solved deterministically; it is null with a note if it cannot be bracketed.",
            "Scenario results are deterministic illustrative stresses, not forecasts.",
            "REIT NAV is a simplified example (NAV per share, premium/discount, P/FFO, "
            "dividend yield) — not live REIT data.",
        ],
        disclaimer=DISCLAIMER,
    )
