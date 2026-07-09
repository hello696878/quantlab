"""
QA Command Center analytics (Phase 36.0) — pure, deterministic.

Given category/status/priority filters, section toggles, and a report-section
selection, it computes the documented coverage rates — ready rate R, smoke
coverage S, test-coverage proxy T, interactivity coverage I, chart coverage C
— and the release score Q = 100·(0.30R + 0.20S + 0.20T + 0.15I + 0.15C), a
rule-based release decision (blocked critical → blocked; low score or ≥3
needs-review → needs review; high score → ready for demo; else ready with
limitations), the smoke-test matrix, a grouped regression checklist, the
exact local verification commands (listed, never executed), a limitations
tracker, draft release notes, and a deterministic Markdown report with a
Markdown + JSON export payload.

Everything is derived from the hand-maintained static registry. The score is
a documentation-coverage read — it does not prove tests were run, and this
layer never runs any command. All outputs are finite by construction.
Educational only — not a compliance system and not advice.
"""

from __future__ import annotations

import json
from typing import List

from app.qa_command_center.models import (
    CommandChecklist,
    ExportPayload,
    GeneratedReport,
    LimitationRow,
    QACommandCenterAnalysisResponse,
    QACommandCenterRequest,
    QAModuleRow,
    ReadinessSummary,
    RegressionGroup,
    ReportSectionOut,
    SmokeTestRow,
)
from app.qa_command_center.sample import (
    CATEGORY_LABELS,
    DISCLAIMER,
    SECTION_TITLES,
    command_checklist,
    qa_module_rows,
)

_SECTION_IDS = list(SECTION_TITLES.keys())
_EXPECTED_RESULT = "All panels render with finite values; no crash; no NaN/Infinity anywhere."


def _scope(request: QACommandCenterRequest) -> List[QAModuleRow]:
    rows = qa_module_rows()
    if request.selected_category is not None:
        rows = [r for r in rows if r.category == request.selected_category]
    if request.selected_release_statuses is not None:
        wanted = set(request.selected_release_statuses)
        rows = [r for r in rows if r.release_status in wanted]
    if request.selected_priorities is not None:
        wanted = set(request.selected_priorities)
        rows = [r for r in rows if r.priority in wanted]
    if not rows:
        raise ValueError("The category/status/priority selection matches no QA modules")
    return rows


def build_readiness_summary(rows: List[QAModuleRow]) -> ReadinessSummary:
    """Documented rates, score, and rule-based decision for a module set.

    Public so tests can exercise the decision rules on constructed fixtures
    (e.g. a blocked critical module) without editing the shipped registry.
    """
    n = len(rows)
    ready = sum(1 for r in rows if r.release_status == "ready") / n
    smoke = sum(1 for r in rows if r.smoke_test_steps) / n
    tests = sum(1 for r in rows if r.has_tests) / n
    interactive = sum(1 for r in rows if r.has_interactive_controls) / n
    charts = sum(1 for r in rows if r.has_charts) / n
    score = 100.0 * (0.30 * ready + 0.20 * smoke + 0.20 * tests + 0.15 * interactive + 0.15 * charts)
    score = min(max(score, 0.0), 100.0)

    critical_blockers = [
        r.module_name for r in rows if r.release_status == "blocked" and r.priority == "critical"
    ]
    needs_review_count = sum(1 for r in rows if r.release_status == "needs_review")
    if critical_blockers:
        decision = "blocked"
    elif score < 70.0 or needs_review_count >= 3:
        decision = "needs_review"
    elif score >= 85.0:
        decision = "ready_for_demo"
    else:
        decision = "ready_with_limitations"

    drivers = [
        f"{sum(1 for r in rows if r.release_status == 'ready')} of {n} scoped module(s) carry the 'ready' label.",
        f"Test-coverage proxy {tests:.0%} (test files exist), interactivity {interactive:.0%}, charts {charts:.0%} — documentation-coverage reads, not proof any test was run.",
        (
            f"Critical blockers: {', '.join(critical_blockers)}."
            if critical_blockers
            else "No blocked critical module in scope."
        ),
    ]
    return ReadinessSummary(
        module_count=n,
        ready_rate=ready,
        smoke_coverage=smoke,
        test_coverage=tests,
        interactive_coverage=interactive,
        chart_coverage=charts,
        release_score=score,
        release_decision=decision,  # type: ignore[arg-type]
        critical_blockers=critical_blockers,
        drivers=drivers,
    )


