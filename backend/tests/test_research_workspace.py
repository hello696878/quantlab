"""
Tests for the Research Workspace, Saved Presets & Experiment Journal
(Phase 33.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf),
the documented change/severity/coverage/reproducibility formulas, the
workspace-regime classification, and the deterministic report/export builder.
Fully deterministic — no network calls.
"""

import json
import math

import pytest
from pydantic import ValidationError

from app.research_workspace.models import (
    ExperimentRunInput,
    ResearchWorkspacePresetInput,
    WorkspaceAnalysisRequest,
)
from app.research_workspace.sample import (
    MODULE_LABELS,
    SECTION_TITLES,
    default_request,
    preset_by_id,
    sample_presets,
)
from app.research_workspace.service import analyze_research_workspace

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


def _request(preset_id="macro_stress_research_pack", **kwargs):
    return WorkspaceAnalysisRequest(
        selected_preset_id=preset_id,
        report_sections=kwargs.pop("report_sections", ALL_SECTIONS),
        **kwargs,
    )


def _analyze(preset_id="macro_stress_research_pack", **kwargs):
    return analyze_research_workspace(_request(preset_id, **kwargs))


def _valid_run(**overrides):
    base = dict(
        run_id="r1", run_name="Run 1", module_id="macro_regime",
        scenario_name="Scenario", created_at="2026-05-01T09:00:00Z",
        key_metric_name="Metric", baseline_value=1.0, stressed_value=2.0,
        severity_score=50.0, confidence_label="medium", notes="n",
    )
    base.update(overrides)
    return base


