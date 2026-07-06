"""
Typed Pydantic models for the Research Workspace, Saved Presets & Experiment
Journal (33.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so
no NaN/Infinity can enter or leave the API. Presets and experiment runs are
hand-written static illustrative samples on fixed timestamps — an educational
research-workflow illustration, not production research records, not
compliance records, and not investment, trading, asset-allocation, legal,
tax, compliance, or risk-management advice; never live data.
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
NoteStr = Annotated[str, StringConstraints(max_length=500)]
UserNoteStr = Annotated[str, StringConstraints(max_length=2000)]
SeverityFloat = Annotated[FiniteFloat, Field(ge=0.0, le=100.0)]

ModuleId = Literal[
    "macro_regime",
    "portfolio_risk",
    "scenario_studio",
    "crypto_derivatives",
    "defi_risk",
    "tokenomics",
    "onchain_analytics",
    "alternative_data",
    "market_microstructure",
]

SectionId = Literal[
    "overview",
    "assumptions",
    "experiment_summary",
    "run_comparison",
    "methodology",
    "limitations",
    "next_steps",
]

ConfidenceLabel = Literal["low", "medium", "high"]
SeverityBucket = Literal["low", "moderate", "elevated", "high", "severe"]
TimelineStatus = Literal["complete", "in_progress", "planned"]

WorkspaceRegimeId = Literal[
    "calm_research_pack",
    "focused_module_review",
    "multi_module_stress",
    "severe_research_pack",
    "incomplete_methodology",
]


class RwModel(BaseModel):
    """Strict base model for stable, JSON-safe research-workspace payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class ExperimentRunInput(RwModel):
    run_id: NonEmptyStr
    run_name: NonEmptyStr
    module_id: ModuleId
    scenario_name: NonEmptyStr
    created_at: NonEmptyStr  # static illustrative ISO timestamp, not a live clock
    key_metric_name: NonEmptyStr
    baseline_value: FiniteFloat
    stressed_value: FiniteFloat
    severity_score: SeverityFloat
    confidence_label: ConfidenceLabel
    notes: NoteStr = ""
    chart_points: Optional[List[FiniteFloat]] = None


class ResearchWorkspacePresetInput(RwModel):
    preset_id: NonEmptyStr
    preset_name: NonEmptyStr
    description: NonEmptyStr
    primary_module: ModuleId
    linked_modules: List[ModuleId] = Field(min_length=1)
    created_at: NonEmptyStr
    tags: List[NonEmptyStr] = Field(default_factory=list)
    assumptions: List[NonEmptyStr] = Field(default_factory=list)
    limitations: List[NonEmptyStr] = Field(default_factory=list)
    experiment_runs: List[ExperimentRunInput] = Field(min_length=1)


class WorkspaceAnalysisRequest(RwModel):
    selected_preset_id: NonEmptyStr
    # None → all of the preset's runs; an explicit list stages a subset.
    included_run_ids: Optional[List[NonEmptyStr]] = None
    user_note: Optional[UserNoteStr] = None
    report_sections: List[SectionId] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class RunComparisonRow(RwModel):
    run_id: NonEmptyStr
    run_name: NonEmptyStr
    module_id: ModuleId
    scenario_name: NonEmptyStr
    key_metric_name: NonEmptyStr
    baseline_value: FiniteFloat
    stressed_value: FiniteFloat
    change: FiniteFloat
    percent_change: FiniteFloat
    severity_score: SeverityFloat
    confidence_label: ConfidenceLabel
    notes: NoteStr


class SeveritySummary(RwModel):
    average_severity: SeverityFloat
    max_severity: SeverityFloat
    highest_severity_run_id: NonEmptyStr
    severity_bucket: SeverityBucket
    workspace_regime: WorkspaceRegimeId
    regime_label: NonEmptyStr
    coverage_score: FiniteFloat
    reproducibility_score: FiniteFloat
    drivers: List[NonEmptyStr]


class WorkflowTimelineItem(RwModel):
    step_id: NonEmptyStr
    step_title: NonEmptyStr
    step_description: NonEmptyStr
    status: TimelineStatus
    linked_module: Optional[ModuleId] = None


class MethodologyChecklistItem(RwModel):
    item_id: NonEmptyStr
    label: NonEmptyStr
    passed: bool
    notes: NonEmptyStr


class ReportSectionOut(RwModel):
    section_id: SectionId
    section_title: NonEmptyStr
    included: bool
    markdown: NonEmptyStr


class ReportPreview(RwModel):
    title: NonEmptyStr
    subtitle: NonEmptyStr
    sections: List[ReportSectionOut]
    markdown: NonEmptyStr


class ExportPayload(RwModel):
    markdown: NonEmptyStr
    json_payload: NonEmptyStr


class ModuleCatalogEntry(RwModel):
    module_id: ModuleId
    module_label: NonEmptyStr


class SectionCatalogEntry(RwModel):
    section_id: SectionId
    section_title: NonEmptyStr


class ResearchWorkspaceAnalysisResponse(RwModel):
    data_status: Literal["static_sample"] = "static_sample"
    selected_preset: ResearchWorkspacePresetInput
    run_comparison: List[RunComparisonRow]
    severity_summary: SeveritySummary
    workflow_timeline: List[WorkflowTimelineItem]
    methodology_checklist: List[MethodologyChecklistItem]
    report_preview: ReportPreview
    export_payload: ExportPayload
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class ResearchWorkspaceSampleResponse(RwModel):
    presets: List[ResearchWorkspacePresetInput]
    modules: List[ModuleCatalogEntry]
    sections: List[SectionCatalogEntry]
    default_request: WorkspaceAnalysisRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