def _smoke_matrix(rows: List[QAModuleRow]) -> List[SmokeTestRow]:
    return [
        SmokeTestRow(
            module_id=r.module_id,
            module_name=r.module_name,
            route=r.route,
            steps=r.smoke_test_steps,
            expected_result=_EXPECTED_RESULT,
            status_label=r.release_status,
        )
        for r in rows
    ]


def _regression_groups(rows: List[QAModuleRow]) -> List[RegressionGroup]:
    groups: List[RegressionGroup] = []
    for cat, label in CATEGORY_LABELS.items():
        items = [
            f"{r.module_name} — {step}"
            for r in rows
            if r.category == cat
            for step in r.manual_regression_steps
        ]
        if items:
            groups.append(RegressionGroup(category=cat, category_label=label, items=items))  # type: ignore[arg-type]
    return groups


def _limitation_rows(rows: List[QAModuleRow]) -> List[LimitationRow]:
    return [
        LimitationRow(
            module_id=r.module_id,
            module_name=r.module_name,
            data_mode=r.data_mode,
            limitations=r.known_limitations,
        )
        for r in rows
    ]


def _release_notes(rows: List[QAModuleRow], summary: ReadinessSummary) -> List[str]:
    categories = sorted({r.category for r in rows})
    static_n = sum(1 for r in rows if r.data_mode == "static_sample")
    return [
        f"{summary.module_count} module(s) in scope across {len(categories)} categories; "
        f"{summary.ready_rate:.0%} carry the 'ready' label.",
        f"{static_n} module(s) run on deterministic static samples; the rest are user-input, "
        "local-calculation, or optional-provider modules with documented fallbacks.",
        "Shared platform layers: sidebar/dashboard/command palette, local charts and controls, "
        "local LaTeX formula panels, and copy-friendly Markdown/JSON exports.",
        "Data policy: deterministic educational sample data; optional external providers are "
        "disabled by default and never relied on in tests; no telemetry, login, or cloud sync.",
        "Verification is manual: the backend suite, frontend typecheck, and production build "
        "listed in the command checklist are to be run locally by the user before any release.",
    ]


# --------------------------------------------------------------------------- #
# Report builder
# --------------------------------------------------------------------------- #
def _yes(b: bool) -> str:
    return "yes" if b else "no"


def _section_markdown(
    sid: str,
    rows: List[QAModuleRow],
    summary: ReadinessSummary,
    commands: CommandChecklist,
    notes_lines: List[str],
    request: QACommandCenterRequest,
) -> str:
    if sid == "overview":
        return (
            f"**QuantLab QA read** over {summary.module_count} scoped module(s): release score "
            f"**{summary.release_score:.1f}/100**, decision label "
            f"**{summary.release_decision.replace('_', ' ')}**. The score is a "
            "documentation-coverage read over a hand-maintained registry — it does not prove "
            "any test or build was executed; the command checklist below is to be run locally."
        )
    if sid == "readiness_summary":
        return (
            f"- Ready rate R = {summary.ready_rate:.0%}\n"
            f"- Smoke coverage S = {summary.smoke_coverage:.0%}\n"
            f"- Test-coverage proxy T = {summary.test_coverage:.0%} (test files exist — not proof they were run)\n"
            f"- Interactivity coverage I = {summary.interactive_coverage:.0%}\n"
            f"- Chart coverage C = {summary.chart_coverage:.0%}\n"
            f"- Release score Q = 100·(0.30R + 0.20S + 0.20T + 0.15I + 0.15C) = {summary.release_score:.1f}\n"
            + "\n".join(f"- {d}" for d in summary.drivers)
        )
    if sid == "smoke_test_matrix":
        return "\n".join(
            f"- **{r.module_name}** (`{r.route}`; {r.release_status.replace('_', ' ')}): "
            + " → ".join(r.smoke_test_steps)
            + f" Expect: {_EXPECTED_RESULT}"
            for r in rows
        )
    if sid == "regression_checklist":
        if not request.include_manual_steps:
            return "- Manual regression steps excluded from this report pass."
        lines = []
        for g in _regression_groups(rows):
            lines.append(f"**{g.category_label}**")
            lines.extend(f"- [ ] {item}" for item in g.items)
        return "\n".join(lines)
    if sid == "command_checklist":
        lines = []
        if request.include_backend_checks:
            lines.append(f"- Backend tests (run locally): `{commands.backend_test_command}`")
            lines.append(f"- Backend dev server: `{commands.backend_run_command}`")
        if request.include_frontend_checks:
            lines.append(f"- Frontend typecheck (run locally): `{commands.frontend_typecheck_command}`")
            lines.append(f"- Production build (run locally by the user): `{commands.frontend_build_command_for_user}`")
        if not lines:
            lines.append("- Backend and frontend command checks excluded from this report pass.")
        lines.extend(f"- {n}" for n in commands.notes)
        return "\n".join(lines)
    if sid == "known_limitations":
        if not request.include_known_limitations:
            return "- Known-limitation details excluded from this report pass."
        return "\n".join(
            f"- **{r.module_name}** ({r.data_mode.replace('_', ' ')}): {r.known_limitations[0]}"
            for r in rows
        )
    if sid == "release_notes":
        return "\n".join(f"- {line}" for line in notes_lines)
    # release_decision
    blockers = (
        f" Critical blockers: {', '.join(summary.critical_blockers)}."
        if summary.critical_blockers
        else " No blocked critical module in scope."
    )
    return (
        f"Decision label (from static metadata): **{summary.release_decision.replace('_', ' ')}** "
        f"at score {summary.release_score:.1f}/100.{blockers} This label summarizes "
        "hand-maintained registry flags — the local verification commands still need to be "
        "run before any demo or release."
    )


