"""
Typed Pydantic models for the Macro Regime & Cross-Asset Allocation Lab (31.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, asset-allocation, legal, tax,
or risk-management advice; never live macro or market data (no FRED, no
yfinance, no scraping in this lab).
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegFloat = Annotated[FiniteFloat, Field(ge=0)]
UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
IndicatorCategory = Literal["growth", "inflation", "policy", "liquidity", "credit", "fx"]
AssetCategory = Literal["equity", "duration", "credit", "commodity", "fx", "real_asset", "crypto", "cash"]
Direction = Literal["higher_is_expansionary", "higher_is_contractionary"]


class MrModel(BaseModel):
    """Strict base model for stable, JSON-safe macro-regime payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class MacroIndicatorInput(MrModel):
    name: NonEmptyStr
    category: IndicatorCategory
    value: FiniteFloat
    long_run_mean: FiniteFloat
    long_run_std: PositiveFloat
    # Sign convention only: the direction flag orients each indicator so that a
    # HIGHER category score always means stronger growth / hotter inflation /
    # tighter policy / easier liquidity / more credit stress / stronger USD.
    direction: Direction
    weight: NonNegFloat = 1.0


class AssetClassInput(MrModel):
    asset_id: NonEmptyStr
    asset_name: NonEmptyStr
    category: AssetCategory
    expected_return: FiniteFloat
    volatility: PositiveFloat
    liquidity_score: UnitFloat
    inflation_beta: FiniteFloat
    growth_beta: FiniteFloat
    rate_beta: FiniteFloat
    usd_beta: FiniteFloat
    credit_beta: FiniteFloat


class MacroScenarioInput(MrModel):
    name: NonEmptyStr
    growth_shock: FiniteFloat = 0.0
    inflation_shock: FiniteFloat = 0.0
    policy_shock: FiniteFloat = 0.0
    liquidity_shock: FiniteFloat = 0.0
    credit_shock: FiniteFloat = 0.0
    usd_shock: FiniteFloat = 0.0
    volatility_multiplier: PositiveFloat = 1.0
    correlation_stress: UnitFloat = 0.0


class MacroRegimeAnalysisRequest(MrModel):
    sample_id: NonEmptyStr
    sample_name: NonEmptyStr
    indicators: List[MacroIndicatorInput] = Field(min_length=1)
    assets: List[AssetClassInput] = Field(min_length=2)
    # Documented editable assumptions for the regime-tilted educational weights.
    risk_aversion_lambda: NonNegFloat = 0.2
    liquidity_preference_eta: NonNegFloat = 0.01
    custom_scenarios: Optional[List[MacroScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class SampleSummary(MrModel):
    sample_id: NonEmptyStr
    sample_name: NonEmptyStr
    indicator_count: int
    asset_count: int


class IndicatorRow(MrModel):
    name: NonEmptyStr
    category: IndicatorCategory
    value: FiniteFloat
    long_run_mean: FiniteFloat
    long_run_std: FiniteFloat
    z_score: FiniteFloat
    direction_adjusted_score: FiniteFloat
    weight: FiniteFloat


class CategoryScores(MrModel):
    growth_score: FiniteFloat
    inflation_score: FiniteFloat
    policy_score: FiniteFloat
    liquidity_score: FiniteFloat
    credit_stress_score: FiniteFloat
    usd_pressure_score: FiniteFloat
    composite_macro_score: FiniteFloat


class MacroRegime(MrModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr


class AssetAssumptionRow(MrModel):
    asset_id: NonEmptyStr
    asset_name: NonEmptyStr
    category: AssetCategory
    expected_return: FiniteFloat
    regime_adjusted_expected_return: FiniteFloat
    volatility: FiniteFloat
    liquidity_score: FiniteFloat
    growth_beta: FiniteFloat
    inflation_beta: FiniteFloat
    rate_beta: FiniteFloat
    usd_beta: FiniteFloat
    credit_beta: FiniteFloat


class AllocationResult(MrModel):
    method: NonEmptyStr
    weights: Dict[str, FiniteFloat]
    portfolio_expected_return: FiniteFloat
    portfolio_volatility_approx: FiniteFloat
    risk_contributions: Dict[str, FiniteFloat]
    notes: List[NonEmptyStr]


class MacroScenarioResult(MrModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    growth_score: FiniteFloat
    inflation_score: FiniteFloat
    policy_score: FiniteFloat
    liquidity_score: FiniteFloat
    credit_stress_score: FiniteFloat
    usd_pressure_score: FiniteFloat
    regime_label: NonEmptyStr
    portfolio_expected_return: FiniteFloat
    portfolio_volatility_approx: FiniteFloat
    largest_weight_asset: NonEmptyStr
    notes: List[NonEmptyStr]


class MacroRegimeAnalysisResponse(MrModel):
    data_status: Literal["static_sample"] = "static_sample"
    sample_summary: SampleSummary
    indicator_table: List[IndicatorRow]
    category_scores: CategoryScores
    macro_regime: MacroRegime
    asset_assumptions: List[AssetAssumptionRow]
    allocation_results: List[AllocationResult]
    scenario_results: List[MacroScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class MacroRegimeSampleResponse(MrModel):
    samples: List[MacroRegimeAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
