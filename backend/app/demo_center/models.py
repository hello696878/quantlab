"""
Typed Pydantic models for the Product Demo Center, Guided Walkthroughs &
Module Health Dashboard (34.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so
no NaN/Infinity can enter or leave the API. Everything here is hand-written
static illustrative demo METADATA about QuantLab's own modules — walkthrough
scripts, health/status labels, and capability flags for presenting the
platform. It is a product-UX layer, not a financial model: no live data, no
telemetry, no login, and not investment, trading, asset-allocation, legal,
tax, compliance, or risk-management advice.
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
UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]

AudienceId = Literal["founder", "investor", "quant_researcher", "recruiter", "student", "general"]

ScriptSectionId = Literal[
    "opening",
    "product_overview",
    "guided_steps",
    "module_highlights",
    "limitations",
    "closing",
]

ModuleStatus = Literal["stable_demo", "review_needed", "experimental", "static_sample_only"]
DataMode = Literal["static_sample", "delayed_sample", "user_input", "local_calculation"]

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


class DcModel(BaseModel):
    """Strict base model for stable, JSON-safe demo-center payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Demo metadata (served by /sample and echoed by /analyze)
# --------------------------------------------------------------------------- #
class DemoStep(DcModel):
    step_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    linked_module: NonEmptyStr
    route: NonEmptyStr  # QuantLab workspace view id (sidebar route)
    expected_user_action: NonEmptyStr
    expected_output: NonEmptyStr
    demo_tip: NonEmptyStr


class DemoPath(DcModel):
    path_id: NonEmptyStr
    title: NonEmptyStr
    audience: AudienceId
    estimated_minutes: PositiveFloat
    summary: NonEmptyStr
    modules: List[NonEmptyStr] = Field(min_length=1)
    steps: List[DemoStep] = Field(min_length=1)
    learning_goals: List[NonEmptyStr] = Field(min_length=1)
    suggested_talking_points: List[NonEmptyStr] = Field(min_length=1)
    limitations: List[NonEmptyStr] = Field(min_length=1)
    output_artifacts: List[NonEmptyStr] = Field(min_length=1)


class ModuleHealthRow(DcModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    category: ModuleCategory
    route: NonEmptyStr
    status: ModuleStatus
    data_mode: DataMode
    has_backend_endpoint: bool
    has_charts: bool
    has_interactive_controls: bool
    has_formula_panel: bool
    has_report_export: bool
    limitations: List[NonEmptyStr] = Field(min_length=1)
    recommended_demo_path: NonEmptyStr
    last_review_label: NonEmptyStr


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class DemoCenterRequest(DcModel):
    selected_path_id: NonEmptyStr
    selected_audience: AudienceId = "general"
    # None → the selected path's own module list; a subset narrows the scope.
    included_modules: Optional[List[NonEmptyStr]] = None
    script_sections: List[ScriptSectionId] = Field(min_length=1)
    time_budget_minutes: PositiveFloat = 20.0
    include_limitations: bool = True
    include_technical_notes: bool = False

    @model_validator(mode="after")
    def _included_modules_non_empty(self) -> "DemoCenterRequest":
        if self.included_modules is not None and len(self.included_modules) == 0:
            raise ValueError("included_modules must be non-empty when provided")
        return self


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class PathSummary(DcModel):
    path_id: NonEmptyStr
    title: NonEmptyStr
    audience: AudienceId
    estimated_minutes: FiniteFloat
    module_count: int
    step_count: int
    talking_point_count: int
    fits_time_budget: bool
    time_note: NonEmptyStr


class CapabilityMatrixRow(DcModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    category: ModuleCategory
    has_backend_endpoint: bool
    has_charts: bool
    has_interactive_controls: bool
    has_formula_panel: bool
    has_report_export: bool
    capability_score: UnitFloat  # K = enabled / total capabilities


class ReadinessSummary(DcModel):
    included_module_count: int
    category_coverage: UnitFloat
    readiness_score: UnitFloat
    demo_complexity_score: UnitFloat
    script_coverage: UnitFloat
    top_ready_modules: List[NonEmptyStr]
    review_needed_modules: List[NonEmptyStr]


class CompletionChecklistItem(DcModel):
    item_id: NonEmptyStr
    label: NonEmptyStr
    passed: bool
    notes: NonEmptyStr


class ScriptSectionOut(DcModel):
    section_id: ScriptSectionId
    section_title: NonEmptyStr
    included: bool
    markdown: NonEmptyStr


class GeneratedScript(DcModel):
    title: NonEmptyStr
    subtitle: NonEmptyStr
    sections: List[ScriptSectionOut]
    markdown: NonEmptyStr


class ExportPayload(DcModel):
    markdown: NonEmptyStr
    json_payload: NonEmptyStr


class DemoCenterAnalysisResponse(DcModel):
    data_status: Literal["static_sample"] = "static_sample"
    selected_path: DemoPath
    demo_paths: List[DemoPath]
    module_health: List[ModuleHealthRow]
    path_summary: PathSummary
    readiness_summary: ReadinessSummary
    capability_matrix: List[CapabilityMatrixRow]
    completion_checklist: List[CompletionChecklistItem]
    generated_script: GeneratedScript
    export_payload: ExportPayload
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class SectionCatalogEntry(DcModel):
    section_id: ScriptSectionId
    section_title: NonEmptyStr


class DemoCenterSampleResponse(DcModel):
    demo_paths: List[DemoPath]
    module_health: List[ModuleHealthRow]
    script_sections: List[SectionCatalogEntry]
    audiences: List[AudienceId]
    default_request: DemoCenterRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
