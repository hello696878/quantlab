"""
Data reliability analytics (Phase 35.0) — pure, deterministic.

Given an optional category/module scope, provider/fixture/test-safety
toggles, and a report-section selection, it computes the documented rates —
demo-safe D, test-safe T, offline-fallback coverage F, external-provider
exposure E — and the reliability score
R = 100·(0.35·D + 0.25·T + 0.25·F + 0.15·(1 − E)), plus a test-safety matrix,
a fallback matrix, and a deterministic Markdown reliability report with a
Markdown + JSON export payload.

Everything is derived from the hand-maintained static registry — this layer
never calls any provider it describes, and external availability is never
guaranteed. All outputs are finite by construction (rates are counts over a
non-empty scope; the score is a fixed convex combination), so no NaN/Infinity
reaches the API. Educational only — not advice and not a data governance
system.
"""

from __future__ import annotations

import json
from typing import List

from app.data_reliability.models import (
    DataReliabilityAnalysisResponse,
    DataReliabilityRequest,
    ExportPayload,
    FallbackRow,
    GeneratedReport,
    ModuleDataModeRow,
    OfflineFixtureRow,
    ProviderRow,
    ReliabilitySummary,
    ReportSectionOut,
    TestSafetyRow,
)
from app.data_reliability.sample import (
    CATEGORY_LABELS,
    DISCLAIMER,
    SECTION_TITLES,
    fixture_rows,
    module_rows,
    provider_rows,
)

_SECTION_IDS = list(SECTION_TITLES.keys())

_DATA_MODE_LABELS = {
    "static_sample": "static sample",
    "delayed_sample": "delayed sample",
    "user_input": "user input",
    "local_calculation": "local calculation",
    "optional_external_provider": "optional external provider",
}


def _scope(request: DataReliabilityRequest) -> List[ModuleDataModeRow]:
    rows = module_rows()
    if request.selected_category is not None:
        rows = [r for r in rows if r.category == request.selected_category]
    if request.selected_modules is not None:
        wanted = set(request.selected_modules)
        rows = [r for r in rows if r.module_id in wanted]
    if not rows:
        raise ValueError("The category/module selection matches no registry modules")
    return rows


def _bucket(score: float) -> str:
    if score >= 90.0:
        return "highly_deterministic"
    if score >= 75.0:
        return "mostly_deterministic"
    if score >= 55.0:
        return "mixed"
    return "external_dependent"


def _summary(rows: List[ModuleDataModeRow]) -> ReliabilitySummary:
    n = len(rows)
    demo = sum(1 for r in rows if r.demo_safe) / n
    test = sum(1 for r in rows if r.test_safe) / n
    fallback = sum(1 for r in rows if r.offline_fallback_available) / n
    external = sum(1 for r in rows if r.external_provider_required) / n
    score = 100.0 * (0.35 * demo + 0.25 * test + 0.25 * fallback + 0.15 * (1.0 - external))
    static_n = sum(1 for r in rows if r.data_mode in ("static_sample", "local_calculation", "user_input"))
    external_names = [r.module_name for r in rows if r.external_provider_required]
    drivers = [
        f"{static_n} of {n} scoped module(s) are fully static/local — no network path exists.",
        (
            f"{len(external_names)} module(s) may reach the optional external provider "
            f"({', '.join(external_names)}) — friendly errors plus the deterministic "
            "demo-pair fixture keep demos and tests offline."
            if external_names
            else "No scoped module can reach an external provider."
        ),
        f"All {n} scoped module(s) have an offline demo path; optional providers are disabled by default and fail closed."
        if fallback == 1.0
        else f"{sum(1 for r in rows if r.offline_fallback_available)} of {n} scoped module(s) have an offline fallback.",
    ]
    return ReliabilitySummary(
        module_count=n,
        demo_safe_rate=demo,
        test_safe_rate=test,
        fallback_coverage=fallback,
        external_provider_exposure=external,
        reliability_score=min(max(score, 0.0), 100.0),
        reliability_bucket=_bucket(score),  # type: ignore[arg-type]
        drivers=drivers,
    )


