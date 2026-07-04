"""
Typed Pydantic models for the DeFi Yield, Stablecoin Peg & Lending Risk Lab (27.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, lending, borrowing, liquidation,
legal, tax, or risk-management advice; never live protocol data, live crypto
prices, wallets, RPC, or smart-contract calls.
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


class DrModel(BaseModel):
    """Strict base model for stable, JSON-safe DeFi-risk payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class StablecoinInput(DrModel):
    symbol: NonEmptyStr
    target_peg: PositiveFloat
    market_price: PositiveFloat
    supply_weight: Optional[UnitFloat] = None
    reserve_quality_score: Optional[UnitFloat] = None


class DeFiMarketInput(DrModel):
    protocol_name: NonEmptyStr
    chain: NonEmptyStr
    asset_symbol: NonEmptyStr
    total_supplied: NonNegFloat
    total_borrowed: NonNegFloat
    liquidity: NonNegFloat
    base_rate: NonNegFloat
    slope_1: NonNegFloat
    slope_2: NonNegFloat
    kink_utilization: Annotated[FiniteFloat, Field(gt=0, lt=1)]
    reserve_factor: UnitFloat
    lending_apy: NonNegFloat
    borrow_apy: NonNegFloat

    @model_validator(mode="after")
    def _check(self) -> "DeFiMarketInput":
        if self.total_borrowed > self.total_supplied:
            raise ValueError(
                "total_borrowed must be <= total_supplied "
                f"({self.total_borrowed} > {self.total_supplied})"
            )
        return self


class CollateralPositionInput(DrModel):
    collateral_asset: NonEmptyStr
    collateral_amount: PositiveFloat
    collateral_price: PositiveFloat
    debt_asset: NonEmptyStr
    debt_amount: NonNegFloat
    debt_price: PositiveFloat
    liquidation_threshold: Annotated[FiniteFloat, Field(gt=0, le=1)]
    collateral_factor: UnitFloat
    liquidation_penalty: UnitFloat
    borrow_apy: NonNegFloat
    supply_apy: NonNegFloat

    @model_validator(mode="after")
    def _check(self) -> "CollateralPositionInput":
        if self.liquidation_threshold < self.collateral_factor:
            raise ValueError(
                "liquidation_threshold must be >= collateral_factor "
                f"({self.liquidation_threshold} < {self.collateral_factor})"
            )
        return self


class DeFiScenarioInput(DrModel):
    name: NonEmptyStr
    collateral_price_shock: FiniteFloat = 0.0
    debt_price_shock: FiniteFloat = 0.0
    stablecoin_depeg_shock: FiniteFloat = 0.0
    utilization_shock: FiniteFloat = 0.0
    liquidity_shock: FiniteFloat = 0.0
    borrow_rate_shock: FiniteFloat = 0.0
    liquidation_threshold_shock: FiniteFloat = 0.0


class DeFiRiskAnalysisRequest(DrModel):
    sample_id: NonEmptyStr
    stablecoin: StablecoinInput
    market: DeFiMarketInput
    position: CollateralPositionInput
    fees_apy: NonNegFloat = 0.0
    custom_scenarios: Optional[List[DeFiScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class ProtocolSummary(DrModel):
    sample_id: NonEmptyStr
    protocol_name: NonEmptyStr
    chain: NonEmptyStr
    asset_symbol: NonEmptyStr
    collateral_asset: NonEmptyStr
    debt_asset: NonEmptyStr


class StablecoinPegAnalysis(DrModel):
    symbol: NonEmptyStr
    target_peg: FiniteFloat
    market_price: FiniteFloat
    peg_deviation: FiniteFloat
    peg_deviation_bps: FiniteFloat
    reserve_quality_score: Optional[FiniteFloat] = None
    status: Literal["on_peg", "minor_deviation", "depegged"]


class UtilizationAnalysis(DrModel):
    total_supplied: FiniteFloat
    total_borrowed: FiniteFloat
    liquidity: FiniteFloat
    utilization: FiniteFloat
    kink_utilization: FiniteFloat
    utilization_regime: Literal["low", "moderate", "high", "extreme"]


class InterestRateModelResult(DrModel):
    borrow_apy_model: FiniteFloat
    supply_apy_model: FiniteFloat
    reserve_factor: FiniteFloat
    base_rate: FiniteFloat
    slope_1: FiniteFloat
    slope_2: FiniteFloat
    kink_utilization: FiniteFloat


class CollateralRisk(DrModel):
    collateral_value: FiniteFloat
    debt_value: FiniteFloat
    loan_to_value: FiniteFloat
    collateral_factor: FiniteFloat
    liquidation_threshold: FiniteFloat
    health_factor: FiniteFloat
    liquidation_price_approx: FiniteFloat
    liquidation_distance_bps: FiniteFloat
    liquidation_penalty: FiniteFloat


class NetAPYAnalysis(DrModel):
    supply_apy: FiniteFloat
    borrow_apy: FiniteFloat
    fees_apy: FiniteFloat
    net_apy: FiniteFloat
    notes: List[NonEmptyStr]


class RiskRegime(DrModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr


class DeFiScenarioResult(DrModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    peg_deviation_bps: FiniteFloat
    utilization: FiniteFloat
    borrow_apy: FiniteFloat
    supply_apy: FiniteFloat
    collateral_value: FiniteFloat
    debt_value: FiniteFloat
    loan_to_value: FiniteFloat
    health_factor: FiniteFloat
    liquidation_price: FiniteFloat
    liquidation_distance_bps: FiniteFloat
    net_apy: FiniteFloat
    regime_label: NonEmptyStr
    notes: List[NonEmptyStr]


class DeFiRiskAnalysisResponse(DrModel):
    data_status: Literal["static_sample"] = "static_sample"
    protocol_summary: ProtocolSummary
    stablecoin_peg: StablecoinPegAnalysis
    utilization_analysis: UtilizationAnalysis
    interest_rate_model: InterestRateModelResult
    collateral_risk: CollateralRisk
    net_apy_analysis: NetAPYAnalysis
    risk_regime: RiskRegime
    scenario_results: List[DeFiScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class DeFiRiskSampleResponse(DrModel):
    samples: List[DeFiRiskAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
