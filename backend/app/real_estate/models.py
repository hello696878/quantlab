"""
Typed Pydantic models for the Real Estate Lab (Phase 22.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment / tax / legal / lending advice.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegFloat = Annotated[FiniteFloat, Field(ge=0)]
Rate = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]


class RealEstateModel(BaseModel):
    """Strict base model for stable, JSON-safe real-estate payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class PropertyInput(RealEstateModel):
    property_name: NonEmptyStr
    property_type: NonEmptyStr
    market: NonEmptyStr
    purchase_price: PositiveFloat
    gross_rent_annual: NonNegFloat
    other_income_annual: NonNegFloat = 0.0
    vacancy_rate: Rate
    operating_expenses_annual: NonNegFloat
    capex_reserve_annual: NonNegFloat = 0.0
    purchase_costs: NonNegFloat = 0.0
    exit_cap_rate: Annotated[FiniteFloat, Field(gt=0.0, le=1.0)]
    holding_period_years: Annotated[int, Field(gt=0, le=50)]


class DebtInput(RealEstateModel):
    loan_amount: NonNegFloat
    interest_rate: Rate
    amortization_years: Annotated[int, Field(gt=0, le=50)]
    term_years: Annotated[int, Field(gt=0, le=50)]
    interest_only_years: Annotated[int, Field(ge=0, le=50)] = 0
    points_or_fees: NonNegFloat = 0.0


class ReitInput(RealEstateModel):
    property_nav: PositiveFloat
    net_debt: NonNegFloat
    shares_outstanding: PositiveFloat
    share_price: PositiveFloat
    funds_from_operations: FiniteFloat
    dividend_per_share: NonNegFloat


class RealEstateAnalysisRequest(RealEstateModel):
    property: PropertyInput
    debt: DebtInput
    reit: ReitInput
    selling_cost_rate: Rate = 0.02


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class PropertySummary(RealEstateModel):
    property_name: NonEmptyStr
    property_type: NonEmptyStr
    market: NonEmptyStr
    purchase_price: FiniteFloat
    purchase_costs: FiniteFloat
    initial_equity: FiniteFloat
    holding_period_years: int
    loan_to_value: FiniteFloat


class IncomeStatement(RealEstateModel):
    gross_rent: FiniteFloat
    vacancy_loss: FiniteFloat
    other_income: FiniteFloat
    effective_gross_income: FiniteFloat
    operating_expenses: FiniteFloat
    net_operating_income: FiniteFloat
    capex_reserve: FiniteFloat
    noi_after_reserves: FiniteFloat


class Valuation(RealEstateModel):
    net_operating_income: FiniteFloat
    in_place_cap_rate: FiniteFloat
    exit_cap_rate: FiniteFloat
    purchase_price: FiniteFloat
    value_at_exit_cap: FiniteFloat


class DebtMetrics(RealEstateModel):
    loan_amount: FiniteFloat
    loan_to_value: FiniteFloat
    interest_rate: FiniteFloat
    amortization_years: int
    term_years: int
    monthly_payment: FiniteFloat
    annual_debt_service: FiniteFloat
    dscr: FiniteFloat
    remaining_balance_at_exit: FiniteFloat


class AmortRow(RealEstateModel):
    month: int
    payment: FiniteFloat
    interest: FiniteFloat
    principal: FiniteFloat
    balance: FiniteFloat


class LeveredReturns(RealEstateModel):
    initial_equity: FiniteFloat
    year1_before_tax_cash_flow: FiniteFloat
    cash_on_cash: FiniteFloat
    exit_value: FiniteFloat
    remaining_loan_balance: FiniteFloat
    selling_costs: FiniteFloat
    sale_proceeds: FiniteFloat
    total_distributions: FiniteFloat
    equity_multiple: FiniteFloat
    irr: Optional[FiniteFloat] = None
    irr_note: Optional[NonEmptyStr] = None


class CashFlowYear(RealEstateModel):
    year: int
    effective_gross_income: FiniteFloat
    net_operating_income: FiniteFloat
    annual_debt_service: FiniteFloat
    before_tax_cash_flow: FiniteFloat
    equity_cash_flow: FiniteFloat  # year 0 = -equity; final year includes sale


class ScenarioResult(RealEstateModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    rent_growth_rate: FiniteFloat
    vacancy_rate: FiniteFloat
    exit_cap_rate: FiniteFloat
    interest_rate: FiniteFloat
    noi: FiniteFloat
    dscr: FiniteFloat
    cash_on_cash: FiniteFloat
    exit_value: FiniteFloat
    equity_multiple: FiniteFloat
    irr: Optional[FiniteFloat] = None
    notes: List[NonEmptyStr]


class ReitNavAnalysis(RealEstateModel):
    property_nav: FiniteFloat
    net_debt: FiniteFloat
    shares_outstanding: FiniteFloat
    nav_per_share: FiniteFloat
    share_price: FiniteFloat
    premium_discount: FiniteFloat
    ffo_per_share: FiniteFloat
    p_ffo: Optional[FiniteFloat] = None
    dividend_per_share: FiniteFloat
    dividend_yield: FiniteFloat


class RealEstateAnalysisResponse(RealEstateModel):
    data_status: Literal["static_sample"] = "static_sample"
    property_summary: PropertySummary
    income_statement: IncomeStatement
    valuation: Valuation
    debt_metrics: DebtMetrics
    amortization_schedule: List[AmortRow]
    levered_returns: LeveredReturns
    cash_flow_projection: List[CashFlowYear]
    scenario_results: List[ScenarioResult]
    reit_nav_analysis: ReitNavAnalysis
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class SampleResponse(RealEstateModel):
    request: RealEstateAnalysisRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]


