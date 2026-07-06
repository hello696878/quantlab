"""
Tests for the Unified Scenario Studio & Cross-Lab Report Builder (Phase 32.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), the
documented impact/severity formulas, the regime classification, and the
deterministic report builder. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.scenario_studio.models import (
    ScenarioShockOverrides,
    ScenarioStudioRequest,
)
from app.scenario_studio.sample import (
    MODULE_LABELS,
    SECTION_TITLES,
    default_request,
    sample_templates,
    template_by_id,
)
from app.scenario_studio.service import analyze_scenario_studio

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

ALL_MODULES = list(MODULE_LABELS.keys())
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


def _request(scenario_id="soft_landing", **kwargs):
    return ScenarioStudioRequest(
        selected_scenario_id=scenario_id,
        included_modules=kwargs.pop("included_modules", ALL_MODULES),
        report_sections=kwargs.pop("report_sections", ALL_SECTIONS),
        **kwargs,
    )


def _analyze(scenario_id="soft_landing", **kwargs):
    return analyze_scenario_studio(_request(scenario_id, **kwargs))


def _impact(out, module_id):
    return next(m for m in out.module_impacts if m.module_id == module_id)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint_deterministic_templates(client):
    res = client.get("/scenario-studio/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = [t["scenario_id"] for t in body["templates"]]
    assert ids == [
        "soft_landing", "inflation_reacceleration", "growth_shock",
        "liquidity_crunch", "credit_stress", "crypto_risk_off",
        "stablecoin_depeg_stress", "exchange_inflow_panic",
        "alternative_data_noise_shock", "severe_cross_asset_stress_combo",
    ]
    assert "not investment" in body["disclaimer"].lower()
    # Deterministic: two calls return identical payloads.
    assert body == client.get("/scenario-studio/sample").json()
    _assert_all_finite(body)


def test_analyze_endpoint_accepts_sample_request(client):
    res = client.post("/scenario-studio/analyze", json=default_request().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "asset-allocation" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–5. Impact scores and severity
# --------------------------------------------------------------------------- #
def test_module_impact_scores_bounded():
    for template in sample_templates():
        out = _analyze(template.scenario_id)
        assert len(out.module_impacts) == len(ALL_MODULES)
        for row in out.module_impacts:
            assert 0.0 <= row.impact_score <= 100.0
            assert 0.0 <= row.baseline_score <= 100.0
            assert 0.0 <= row.stressed_score <= 100.0


def test_composite_severity_finite_and_bounded():
    for template in sample_templates():
        out = _analyze(template.scenario_id)
        assert math.isfinite(out.composite_severity)
        assert 0.0 <= out.composite_severity <= 100.0
        expected = sum(m.impact_score for m in out.module_impacts) / len(out.module_impacts)
        assert math.isclose(out.composite_severity, expected, rel_tol=1e-12)


def test_severe_combo_more_severe_than_soft_landing():
    soft = _analyze("soft_landing")
    severe = _analyze("severe_cross_asset_stress_combo")
    assert severe.composite_severity > soft.composite_severity
    assert severe.scenario_regime.severity_score > soft.scenario_regime.severity_score


# --------------------------------------------------------------------------- #
# 6–10. Scenario-specific impact behaviour
# --------------------------------------------------------------------------- #
def test_crypto_risk_off_raises_crypto_impacts():
    soft = _analyze("soft_landing")
    out = _analyze("crypto_risk_off")
    for mid in ("crypto_derivatives", "defi_risk", "tokenomics", "onchain_analytics"):
        assert _impact(out, mid).impact_score > _impact(soft, mid).impact_score


def test_stablecoin_depeg_raises_defi_impact():
    soft = _analyze("soft_landing")
    out = _analyze("stablecoin_depeg_stress")
    assert _impact(out, "defi_risk").impact_score > _impact(soft, "defi_risk").impact_score
    assert _impact(out, "defi_risk").impact_score >= 70.0


def test_exchange_inflow_panic_raises_onchain_impact():
    soft = _analyze("soft_landing")
    out = _analyze("exchange_inflow_panic")
    assert (
        _impact(out, "onchain_analytics").impact_score
        > _impact(soft, "onchain_analytics").impact_score
    )
    assert _impact(out, "onchain_analytics").impact_score >= 70.0


def test_altdata_noise_shock_raises_alternative_data_impact():
    soft = _analyze("soft_landing")
    out = _analyze("alternative_data_noise_shock")
    assert (
        _impact(out, "alternative_data").impact_score
        > _impact(soft, "alternative_data").impact_score
    )
    assert _impact(out, "alternative_data").impact_score >= 70.0


def test_credit_stress_raises_portfolio_and_macro_impacts():
    soft = _analyze("soft_landing")
    out = _analyze("credit_stress")
    assert _impact(out, "portfolio_risk").impact_score > _impact(soft, "portfolio_risk").impact_score
    assert _impact(out, "macro_regime").impact_score > _impact(soft, "macro_regime").impact_score
    assert out.scenario_regime.regime_id == "credit_liquidity_stress"


# --------------------------------------------------------------------------- #
# 11. Regime classification
# --------------------------------------------------------------------------- #
def test_regime_classification_per_template():
    expected = {
        "soft_landing": "benign_cross_asset",
        "inflation_reacceleration": "macro_policy_stress",
        "growth_shock": "broad_risk_off",
        "liquidity_crunch": "credit_liquidity_stress",
        "credit_stress": "credit_liquidity_stress",
        "crypto_risk_off": "crypto_specific_stress",
        "stablecoin_depeg_stress": "crypto_specific_stress",
        "exchange_inflow_panic": "crypto_specific_stress",
        "alternative_data_noise_shock": "data_quality_stress",
        "severe_cross_asset_stress_combo": "severe_systemic_stress",
    }
    for scenario_id, regime_id in expected.items():
        out = _analyze(scenario_id)
        assert out.scenario_regime.regime_id == regime_id, scenario_id
        assert out.scenario_regime.regime_label
        assert out.scenario_regime.explanation
        assert out.scenario_regime.drivers


# --------------------------------------------------------------------------- #
# 12–15. Report builder
# --------------------------------------------------------------------------- #
def test_report_builder_returns_selected_sections():
    out = _analyze(report_sections=["executive_summary", "macro"])
    # Limitations is always force-included.
    assert out.report_builder.included_sections == ["executive_summary", "macro", "limitations"]
    included = {s.section_id for s in out.generated_report.sections if s.included}
    assert included == {"executive_summary", "macro", "limitations"}
    assert "## Executive Summary" in out.generated_report.markdown
    assert "## Macro Regime" in out.generated_report.markdown
    assert "## Portfolio Risk" not in out.generated_report.markdown


def test_generated_markdown_includes_limitations():
    out = _analyze(report_sections=["executive_summary"])
    assert "## Limitations" in out.generated_report.markdown
    assert out.generated_report.limitations
    assert "not investment" in out.generated_report.markdown.lower()


def test_generated_report_has_no_recommendation_wording():
    for template in sample_templates():
        out = _analyze(template.scenario_id)
        text = out.generated_report.markdown.lower()
        for forbidden in ("recommend", "overweight", "underweight", "you should", "buy ", "sell "):
            assert forbidden not in text, (template.scenario_id, forbidden)


def test_section_coverage_formula():
    out = _analyze(report_sections=["executive_summary", "macro", "crypto"])
    # 3 requested + forced limitations = 4 of 9 available.
    assert math.isclose(out.report_builder.section_coverage, 4 / 9, rel_tol=1e-12)
    full = _analyze(report_sections=ALL_SECTIONS)
    assert math.isclose(full.report_builder.section_coverage, 1.0, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 16–20. Validation
# --------------------------------------------------------------------------- #
def test_reject_non_positive_volatility_multiplier():
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(volatility_multiplier=-1.0)
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(volatility_multiplier=0.0)


def test_reject_negative_exchange_inflow_multiplier():
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(exchange_inflow_multiplier=-0.5)
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(token_unlock_multiplier=-0.5)
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(publication_lag_shock=-0.1)


def test_reject_empty_included_modules(client):
    payload = default_request().model_dump()
    payload["included_modules"] = []
    assert client.post("/scenario-studio/analyze", json=payload).status_code == 422


def test_reject_empty_report_sections(client):
    payload = default_request().model_dump()
    payload["report_sections"] = []
    assert client.post("/scenario-studio/analyze", json=payload).status_code == 422


def test_reject_non_finite_values(client):
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(growth_shock=float("nan"))
    with pytest.raises(ValidationError):
        ScenarioShockOverrides(equity_shock=float("inf"))
    payload = default_request().model_dump()
    payload["custom_overrides"] = {"growth_shock": "NaN"}
    assert client.post("/scenario-studio/analyze", json=payload).status_code == 422


def test_reject_unknown_scenario_id(client):
    payload = default_request().model_dump()
    payload["selected_scenario_id"] = "not_a_real_scenario"
    assert client.post("/scenario-studio/analyze", json=payload).status_code == 422


# --------------------------------------------------------------------------- #
# 21. JSON safety across all templates
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity_in_any_response(client):
    for template in sample_templates():
        payload = _request(template.scenario_id).model_dump()
        res = client.post("/scenario-studio/analyze", json=payload)
        assert res.status_code == 200, template.scenario_id
        _assert_all_finite(res.json())


# --------------------------------------------------------------------------- #
# Extra behaviour: overrides, module filtering, formula spot-checks
# --------------------------------------------------------------------------- #
def test_custom_overrides_change_impacts():
    base = _analyze("soft_landing")
    out = _analyze(
        "soft_landing",
        custom_overrides=ScenarioShockOverrides(crypto_price_shock=-2.0),
    )
    assert (
        _impact(out, "crypto_derivatives").impact_score
        > _impact(base, "crypto_derivatives").impact_score
    )
    row = next(r for r in out.global_shocks if r.shock_id == "crypto_price_shock")
    assert row.overridden is True
    assert row.value == -2.0


def test_included_modules_filter_rows_and_composite():
    out = _analyze("crypto_risk_off", included_modules=["defi_risk"])
    assert [m.module_id for m in out.module_impacts] == ["defi_risk"]
    assert math.isclose(
        out.composite_severity, _impact(out, "defi_risk").impact_score, rel_tol=1e-12
    )
    assert [r.module_id for r in out.baseline_vs_stress] == ["defi_risk"]
    assert {c.row_label for c in out.heatmap} == {"DeFi Risk"}


def test_macro_impact_formula_spot_check():
    t = template_by_id("soft_landing")
    out = _analyze("soft_landing")
    expected = min(
        max(
            20.0 * abs(t.growth_shock) + 20.0 * abs(t.inflation_shock)
            + 15.0 * abs(t.policy_shock) + 15.0 * abs(t.liquidity_shock)
            + 20.0 * abs(t.credit_shock) + 10.0 * abs(t.usd_shock),
            0.0,
        ),
        100.0,
    )
    assert math.isclose(_impact(out, "macro_regime").impact_score, expected, rel_tol=1e-12)


def test_heatmap_shape_and_buckets():
    out = _analyze("severe_cross_asset_stress_combo")
    assert len(out.heatmap) == len(ALL_MODULES) * 6
    for cell in out.heatmap:
        assert 0.0 <= cell.value <= 100.0
        assert cell.bucket in {"low", "moderate", "elevated", "high", "severe"}


def test_baseline_vs_stress_change_formula():
    out = _analyze("severe_cross_asset_stress_combo")
    for row in out.baseline_vs_stress:
        assert math.isclose(row.change, row.stressed_value - row.baseline_value, rel_tol=1e-12)