def _valid_preset(**overrides):
    base = dict(
        preset_id="p1", preset_name="Pack", description="Desc",
        primary_module="macro_regime", linked_modules=["macro_regime"],
        created_at="2026-05-01T09:00:00Z", tags=[], assumptions=["a"],
        limitations=["l"], experiment_runs=[_valid_run()],
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint_deterministic_presets(client):
    res = client.get("/research-workspace/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = [p["preset_id"] for p in body["presets"]]
    assert ids == [
        "macro_stress_research_pack", "crypto_risk_off_research_pack",
        "defi_liquidity_stress_research_pack", "tokenomics_unlock_review_pack",
        "alternative_data_signal_quality_pack", "cross_asset_scenario_report_pack",
    ]
    assert "not investment" in body["disclaimer"].lower()
    assert body == client.get("/research-workspace/sample").json()
    _assert_all_finite(body)


def test_analyze_endpoint_accepts_sample_request(client):
    res = client.post("/research-workspace/analyze", json=default_request().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "compliance" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–8. Formulas and ranking
# --------------------------------------------------------------------------- #
def test_run_change_formula():
    out = _analyze()
    preset = preset_by_id("macro_stress_research_pack")
    by_id = {r.run_id: r for r in preset.experiment_runs}
    for row in out.run_comparison:
        src = by_id[row.run_id]
        assert math.isclose(row.change, src.stressed_value - src.baseline_value, rel_tol=1e-12)


def test_percent_change_handles_zero_baseline():
    # The leakage run in the alt-data pack has baseline 0.0.
    out = _analyze("alternative_data_signal_quality_pack")
    row = next(r for r in out.run_comparison if r.run_id == "run_leakage_flags")
    assert row.baseline_value == 0.0
    assert math.isfinite(row.percent_change)
    assert math.isclose(row.percent_change, row.change / (abs(row.baseline_value) + 1e-9), rel_tol=1e-12)
    for r in out.run_comparison:
        assert math.isclose(r.percent_change, r.change / (abs(r.baseline_value) + 1e-9), rel_tol=1e-12)


def test_average_severity_formula():
    out = _analyze()
    expected = sum(r.severity_score for r in out.run_comparison) / len(out.run_comparison)
    assert math.isclose(out.severity_summary.average_severity, expected, rel_tol=1e-12)


def test_max_severity_formula():
    out = _analyze()
    expected = max(r.severity_score for r in out.run_comparison)
    assert math.isclose(out.severity_summary.max_severity, expected, rel_tol=1e-12)
    assert out.severity_summary.highest_severity_run_id == "run_portfolio_vol"


def test_severity_scores_bounded():
    for preset in sample_presets():
        out = _analyze(preset.preset_id)
        for r in out.run_comparison:
            assert 0.0 <= r.severity_score <= 100.0
        assert 0.0 <= out.severity_summary.average_severity <= 100.0
        assert 0.0 <= out.severity_summary.max_severity <= 100.0


def test_run_ranking_sorted_by_severity_descending():
    for preset in sample_presets():
        out = _analyze(preset.preset_id)
        sevs = [r.severity_score for r in out.run_comparison]
        assert sevs == sorted(sevs, reverse=True)


# --------------------------------------------------------------------------- #
# 9–11. Coverage, reproducibility, regime
# --------------------------------------------------------------------------- #
def test_coverage_score_finite_and_bounded():
    for preset in sample_presets():
        out = _analyze(preset.preset_id)
        c = out.severity_summary.coverage_score
        assert math.isfinite(c) and 0.0 <= c <= 1.0
    # Macro pack stages 3 distinct modules of the 9 available.
    out = _analyze("macro_stress_research_pack")
    assert math.isclose(out.severity_summary.coverage_score, 3 / len(MODULE_LABELS), rel_tol=1e-12)


def test_reproducibility_score_finite_and_bounded():
    out = _analyze()
    r = out.severity_summary.reproducibility_score
    assert math.isfinite(r) and 0.0 <= r <= 1.0
    passed = sum(1 for c in out.methodology_checklist if c.passed)
    assert math.isclose(r, passed / len(out.methodology_checklist), rel_tol=1e-12)
    # All macro-pack checks pass with the full default request.
    assert math.isclose(r, 1.0, rel_tol=1e-12)


def test_workspace_regime_per_preset():
    expected = {
        "macro_stress_research_pack": "multi_module_stress",
        "crypto_risk_off_research_pack": "multi_module_stress",
        "defi_liquidity_stress_research_pack": "focused_module_review",
        "tokenomics_unlock_review_pack": "focused_module_review",
        "alternative_data_signal_quality_pack": "focused_module_review",
        "cross_asset_scenario_report_pack": "severe_research_pack",
    }
    for preset_id, regime in expected.items():
        out = _analyze(preset_id)
        assert out.severity_summary.workspace_regime == regime, preset_id
        assert out.severity_summary.regime_label
        assert out.severity_summary.drivers


def test_workspace_regime_calm_and_incomplete_reachable():
    # Staging only the mild concentration run → calm_research_pack.
    calm = _analyze("tokenomics_unlock_review_pack", included_run_ids=["run_concentration"])
    assert calm.severity_summary.workspace_regime == "calm_research_pack"
    # A single un-annotated run without the limitations section fails 3 of the
    # 6 documented checks → incomplete_methodology.
    incomplete = _analyze(
        "tokenomics_unlock_review_pack",
        included_run_ids=["run_whale_deposits"],
        report_sections=["overview"],
    )
    assert math.isclose(incomplete.severity_summary.reproducibility_score, 0.5, rel_tol=1e-12)
    assert incomplete.severity_summary.workspace_regime == "incomplete_methodology"


# --------------------------------------------------------------------------- #
# 12–15. Report builder + export
# --------------------------------------------------------------------------- #
def test_report_builder_returns_selected_sections():
    out = _analyze(report_sections=["overview", "run_comparison"])
    included = {s.section_id for s in out.report_preview.sections if s.included}
    assert included == {"overview", "run_comparison"}
    assert "## Overview" in out.report_preview.markdown
    assert "## Run Comparison" in out.report_preview.markdown
    assert "## Methodology" not in out.report_preview.markdown


def test_generated_markdown_includes_limitations_when_selected():
    out = _analyze(report_sections=["overview", "limitations"])
    assert "## Limitations" in out.report_preview.markdown
    assert "not recorded lab outputs" in out.report_preview.markdown
    without = _analyze(report_sections=["overview"])
    assert "## Limitations" not in without.report_preview.markdown
    # The disclaimer footer is always present either way.
    assert "not investment" in without.report_preview.markdown.lower()


def test_generated_markdown_has_no_recommendation_wording():
    for preset in sample_presets():
        out = _analyze(preset.preset_id)
        text = out.report_preview.markdown.lower()
        for forbidden in ("recommend", "overweight", "underweight", "you should", "buy ", "sell "):
            assert forbidden not in text, (preset.preset_id, forbidden)


def test_export_payload_markdown_and_json():
    out = _analyze(user_note="Sample workspace note.")
    assert out.export_payload.markdown == out.report_preview.markdown
    payload = json.loads(out.export_payload.json_payload)
    assert payload["data_status"] == "static_sample"
    assert payload["preset_id"] == "macro_stress_research_pack"
    assert payload["user_note"] == "Sample workspace note."
    assert len(payload["runs"]) == len(out.run_comparison)
    assert "disclaimer" in payload
    _assert_all_finite(payload)


# --------------------------------------------------------------------------- #
# 16–20. Validation
# --------------------------------------------------------------------------- #
def test_reject_empty_linked_modules():
    with pytest.raises(ValidationError):
        ResearchWorkspacePresetInput(**_valid_preset(linked_modules=[]))


def test_reject_empty_experiment_runs():
    with pytest.raises(ValidationError):
        ResearchWorkspacePresetInput(**_valid_preset(experiment_runs=[]))


def test_reject_severity_outside_bounds():
    with pytest.raises(ValidationError):
        ExperimentRunInput(**_valid_run(severity_score=150.0))
    with pytest.raises(ValidationError):
        ExperimentRunInput(**_valid_run(severity_score=-1.0))


def test_reject_empty_report_sections(client):
    payload = default_request().model_dump()
    payload["report_sections"] = []
    assert client.post("/research-workspace/analyze", json=payload).status_code == 422


def test_reject_non_finite_values(client):
    with pytest.raises(ValidationError):
        ExperimentRunInput(**_valid_run(baseline_value=float("nan")))
    with pytest.raises(ValidationError):
        ExperimentRunInput(**_valid_run(stressed_value=float("inf")))
    payload = default_request().model_dump()
    payload["user_note"] = "x" * 5000  # over the documented 2000-char bound
    assert client.post("/research-workspace/analyze", json=payload).status_code == 422


def test_reject_unknown_preset_and_unmatched_runs(client):
    payload = default_request().model_dump()
    payload["selected_preset_id"] = "not_a_real_preset"
    assert client.post("/research-workspace/analyze", json=payload).status_code == 422
    payload = default_request().model_dump()
    payload["included_run_ids"] = ["no_such_run"]
    assert client.post("/research-workspace/analyze", json=payload).status_code == 422


# --------------------------------------------------------------------------- #
# 21. JSON safety across all presets
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity_in_any_response(client):
    for preset in sample_presets():
        payload = _request(preset.preset_id).model_dump()
        res = client.post("/research-workspace/analyze", json=payload)
        assert res.status_code == 200, preset.preset_id
        _assert_all_finite(res.json())


# --------------------------------------------------------------------------- #
# Extra behaviour: run staging, timeline, checklist
# --------------------------------------------------------------------------- #
def test_included_run_ids_filter_rows():
    out = _analyze(included_run_ids=["run_macro_inflation", "run_portfolio_vol"])
    assert {r.run_id for r in out.run_comparison} == {"run_macro_inflation", "run_portfolio_vol"}
    stage = next(t for t in out.workflow_timeline if t.step_id == "stage_runs")
    assert stage.status == "in_progress"


def test_workflow_timeline_shape():
    out = _analyze()
    ids = [t.step_id for t in out.workflow_timeline]
    assert ids == [
        "select_preset", "review_assumptions", "stage_runs", "compare_runs",
        "annotate", "methodology_check", "export_report",
    ]
    assert all(t.status in {"complete", "in_progress", "planned"} for t in out.workflow_timeline)


def test_methodology_checklist_flags_missing_run_notes():
    # The whale-deposit run in the tokenomics pack has empty notes.
    out = _analyze("tokenomics_unlock_review_pack")
    item = next(c for c in out.methodology_checklist if c.item_id == "run_notes_present")
    assert item.passed is False
    # Excluding the un-annotated run makes the check pass.
    out2 = _analyze(
        "tokenomics_unlock_review_pack",
        included_run_ids=["run_unlock_double", "run_runway_cut", "run_concentration"],
    )
    item2 = next(c for c in out2.methodology_checklist if c.item_id == "run_notes_present")
    assert item2.passed is True
