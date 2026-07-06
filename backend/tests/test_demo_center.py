"""
Tests for the Product Demo Center, Guided Walkthroughs & Module Health
Dashboard (Phase 34.0).

Confirms the static demo-metadata API shape, validation, JSON-safety (no
NaN/Inf), the documented coverage/readiness/complexity/script formulas, the
capability matrix, and the deterministic script/export builder. Fully
deterministic — no network calls.
"""

import json
import math

import pytest
from pydantic import ValidationError

from app.demo_center.models import DemoCenterRequest
from app.demo_center.sample import (
    CATEGORY_LABELS,
    SCRIPT_SECTION_TITLES,
    default_request,
    module_health_rows,
    path_by_id,
    sample_demo_paths,
)
from app.demo_center.service import analyze_demo_center

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

ALL_SECTIONS = list(SCRIPT_SECTION_TITLES.keys())
PATH_IDS = [
    "founder_investor_product_tour", "quant_research_workflow_tour",
    "crypto_risk_research_tour", "macro_portfolio_stress_tour",
    "microstructure_execution_tour", "alternative_data_signal_tour",
    "real_estate_credit_tour", "full_platform_showcase_tour",
]


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


def _request(path_id="founder_investor_product_tour", **kwargs):
    return DemoCenterRequest(
        selected_path_id=path_id,
        script_sections=kwargs.pop("script_sections", ALL_SECTIONS),
        **kwargs,
    )


def _analyze(path_id="founder_investor_product_tour", **kwargs):
    return analyze_demo_center(_request(path_id, **kwargs))


