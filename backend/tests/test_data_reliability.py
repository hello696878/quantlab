"""
Tests for the Data Mode Registry, Offline Fixtures & API Reliability Center
(Phase 35.0).

Confirms the static registry API shape, validation, JSON-safety (no NaN/Inf),
the documented rate/score formulas, enum validity, the yfinance test-safety
contract, and the deterministic report/export builder. Fully deterministic —
no network calls and no provider imports.
"""

import json
import math

import pytest
from pydantic import ValidationError

from app.data_reliability.models import DataReliabilityRequest
from app.data_reliability.sample import (
    SECTION_TITLES,
    default_request,
    fixture_rows,
    module_rows,
    provider_rows,
)
from app.data_reliability.service import analyze_data_reliability

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
    return DataReliabilityRequest(
        report_sections=kwargs.pop("report_sections", ALL_SECTIONS),
        **kwargs,
    )


def _analyze(**kwargs):
    return analyze_data_reliability(_request(**kwargs))


# --------------------------------------------------------------------------- #
# 1–4. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint_module_data_modes(client):
    res = client.get("/data-reliability/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = {m["module_id"] for m in body["module_modes"]}
    assert len(body["module_modes"]) == 20
    for expected in (
        "global_markets_globe", "backtest_studio", "strategy_comparison",
        "portfolio_risk_lab", "macro_regime_lab", "scenario_studio",
        "research_workspace", "demo_center", "crypto_derivatives_lab",
        "defi_risk_lab", "tokenomics_lab", "onchain_analytics_lab",
        "alternative_data_lab", "market_microstructure_lab", "options_lab",
        "volatility_lab", "futures_commodities_lab", "real_estate_lab",
        "credit_risk_lab", "export_report",
    ):
        assert expected in ids, expected
    assert body == client.get("/data-reliability/sample").json()
    _assert_all_finite(body)


def test_sample_endpoint_provider_registry(client):
    body = client.get("/data-reliability/sample").json()
    provider_ids = {p["provider_id"] for p in body["providers"]}
    assert {
        "static_fixtures", "local_calculation_engine", "user_input",
        "internal_sample_registry", "yfinance_optional", "fred_optional",
        "globe_delayed_quotes",
    } == provider_ids


def test_sample_endpoint_offline_fixture_registry(client):
    body = client.get("/data-reliability/sample").json()
    fixture_ids = {f["fixture_id"] for f in body["offline_fixtures"]}
    assert {
        "pairs_demo_fallback", "portfolio_sample", "macro_regime_samples",
        "scenario_studio_templates", "research_workspace_presets",
        "demo_center_metadata", "crypto_derivatives_samples", "defi_samples",
        "tokenomics_samples", "onchain_samples", "alternative_data_samples",
    } == fixture_ids


def test_analyze_endpoint_accepts_sample_request(client):
    res = client.post("/data-reliability/analyze", json=default_request().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 5–9. Rate and score formulas
# --------------------------------------------------------------------------- #
def test_demo_safe_rate_formula():
    out = _analyze()
    rows = out.module_modes
    expected = sum(1 for r in rows if r.demo_safe) / len(rows)
    assert math.isclose(out.reliability_summary.demo_safe_rate, expected, rel_tol=1e-12)


def test_test_safe_rate_formula():
    out = _analyze()
    rows = out.module_modes
    expected = sum(1 for r in rows if r.test_safe) / len(rows)
    assert math.isclose(out.reliability_summary.test_safe_rate, expected, rel_tol=1e-12)


def test_fallback_coverage_formula():
    out = _analyze()
    rows = out.module_modes
    expected = sum(1 for r in rows if r.offline_fallback_available) / len(rows)
    assert math.isclose(out.reliability_summary.fallback_coverage, expected, rel_tol=1e-12)


def test_external_exposure_formula():
    out = _analyze()
    rows = out.module_modes
    expected = sum(1 for r in rows if r.external_provider_required) / len(rows)
    assert math.isclose(out.reliability_summary.external_provider_exposure, expected, rel_tol=1e-12)
    # Only the two backtesting modules can require the optional provider.
    assert math.isclose(expected, 2 / 20, rel_tol=1e-12)


def test_reliability_score_finite_bounded_and_formula():
    for kwargs in ({}, {"selected_category": "backtesting"}, {"selected_category": "crypto"}):
        out = _analyze(**kwargs)
        s = out.reliability_summary
        assert math.isfinite(s.reliability_score)
        assert 0.0 <= s.reliability_score <= 100.0
        expected = 100.0 * (
            0.35 * s.demo_safe_rate + 0.25 * s.test_safe_rate
            + 0.25 * s.fallback_coverage + 0.15 * (1.0 - s.external_provider_exposure)
        )
        assert math.isclose(s.reliability_score, expected, rel_tol=1e-12)
    # The backtesting category is fully external-exposed → lower score.
    full = _analyze().reliability_summary.reliability_score
    backtesting = _analyze(selected_category="backtesting").reliability_summary.reliability_score
    assert backtesting < full


# --------------------------------------------------------------------------- #
# 10–14. Enum validity and safety contracts
# --------------------------------------------------------------------------- #
def test_module_data_modes_valid_enums():
    valid = {"static_sample", "delayed_sample", "user_input", "local_calculation", "optional_external_provider"}
    for row in module_rows():
        assert row.data_mode in valid, row.module_id


def test_provider_failure_modes_valid_enums():
    valid_modes = {"fallback_to_fixture", "friendly_error", "disabled_in_tests", "static_only"}
    valid_types = {"market_data", "macro_data", "static_fixture", "local_calculation", "user_input"}
    for p in provider_rows():
        assert p.default_failure_mode in valid_modes, p.provider_id
        assert p.provider_type in valid_types, p.provider_id


def test_offline_fixtures_deterministic_and_test_safe():
    for f in fixture_rows():
        assert f.deterministic is True, f.fixture_id
        assert f.test_safe is True, f.fixture_id
        assert f.observation_count >= 1


def test_yfinance_not_allowed_in_tests_and_has_fallback():
    yf = next(p for p in provider_rows() if p.provider_id == "yfinance_optional")
    assert yf.is_external is True
    assert yf.requires_network is True
    assert yf.requires_api_key is False
    assert yf.allowed_in_tests is False
    assert yf.has_offline_fallback is True
    fred = next(p for p in provider_rows() if p.provider_id == "fred_optional")
    assert fred.allowed_in_tests is False and fred.requires_api_key is True


def test_pairs_trading_demo_fallback_represented():
    fixture = next(f for f in fixture_rows() if f.fixture_id == "pairs_demo_fallback")
    assert fixture.fixture_type == "price_series"
    assert "backtest_studio" in fixture.used_by_modules
    backtest = next(r for r in module_rows() if r.module_id == "backtest_studio")
    assert "pairs_demo_fallback" in backtest.fixture_names
    assert backtest.offline_fallback_available is True
    assert "KO/PEP" in backtest.failure_behavior


# --------------------------------------------------------------------------- #
# 15–16. Report wording
# --------------------------------------------------------------------------- #
def test_generated_markdown_includes_limitations_when_selected():
    out = _analyze(report_sections=["overview", "limitations"])
    assert "## Limitations" in out.generated_report.markdown
    assert "never guaranteed" in out.generated_report.markdown
    without = _analyze(report_sections=["overview"])
    assert "## Limitations" not in without.generated_report.markdown
    assert "not investment" in without.generated_report.markdown.lower()


def test_generated_markdown_has_no_recommendation_wording():
    for kwargs in (
        {},
        {"include_external_providers": False, "include_static_fixtures": False, "include_test_safety": False},
        {"selected_category": "backtesting"},
    ):
        out = _analyze(**kwargs)
        text = out.generated_report.markdown.lower()
        for forbidden in ("recommend", "overweight", "underweight", "you should", "buy ", "sell "):
            assert forbidden not in text, (kwargs, forbidden)
        # Never guarantee external availability.
        assert "guaranteed available" not in text
        assert "always available" not in text


# --------------------------------------------------------------------------- #
# 17–19. Validation and JSON safety
# --------------------------------------------------------------------------- #
def test_reject_empty_report_sections(client):
    payload = default_request().model_dump()
    payload["report_sections"] = []
    assert client.post("/data-reliability/analyze", json=payload).status_code == 422


def test_reject_invalid_values(client):
    with pytest.raises(ValidationError):
        _request(selected_modules=[])
    with pytest.raises(ValidationError):
        _request(selected_category="not_a_category")
    payload = default_request().model_dump()
    payload["include_external_providers"] = "not_a_bool"
    assert client.post("/data-reliability/analyze", json=payload).status_code == 422
    payload = default_request().model_dump()
    payload["selected_modules"] = ["module_that_does_not_exist"]
    assert client.post("/data-reliability/analyze", json=payload).status_code == 422


def test_no_nan_or_infinity_in_any_response(client):
    for payload_kwargs in (
        {},
        {"selected_category": "crypto"},
        {"include_external_providers": False, "include_static_fixtures": False, "include_test_safety": False},
    ):
        payload = _request(**payload_kwargs).model_dump()
        res = client.post("/data-reliability/analyze", json=payload)
        assert res.status_code == 200, payload_kwargs
        _assert_all_finite(res.json())


# --------------------------------------------------------------------------- #
# Extra behaviour: toggles, scoping, export
# --------------------------------------------------------------------------- #
def test_toggles_filter_response():
    out = _analyze(
        include_external_providers=False,
        include_static_fixtures=False,
        include_test_safety=False,
    )
    assert all(not p.is_external for p in out.providers)
    assert out.offline_fixtures == []
    assert out.test_safety_matrix == []
    # The fallback matrix is always present for the scoped modules.
    assert len(out.fallback_matrix) == len(out.module_modes)


def test_category_and_module_scoping():
    out = _analyze(selected_category="crypto")
    assert {r.category for r in out.module_modes} == {"crypto"}
    assert out.reliability_summary.module_count == 4
    narrowed = _analyze(selected_modules=["backtest_studio"])
    assert [r.module_id for r in narrowed.module_modes] == ["backtest_studio"]
    assert math.isclose(narrowed.reliability_summary.external_provider_exposure, 1.0, rel_tol=1e-12)


def test_export_payload_markdown_and_json():
    out = _analyze()
    assert out.export_payload.markdown == out.generated_report.markdown
    payload = json.loads(out.export_payload.json_payload)
    assert payload["data_status"] == "static_sample"
    assert payload["module_count"] == 20
    assert len(payload["modules"]) == 20
    assert "disclaimer" in payload
    _assert_all_finite(payload)


def test_this_module_makes_no_network_calls():
    # The reliability layer must not import provider libraries at all.
    import app.data_reliability.sample as sample_mod
    import app.data_reliability.service as service_mod

    for mod in (sample_mod, service_mod):
        source = open(mod.__file__, encoding="utf-8").read()
        assert "import yfinance" not in source
        assert "requests" not in source
        assert "urllib" not in source
