"""
Tests for the Release Readiness, Smoke Test Matrix & QA Command Center
(Phase 36.0).

Confirms the static QA registry API shape, validation, JSON-safety (no
NaN/Inf), all documented coverage/score formulas, the rule-based release
decision (including a blocked-critical fixture), the command checklist, and
the deterministic report/export builder. Fully deterministic — no network
calls and no command execution.
"""

import json
import math

import pytest
from pydantic import ValidationError

from app.qa_command_center.models import QACommandCenterRequest, QAModuleRow
from app.qa_command_center.sample import (
    SECTION_TITLES,
    command_checklist,
    default_request,
    qa_module_rows,
)
from app.qa_command_center.service import (
    analyze_qa_command_center,
    build_readiness_summary,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

ALL_SECTIONS = list(SECTION_TITLES.keys())


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float in payload: {obj}"


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _request(**kwargs):
    return QACommandCenterRequest(
        report_sections=kwargs.pop("report_sections", ALL_SECTIONS),
        **kwargs,
    )


def _analyze(**kwargs):
    return analyze_qa_command_center(_request(**kwargs))


def _fixture_row(**overrides) -> QAModuleRow:
    base = dict(
        module_id="m1", module_name="Module 1", category="platform", route="home",
        has_backend_endpoint=True, has_frontend_page=True, has_charts=True,
        has_interactive_controls=True, has_formula_panel=True, has_tests=True,
        demo_safe=True, data_mode="static_sample", release_status="ready",
        priority="medium", smoke_test_steps=["step"],
        manual_regression_steps=["step"], known_limitations=["limitation"],
    )
    base.update(overrides)
    return QAModuleRow(**base)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint_deterministic_qa_records(client):
    res = client.get("/qa-command-center/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = {m["module_id"] for m in body["qa_modules"]}
    assert len(body["qa_modules"]) == 21
    for expected in (
        "global_markets_globe", "backtest_studio", "strategy_comparison",
        "portfolio_risk_lab", "macro_regime_lab", "scenario_studio",
        "research_workspace", "demo_center", "data_reliability_center",
        "crypto_derivatives_lab", "defi_risk_lab", "tokenomics_lab",
        "onchain_analytics_lab", "alternative_data_lab",
        "market_microstructure_lab", "options_lab", "volatility_lab",
        "futures_commodities_lab", "real_estate_lab", "credit_risk_lab",
        "export_report",
    ):
        assert expected in ids, expected
    assert body == client.get("/qa-command-center/sample").json()
    _assert_all_finite(body)


def test_analyze_endpoint_accepts_sample_request(client):
    res = client.post("/qa-command-center/analyze", json=default_request().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–8. Coverage and score formulas
# --------------------------------------------------------------------------- #
def test_ready_rate_formula():
    out = _analyze()
    rows = out.qa_modules
    expected = sum(1 for r in rows if r.release_status == "ready") / len(rows)
    assert math.isclose(out.readiness_summary.ready_rate, expected, rel_tol=1e-12)


def test_smoke_coverage_formula():
    out = _analyze()
    rows = out.qa_modules
    expected = sum(1 for r in rows if r.smoke_test_steps) / len(rows)
    assert math.isclose(out.readiness_summary.smoke_coverage, expected, rel_tol=1e-12)


def test_test_coverage_formula():
    out = _analyze()
    rows = out.qa_modules
    expected = sum(1 for r in rows if r.has_tests) / len(rows)
    assert math.isclose(out.readiness_summary.test_coverage, expected, rel_tol=1e-12)


def test_interactive_coverage_formula():
    out = _analyze()
    rows = out.qa_modules
    expected = sum(1 for r in rows if r.has_interactive_controls) / len(rows)
    assert math.isclose(out.readiness_summary.interactive_coverage, expected, rel_tol=1e-12)


def test_chart_coverage_formula():
    out = _analyze()
    rows = out.qa_modules
    expected = sum(1 for r in rows if r.has_charts) / len(rows)
    assert math.isclose(out.readiness_summary.chart_coverage, expected, rel_tol=1e-12)


def test_release_score_finite_bounded_and_formula():
    for kwargs in ({}, {"selected_category": "crypto"}, {"selected_priorities": ["critical"]}):
        out = _analyze(**kwargs)
        s = out.readiness_summary
        assert math.isfinite(s.release_score)
        assert 0.0 <= s.release_score <= 100.0
        expected = 100.0 * (
            0.30 * s.ready_rate + 0.20 * s.smoke_coverage + 0.20 * s.test_coverage
            + 0.15 * s.interactive_coverage + 0.15 * s.chart_coverage
        )
        assert math.isclose(s.release_score, expected, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 9–10. Release decision
# --------------------------------------------------------------------------- #
def test_release_decision_exists():
    out = _analyze()
    assert out.readiness_summary.release_decision in {
        "ready_for_demo", "ready_with_limitations", "needs_review", "blocked",
    }
    # The shipped all-ready registry reads ready_for_demo at full scope.
    assert out.readiness_summary.release_decision == "ready_for_demo"
    assert out.readiness_summary.critical_blockers == []


def test_blocked_critical_module_forces_blocked_decision():
    rows = [
        _fixture_row(module_id="ok", module_name="OK Module"),
        _fixture_row(
            module_id="broken", module_name="Broken Module",
            release_status="blocked", priority="critical",
        ),
    ]
    summary = build_readiness_summary(rows)
    assert summary.release_decision == "blocked"
    assert summary.critical_blockers == ["Broken Module"]
    # Low score without blockers → needs_review.
    weak = [
        _fixture_row(
            module_id=f"w{i}", module_name=f"Weak {i}", release_status="needs_review",
            has_tests=False, has_charts=False, has_interactive_controls=False,
        )
        for i in range(3)
    ]
    assert build_readiness_summary(weak).release_decision == "needs_review"


# --------------------------------------------------------------------------- #
# 11–13. Report wording
# --------------------------------------------------------------------------- #
def test_generated_markdown_includes_selected_sections():
    out = _analyze(report_sections=["overview", "command_checklist"])
    md = out.generated_report.markdown
    assert "## Overview" in md
    assert "## Command Checklist" in md
    assert "## Smoke Test Matrix" not in md
    assert "## Release Notes" not in md


def test_generated_markdown_does_not_claim_tests_were_run():
    for kwargs in ({}, {"include_backend_checks": False, "include_frontend_checks": False}):
        out = _analyze(**kwargs)
        text = out.generated_report.markdown.lower()
        for forbidden in ("tests passed", "all tests pass", "build succeeded", "build passed", "tests were run", "verified locally by this page"):
            assert forbidden not in text, (kwargs, forbidden)
        # It must say verification is the user's local step.
        assert "run locally" in text or "run them" in text


def test_generated_markdown_has_no_recommendation_wording():
    for kwargs in ({}, {"selected_category": "backtesting"}, {"include_manual_steps": False}):
        out = _analyze(**kwargs)
        text = out.generated_report.markdown.lower()
        for forbidden in ("recommend", "overweight", "underweight", "you should", "buy ", "sell "):
            assert forbidden not in text, (kwargs, forbidden)


# --------------------------------------------------------------------------- #
# 14–16. Command checklist
# --------------------------------------------------------------------------- #
def test_command_checklist_backend_pytest_command():
    c = command_checklist()
    assert "pytest backend\\tests -q" in c.backend_test_command
    assert "backend\\venv\\Scripts\\python.exe" in c.backend_test_command
    out = _analyze()
    assert out.command_checklist.backend_test_command == c.backend_test_command
    assert "pytest" in out.generated_report.markdown


def test_command_checklist_frontend_typecheck_command():
    c = command_checklist()
    assert "npx tsc --noEmit" in c.frontend_typecheck_command
    assert "npx tsc --noEmit" in _analyze().generated_report.markdown


def test_command_checklist_frontend_build_command_for_user():
    c = command_checklist()
    assert "npm run build" in c.frontend_build_command_for_user
    md = _analyze().generated_report.markdown
    assert "npm run build" in md
    assert "run locally by the user" in md


# --------------------------------------------------------------------------- #
# 17–19. Validation and JSON safety
# --------------------------------------------------------------------------- #
def test_reject_empty_report_sections(client):
    payload = default_request().model_dump()
    payload["report_sections"] = []
    assert client.post("/qa-command-center/analyze", json=payload).status_code == 422


def test_reject_invalid_filter_values(client):
    with pytest.raises(ValidationError):
        _request(selected_category="not_a_category")
    with pytest.raises(ValidationError):
        _request(selected_release_statuses=["not_a_status"])
    with pytest.raises(ValidationError):
        _request(selected_priorities=[])
    payload = default_request().model_dump()
    payload["selected_release_statuses"] = ["blocked"]  # valid enum, matches nothing
    assert client.post("/qa-command-center/analyze", json=payload).status_code == 422


def test_no_nan_or_infinity_in_any_response(client):
    for payload_kwargs in (
        {},
        {"selected_category": "platform"},
        {"include_manual_steps": False, "include_known_limitations": False},
    ):
        payload = _request(**payload_kwargs).model_dump()
        res = client.post("/qa-command-center/analyze", json=payload)
        assert res.status_code == 200, payload_kwargs
        _assert_all_finite(res.json())


# --------------------------------------------------------------------------- #
# Extra behaviour: scoping, toggles, matrix, export, registry facts
# --------------------------------------------------------------------------- #
def test_filters_scope_rows():
    out = _analyze(selected_category="crypto")
    assert {r.category for r in out.qa_modules} == {"crypto"}
    assert out.readiness_summary.module_count == 4
    crit = _analyze(selected_priorities=["critical"])
    assert {r.priority for r in crit.qa_modules} == {"critical"}


def test_toggles_filter_response():
    out = _analyze(include_manual_steps=False, include_known_limitations=False)
    assert out.regression_checklist == []
    assert out.limitation_tracker == []
    assert len(out.smoke_test_matrix) == len(out.qa_modules)


def test_smoke_matrix_shape():
    out = _analyze()
    assert len(out.smoke_test_matrix) == 21
    for row in out.smoke_test_matrix:
        assert row.steps
        assert "no crash" in row.expected_result.lower()


def test_export_payload_markdown_and_json():
    out = _analyze()
    assert out.export_payload.markdown == out.generated_report.markdown
    payload = json.loads(out.export_payload.json_payload)
    assert payload["data_status"] == "static_sample"
    assert payload["module_count"] == 21
    assert len(payload["modules"]) == 21
    assert "disclaimer" in payload
    _assert_all_finite(payload)


def test_registry_facts_all_tested_and_paged():
    for row in qa_module_rows():
        assert row.has_frontend_page is True, row.module_id
        assert row.has_tests is True, row.module_id
        assert row.demo_safe is True, row.module_id
    options = next(r for r in qa_module_rows() if r.module_id == "options_lab")
    credit = next(r for r in qa_module_rows() if r.module_id == "credit_risk_lab")
    # Fact-checked this phase: options/credit endpoints live directly in main.py.
    assert options.has_backend_endpoint is True
    assert credit.has_backend_endpoint is True
