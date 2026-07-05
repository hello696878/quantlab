"""
Typed Pydantic models for the On-Chain Flow, Exchange Reserve & Whale
Concentration Lab (29.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, token, legal, tax, or
risk-management advice; never live on-chain data, live token prices, wallets,
RPC, smart-contract, explorer, or exchange API calls.
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


class OcModel(BaseModel):
    """Strict base model for stable, JSON-safe on-chain analytics payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class OnChainNetworkInput(OcModel):
    symbol: NonEmptyStr
    token_name: NonEmptyStr
    network_name: NonEmptyStr
    token_price: PositiveFloat
    circulating_supply: PositiveFloat
    exchange_reserve_tokens: NonNegFloat
    exchange_inflow_tokens_24h: NonNegFloat
    exchange_outflow_tokens_24h: NonNegFloat
    active_addresses_24h: NonNegFloat
    transfer_volume_tokens_24h: NonNegFloat
    transaction_count_24h: NonNegFloat
    average_transaction_value_tokens: Optional[NonNegFloat] = None


class HolderCohortInput(OcModel):
    cohort_name: NonEmptyStr
    holder_count: NonNegFloat
    token_balance: NonNegFloat
    description: Optional[NonEmptyStr] = None


class WhaleFlowInput(OcModel):
    whale_inflow_tokens_24h: NonNegFloat
    whale_outflow_tokens_24h: NonNegFloat
    top_10_holder_share: UnitFloat
    top_50_holder_share: UnitFloat
    top_100_holder_share: UnitFloat

    @model_validator(mode="after")
    def _check(self) -> "WhaleFlowInput":
        if not (self.top_10_holder_share <= self.top_50_holder_share <= self.top_100_holder_share):
            raise ValueError(
                "holder shares must satisfy top_10 <= top_50 <= top_100 "
                f"({self.top_10_holder_share}, {self.top_50_holder_share}, {self.top_100_holder_share})"
            )
        return self


class OnChainScenarioInput(OcModel):
    name: NonEmptyStr
    price_shock: FiniteFloat = 0.0
    inflow_multiplier: NonNegFloat = 1.0
    outflow_multiplier: NonNegFloat = 1.0
    reserve_change_multiplier: NonNegFloat = 1.0
    active_address_shock: FiniteFloat = 0.0
    transfer_volume_multiplier: NonNegFloat = 1.0
    whale_concentration_shock: FiniteFloat = 0.0


class OnChainAnalysisRequest(OcModel):
    network: OnChainNetworkInput
    holder_cohorts: List[HolderCohortInput] = Field(min_length=1)
    whale_flow: WhaleFlowInput
    custom_scenarios: Optional[List[OnChainScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class NetworkSummary(OcModel):
    symbol: NonEmptyStr
    token_name: NonEmptyStr
    network_name: NonEmptyStr
    token_price: FiniteFloat
    circulating_supply: FiniteFloat


class ExchangeFlowAnalysis(OcModel):
    exchange_reserve_tokens: FiniteFloat
    exchange_reserve_value: FiniteFloat
    exchange_reserve_ratio: FiniteFloat
    exchange_inflow_tokens_24h: FiniteFloat
    exchange_outflow_tokens_24h: FiniteFloat
    net_exchange_flow_tokens: FiniteFloat
    net_exchange_flow_value: FiniteFloat
    net_exchange_flow_pct_circulating: FiniteFloat
    reserve_change_tokens: FiniteFloat


class ActivityMetrics(OcModel):
    active_addresses_24h: FiniteFloat
    transfer_volume_tokens_24h: FiniteFloat
    transfer_volume_value_24h: FiniteFloat
    transaction_count_24h: FiniteFloat
    average_transaction_value_tokens: FiniteFloat
    token_velocity: FiniteFloat


class OnChainValuationMetrics(OcModel):
    token_price: FiniteFloat
    market_cap: FiniteFloat
    nvt_ratio: FiniteFloat
    nvt_status: Literal["low", "moderate", "elevated", "high"]


class HolderDistributionRow(OcModel):
    cohort_name: NonEmptyStr
    holder_count: FiniteFloat
    token_balance: FiniteFloat
    balance_share: FiniteFloat
    average_balance: FiniteFloat
    description: Optional[NonEmptyStr] = None


class WhaleAnalysis(OcModel):
    whale_inflow_tokens_24h: FiniteFloat
    whale_outflow_tokens_24h: FiniteFloat
    whale_net_flow_tokens: FiniteFloat
    whale_net_flow_pct_circulating: FiniteFloat
    top_10_holder_share: FiniteFloat
    top_50_holder_share: FiniteFloat
    top_100_holder_share: FiniteFloat


class ConcentrationAnalysis(OcModel):
    concentration_score: FiniteFloat
    gini_style_score: FiniteFloat
    largest_cohort_share: FiniteFloat
    notes: List[NonEmptyStr]


class RiskRegime(OcModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr


class OnChainScenarioResult(OcModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    token_price: FiniteFloat
    market_cap: FiniteFloat
    net_exchange_flow_tokens: FiniteFloat
    net_exchange_flow_pct_circulating: FiniteFloat
    exchange_reserve_ratio: FiniteFloat
    active_addresses_24h: FiniteFloat
    transfer_volume_tokens_24h: FiniteFloat
    token_velocity: FiniteFloat
    nvt_ratio: FiniteFloat
    whale_net_flow_tokens: FiniteFloat
    concentration_score: FiniteFloat
    regime_label: NonEmptyStr
    notes: List[NonEmptyStr]


class OnChainAnalysisResponse(OcModel):
    data_status: Literal["static_sample"] = "static_sample"
    network_summary: NetworkSummary
    exchange_flow: ExchangeFlowAnalysis
    activity_metrics: ActivityMetrics
    valuation_metrics: OnChainValuationMetrics
    holder_distribution: List[HolderDistributionRow]
    whale_analysis: WhaleAnalysis
    concentration_analysis: ConcentrationAnalysis
    risk_regime: RiskRegime
    scenario_results: List[OnChainScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class OnChainSampleResponse(OcModel):
    networks: List[OnChainAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
