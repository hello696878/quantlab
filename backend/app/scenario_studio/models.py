"""
Typed Pydantic models for the Unified Scenario Studio & Cross-Lab Report
Builder (32.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so
no NaN/Infinity can enter or leave the API. Scenario shocks are standardized
illustrative stress intensities (z-score-like units, not market returns);
multipliers are neutral at 1.0. All data is static illustrative sample data —
educational only, not investment, trading, asset-allocation, legal, tax, or
risk-management advice; never live macro, market, crypto, or news data.
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
NonNegFloat = Annotated[FiniteFloat, Field(ge=0)]

ModuleId = Literal[
    "macro_regime",
    "portfolio_risk",
    "crypto_derivatives",
    "defi_risk",
    "tokenomics",
    "onchain_analytics",
    "alternative_data",
    "market_microstructure",
]

SectionId = Literal[
    "executive_summary",
    "macro",
    "portfolio",
    "crypto",
    "defi",
    "tokenomics",
    "onchain",
    "alternative_data",
    "limitations",
]

ImpactBucket = Literal["low", "moderate", "elevated", "high", "severe"]

RegimeId = Literal[
    "benign_cross_asset",
    "macro_policy_stress",
    "credit_liquidity_stress",
    "crypto_specific_stress",
    "data_quality_stress",
    "broad_risk_off",
    "severe_systemic_stress",
]


class SsModel(BaseModel):
    """Strict base model for stable, JSON-safe scenario-studio payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class ScenarioTemplateInput(SsModel):
    scenario_id: NonEmptyStr
    scenario_name: NonEmptyStr
    description: NonEmptyStr
    # Signed standardized shocks (illustrative z-score-like intensities).
    growth_shock: FiniteFloat = 0.0
    inflation_shock: FiniteFloat = 0.0
    policy_shock: FiniteFloat = 0.0
    liquidity_shock: FiniteFloat = 0.0
    credit_shock: FiniteFloat = 0.0
    usd_shock: FiniteFloat = 0.0
    equity_shock: FiniteFloat = 0.0
    rate_shock: FiniteFloat = 0.0
    credit_spread_shock: FiniteFloat = 0.0
    crypto_price_shock: FiniteFloat = 0.0
    funding_rate_shock: FiniteFloat = 0.0
    defi_liquidity_shock: FiniteFloat = 0.0
    stablecoin_depeg_shock: FiniteFloat = 0.0
    whale_concentration_shock: FiniteFloat = 0.0
    sentiment_shock: FiniteFloat = 0.0
    # Multipliers (neutral at 1.0) and non-negative lag intensity.
    volatility_multiplier: PositiveFloat = 1.0
    token_unlock_multiplier: NonNegFloat = 1.0
    exchange_inflow_multiplier: NonNegFloat = 1.0
    publication_lag_shock: NonNegFloat = 0.0


class ScenarioShockOverrides(SsModel):
    """Optional per-shock overrides applied on top of the selected template."""

    growth_shock: Optional[FiniteFloat] = None
    inflation_shock: Optional[FiniteFloat] = None
    policy_shock: Optional[FiniteFloat] = None
    liquidity_shock: Optional[FiniteFloat] = None
    credit_shock: Optional[FiniteFloat] = None
    usd_shock: Optional[FiniteFloat] = None
    equity_shock: Optional[FiniteFloat] = None
    rate_shock: Optional[FiniteFloat] = None
    credit_spread_shock: Optional[FiniteFloat] = None
    crypto_price_shock: Optional[FiniteFloat] = None
    funding_rate_shock: Optional[FiniteFloat] = None
    defi_liquidity_shock: Optional[FiniteFloat] = None
    stablecoin_depeg_shock: Optional[FiniteFloat] = None
    whale_concentration_shock: Optional[FiniteFloat] = None
    sentiment_shock: Optional[FiniteFloat] = None
    volatility_multiplier: Optional[PositiveFloat] = None
    token_unlock_multiplier: Optional[NonNegFloat] = None
    exchange_inflow_multiplier: Optional[NonNegFloat] = None
    publication_lag_shock: Optional[NonNegFloat] = None


class ScenarioStudioRequest(SsModel):
    selected_scenario_id: NonEmptyStr
    custom_overrides: Optional[ScenarioShockOverrides] = None
    included_modules: List[ModuleId] = Field(min_length=1)
    report_sections: List[SectionId] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class ModuleImpactRow(SsModel):
    module_id: ModuleId
    module_label: NonEmptyStr
    baseline_score: FiniteFloat
    stressed_score: FiniteFloat
    impact_score: FiniteFloat
    impact_bucket: ImpactBucket
    drivers: List[NonEmptyStr]
    notes: List[NonEmptyStr]


class ScenarioRegime(SsModel):
    regime_id: RegimeId
    regime_label: NonEmptyStr
    severity_score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr
    notes: List[NonEmptyStr]


class BaselineStressRow(SsModel):
    metric_name: NonEmptyStr
    baseline_value: FiniteFloat
    stressed_value: FiniteFloat
    change: FiniteFloat
    module_id: ModuleId


class HeatmapCell(SsModel):
    row_label: NonEmptyStr
    column_label: NonEmptyStr
    value: FiniteFloat
    bucket: ImpactBucket


class ReportSection(SsModel):
    section_id: SectionId
    section_title: NonEmptyStr
    included: bool
    markdown: NonEmptyStr


class GeneratedReport(SsModel):
    title: NonEmptyStr
    subtitle: NonEmptyStr
    sections: List[ReportSection]
    markdown: NonEmptyStr
    limitations: List[NonEmptyStr]


class ReportBuilderSummary(SsModel):
    available_sections: List[SectionId]
    included_sections: List[SectionId]
    # C = N_included / N_available (limitations is always included).
    section_coverage: FiniteFloat
    notes: List[NonEmptyStr]


class GlobalShockRow(SsModel):
    shock_id: NonEmptyStr
    shock_label: NonEmptyStr
    value: FiniteFloat
    neutral_value: FiniteFloat
    overridden: bool


class ModuleCatalogEntry(SsModel):
    module_id: ModuleId
    module_label: NonEmptyStr


class SectionCatalogEntry(SsModel):
    section_id: SectionId
    section_title: NonEmptyStr


class ScenarioStudioAnalysisResponse(SsModel):
    data_status: Literal["static_sample"] = "static_sample"
    selected_scenario: ScenarioTemplateInput
    global_shocks: List[GlobalShockRow]
    module_impacts: List[ModuleImpactRow]
    composite_severity: FiniteFloat
    scenario_regime: ScenarioRegime
    baseline_vs_stress: List[BaselineStressRow]
    heatmap: List[HeatmapCell]
    report_builder: ReportBuilderSummary
    generated_report: GeneratedReport
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class ScenarioStudioSampleResponse(SsModel):
    templates: List[ScenarioTemplateInput]
    modules: List[ModuleCatalogEntry]
    sections: List[SectionCatalogEntry]
    default_request: ScenarioStudioRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
