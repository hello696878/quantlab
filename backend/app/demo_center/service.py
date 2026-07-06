"""
Product Demo Center analytics (Phase 34.0) — pure, deterministic.

Given a selected demo path (plus audience, optional module subset, script
sections, a time budget, and limitation/technical toggles) it computes a path
summary, category coverage C = categories_included / categories_available, a
module readiness score R = mean(rᵢ) over documented status weights, a demo
complexity score D = 0.4·M_norm + 0.3·S_norm + 0.3·T_norm, script coverage
Q = selected/available sections, per-module capability scores
K = enabled/total capabilities, a completion checklist, and a deterministic
audience-tailored Markdown demo script with a Markdown + JSON export payload.

Everything is derived from hand-written static demo metadata about QuantLab's
own modules — no telemetry, no runtime introspection, no live data. All
outputs are finite by construction (weights fixed, every ratio has a constant
positive denominator, normalizers clamped), so no NaN/Infinity reaches the
API. Educational only — not advice; no module is a production trading system.
"""

from __future__ import annotations

import json
from typing import Dict, List

from app.demo_center.models import (
    CapabilityMatrixRow,
    CompletionChecklistItem,
    DemoCenterAnalysisResponse,
    DemoCenterRequest,
    DemoPath,
    ExportPayload,
    GeneratedScript,
    ModuleHealthRow,
    PathSummary,
    ReadinessSummary,
    ScriptSectionOut,
)
from app.demo_center.sample import (
    AUDIENCES,
    CATEGORY_LABELS,
    DISCLAIMER,
    SCRIPT_SECTION_TITLES,
    module_health_rows,
    path_by_id,
    sample_demo_paths,
)

_SECTION_IDS = list(SCRIPT_SECTION_TITLES.keys())

# Documented readiness weights per module status (spec §6).
_READINESS_WEIGHTS = {
    "stable_demo": 1.0,
    "static_sample_only": 0.85,
    "experimental": 0.65,
    "review_needed": 0.5,
}

# Complexity normalizers (documented): 10 modules, 10 steps, 60 minutes ≙ 1.0.
_NORM_MODULES = 10.0
_NORM_STEPS = 10.0
_NORM_MINUTES = 60.0

_DATA_MODE_LABELS = {
    "static_sample": "static sample",
    "delayed_sample": "delayed sample",
    "user_input": "user input",
    "local_calculation": "local calculation",
}

_AUDIENCE_FRAMES = {
    "founder": "framed for a founder audience: product breadth, polish, and the local-first data policy",
    "investor": "framed for an investor audience: scope, engineering discipline, and honest limitations",
    "quant_researcher": "framed for a quant researcher: methodology guards, documented formulas, and reproducible workflows",
    "recruiter": "framed for a recruiter: engineering breadth across backend analytics, frontend product, and testing",
    "student": "framed for a student: each stop teaches one mechanism with the formulas beside the numbers",
    "general": "framed for a general audience: what QuantLab is, what it deliberately is not, and how to explore it",
}

_GLOBAL_LIMITATIONS = [
    "Every module runs on deterministic static sample, synthetic, or user-entered data — no live or current market data is shown anywhere in the demo.",
    "All analytics are simplified educational models — QuantLab is not a production trading, risk, or research-management system.",
    "Health/status labels and capability flags are hand-maintained static annotations, not telemetry or a quality certification.",
    "Nothing in any walkthrough is investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice.",
]


