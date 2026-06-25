"""
Typed Pydantic models for the Futures & Commodities Lab (Phase 23.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment / trading / risk-management advice.
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
Rate = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
SignedRate = Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]

PositionType = Literal["long", "short"]
CurveShape = Literal["contango", "backwardation", "mixed"]


class FuturesModel(BaseModel):
    """Strict base model for stable, JSON-safe futures payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class FuturesContractInput(FuturesModel):
    commodity_name: NonEmptyStr
    symbol: NonEmptyStr
    spot_price: PositiveFloat
    risk_free_rate: Rate
    storage_cost_rate: Rate
    convenience_yield: SignedRate
    contract_multiplier: PositiveFloat
    initial_margin_rate: Rate
    maintenance_margin_rate: Rate

    @model_validator(mode="after")
    def _check(self) -> "FuturesContractInput":
        if self.initial_margin_rate < self.maintenance_margin_rate - 1e-12:
            raise ValueError("initial_margin_rate must be >= maintenance_margin_rate")
        return self


class FuturesCurvePoint(FuturesModel):
    contract: NonEmptyStr
    maturity_months: Annotated[int, Field(gt=0, le=120)]
    futures_price: PositiveFloat
    volume: Optional[Annotated[int, Field(ge=0)]] = None
    open_interest: Optional[Annotated[int, Field(ge=0)]] = None


class FuturesPositionInput(FuturesModel):
    position_type: PositionType
    contracts: Annotated[int, Field(gt=0, le=1_000_000)]
    entry_price: PositiveFloat
    exit_price: PositiveFloat
    contract_multiplier: PositiveFloat


class FuturesAnalysisRequest(FuturesModel):
    contract: FuturesContractInput
    curve: List[FuturesCurvePoint] = Field(min_length=2)
    position: FuturesPositionInput


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class CommoditySummary(FuturesModel):
    commodity_name: NonEmptyStr
    symbol: NonEmptyStr
    spot_price: FiniteFloat
    risk_free_rate: FiniteFloat
    storage_cost_rate: FiniteFloat
    convenience_yield: FiniteFloat
    contract_multiplier: FiniteFloat
    initial_margin_rate: FiniteFloat
    maintenance_margin_rate: FiniteFloat
    cost_of_carry_rate: FiniteFloat


class TheoreticalPricing(FuturesModel):
    spot_price: FiniteFloat
    cost_of_carry_rate: FiniteFloat
    model_futures_12m: FiniteFloat
    model_near: FiniteFloat
    model_far: FiniteFloat


class CurveAnalysisPoint(FuturesModel):
    contract: NonEmptyStr
    maturity_months: int
    maturity_years: FiniteFloat
    observed_futures: FiniteFloat
    model_futures: FiniteFloat
    basis: FiniteFloat
    annualized_basis: FiniteFloat
    implied_convenience_yield: FiniteFloat
    pricing_deviation: FiniteFloat
    roll_yield: Optional[FiniteFloat] = None


class CurveAnalysis(FuturesModel):
    points: List[CurveAnalysisPoint]
    curve_slope: FiniteFloat
    curve_shape: CurveShape
    near_contract: NonEmptyStr
    far_contract: NonEmptyStr
    near_basis: FiniteFloat


class RollYieldRow(FuturesModel):
    from_contract: NonEmptyStr
    to_contract: NonEmptyStr
    near_price: FiniteFloat
    next_price: FiniteFloat
    roll_yield: FiniteFloat


class CalendarSpreadAnalysis(FuturesModel):
    near_contract: NonEmptyStr
    deferred_contract: NonEmptyStr
    near_price: FiniteFloat
    deferred_price: FiniteFloat
    spread: FiniteFloat
    spread_pct: FiniteFloat


class PositionPnl(FuturesModel):
    position_type: PositionType
    contracts: int
    entry_price: FiniteFloat
    exit_price: FiniteFloat
    contract_multiplier: FiniteFloat
    pnl: FiniteFloat
    notional: FiniteFloat
    initial_margin: FiniteFloat
    return_on_margin: FiniteFloat


class MarginAnalysis(FuturesModel):
    notional: FiniteFloat
    initial_margin: FiniteFloat
    maintenance_margin: FiniteFloat
    leverage: FiniteFloat
    initial_margin_rate: FiniteFloat
    maintenance_margin_rate: FiniteFloat


class FuturesScenarioResult(FuturesModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    spot_shock: FiniteFloat
    curve_parallel_shift: FiniteFloat
    curve_slope_shock: FiniteFloat
    convenience_yield_shock: FiniteFloat
    shocked_spot: FiniteFloat
    curve_shape: CurveShape
    near_pnl: FiniteFloat
    calendar_spread_pnl: FiniteFloat
    roll_yield: FiniteFloat
    margin_requirement: FiniteFloat
    return_on_margin: FiniteFloat
    notes: List[NonEmptyStr]


class FuturesAnalysisResponse(FuturesModel):
    data_status: Literal["static_sample"] = "static_sample"
    commodity_summary: CommoditySummary
    theoretical_pricing: TheoreticalPricing
    curve_analysis: CurveAnalysis
    roll_yield_table: List[RollYieldRow]
    calendar_spread_analysis: CalendarSpreadAnalysis
    position_pnl: PositionPnl
    margin_analysis: MarginAnalysis
    scenario_results: List[FuturesScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class FuturesSampleResponse(FuturesModel):
    commodities: List[FuturesAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