def _build_report(
    rows: List[QAModuleRow],
    summary: ReadinessSummary,
    commands: CommandChecklist,
    notes_lines: List[str],
    request: QACommandCenterRequest,
) -> GeneratedReport:
    requested = set(request.report_sections)
    sections = [
        ReportSectionOut(
            section_id=sid,  # type: ignore[arg-type]
            section_title=SECTION_TITLES[sid],
            included=sid in requested,
            markdown=_section_markdown(sid, rows, summary, commands, notes_lines, request),
        )
        for sid in _SECTION_IDS
    ]
    title = "QuantLab Release Readiness & QA Report"
    subtitle = (
        "Deterministic educational QA summary from a hand-maintained static "
        "registry — it lists verification commands but does not run them."
    )
    parts = [f"# {title}", f"_{subtitle}_", ""]
    for sec in sections:
        if not sec.included:
            continue
        parts.append(f"## {sec.section_title}")
        parts.append(sec.markdown)
        parts.append("")
    parts.append(f"> {DISCLAIMER}")
    return GeneratedReport(title=title, subtitle=subtitle, sections=sections, markdown="\n".join(parts))


def _export_payload(
    rows: List[QAModuleRow],
    summary: ReadinessSummary,
    report: GeneratedReport,
    request: QACommandCenterRequest,
) -> ExportPayload:
    payload = {
        "data_status": "static_sample",
        "selected_category": request.selected_category,
        "report_sections": list(request.report_sections),
        "module_count": summary.module_count,
        "rates": {
            "ready_rate": summary.ready_rate,
            "smoke_coverage": summary.smoke_coverage,
            "test_coverage_proxy": summary.test_coverage,
            "interactive_coverage": summary.interactive_coverage,
            "chart_coverage": summary.chart_coverage,
            "release_score": summary.release_score,
            "release_decision": summary.release_decision,
        },
        "modules": [
            {
                "module_id": r.module_id,
                "release_status": r.release_status,
                "priority": r.priority,
                "has_tests": r.has_tests,
                "data_mode": r.data_mode,
            }
            for r in rows
        ],
        "disclaimer": DISCLAIMER,
    }
    return ExportPayload(
        markdown=report.markdown,
        json_payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def analyze_qa_command_center(request: QACommandCenterRequest) -> QACommandCenterAnalysisResponse:
    """Deterministic QA analytics for one request.

    Raises ``ValueError`` when the filter selection matches nothing (the
    route maps it to a 422).
    """
    rows = _scope(request)
    summary = build_readiness_summary(rows)
    commands = command_checklist()
    notes_lines = _release_notes(rows, summary)
    report = _build_report(rows, summary, commands, notes_lines, request)

    return QACommandCenterAnalysisResponse(
        qa_modules=rows,
        readiness_summary=summary,
        smoke_test_matrix=_smoke_matrix(rows),
        regression_checklist=_regression_groups(rows) if request.include_manual_steps else [],
        command_checklist=commands,
        limitation_tracker=_limitation_rows(rows) if request.include_known_limitations else [],
        release_notes=notes_lines,
        generated_report=report,
        export_payload=_export_payload(rows, summary, report, request),
        notes=[
            "All rows come from a hand-maintained static QA registry "
            "fact-checked against the code when written — not telemetry.",
            "The release score is a documentation-coverage read — it does not "
            "prove any test or build was executed.",
            "This layer lists verification commands but never runs them; the "
            "user runs the backend suite, typecheck, and production build "
            "locally.",
            "Educational project-management aid only — not a compliance "
            "system and not investment or trading advice.",
        ],
        disclaimer=DISCLAIMER,
    )
