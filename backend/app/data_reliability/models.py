"""
Typed Pydantic models for the Data Mode Registry, Offline Fixtures & API
Reliability Center (35.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so
no NaN/Infinity can enter or leave the API. Everything here is hand-written
static reliability METADATA about QuantLab's own modules, providers, and
fixtures — a product reliability layer, not a financial model and not a data
governance system. It never calls the providers it describes; external
availability is never guaranteed. Educational only — not investment, trading,
asset-allocation, legal, tax, compliance, or risk-management advice.
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
UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
Score100 = Annotated[FiniteFloat, Field(ge=0.0, le=100.0)]

DataMode = Literal[
    "static_sample",
    "delayed_sample",
    "user_input",
    "local_calculation",
    "optional_external_provider",
]

ProviderType = Literal[
    "market_data",
    "macro_data",
    "static_fixture",
    "local_calculation",
    "user_input",
]

FailureMode = Literal[
    "fallback_to_fixture",
    "friendly_error",
    "disabled_in_tests",
    "static_only",
]

FixtureType = Literal[
    "price_series",
    "macro_series",
    "scenario_template",
    "lab_sample",
    "report_sample",
]

ModuleCategory = Literal[
    "platform",
    "backtesting",
    "portfolio_risk",
    "macro_cross_asset",
    "research_workflow",
    "crypto",
    "alternative_data",
    "microstructure",
    "derivatives_volatility",
    "real_assets_credit",
]

SectionId = Literal[
    "overview",
    "module_modes",
    "providers",
    "offline_fixtures",
    "test_safety",
    "limitations",
    "recommendations",
]

ReliabilityBucket = Literal[
    "highly_deterministic",
    "mostly_deterministic",
    "mixed",
    "external_dependent",
]


class DrModel(BaseModel):
    """Strict base model for stable, JSON-safe data-reliability payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Registry rows (served by /sample and echoed by /analyze)
# --------------------------------------------------------------------------- #
class ModuleDataModeRow(DrModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    category: ModuleCategory
    route: NonEmptyStr
    data_mode: DataMode
    demo_safe: bool
    test_safe: bool
    external_provider_required: bool
    offline_fallback_available: bool
    default_demo_deterministic: bool
    provider_names: List[NonEmptyStr] = Field(min_length=1)
    fixture_names: List[NonEmptyStr] = Field(default_factory=list)
    failure_behavior: NonEmptyStr
    user_visible_label: NonEmptyStr
    limitations: List[NonEmptyStr] = Field(min_length=1)
    recommended_handling: NonEmptyStr


class ProviderRow(DrModel):
    provider_id: NonEmptyStr
    provider_name: NonEmptyStr
    provider_type: ProviderType
    used_by_modules: List[NonEmptyStr] = Field(min_length=1)
    is_external: bool
    requires_network: bool
    requires_api_key: bool
    allowed_in_tests: bool
    has_offline_fallback: bool
    default_failure_mode: FailureMode
    limitations: List[NonEmptyStr] = Field(min_length=1)
    user_message: NonEmptyStr


class OfflineFixtureRow(DrModel):
    fixture_id: NonEmptyStr
    fixture_name: NonEmptyStr
    fixture_type: FixtureType
    used_by_modules: List[NonEmptyStr] = Field(min_length=1)
    observation_count: int = Field(ge=1)
    date_range_label: NonEmptyStr
    deterministic: bool
    test_safe: bool
    description: NonEmptyStr
    limitations: List[NonEmptyStr] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class DataReliabilityRequest(DrModel):
    selected_category: Optional[ModuleCategory] = None
    include_external_providers: bool = True
    include_static_fixtures: bool = True
    include_test_safety: bool = True
    # None → the full registry; a subset narrows the analysis scope.
    selected_modules: Optional[List[NonEmptyStr]] = None
    report_sections: List[SectionId] = Field(min_length=1)

    @model_validator(mode="after")
    def _selected_modules_non_empty(self) -> "DataReliabilityRequest":
        if self.selected_modules is not None and len(self.selected_modules) == 0:
            raise ValueError("selected_modules must be non-empty when provided")
        return self


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class ReliabilitySummary(DrModel):
    module_count: int
    demo_safe_rate: UnitFloat
    test_safe_rate: UnitFloat
    fallback_coverage: UnitFloat
    external_provider_exposure: UnitFloat
    reliability_score: Score100
    reliability_bucket: ReliabilityBucket
    drivers: List[NonEmptyStr]


class TestSafetyRow(DrModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    test_safe: bool
    external_provider_required: bool
    notes: NonEmptyStr


class FallbackRow(DrModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    external_provider_required: bool
    offline_fallback_available: bool
    failure_behavior: NonEmptyStr


class ReportSectionOut(DrModel):
    section_id: SectionId
    section_title: NonEmptyStr
    included: bool
    markdown: NonEmptyStr


class GeneratedReport(DrModel):
    title: NonEmptyStr
    subtitle: NonEmptyStr
    sections: List[ReportSectionOut]
    markdown: NonEmptyStr


class ExportPayload(DrModel):
    markdown: NonEmptyStr
    json_payload: NonEmptyStr


class DataReliabilityAnalysisResponse(DrModel):
    data_status: Literal["static_sample"] = "static_sample"
    module_modes: List[ModuleDataModeRow]
    providers: List[ProviderRow]
    offline_fixtures: List[OfflineFixtureRow]
    reliability_summary: ReliabilitySummary
    test_safety_matrix: List[TestSafetyRow]
    fallback_matrix: List[FallbackRow]
    generated_report: GeneratedReport
    export_payload: ExportPayload
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class SectionCatalogEntry(DrModel):
    section_id: SectionId
    section_title: NonEmptyStr


class CategoryCatalogEntry(DrModel):
    category: ModuleCategory
    category_label: NonEmptyStr


class DataReliabilitySampleResponse(DrModel):
    module_modes: List[ModuleDataModeRow]
    providers: List[ProviderRow]
    offline_fixtures: List[OfflineFixtureRow]
    sections: List[SectionCatalogEntry]
    categories: List[CategoryCatalogEntry]
    default_request: DataReliabilityRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