def _clamp01(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def _scope_modules(path: DemoPath, request: DemoCenterRequest) -> List[str]:
    if request.included_modules is None:
        return list(path.modules)
    wanted = set(request.included_modules)
    scope = [m for m in path.modules if m in wanted]
    if not scope:
        raise ValueError("included_modules matches none of the selected path's modules")
    return scope


def _effective_sections(request: DemoCenterRequest) -> List[str]:
    requested = set(request.script_sections)
    if request.include_limitations:
        requested.add("limitations")
    return [sid for sid in _SECTION_IDS if sid in requested]


# --------------------------------------------------------------------------- #
# Scores
# --------------------------------------------------------------------------- #
def _capability_score(row: ModuleHealthRow) -> float:
    flags = [
        row.has_backend_endpoint, row.has_charts, row.has_interactive_controls,
        row.has_formula_panel, row.has_report_export,
    ]
    return sum(1.0 for f in flags if f) / len(flags)


def _capability_matrix(rows: List[ModuleHealthRow]) -> List[CapabilityMatrixRow]:
    return [
        CapabilityMatrixRow(
            module_id=row.module_id,
            module_name=row.module_name,
            category=row.category,
            has_backend_endpoint=row.has_backend_endpoint,
            has_charts=row.has_charts,
            has_interactive_controls=row.has_interactive_controls,
            has_formula_panel=row.has_formula_panel,
            has_report_export=row.has_report_export,
            capability_score=_capability_score(row),
        )
        for row in rows
    ]


def _readiness_summary(
    scope: List[str],
    health: Dict[str, ModuleHealthRow],
    path: DemoPath,
    request: DemoCenterRequest,
) -> ReadinessSummary:
    scope_rows = [health[m] for m in scope if m in health]
    categories = {r.category for r in scope_rows}
    coverage = len(categories) / len(CATEGORY_LABELS)
    readiness = (
        sum(_READINESS_WEIGHTS[r.status] for r in scope_rows) / len(scope_rows)
        if scope_rows
        else 0.0
    )
    complexity = _clamp01(
        0.4 * _clamp01(len(scope) / _NORM_MODULES)
        + 0.3 * _clamp01(len(path.steps) / _NORM_STEPS)
        + 0.3 * _clamp01(request.time_budget_minutes / _NORM_MINUTES)
    )
    script_coverage = len(set(request.script_sections)) / len(_SECTION_IDS)
    ranked = sorted(scope_rows, key=lambda r: (-_READINESS_WEIGHTS[r.status], r.module_name))
    return ReadinessSummary(
        included_module_count=len(scope),
        category_coverage=coverage,
        readiness_score=readiness,
        demo_complexity_score=complexity,
        script_coverage=script_coverage,
        top_ready_modules=[r.module_name for r in ranked[:3]],
        review_needed_modules=[r.module_name for r in scope_rows if r.status == "review_needed"],
    )


def _path_summary(path: DemoPath, scope: List[str], request: DemoCenterRequest) -> PathSummary:
    fits = request.time_budget_minutes >= path.estimated_minutes
    return PathSummary(
        path_id=path.path_id,
        title=path.title,
        audience=path.audience,
        estimated_minutes=path.estimated_minutes,
        module_count=len(scope),
        step_count=len(path.steps),
        talking_point_count=len(path.suggested_talking_points),
        fits_time_budget=fits,
        time_note=(
            f"Estimated {path.estimated_minutes:.0f} min fits the "
            f"{request.time_budget_minutes:.0f}-min budget."
            if fits
            else f"Estimated {path.estimated_minutes:.0f} min exceeds the "
            f"{request.time_budget_minutes:.0f}-min budget — trim steps or raise the budget."
        ),
    )


def _completion_checklist(
    path: DemoPath, scope: List[str], sections: List[str], request: DemoCenterRequest
) -> List[CompletionChecklistItem]:
    audience_aligned = request.selected_audience in (path.audience, "general")
    fits = request.time_budget_minutes >= path.estimated_minutes
    checks = [
        ("path_selected", "Demo path selected", True,
         f"{path.title} ({len(path.steps)} steps)."),
        ("audience_aligned", "Audience matches the path framing", audience_aligned,
         f"Selected audience: {request.selected_audience}; path framing: {path.audience}."),
        ("time_budget_fits", "Time budget covers the estimate", fits,
         f"Budget {request.time_budget_minutes:.0f} min vs estimate {path.estimated_minutes:.0f} min."),
        ("limitations_in_script", "Limitations section in the script",
         "limitations" in sections,
         "The generated script carries the limitations section."
         if "limitations" in sections
         else "Enable the limitations toggle or select the section."),
        ("full_module_scope", "All path modules staged", len(scope) == len(path.modules),
         f"{len(scope)} of {len(path.modules)} path modules staged."),
        ("full_script", "All script sections selected",
         len(set(request.script_sections)) == len(_SECTION_IDS),
         f"{len(set(request.script_sections))} of {len(_SECTION_IDS)} sections selected."),
    ]
    return [
        CompletionChecklistItem(item_id=i, label=label, passed=passed, notes=note)
        for i, label, passed, note in checks
    ]


# --------------------------------------------------------------------------- #
# Script builder
# --------------------------------------------------------------------------- #
def _section_markdown(
    sid: str,
    path: DemoPath,
    scope: List[str],
    health: Dict[str, ModuleHealthRow],
    summary: ReadinessSummary,
    request: DemoCenterRequest,
) -> str:
    if sid == "opening":
        return (
            f"Welcome to the **{path.title}** — {_AUDIENCE_FRAMES[request.selected_audience]}. "
            f"Estimated {path.estimated_minutes:.0f} minutes against a "
            f"{request.time_budget_minutes:.0f}-minute budget; {len(scope)} module(s) staged. "
            "Everything shown runs locally on deterministic sample data."
        )
    if sid == "product_overview":
        return (
            f"QuantLab is a local-first educational quant research platform: "
            f"{len(module_health_rows())} modules across {len(CATEGORY_LABELS)} categories behind one "
            "shell (sidebar, dashboard, command palette, shared charts and LaTeX formula panels). "
            f"{path.summary} Talking points: "
            + " ".join(f"({i + 1}) {tp}" for i, tp in enumerate(path.suggested_talking_points))
        )
    if sid == "guided_steps":
        lines = []
        for i, step in enumerate(path.steps, start=1):
            tech = ""
            if request.include_technical_notes:
                row = health.get(step.linked_module)
                if row is not None:
                    tech = (
                        f" _(route `{step.route}`; backend endpoint: "
                        f"{'yes' if row.has_backend_endpoint else 'no'}; data mode: "
                        f"{_DATA_MODE_LABELS[row.data_mode]})_"
                    )
            lines.append(
                f"{i}. **{step.title}** — {step.description} "
                f"Action: {step.expected_user_action} "
                f"Expect: {step.expected_output} "
                f"Tip: {step.demo_tip}{tech}"
            )
        return "\n".join(lines)
    if sid == "module_highlights":
        lines = []
        for mid in scope:
            row = health.get(mid)
            if row is None:
                continue
            tech = ""
            if request.include_technical_notes:
                caps = []
                if row.has_backend_endpoint:
                    caps.append("backend API")
                if row.has_charts:
                    caps.append("charts")
                if row.has_interactive_controls:
                    caps.append("interactive controls")
                if row.has_formula_panel:
                    caps.append("LaTeX formulas")
                if row.has_report_export:
                    caps.append("report export")
                tech = f" Capabilities: {', '.join(caps) if caps else 'core view'}."
            lines.append(
                f"- **{row.module_name}** ({CATEGORY_LABELS[row.category]}; "
                f"{_DATA_MODE_LABELS[row.data_mode]}; status: {row.status.replace('_', ' ')}): "
                f"{row.limitations[0]}{tech}"
            )
        return "\n".join(lines) if lines else "- No modules staged."
    if sid == "limitations":
        return "\n".join(f"- {line}" for line in [*_GLOBAL_LIMITATIONS, *path.limitations])
    # closing
    return (
        f"Wrap up with the output artifacts — {'; '.join(path.output_artifacts)} — and restate "
        "the ground rules: deterministic educational sample data, local-first (no accounts, no "
        "keys, no telemetry), and nothing shown is advice or a production trading system."
    )


def _build_script(
    path: DemoPath,
    scope: List[str],
    sections: List[str],
    health: Dict[str, ModuleHealthRow],
    summary: ReadinessSummary,
    request: DemoCenterRequest,
) -> GeneratedScript:
    included = set(sections)
    out_sections = [
        ScriptSectionOut(
            section_id=sid,  # type: ignore[arg-type]
            section_title=SCRIPT_SECTION_TITLES[sid],
            included=sid in included,
            markdown=_section_markdown(sid, path, scope, health, summary, request),
        )
        for sid in _SECTION_IDS
    ]
    title = f"QuantLab Demo Script — {path.title}"
    subtitle = (
        "Deterministic educational walkthrough script on static demo metadata "
        "— not investment research and not a production runbook."
    )
    parts = [f"# {title}", f"_{subtitle}_", ""]
    for sec in out_sections:
        if not sec.included:
            continue
        parts.append(f"## {sec.section_title}")
        parts.append(sec.markdown)
        parts.append("")
    parts.append(f"> {DISCLAIMER}")
    return GeneratedScript(
        title=title, subtitle=subtitle, sections=out_sections, markdown="\n".join(parts)
    )


def _export_payload(
    path: DemoPath,
    scope: List[str],
    sections: List[str],
    summary: ReadinessSummary,
    script: GeneratedScript,
    request: DemoCenterRequest,
) -> ExportPayload:
    payload = {
        "data_status": "static_sample",
        "path_id": path.path_id,
        "path_title": path.title,
        "audience": request.selected_audience,
        "time_budget_minutes": request.time_budget_minutes,
        "included_modules": list(scope),
        "script_sections": list(sections),
        "scores": {
            "category_coverage": summary.category_coverage,
            "readiness_score": summary.readiness_score,
            "demo_complexity_score": summary.demo_complexity_score,
            "script_coverage": summary.script_coverage,
        },
        "steps": [
            {"step_id": s.step_id, "title": s.title, "route": s.route}
            for s in path.steps
        ],
        "disclaimer": DISCLAIMER,
    }
    return ExportPayload(
        markdown=script.markdown,
        json_payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def analyze_demo_center(request: DemoCenterRequest) -> DemoCenterAnalysisResponse:
    """Deterministic demo-center analytics for one request.

    Raises ``KeyError`` for an unknown ``selected_path_id`` and ``ValueError``
    when ``included_modules`` matches none of the path's modules (the route
    maps both to a 422).
    """
    path = path_by_id(request.selected_path_id)
    health_rows = module_health_rows()
    health = {row.module_id: row for row in health_rows}
    scope = _scope_modules(path, request)
    sections = _effective_sections(request)

    summary = _readiness_summary(scope, health, path, request)
    script = _build_script(path, scope, sections, health, summary, request)

    return DemoCenterAnalysisResponse(
        selected_path=path,
        demo_paths=sample_demo_paths(),
        module_health=health_rows,
        path_summary=_path_summary(path, scope, request),
        readiness_summary=summary,
        capability_matrix=_capability_matrix(health_rows),
        completion_checklist=_completion_checklist(path, scope, sections, request),
        generated_script=script,
        export_payload=_export_payload(path, scope, sections, summary, script, request),
        notes=[
            "Demo paths and module health rows are hand-written static demo "
            "metadata — not telemetry, runtime introspection, or live data.",
            "Readiness, coverage, complexity, and capability scores are "
            "documented deterministic teaching formulas over those labels.",
            "The generated script is an educational walkthrough summary — "
            "not investment research and not a production runbook.",
            "Educational only — not investment, trading, or asset-allocation "
            "advice; no module is a production trading system.",
        ],
        disclaimer=DISCLAIMER,
    )


__all__ = ["analyze_demo_center", "AUDIENCES"]