# --------------------------------------------------------------------------- #
# Mortgage & MBS prepayment (Phase 22.1)
# --------------------------------------------------------------------------- #
PrepaymentModel = Literal["constant_cpr", "psa"]


class MortgagePoolInput(RealEstateModel):
    pool_name: NonEmptyStr
    original_balance: PositiveFloat
    current_balance: PositiveFloat
    coupon_rate: Rate
    servicing_fee_rate: NonNegFloat = 0.0
    remaining_term_months: Annotated[int, Field(gt=0, le=480)]
    seasoning_months: Annotated[int, Field(ge=0, le=480)] = 0
    wam_months: Optional[Annotated[int, Field(gt=0, le=600)]] = None
    wala_months: Optional[Annotated[int, Field(ge=0, le=600)]] = None

    @model_validator(mode="after")
    def _check(self) -> "MortgagePoolInput":
        if self.current_balance > self.original_balance + 1e-6:
            raise ValueError("current_balance must be <= original_balance")
        if self.servicing_fee_rate > self.coupon_rate + 1e-12:
            raise ValueError("servicing_fee_rate must be <= coupon_rate")
        return self


class PrepaymentInput(RealEstateModel):
    model: PrepaymentModel = "psa"
    cpr: Optional[Rate] = None
    psa_speed: Optional[Annotated[FiniteFloat, Field(gt=0.0, le=2000.0)]] = None
    prepayment_lag_months: Annotated[int, Field(ge=0, le=60)] = 0


class ValuationInput(RealEstateModel):
    discount_rate: NonNegFloat
    price: Optional[PositiveFloat] = None
    rate_shock_bps: FiniteFloat = 0.0
    prepayment_stress_multiplier: Annotated[FiniteFloat, Field(gt=0.0, le=20.0)] = 1.0


class MortgageMbsRequest(RealEstateModel):
    pool: MortgagePoolInput
    prepayment: PrepaymentInput
    valuation: ValuationInput


class PoolSummary(RealEstateModel):
    pool_name: NonEmptyStr
    original_balance: FiniteFloat
    current_balance: FiniteFloat
    pool_factor: FiniteFloat
    coupon_rate: FiniteFloat
    servicing_fee_rate: FiniteFloat
    net_coupon: FiniteFloat
    remaining_term_months: int
    seasoning_months: int


class PrepaymentAssumption(RealEstateModel):
    model: PrepaymentModel
    cpr: Optional[FiniteFloat] = None
    psa_speed: Optional[FiniteFloat] = None
    prepayment_lag_months: int
    prepayment_stress_multiplier: FiniteFloat


class ValuationAssumption(RealEstateModel):
    discount_rate: FiniteFloat
    net_coupon: FiniteFloat
    price: Optional[FiniteFloat] = None


class MbsCashFlowSummary(RealEstateModel):
    num_months: int
    total_interest: FiniteFloat
    total_scheduled_principal: FiniteFloat
    total_prepayment: FiniteFloat
    total_principal: FiniteFloat
    total_cash_flow: FiniteFloat
    final_balance: FiniteFloat


class MbsCashFlowRow(RealEstateModel):
    month: int
    beginning_balance: FiniteFloat
    scheduled_principal: FiniteFloat
    prepayment_principal: FiniteFloat
    interest: FiniteFloat
    total_cash_flow: FiniteFloat
    ending_balance: FiniteFloat


class PsaPathPoint(RealEstateModel):
    month: int
    pool_age_month: int
    cpr: FiniteFloat
    smm: FiniteFloat


class DurationConvexity(RealEstateModel):
    shock_bps: FiniteFloat
    price_base: FiniteFloat
    price_up: FiniteFloat
    price_down: FiniteFloat
    duration: FiniteFloat
    convexity: FiniteFloat
    yield_estimate: Optional[FiniteFloat] = None


class MbsScenarioResult(RealEstateModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    price_100: FiniteFloat
    wal: FiniteFloat
    duration: FiniteFloat
    convexity: FiniteFloat
    total_interest: FiniteFloat
    total_principal: FiniteFloat
    final_balance: FiniteFloat
    notes: List[NonEmptyStr]


class MortgageMbsAnalysisResponse(RealEstateModel):
    data_status: Literal["static_sample"] = "static_sample"
    pool_summary: PoolSummary
    prepayment_assumption: PrepaymentAssumption
    valuation_assumption: ValuationAssumption
    price: FiniteFloat
    price_100: FiniteFloat
    wal: FiniteFloat
    cash_flow_summary: MbsCashFlowSummary
    cash_flow_schedule: List[MbsCashFlowRow]
    psa_path: List[PsaPathPoint]
    duration_convexity: DurationConvexity
    scenario_results: List[MbsScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class MbsSampleResponse(RealEstateModel):
    request: MortgageMbsRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