def _test_safety_matrix(rows: List[ModuleDataModeRow]) -> List[TestSafetyRow]:
    out = []
    for r in rows:
        if not r.external_provider_required:
            note = "No network path — static/local data only; tests exercise deterministic payloads."
        else:
            note = (
                "Tests monkeypatch the fetch layer and the built-in demo pair "
                "falls back to its deterministic fixture — no live provider call in tests."
            )
        out.append(
            TestSafetyRow(
                module_id=r.module_id,
                module_name=r.module_name,
                test_safe=r.test_safe,
                external_provider_required=r.external_provider_required,
                notes=note,
            )
        )
    return out


def _fallback_matrix(rows: List[ModuleDataModeRow]) -> List[FallbackRow]:
    return [
        FallbackRow(
            module_id=r.module_id,
            module_name=r.module_name,
            external_provider_required=r.external_provider_required,
            offline_fallback_available=r.offline_fallback_available,
            failure_behavior=r.failure_behavior,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Report builder
# --------------------------------------------------------------------------- #
def _yes(b: bool) -> str:
    return "yes" if b else "no"


def _section_markdown(
    sid: str,
    rows: List[ModuleDataModeRow],
    providers: List[ProviderRow],
    fixtures: List[OfflineFixtureRow],
    summary: ReliabilitySummary,
    request: DataReliabilityRequest,
) -> str:
    if sid == "overview":
        return (
            f"**QuantLab data reliability read** over {summary.module_count} scoped module(s): "
            f"demo-safe rate **{summary.demo_safe_rate:.0%}**, test-safe rate "
            f"**{summary.test_safe_rate:.0%}**, offline-fallback coverage "
            f"**{summary.fallback_coverage:.0%}**, external-provider exposure "
            f"**{summary.external_provider_exposure:.0%}** → reliability score "
            f"**{summary.reliability_score:.1f}/100** ({summary.reliability_bucket.replace('_', ' ')}). "
            "All figures are computed from a hand-maintained static registry — not telemetry, "
            "and never a guarantee that any external provider is available."
        )
    if sid == "module_modes":
        return "\n".join(
            f"- **{r.module_name}** — {_DATA_MODE_LABELS[r.data_mode]}; demo safe: {_yes(r.demo_safe)}; "
            f"test safe: {_yes(r.test_safe)}; external provider required: {_yes(r.external_provider_required)}; "
            f"offline fallback: {_yes(r.offline_fallback_available)}. {r.user_visible_label}."
            for r in rows
        )
    if sid == "providers":
        if not providers:
            return "- Provider details excluded from this report pass."
        return "\n".join(
            f"- **{p.provider_name}** ({p.provider_type.replace('_', ' ')}; "
            f"{'external' if p.is_external else 'internal'}; network: {_yes(p.requires_network)}; "
            f"API key: {_yes(p.requires_api_key)}; allowed in tests: {_yes(p.allowed_in_tests)}; "
            f"failure mode: {p.default_failure_mode.replace('_', ' ')}): {p.user_message}"
            for p in providers
        )
    if sid == "offline_fixtures":
        if not fixtures:
            return "- Fixture details excluded from this report pass."
        return "\n".join(
            f"- **{f.fixture_name}** ({f.fixture_type.replace('_', ' ')}; "
            f"{f.observation_count} record(s); {f.date_range_label}): {f.description}"
            for f in fixtures
        )
    if sid == "test_safety":
        if not request.include_test_safety:
            return "- Test-safety details excluded from this report pass."
        lines = [
            "Tests never depend on a live provider: the optional yfinance/FRED/delayed-quote "
            "paths are disabled by default and not allowed in tests; backtest API tests "
            "monkeypatch the fetch layer; and the built-in KO/PEP pairs demo always falls "
            "back to its deterministic fixture.",
        ]
        flagged = [r for r in rows if r.external_provider_required]
        if flagged:
            lines.append(
                "Modules with an optional external path: "
                + ", ".join(r.module_name for r in flagged)
                + " — each is test-safe through mocking plus fixtures."
            )
        return "\n".join(lines)
    if sid == "limitations":
        return "\n".join(
            f"- {line}"
            for line in [
                "The registry is hand-maintained static metadata fact-checked against the code when written — it is not telemetry and can drift until manually re-reviewed.",
                "External providers (yfinance, FRED) are optional, disabled by default, and their availability is never guaranteed.",
                "The reliability score is a documented teaching formula over registry flags — not an SLA, uptime measurement, or data-quality audit.",
                "This is a product reliability layer for an educational platform — not a production data governance system, and nothing here is investment, trading, legal, tax, compliance, or risk-management advice.",
            ]
        )
    # recommendations → "Suggested Handling"
    return "\n".join(
        f"- **{r.module_name}**: {r.recommended_handling}" for r in rows
    )


def _build_report(
    rows: List[ModuleDataModeRow],
    providers: List[ProviderRow],
    fixtures: List[OfflineFixtureRow],
    summary: ReliabilitySummary,
    request: DataReliabilityRequest,
) -> GeneratedReport:
    requested = set(request.report_sections)
    sections = [
        ReportSectionOut(
            section_id=sid,  # type: ignore[arg-type]
            section_title=SECTION_TITLES[sid],
            included=sid in requested,
            markdown=_section_markdown(sid, rows, providers, fixtures, summary, request),
        )
        for sid in _SECTION_IDS
    ]
    title = "QuantLab Data Reliability Report"
    subtitle = (
        "Deterministic educational reliability summary from a hand-maintained "
        "static registry — not telemetry and not a data governance record."
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
    rows: List[ModuleDataModeRow],
    summary: ReliabilitySummary,
    report: GeneratedReport,
    request: DataReliabilityRequest,
) -> ExportPayload:
    payload = {
        "data_status": "static_sample",
        "selected_category": request.selected_category,
        "report_sections": list(request.report_sections),
        "module_count": summary.module_count,
        "rates": {
            "demo_safe_rate": summary.demo_safe_rate,
            "test_safe_rate": summary.test_safe_rate,
            "fallback_coverage": summary.fallback_coverage,
            "external_provider_exposure": summary.external_provider_exposure,
            "reliability_score": summary.reliability_score,
            "reliability_bucket": summary.reliability_bucket,
        },
        "modules": [
            {
                "module_id": r.module_id,
                "data_mode": r.data_mode,
                "demo_safe": r.demo_safe,
                "test_safe": r.test_safe,
                "external_provider_required": r.external_provider_required,
                "offline_fallback_available": r.offline_fallback_available,
                "default_demo_deterministic": r.default_demo_deterministic,
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
def analyze_data_reliability(request: DataReliabilityRequest) -> DataReliabilityAnalysisResponse:
    """Deterministic reliability analytics for one request.

    Raises ``ValueError`` when the category/module selection matches nothing
    (the route maps it to a 422).
    """
    rows = _scope(request)
    providers = provider_rows()
    if not request.include_external_providers:
        providers = [p for p in providers if not p.is_external]
    fixtures = fixture_rows() if request.include_static_fixtures else []
    summary = _summary(rows)
    report = _build_report(rows, providers, fixtures, summary, request)

    return DataReliabilityAnalysisResponse(
        module_modes=rows,
        providers=providers,
        offline_fixtures=fixtures,
        reliability_summary=summary,
        test_safety_matrix=_test_safety_matrix(rows) if request.include_test_safety else [],
        fallback_matrix=_fallback_matrix(rows),
        generated_report=report,
        export_payload=_export_payload(rows, summary, report, request),
        notes=[
            "All rows come from a hand-maintained static registry fact-checked "
            "against the code when written — not telemetry or runtime checks.",
            "Optional external providers are disabled by default, fail closed, "
            "and are never relied on in tests; availability is never guaranteed.",
            "Rates and the reliability score are documented deterministic "
            "teaching formulas over registry flags — not an SLA or audit.",
            "Educational only — not investment, trading, or compliance advice, "
            "and not a production data governance system.",
        ],
        disclaimer=DISCLAIMER,
    )
