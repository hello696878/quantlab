"""
Typed Pydantic models for the Tokenomics, Unlock Schedule & Treasury Risk Lab (28.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, token, venture, legal, tax, or
risk-management advice; never live token prices, live on-chain data, wallets,
RPC, or smart-contract calls.
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


class TkModel(BaseModel):
    """Strict base model for stable, JSON-safe tokenomics payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class TokenMarketInput(TkModel):
    symbol: NonEmptyStr
    token_name: NonEmptyStr
    price: PositiveFloat
    circulating_supply: PositiveFloat
    total_supply: PositiveFloat
    max_supply: Optional[PositiveFloat] = None
    treasury_tokens: Optional[NonNegFloat] = 0.0
    treasury_stables: Optional[NonNegFloat] = 0.0
    monthly_burn_usd: NonNegFloat
    staking_yield: NonNegFloat
    emission_rate_annual: NonNegFloat
    protocol_revenue_annual: Optional[NonNegFloat] = None

    @model_validator(mode="after")
    def _check(self) -> "TokenMarketInput":
        if self.total_supply < self.circulating_supply:
            raise ValueError(
                "total_supply must be >= circulating_supply "
                f"({self.total_supply} < {self.circulating_supply})"
            )
        if self.max_supply is not None and self.max_supply < self.total_supply:
            raise ValueError(
                f"max_supply must be >= total_supply ({self.max_supply} < {self.total_supply})"
            )
        return self


class UnlockEventInput(TkModel):
    date: NonEmptyStr
    # Deterministic day offset from the static sample "as of" point (no live
    # clock, no date parsing) — used for the 30/90/180/365-day buckets.
    days_until: NonNegFloat
    category: NonEmptyStr
    tokens: NonNegFloat
    description: Optional[NonEmptyStr] = None


class HolderConcentrationInput(TkModel):
    top_1_holder_share: UnitFloat
    top_5_holder_share: UnitFloat
    top_10_holder_share: UnitFloat
    insider_share: Optional[UnitFloat] = None
    foundation_share: Optional[UnitFloat] = None
    community_share: Optional[UnitFloat] = None

    @model_validator(mode="after")
    def _check(self) -> "HolderConcentrationInput":
        if not (self.top_1_holder_share <= self.top_5_holder_share <= self.top_10_holder_share):
            raise ValueError(
                "holder shares must satisfy top_1 <= top_5 <= top_10 "
                f"({self.top_1_holder_share}, {self.top_5_holder_share}, {self.top_10_holder_share})"
            )
        return self


class TokenomicsScenarioInput(TkModel):
    name: NonEmptyStr
    price_shock: FiniteFloat = 0.0
    unlock_multiplier: NonNegFloat = 1.0
    emission_multiplier: NonNegFloat = 1.0
    burn_multiplier: NonNegFloat = 1.0
    treasury_asset_shock: FiniteFloat = 0.0
    holder_concentration_shock: FiniteFloat = 0.0


class TokenomicsAnalysisRequest(TkModel):
    market: TokenMarketInput
    unlock_events: List[UnlockEventInput] = Field(min_length=1)
    holder_concentration: HolderConcentrationInput
    custom_scenarios: Optional[List[TokenomicsScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class TokenSummary(TkModel):
    symbol: NonEmptyStr
    token_name: NonEmptyStr
    price: FiniteFloat


class ValuationMetrics(TkModel):
    market_cap: FiniteFloat
    fully_diluted_valuation: FiniteFloat
    fdv_to_market_cap: FiniteFloat
    float_ratio: FiniteFloat
    circulating_supply: FiniteFloat
    total_supply: FiniteFloat
    max_supply: Optional[FiniteFloat] = None


class UnlockScheduleRow(TkModel):
    date: NonEmptyStr
    days_until: FiniteFloat
    category: NonEmptyStr
    tokens: FiniteFloat
    unlock_value: FiniteFloat
    unlock_pct_circulating: FiniteFloat
    cumulative_unlock_tokens: FiniteFloat
    cumulative_unlock_pct_circulating: FiniteFloat
    description: Optional[NonEmptyStr] = None


class UnlockPressure(TkModel):
    next_30d_tokens: FiniteFloat
    next_90d_tokens: FiniteFloat
    next_180d_tokens: FiniteFloat
    next_365d_tokens: FiniteFloat
    next_180d_pct_circulating: FiniteFloat
    pressure_score: FiniteFloat
    notes: List[NonEmptyStr]


class EmissionAnalysis(TkModel):
    emission_rate_annual: FiniteFloat
    annual_emission_tokens: FiniteFloat
    annual_emission_value: FiniteFloat
    emission_inflation: FiniteFloat
    notes: List[NonEmptyStr]


class StakingAnalysis(TkModel):
    staking_yield: FiniteFloat
    real_yield_approx: FiniteFloat
    protocol_revenue_yield: Optional[FiniteFloat] = None
    notes: List[NonEmptyStr]


class TreasuryAnalysis(TkModel):
    treasury_token_value: FiniteFloat
    treasury_stables: FiniteFloat
    treasury_total_value: FiniteFloat
    monthly_burn_usd: FiniteFloat
    monthly_revenue_usd: FiniteFloat
    runway_months: FiniteFloat
    revenue_adjusted_runway_months: FiniteFloat
    notes: List[NonEmptyStr]


class HolderConcentration(TkModel):
    top_1_holder_share: FiniteFloat
    top_5_holder_share: FiniteFloat
    top_10_holder_share: FiniteFloat
    insider_share: Optional[FiniteFloat] = None
    foundation_share: Optional[FiniteFloat] = None
    community_share: Optional[FiniteFloat] = None
    concentration_score: FiniteFloat
    notes: List[NonEmptyStr]


class RiskRegime(TkModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr


class TokenomicsScenarioResult(TkModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    price: FiniteFloat
    market_cap: FiniteFloat
    fully_diluted_valuation: FiniteFloat
    fdv_to_market_cap: FiniteFloat
    next_180d_unlock_pressure: FiniteFloat
    emission_inflation: FiniteFloat
    real_yield_approx: FiniteFloat
    treasury_value: FiniteFloat
    runway_months: FiniteFloat
    concentration_score: FiniteFloat
    regime_label: NonEmptyStr
    notes: List[NonEmptyStr]


class TokenomicsAnalysisResponse(TkModel):
    data_status: Literal["static_sample"] = "static_sample"
    token_summary: TokenSummary
    valuation_metrics: ValuationMetrics
    unlock_schedule: List[UnlockScheduleRow]
    unlock_pressure: UnlockPressure
    emission_analysis: EmissionAnalysis
    staking_analysis: StakingAnalysis
    treasury_analysis: TreasuryAnalysis
    holder_concentration: HolderConcentration
    risk_regime: RiskRegime
    scenario_results: List[TokenomicsScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class TokenomicsSampleResponse(TkModel):
    tokens: List[TokenomicsAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
