"""
Typed Pydantic models for the Release Readiness, Smoke Test Matrix & QA
Command Center (36.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so
no NaN/Infinity can enter or leave the API. Everything here is hand-written
static QA METADATA about QuantLab's own modules — smoke-test steps, manual
regression steps, release-status labels, and verification commands. It is a
project-quality workflow layer: it lists commands but NEVER runs them, and it
never claims tests or builds were executed. Educational only — not a
production compliance or release-management system, and not investment,
trading, legal, tax, compliance, or risk-management advice.
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

ReleaseStatus = Literal["ready", "needs_review", "experimental", "blocked"]
Priority = Literal["critical", "high", "medium", "low"]

DataMode = Literal[
    "static_sample",
    "delayed_sample",
    "user_input",
    "local_calculation",
    "optional_external_provider",
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
    "readiness_summary",
    "smoke_test_matrix",
    "regression_checklist",
    "command_checklist",
    "known_limitations",
    "release_notes",
    "release_decision",
]

ReleaseDecision = Literal[
    "ready_for_demo",
    "ready_with_limitations",
    "needs_review",
    "blocked",
]


class QaModel(BaseModel):
    """Strict base model for stable, JSON-safe QA-command-center payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Registry rows
# --------------------------------------------------------------------------- #
class QAModuleRow(QaModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    category: ModuleCategory
    route: NonEmptyStr
    has_backend_endpoint: bool
    has_frontend_page: bool
    has_charts: bool
    has_interactive_controls: bool
    has_formula_panel: bool
    has_tests: bool
    demo_safe: bool
    data_mode: DataMode
    release_status: ReleaseStatus
    priority: Priority
    smoke_test_steps: List[NonEmptyStr] = Field(min_length=1)
    manual_regression_steps: List[NonEmptyStr] = Field(min_length=1)
    known_limitations: List[NonEmptyStr] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class QACommandCenterRequest(QaModel):
    selected_category: Optional[ModuleCategory] = None
    selected_release_statuses: Optional[List[ReleaseStatus]] = None
    selected_priorities: Optional[List[Priority]] = None
    include_manual_steps: bool = True
    include_backend_checks: bool = True
    include_frontend_checks: bool = True
    include_known_limitations: bool = True
    report_sections: List[SectionId] = Field(min_length=1)

    @model_validator(mode="after")
    def _optional_lists_non_empty(self) -> "QACommandCenterRequest":
        if self.selected_release_statuses is not None and len(self.selected_release_statuses) == 0:
            raise ValueError("selected_release_statuses must be non-empty when provided")
        if self.selected_priorities is not None and len(self.selected_priorities) == 0:
            raise ValueError("selected_priorities must be non-empty when provided")
        return self


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class ReadinessSummary(QaModel):
    module_count: int
    ready_rate: UnitFloat
    smoke_coverage: UnitFloat
    test_coverage: UnitFloat
    interactive_coverage: UnitFloat
    chart_coverage: UnitFloat
    release_score: Score100
    release_decision: ReleaseDecision
    critical_blockers: List[NonEmptyStr]
    drivers: List[NonEmptyStr]


class SmokeTestRow(QaModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    route: NonEmptyStr
    steps: List[NonEmptyStr] = Field(min_length=1)
    expected_result: NonEmptyStr
    status_label: ReleaseStatus


class RegressionGroup(QaModel):
    category: ModuleCategory
    category_label: NonEmptyStr
    items: List[NonEmptyStr] = Field(min_length=1)


class CommandChecklist(QaModel):
    backend_test_command: NonEmptyStr
    frontend_typecheck_command: NonEmptyStr
    frontend_build_command_for_user: NonEmptyStr
    backend_run_command: NonEmptyStr
    notes: List[NonEmptyStr] = Field(min_length=1)


class LimitationRow(QaModel):
    module_id: NonEmptyStr
    module_name: NonEmptyStr
    data_mode: DataMode
    limitations: List[NonEmptyStr] = Field(min_length=1)


class ReportSectionOut(QaModel):
    section_id: SectionId
    section_title: NonEmptyStr
    included: bool
    markdown: NonEmptyStr


class GeneratedReport(QaModel):
    title: NonEmptyStr
    subtitle: NonEmptyStr
    sections: List[ReportSectionOut]
    markdown: NonEmptyStr


class ExportPayload(QaModel):
    markdown: NonEmptyStr
    json_payload: NonEmptyStr


class QACommandCenterAnalysisResponse(QaModel):
    data_status: Literal["static_sample"] = "static_sample"
    qa_modules: List[QAModuleRow]
    readiness_summary: ReadinessSummary
    smoke_test_matrix: List[SmokeTestRow]
    regression_checklist: List[RegressionGroup]
    command_checklist: CommandChecklist
    limitation_tracker: List[LimitationRow]
    release_notes: List[NonEmptyStr]
    generated_report: GeneratedReport
    export_payload: ExportPayload
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class SectionCatalogEntry(QaModel):
    section_id: SectionId
    section_title: NonEmptyStr


class CategoryCatalogEntry(QaModel):
    category: ModuleCategory
    category_label: NonEmptyStr


class QACommandCenterSampleResponse(QaModel):
    qa_modules: List[QAModuleRow]
    sections: List[SectionCatalogEntry]
    categories: List[CategoryCatalogEntry]
    release_statuses: List[ReleaseStatus]
    priorities: List[Priority]
    default_request: QACommandCenterRequest
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