# --------------------------------------------------------------------------- #
# 1–4. Endpoints and path lookup
# --------------------------------------------------------------------------- #
def test_sample_endpoint_deterministic_demo_paths(client):
    res = client.get("/demo-center/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert [p["path_id"] for p in body["demo_paths"]] == PATH_IDS
    assert "not investment" in body["disclaimer"].lower()
    assert body == client.get("/demo-center/sample").json()
    _assert_all_finite(body)


def test_sample_endpoint_module_health_rows(client):
    body = client.get("/demo-center/sample").json()
    rows = body["module_health"]
    assert len(rows) == 21
    ids = {r["module_id"] for r in rows}
    for expected in (
        "global_markets_globe", "backtest_studio", "strategy_comparison",
        "portfolio_risk_lab", "macro_regime_lab", "scenario_studio",
        "research_workspace", "crypto_derivatives_lab", "defi_risk_lab",
        "tokenomics_lab", "onchain_analytics_lab", "alternative_data_lab",
        "market_microstructure_lab", "options_lab", "volatility_lab",
        "futures_commodities_lab", "real_estate_lab", "credit_risk_lab",
        "export_report",
    ):
        assert expected in ids, expected


def test_analyze_endpoint_accepts_sample_request(client):
    res = client.post("/demo-center/analyze", json=default_request().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "compliance" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_every_selected_path_exists_and_analyzes():
    for path_id in PATH_IDS:
        out = _analyze(path_id)
        assert out.selected_path.path_id == path_id
        assert out.path_summary.step_count == len(out.selected_path.steps)


# --------------------------------------------------------------------------- #
# 5–8. Score formulas
# --------------------------------------------------------------------------- #
def test_category_coverage_finite_and_bounded():
    for path_id in PATH_IDS:
        out = _analyze(path_id)
        c = out.readiness_summary.category_coverage
        assert math.isfinite(c) and 0.0 <= c <= 1.0
    # Founder tour: globe (platform), backtest (backtesting), studio
    # (macro_cross_asset), workspace (research_workflow) → 4 of 10 categories.
    out = _analyze("founder_investor_product_tour")
    assert math.isclose(out.readiness_summary.category_coverage, 4 / len(CATEGORY_LABELS), rel_tol=1e-12)


def test_readiness_score_finite_and_bounded():
    health = {r.module_id: r for r in module_health_rows()}
    weights = {"stable_demo": 1.0, "static_sample_only": 0.85, "experimental": 0.65, "review_needed": 0.5}
    for path_id in PATH_IDS:
        out = _analyze(path_id)
        r = out.readiness_summary.readiness_score
        assert math.isfinite(r) and 0.0 <= r <= 1.0
        path = path_by_id(path_id)
        expected = sum(weights[health[m].status] for m in path.modules) / len(path.modules)
        assert math.isclose(r, expected, rel_tol=1e-12), path_id


def test_demo_complexity_finite_and_bounded():
    for path_id in PATH_IDS:
        for budget in (5.0, 20.0, 240.0):
            out = _analyze(path_id, time_budget_minutes=budget)
            d = out.readiness_summary.demo_complexity_score
            assert math.isfinite(d) and 0.0 <= d <= 1.0
    # Spot-check the documented formula (normalizers 10/10/60, clamped).
    out = _analyze("founder_investor_product_tour", time_budget_minutes=30.0)
    expected = 0.4 * (4 / 10) + 0.3 * (4 / 10) + 0.3 * (30 / 60)
    assert math.isclose(out.readiness_summary.demo_complexity_score, expected, rel_tol=1e-12)


def test_script_coverage_formula():
    out = _analyze(script_sections=["opening", "guided_steps", "closing"])
    assert math.isclose(out.readiness_summary.script_coverage, 3 / 6, rel_tol=1e-12)
    full = _analyze(script_sections=ALL_SECTIONS)
    assert math.isclose(full.readiness_summary.script_coverage, 1.0, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 9–12. Script builder + export
# --------------------------------------------------------------------------- #
def test_generated_markdown_includes_selected_sections():
    out = _analyze(script_sections=["opening", "guided_steps"], include_limitations=False)
    md = out.generated_script.markdown
    assert "## Opening" in md
    assert "## Guided Steps" in md
    assert "## Product Overview" not in md
    assert "## Module Highlights" not in md


def test_generated_markdown_includes_limitations_when_selected():
    out = _analyze(script_sections=["opening", "limitations"], include_limitations=False)
    assert "## Limitations" in out.generated_script.markdown
    # The include_limitations toggle force-adds the section even if unselected.
    forced = _analyze(script_sections=["opening"], include_limitations=True)
    assert "## Limitations" in forced.generated_script.markdown
    off = _analyze(script_sections=["opening"], include_limitations=False)
    assert "## Limitations" not in off.generated_script.markdown
    # The disclaimer footer is always present.
    assert "not investment" in off.generated_script.markdown.lower()


def test_generated_markdown_has_no_recommendation_wording():
    for path_id in PATH_IDS:
        for tech in (False, True):
            out = _analyze(path_id, include_technical_notes=tech)
            text = out.generated_script.markdown.lower()
            for forbidden in ("recommend", "overweight", "underweight", "you should", "buy ", "sell "):
                assert forbidden not in text, (path_id, tech, forbidden)


def test_export_payload_markdown_and_json():
    out = _analyze("crypto_risk_research_tour", selected_audience="quant_researcher")
    assert out.export_payload.markdown == out.generated_script.markdown
    payload = json.loads(out.export_payload.json_payload)
    assert payload["data_status"] == "static_sample"
    assert payload["path_id"] == "crypto_risk_research_tour"
    assert payload["audience"] == "quant_researcher"
    assert len(payload["steps"]) == len(out.selected_path.steps)
    assert "disclaimer" in payload
    _assert_all_finite(payload)


# --------------------------------------------------------------------------- #
# 13–15. Health enums and capability matrix
# --------------------------------------------------------------------------- #
def test_module_health_statuses_valid():
    valid = {"stable_demo", "review_needed", "experimental", "static_sample_only"}
    for row in module_health_rows():
        assert row.status in valid, row.module_id


def test_data_modes_valid():
    valid = {"static_sample", "delayed_sample", "user_input", "local_calculation"}
    for row in module_health_rows():
        assert row.data_mode in valid, row.module_id


def test_capability_matrix_includes_expected_modules():
    out = _analyze()
    ids = {r.module_id for r in out.capability_matrix}
    assert len(out.capability_matrix) == 21
    assert {"scenario_studio", "research_workspace", "backtest_studio", "export_report"} <= ids
    for row in out.capability_matrix:
        flags = [
            row.has_backend_endpoint, row.has_charts, row.has_interactive_controls,
            row.has_formula_panel, row.has_report_export,
        ]
        assert math.isclose(row.capability_score, sum(flags) / 5, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 16–19. Validation
# --------------------------------------------------------------------------- #
def test_reject_invalid_selected_path_id(client):
    payload = default_request().model_dump()
    payload["selected_path_id"] = "not_a_real_path"
    assert client.post("/demo-center/analyze", json=payload).status_code == 422


def test_reject_invalid_time_budget(client):
    with pytest.raises(ValidationError):
        _request(time_budget_minutes=0.0)
    with pytest.raises(ValidationError):
        _request(time_budget_minutes=-5.0)
    payload = default_request().model_dump()
    payload["time_budget_minutes"] = 0
    assert client.post("/demo-center/analyze", json=payload).status_code == 422


def test_reject_empty_script_sections(client):
    payload = default_request().model_dump()
    payload["script_sections"] = []
    assert client.post("/demo-center/analyze", json=payload).status_code == 422


def test_reject_non_finite_and_empty_modules(client):
    with pytest.raises(ValidationError):
        _request(time_budget_minutes=float("nan"))
    with pytest.raises(ValidationError):
        _request(time_budget_minutes=float("inf"))
    with pytest.raises(ValidationError):
        _request(included_modules=[])
    payload = default_request().model_dump()
    payload["included_modules"] = ["module_that_is_not_in_the_path"]
    assert client.post("/demo-center/analyze", json=payload).status_code == 422


# --------------------------------------------------------------------------- #
# 20. JSON safety across all paths
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity_in_any_response(client):
    for path_id in PATH_IDS:
        payload = _request(path_id).model_dump()
        res = client.post("/demo-center/analyze", json=payload)
        assert res.status_code == 200, path_id
        _assert_all_finite(res.json())


# --------------------------------------------------------------------------- #
# Extra behaviour: module scoping, checklist, routes
# --------------------------------------------------------------------------- #
def test_included_modules_narrow_scope():
    out = _analyze(
        "quant_research_workflow_tour",
        included_modules=["backtest_studio", "research_workspace"],
    )
    assert out.readiness_summary.included_module_count == 2
    item = next(c for c in out.completion_checklist if c.item_id == "full_module_scope")
    assert item.passed is False


def test_step_routes_reference_known_views():
    known_routes = {r.route for r in module_health_rows()}
    for path in sample_demo_paths():
        for step in path.steps:
            assert step.route in known_routes, (path.path_id, step.step_id)
        for mid in path.modules:
            assert any(r.module_id == mid for r in module_health_rows()), (path.path_id, mid)


def test_completion_checklist_time_budget():
    fits = _analyze("founder_investor_product_tour", time_budget_minutes=20.0)
    assert next(c for c in fits.completion_checklist if c.item_id == "time_budget_fits").passed
    tight = _analyze("full_platform_showcase_tour", time_budget_minutes=10.0)
    assert not next(c for c in tight.completion_checklist if c.item_id == "time_budget_fits").passed
    assert tight.path_summary.fits_time_budget is False
