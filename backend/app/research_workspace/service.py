"""
Research Workspace, Saved Presets & Experiment Journal analytics (Phase 33.0)
— pure, deterministic.

Given a selected preset (plus an optional staged-run subset, a user note, and
a report-section selection) it computes run change Δ = stress − base, a
guarded percentage change Δ% = Δ/(|base| + ε), average/max severity, a
severity-ranked run comparison, a module coverage score, a deterministic
reproducibility score R = passed_checks/total_checks from a documented
methodology checklist, a workspace-regime classification, a workflow
timeline, a deterministic Markdown report preview, and a copyable
Markdown + JSON export payload.

All outputs are finite by construction (inputs are FiniteFloat, every
division is guarded), so no NaN/Infinity reaches the API. Educational only —
not investment, trading, or asset-allocation advice; not production research
records or compliance records; never live data.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from app.research_workspace.models import (
    ExperimentRunInput,
    ExportPayload,
    MethodologyChecklistItem,
    ReportPreview,
    ReportSectionOut,
    ResearchWorkspaceAnalysisResponse,
    ResearchWorkspacePresetInput,
    RunComparisonRow,
    SeveritySummary,
    WorkflowTimelineItem,
    WorkspaceAnalysisRequest,
)
from app.research_workspace.sample import (
    DISCLAIMER,
    MODULE_LABELS,
    SECTION_TITLES,
    preset_by_id,
)

_EPS = 1e-9
_SECTION_IDS = list(SECTION_TITLES.keys())

_REGIME_LABELS = {
    "calm_research_pack": "Calm research pack",
    "focused_module_review": "Focused module review",
    "multi_module_stress": "Multi-module stress",
    "severe_research_pack": "Severe research pack",
    "incomplete_methodology": "Incomplete methodology",
}

_GLOBAL_LIMITATIONS = [
    "Static illustrative sample presets and runs — hand-written numbers on fixed timestamps, not recorded lab outputs, not live or current data.",
    "Severity scores and confidence labels are documented teaching heuristics, not risk measurements or research quality ratings.",
    "The reproducibility score counts documentation checks — it does not verify that any result actually reproduces.",
    "The generated report and export payload are deterministic educational summaries — not production research records, not compliance records, and not investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice.",
]


def _bucket(x: float) -> str:
    if x < 15.0:
        return "low"
    if x < 35.0:
        return "moderate"
    if x < 55.0:
        return "elevated"
    if x < 75.0:
        return "high"
    return "severe"


def _pct_change(change: float, baseline: float) -> float:
    return change / (abs(baseline) + _EPS)


def _included_runs(
    preset: ResearchWorkspacePresetInput, request: WorkspaceAnalysisRequest
) -> List[ExperimentRunInput]:
    if request.included_run_ids is None:
        return list(preset.experiment_runs)
    wanted = set(request.included_run_ids)
    runs = [r for r in preset.experiment_runs if r.run_id in wanted]
    if not runs:
        raise ValueError("included_run_ids matches none of the preset's experiment runs")
    return runs


# --------------------------------------------------------------------------- #
# Run comparison + severity summary
# --------------------------------------------------------------------------- #
def _comparison_rows(runs: List[ExperimentRunInput]) -> List[RunComparisonRow]:
    rows = []
    for r in runs:
        change = r.stressed_value - r.baseline_value
        rows.append(
            RunComparisonRow(
                run_id=r.run_id,
                run_name=r.run_name,
                module_id=r.module_id,
                scenario_name=r.scenario_name,
                key_metric_name=r.key_metric_name,
                baseline_value=r.baseline_value,
                stressed_value=r.stressed_value,
                change=change,
                percent_change=_pct_change(change, r.baseline_value),
                severity_score=r.severity_score,
                confidence_label=r.confidence_label,
                notes=r.notes,
            )
        )
    # Ranked by severity descending; run_id is the deterministic tie-break.
    return sorted(rows, key=lambda x: (-x.severity_score, x.run_id))


def _checklist(
    preset: ResearchWorkspacePresetInput,
    runs: List[ExperimentRunInput],
    request: WorkspaceAnalysisRequest,
) -> List[MethodologyChecklistItem]:
    runs_annotated = all(r.notes.strip() for r in runs)
    checks: List[Tuple[str, str, bool, str]] = [
        (
            "assumptions_documented", "Assumptions documented",
            len(preset.assumptions) > 0,
            f"{len(preset.assumptions)} assumption(s) recorded on the preset.",
        ),
        (
            "limitations_documented", "Limitations documented",
            len(preset.limitations) > 0,
            f"{len(preset.limitations)} limitation(s) recorded on the preset.",
        ),
        (
            "run_notes_present", "Every staged run annotated",
            runs_annotated,
            "All staged runs carry notes." if runs_annotated
            else "At least one staged run has an empty notes field.",
        ),
        (
            "limitations_section_selected", "Limitations section selected",
            "limitations" in request.report_sections,
            "The generated report will carry the limitations section."
            if "limitations" in request.report_sections
            else "The limitations section is not part of the current report selection.",
        ),
        (
            "multiple_runs_compared", "At least two runs compared",
            len(runs) >= 2,
            f"{len(runs)} run(s) staged for comparison.",
        ),
        (
            "baselines_recorded", "Baseline and stressed values recorded",
            all(True for _ in runs),  # schema-enforced FiniteFloat; kept as a visible check
            "Every staged run records finite baseline and stressed values.",
        ),
    ]
    return [
        MethodologyChecklistItem(item_id=i, label=label, passed=passed, notes=note)
        for i, label, passed, note in checks
    ]


def _severity_summary(
    preset: ResearchWorkspacePresetInput,
    rows: List[RunComparisonRow],
    checklist: List[MethodologyChecklistItem],
) -> SeveritySummary:
    avg = sum(r.severity_score for r in rows) / len(rows)
    top = rows[0]  # rows are severity-ranked
    distinct_modules = sorted({r.module_id for r in rows})
    coverage = len(distinct_modules) / len(MODULE_LABELS)
    passed = sum(1 for c in checklist if c.passed)
    repro = passed / len(checklist)

    if repro < 0.6:
        regime = "incomplete_methodology"
    elif avg >= 70.0:
        regime = "severe_research_pack"
    elif avg < 30.0:
        regime = "calm_research_pack"
    elif len(distinct_modules) >= 3:
        regime = "multi_module_stress"
    else:
        regime = "focused_module_review"

    drivers = [
        f"{r.run_name} — severity {r.severity_score:.0f}/100 ({MODULE_LABELS[r.module_id]})"
        for r in rows[:3]
    ]
    return SeveritySummary(
        average_severity=avg,
        max_severity=top.severity_score,
        highest_severity_run_id=top.run_id,
        severity_bucket=_bucket(avg),  # type: ignore[arg-type]
        workspace_regime=regime,  # type: ignore[arg-type]
        regime_label=_REGIME_LABELS[regime],
        coverage_score=coverage,
        reproducibility_score=repro,
        drivers=drivers,
    )


# --------------------------------------------------------------------------- #
# Workflow timeline
# --------------------------------------------------------------------------- #
def _timeline(
    preset: ResearchWorkspacePresetInput,
    runs: List[ExperimentRunInput],
    request: WorkspaceAnalysisRequest,
    summary: SeveritySummary,
) -> List[WorkflowTimelineItem]:
    total = len(preset.experiment_runs)
    annotated = summary.reproducibility_score  # checks already computed
    note_present = bool((request.user_note or "").strip()) or all(r.notes.strip() for r in runs)
    return [
        WorkflowTimelineItem(
            step_id="select_preset", step_title="Select research preset",
            step_description=f"{preset.preset_name} ({MODULE_LABELS[preset.primary_module]} first).",
            status="complete", linked_module=preset.primary_module,
        ),
        WorkflowTimelineItem(
            step_id="review_assumptions", step_title="Review assumptions",
            step_description=f"{len(preset.assumptions)} documented sample assumption(s).",
            status="complete" if preset.assumptions else "planned",
        ),
        WorkflowTimelineItem(
            step_id="stage_runs", step_title="Stage experiment runs",
            step_description=f"{len(runs)} of {total} sample run(s) staged for this pass.",
            status="complete" if len(runs) == total else "in_progress",
        ),
        WorkflowTimelineItem(
            step_id="compare_runs", step_title="Compare baseline vs stressed",
            step_description="Δ and Δ% computed per staged run; ranked by severity.",
            status="complete" if len(runs) >= 2 else "planned",
        ),
        WorkflowTimelineItem(
            step_id="annotate", step_title="Write research notes",
            step_description="Run notes plus the optional workspace note feed the journal.",
            status="complete" if note_present else "in_progress",
        ),
        WorkflowTimelineItem(
            step_id="methodology_check", step_title="Run methodology checklist",
            step_description=f"Reproducibility score R = {annotated:.2f} from the documented checks.",
            status="complete" if annotated >= 1.0 else ("in_progress" if annotated >= 0.6 else "planned"),
        ),
        WorkflowTimelineItem(
            step_id="export_report", step_title="Export Markdown / JSON summary",
            step_description=f"{len(request.report_sections)} report section(s) selected.",
            status="complete" if "limitations" in request.report_sections else "in_progress",
        ),
    ]


# --------------------------------------------------------------------------- #
# Report builder + export
# --------------------------------------------------------------------------- #
def _fmt(v: float) -> str:
    return f"{v:,.3f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:,.0f}"


def _section_markdown(
    sid: str,
    preset: ResearchWorkspacePresetInput,
    rows: List[RunComparisonRow],
    summary: SeveritySummary,
    checklist: List[MethodologyChecklistItem],
    request: WorkspaceAnalysisRequest,
) -> str:
    if sid == "overview":
        note = (request.user_note or "").strip()
        note_line = f"\n\nWorkspace note (user-provided): {note}" if note else ""
        return (
            f"**{preset.preset_name}** — {preset.description} Primary module: "
            f"{MODULE_LABELS[preset.primary_module]}; linked modules: "
            f"{', '.join(MODULE_LABELS[m] for m in preset.linked_modules)}. "
            f"Average severity **{summary.average_severity:.1f}/100** "
            f"({summary.severity_bucket}); max {summary.max_severity:.1f}/100; "
            f"workspace regime **{summary.regime_label}**; module coverage "
            f"{summary.coverage_score:.2f}; reproducibility score "
            f"{summary.reproducibility_score:.2f}. All figures are static "
            f"illustrative sample numbers.{note_line}"
        )
    if sid == "assumptions":
        lines = [f"- {a}" for a in preset.assumptions] or ["- No assumptions recorded on this preset."]
        if preset.tags:
            lines.append(f"- Tags: {', '.join(preset.tags)}.")
        return "\n".join(lines)
    if sid == "experiment_summary":
        return "\n".join(
            f"- **{r.run_name}** ({MODULE_LABELS[r.module_id]}, scenario “{r.scenario_name}”): "
            f"{r.key_metric_name} {_fmt(r.baseline_value)} → {_fmt(r.stressed_value)} "
            f"(Δ {r.change:+,.3f}); severity {r.severity_score:.0f}/100; "
            f"confidence label: {r.confidence_label} (illustrative)."
            for r in rows
        )
    if sid == "run_comparison":
        header = (
            "| Run | Metric | Baseline | Stressed | Δ | Severity |\n"
            "|---|---|---|---|---|---|"
        )
        body = "\n".join(
            f"| {r.run_name} | {r.key_metric_name} | {_fmt(r.baseline_value)} "
            f"| {_fmt(r.stressed_value)} | {r.change:+,.3f} | {r.severity_score:.0f} |"
            for r in rows
        )
        return f"{header}\n{body}"
    if sid == "methodology":
        lines = [
            f"- {'[x]' if c.passed else '[ ]'} {c.label} — {c.notes}" for c in checklist
        ]
        lines.append(
            f"- Reproducibility score R = passed/total = {summary.reproducibility_score:.2f} "
            "(a documentation-completeness count, not a verification that results reproduce)."
        )
        return "\n".join(lines)
    if sid == "limitations":
        return "\n".join(f"- {line}" for line in [*preset.limitations, *_GLOBAL_LIMITATIONS])
    # next_steps
    return (
        "Possible follow-up experiments (educational only): stage a different "
        "subset of runs and re-compare; sweep the linked labs' scenario "
        "templates and journal the new reads; document additional assumptions "
        "and limitations before exporting; extend the pack with runs from other "
        "modules to raise coverage. These are educational workflow ideas, not "
        "calls to any market action."
    )


def _build_report(
    preset: ResearchWorkspacePresetInput,
    rows: List[RunComparisonRow],
    summary: SeveritySummary,
    checklist: List[MethodologyChecklistItem],
    request: WorkspaceAnalysisRequest,
) -> ReportPreview:
    requested = set(request.report_sections)
    sections = [
        ReportSectionOut(
            section_id=sid,  # type: ignore[arg-type]
            section_title=SECTION_TITLES[sid],
            included=sid in requested,
            markdown=_section_markdown(sid, preset, rows, summary, checklist, request),
        )
        for sid in _SECTION_IDS
    ]
    title = f"Research Workspace Summary — {preset.preset_name}"
    subtitle = (
        "Deterministic educational experiment-journal summary on static "
        "illustrative sample data — not investment research."
    )
    parts = [f"# {title}", f"_{subtitle}_", ""]
    for sec in sections:
        if not sec.included:
            continue
        parts.append(f"## {sec.section_title}")
        parts.append(sec.markdown)
        parts.append("")
    parts.append(f"> {DISCLAIMER}")
    return ReportPreview(title=title, subtitle=subtitle, sections=sections, markdown="\n".join(parts))


def _export_payload(
    preset: ResearchWorkspacePresetInput,
    rows: List[RunComparisonRow],
    summary: SeveritySummary,
    report: ReportPreview,
    request: WorkspaceAnalysisRequest,
) -> ExportPayload:
    payload = {
        "data_status": "static_sample",
        "preset_id": preset.preset_id,
        "preset_name": preset.preset_name,
        "primary_module": preset.primary_module,
        "linked_modules": list(preset.linked_modules),
        "report_sections": list(request.report_sections),
        "user_note": (request.user_note or ""),
        "runs": [
            {
                "run_id": r.run_id,
                "run_name": r.run_name,
                "module_id": r.module_id,
                "scenario_name": r.scenario_name,
                "key_metric_name": r.key_metric_name,
                "baseline_value": r.baseline_value,
                "stressed_value": r.stressed_value,
                "change": r.change,
                "percent_change": r.percent_change,
                "severity_score": r.severity_score,
                "confidence_label": r.confidence_label,
            }
            for r in rows
        ],
        "severity_summary": {
            "average_severity": summary.average_severity,
            "max_severity": summary.max_severity,
            "severity_bucket": summary.severity_bucket,
            "workspace_regime": summary.workspace_regime,
            "coverage_score": summary.coverage_score,
            "reproducibility_score": summary.reproducibility_score,
        },
        "disclaimer": DISCLAIMER,
    }
    return ExportPayload(
        markdown=report.markdown,
        json_payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def analyze_research_workspace(
    request: WorkspaceAnalysisRequest,
) -> ResearchWorkspaceAnalysisResponse:
    """Deterministic workspace analytics for one request.

    Raises ``KeyError`` for an unknown ``selected_preset_id`` and
    ``ValueError`` when ``included_run_ids`` matches no runs (the route maps
    both to a 422).
    """
    preset = preset_by_id(request.selected_preset_id)
    runs = _included_runs(preset, request)
    rows = _comparison_rows(runs)
    checklist = _checklist(preset, runs, request)
    summary = _severity_summary(preset, rows, checklist)
    timeline = _timeline(preset, runs, request, summary)
    report = _build_report(preset, rows, summary, checklist, request)
    export = _export_payload(preset, rows, summary, report, request)

    return ResearchWorkspaceAnalysisResponse(
        selected_preset=preset,
        run_comparison=rows,
        severity_summary=summary,
        workflow_timeline=timeline,
        methodology_checklist=checklist,
        report_preview=report,
        export_payload=export,
        notes=[
            "Presets and experiment runs are hand-written static sample numbers "
            "on fixed timestamps — not recorded lab outputs, not live data.",
            "Severity, coverage, and reproducibility scores are documented "
            "deterministic teaching formulas.",
            "The report and export payload are educational summaries — not "
            "production research records or compliance records.",
            "Educational only — not investment, trading, or asset-allocation "
            "advice.",
        ],
        disclaimer=DISCLAIMER,
    )
