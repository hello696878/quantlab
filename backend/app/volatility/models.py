"""
Typed Pydantic models for the Volatility Surface & Variance Swap Lab (24.0).

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
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]
OptionType = Literal["call", "put"]


class VolModel(BaseModel):
    """Strict base model for stable, JSON-safe volatility payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class UnderlyingInput(VolModel):
    symbol: NonEmptyStr
    spot_price: PositiveFloat
    risk_free_rate: FiniteFloat
    dividend_yield: FiniteFloat
    realized_returns: Optional[List[FiniteFloat]] = None


class OptionQuoteInput(VolModel):
    option_id: NonEmptyStr
    option_type: OptionType
    strike: PositiveFloat
    maturity_days: Annotated[int, Field(gt=0, le=3650)]
    mid_price: PositiveFloat
    bid: Optional[PositiveFloat] = None
    ask: Optional[PositiveFloat] = None
    open_interest: Optional[Annotated[int, Field(ge=0)]] = None
    volume: Optional[Annotated[int, Field(ge=0)]] = None


class OptionPositionInput(VolModel):
    option_id: NonEmptyStr
    quantity: FiniteFloat
    contract_multiplier: PositiveFloat = 100.0


class VolatilityAnalysisRequest(VolModel):
    underlying: UnderlyingInput
    option_quotes: List[OptionQuoteInput] = Field(min_length=4)
    positions: Optional[List[OptionPositionInput]] = None
    variance_swap_maturity_days: Optional[Annotated[int, Field(gt=0, le=3650)]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class UnderlyingSummary(VolModel):
    symbol: NonEmptyStr
    spot_price: FiniteFloat
    risk_free_rate: FiniteFloat
    dividend_yield: FiniteFloat


class OptionAnalysis(VolModel):
    option_id: NonEmptyStr
    option_type: OptionType
    strike: FiniteFloat
    maturity_days: int
    maturity_years: FiniteFloat
    moneyness: FiniteFloat
    log_moneyness: FiniteFloat
    mid_price: FiniteFloat
    implied_volatility: Optional[FiniteFloat] = None
    iv_note: Optional[NonEmptyStr] = None
    vega: FiniteFloat
    delta: FiniteFloat
    intrinsic_value: FiniteFloat
    time_value: FiniteFloat


class SmilePoint(VolModel):
    maturity_days: int
    strike: FiniteFloat
    moneyness: FiniteFloat
    implied_volatility: FiniteFloat
    option_type: OptionType
    vega: FiniteFloat


class TermStructurePoint(VolModel):
    maturity_days: int
    atm_implied_volatility: FiniteFloat


class SkewMetric(VolModel):
    maturity_days: int
    put_90_iv: FiniteFloat
    atm_iv: FiniteFloat
    call_110_iv: FiniteFloat
    put_spread: FiniteFloat
    call_spread: FiniteFloat
    skew_slope: FiniteFloat
    risk_reversal_25d: Optional[FiniteFloat] = None


class SurfaceSummary(VolModel):
    atm_iv_30d: FiniteFloat
    atm_iv_90d: FiniteFloat
    atm_iv_1y: FiniteFloat
    min_iv: FiniteFloat
    max_iv: FiniteFloat
    average_iv: FiniteFloat
    steepest_skew_maturity: int
    term_structure_slope: FiniteFloat


class RealizedVolatility(VolModel):
    num_returns: int
    realized_vol_annual: FiniteFloat
    realized_vol_20d: Optional[FiniteFloat] = None
    realized_vol_60d: Optional[FiniteFloat] = None
    realized_vol_120d: Optional[FiniteFloat] = None


class ImpliedRealizedSpread(VolModel):
    implied_atm_30d: FiniteFloat
    realized_vol: FiniteFloat
    spread: FiniteFloat


class VarianceStripPoint(VolModel):
    strike: FiniteFloat
    otm_type: OptionType
    otm_price: FiniteFloat
    delta_k: FiniteFloat
    weight: FiniteFloat
    contribution: FiniteFloat


class VarianceSwap(VolModel):
    maturity_days: int
    maturity_years: FiniteFloat
    forward: FiniteFloat
    variance_strike: FiniteFloat
    volatility_strike: FiniteFloat
    strip_points: List[VarianceStripPoint]
    notes: List[NonEmptyStr]


class VegaGroup(VolModel):
    key: NonEmptyStr
    vega: FiniteFloat


class VegaExposure(VolModel):
    total_vega: FiniteFloat
    positions_used: int
    vega_by_maturity: List[VegaGroup]
    vega_by_moneyness: List[VegaGroup]


class VolatilityScenarioResult(VolModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    parallel_iv_shift: FiniteFloat
    skew_shift: FiniteFloat
    term_structure_shift: FiniteFloat
    spot_shock: FiniteFloat
    shifted_atm_iv_30d: FiniteFloat
    shifted_atm_iv_1y: FiniteFloat
    term_structure_slope: FiniteFloat
    atm_iv_change: FiniteFloat
    skew_change: FiniteFloat
    portfolio_value_change: FiniteFloat
    total_vega: FiniteFloat
    notes: List[NonEmptyStr]


class VolatilityAnalysisResponse(VolModel):
    data_status: Literal["static_sample"] = "static_sample"
    underlying: UnderlyingSummary
    option_quotes: List[OptionAnalysis]
    smile_points: List[SmilePoint]
    term_structure: List[TermStructurePoint]
    skew_metrics: List[SkewMetric]
    surface_summary: SurfaceSummary
    realized_volatility: RealizedVolatility
    implied_realized_spread: ImpliedRealizedSpread
    variance_swap: VarianceSwap
    vega_exposure: VegaExposure
    scenario_results: List[VolatilityScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class VolatilitySampleResponse(VolModel):
    request: VolatilityAnalysisRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
