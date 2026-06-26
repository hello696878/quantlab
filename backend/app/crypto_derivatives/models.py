"""
Typed Pydantic models for the Crypto Perpetual Futures Funding & Basis Lab (26.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, liquidation, legal, tax, or
risk-management advice, and never live exchange data or live crypto prices.
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
UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
PositiveInt = Annotated[int, Field(gt=0)]
Side = Literal["long", "short"]
CurveShape = Literal["contango", "backwardation", "mixed", "flat"]


class CdModel(BaseModel):
    """Strict base model for stable, JSON-safe crypto-derivatives payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class CryptoMarketInput(CdModel):
    symbol: NonEmptyStr
    spot_price: PositiveFloat
    perp_mark_price: PositiveFloat
    index_price: PositiveFloat
    funding_rate_8h: FiniteFloat  # may be negative
    next_funding_hours: NonNegFloat
    risk_free_rate: Optional[NonNegFloat] = 0.0


class DatedFutureInput(CdModel):
    contract: NonEmptyStr
    maturity_days: PositiveFloat
    futures_price: PositiveFloat


class PositionInput(CdModel):
    side: Side
    notional: PositiveFloat
    entry_price: PositiveFloat
    mark_price: PositiveFloat
    leverage: PositiveFloat
    initial_margin_rate: UnitFloat
    maintenance_margin_rate: UnitFloat
    taker_fee_rate: Optional[NonNegFloat] = 0.0004
    maker_fee_rate: Optional[NonNegFloat] = 0.0001

    @model_validator(mode="after")
    def _check(self) -> "PositionInput":
        if self.initial_margin_rate < self.maintenance_margin_rate:
            raise ValueError(
                "initial_margin_rate must be >= maintenance_margin_rate "
                f"({self.initial_margin_rate} < {self.maintenance_margin_rate})"
            )
        return self


class FundingScenarioInput(CdModel):
    name: NonEmptyStr
    spot_shock: FiniteFloat = 0.0
    perp_basis_shock_bps: FiniteFloat = 0.0
    futures_premium_mult: NonNegFloat = 1.0
    funding_rate_shock: FiniteFloat = 0.0
    volatility_multiplier: PositiveFloat = 1.0
    margin_multiplier: PositiveFloat = 1.0


class CryptoDerivativesAnalysisRequest(CdModel):
    market: CryptoMarketInput
    dated_futures: List[DatedFutureInput] = Field(min_length=1)
    position: PositionInput
    funding_intervals_per_day: PositiveInt = 3
    custom_scenarios: Optional[List[FundingScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class MarketSummary(CdModel):
    symbol: NonEmptyStr
    spot_price: FiniteFloat
    index_price: FiniteFloat
    perp_mark_price: FiniteFloat
    funding_rate_8h: FiniteFloat
    next_funding_hours: FiniteFloat


class FuturesCurvePoint(CdModel):
    contract: NonEmptyStr
    maturity_days: FiniteFloat
    futures_price: FiniteFloat
    basis: FiniteFloat
    basis_bps: FiniteFloat
    annualized_basis: FiniteFloat


class BasisAnalysis(CdModel):
    perp_basis: FiniteFloat
    perp_basis_bps: FiniteFloat
    average_futures_basis_bps: FiniteFloat
    max_annualized_basis: FiniteFloat
    curve_shape: CurveShape


class FundingAnalysis(CdModel):
    funding_rate_8h: FiniteFloat
    funding_annualized_compound: FiniteFloat
    funding_annualized_simple: FiniteFloat
    long_funding_pnl_daily: FiniteFloat
    short_funding_pnl_daily: FiniteFloat
    next_funding_hours: FiniteFloat


class PositionRisk(CdModel):
    side: Side
    notional: FiniteFloat
    leverage: FiniteFloat
    initial_margin: FiniteFloat
    maintenance_margin: FiniteFloat
    unrealized_pnl: FiniteFloat
    margin_ratio: FiniteFloat
    liquidation_price_approx: FiniteFloat
    liquidation_distance_bps: FiniteFloat


class CarryAnalysis(CdModel):
    best_carry_contract: NonEmptyStr
    annualized_basis: FiniteFloat
    estimated_costs: FiniteFloat
    expected_gross_carry: FiniteFloat
    notes: List[NonEmptyStr]


class FundingRegime(CdModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr
    notes: List[NonEmptyStr]


class CryptoScenarioResult(CdModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    shocked_spot: FiniteFloat
    shocked_perp_mark: FiniteFloat
    perp_basis_bps: FiniteFloat
    annualized_basis: FiniteFloat
    funding_annualized: FiniteFloat
    long_funding_pnl: FiniteFloat
    short_funding_pnl: FiniteFloat
    position_pnl: FiniteFloat
    margin_ratio: FiniteFloat
    liquidation_distance_bps: FiniteFloat
    regime_label: NonEmptyStr
    notes: List[NonEmptyStr]


class CryptoDerivativesAnalysisResponse(CdModel):
    data_status: Literal["static_sample"] = "static_sample"
    market_summary: MarketSummary
    basis_analysis: BasisAnalysis
    funding_analysis: FundingAnalysis
    futures_curve: List[FuturesCurvePoint]
    position_risk: PositionRisk
    carry_analysis: CarryAnalysis
    funding_regime: FundingRegime
    scenario_results: List[CryptoScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class CryptoDerivativesSampleResponse(CdModel):
    markets: List[CryptoDerivativesAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
