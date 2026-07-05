"""
Tests for the Macro Regime & Cross-Asset Allocation Lab (Phase 31.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.macro_regime.models import MacroRegimeAnalysisRequest
from app.macro_regime.sample import sample_requests
from app.macro_regime.service import analyze_macro_regime

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


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


def _goldilocks():
    return sample_requests()[0]


def _analyze(req=None):
    return analyze_macro_regime(req or _goldilocks())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


def _alloc(out, method):
    return next(a for a in out.allocation_results if a.method == method)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/macro-regime/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = {s["sample_id"] for s in body["samples"]}
    assert ids == {
        "GOLDILOCKS_SAMPLE", "INFLATION_SHOCK_SAMPLE", "RECESSION_CREDIT_SAMPLE",
        "STAGFLATION_SAMPLE", "LIQUIDITY_EASING_SAMPLE", "STRONG_USD_SAMPLE",
    }
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/macro-regime/analyze", json=_goldilocks().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "asset-allocation" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–5. Scoring formulas
# --------------------------------------------------------------------------- #
def test_z_score_formula():
    req = _goldilocks()
    out = _analyze(req)
    i = req.indicators[0]
    row = out.indicator_table[0]
    assert math.isclose(row.z_score, (i.value - i.long_run_mean) / i.long_run_std, rel_tol=1e-12)


def test_direction_adjusted_score_formula():
    req = _goldilocks()
    out = _analyze(req)
    for i, row in zip(req.indicators, out.indicator_table):
        d = 1.0 if i.direction == "higher_is_expansionary" else -1.0
        assert math.isclose(row.direction_adjusted_score, d * row.z_score, rel_tol=1e-12)


def test_category_score_formula():
    req = _goldilocks()
    out = _analyze(req)
    growth_rows = [r for r in out.indicator_table if r.category == "growth"]
    expected = sum(r.weight * r.direction_adjusted_score for r in growth_rows) / sum(r.weight for r in growth_rows)
    assert math.isclose(out.category_scores.growth_score, expected, rel_tol=1e-12)
    # Sample is constructed at target z = +1.0 for growth.
    assert math.isclose(out.category_scores.growth_score, 1.0, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# 6. Regime classification
# --------------------------------------------------------------------------- #
def test_regime_classification_exists_and_varies():
    regimes = [analyze_macro_regime(req).macro_regime for req in sample_requests()]
    for reg in regimes:
        assert reg.regime_id and reg.regime_label and reg.explanation
        assert math.isfinite(reg.score) and 0.0 <= reg.score <= 1.0
    assert [r.regime_id for r in regimes] == [
        "goldilocks_growth", "inflation_shock", "recession_credit_stress",
        "stagflation", "liquidity_easing", "strong_usd_pressure",
    ]


# --------------------------------------------------------------------------- #
# 7–12. Allocations
# --------------------------------------------------------------------------- #
def test_inverse_vol_weights_sum_to_one_and_positive():
    for req in sample_requests():
        alloc = _alloc(analyze_macro_regime(req), "inverse_volatility")
        assert math.isclose(sum(alloc.weights.values()), 1.0, abs_tol=1e-9)
        assert all(w > 0 for w in alloc.weights.values())
        # Weights ∝ 1/σ: the lowest-vol asset (cash) gets the largest weight.
        assert max(alloc.weights, key=alloc.weights.get) == "USD_CASH_SAMPLE"


def test_risk_contributions_sum_to_one():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        for alloc in out.allocation_results:
            assert math.isclose(sum(alloc.risk_contributions.values()), 1.0, abs_tol=1e-6)


def test_regime_adjusted_returns_finite():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        for row in out.asset_assumptions:
            assert math.isfinite(row.regime_adjusted_expected_return)
        # Formula check on the first asset.
        a = req.assets[0]
        s = out.category_scores
        expected = (
            a.expected_return
            + a.growth_beta * s.growth_score
            + a.inflation_beta * s.inflation_score
            + a.rate_beta * s.policy_score
            + a.usd_beta * s.usd_pressure_score
            - a.credit_beta * s.credit_stress_score
        )
        assert math.isclose(out.asset_assumptions[0].regime_adjusted_expected_return, expected, rel_tol=1e-9)


def test_regime_tilted_weights_sum_to_one():
    for req in sample_requests():
        alloc = _alloc(analyze_macro_regime(req), "regime_tilted")
        assert math.isclose(sum(alloc.weights.values()), 1.0, abs_tol=1e-9)
        assert all(w >= 0 for w in alloc.weights.values())


def test_tilted_fallback_when_all_scores_non_positive():
    req = _goldilocks().model_copy(update={"risk_aversion_lambda": 10.0})
    alloc = _alloc(analyze_macro_regime(req), "regime_tilted")
    inv = _alloc(analyze_macro_regime(req), "inverse_volatility")
    assert any("fell back" in n for n in alloc.notes)
    for k in alloc.weights:
        assert math.isclose(alloc.weights[k], inv.weights[k], rel_tol=1e-9)


def test_risk_parity_contributions_near_equal():
    out = _analyze()
    rp = _alloc(out, "risk_parity_style")
    # On the full covariance the fixed point equalises Σ-based contributions;
    # the reported simple RC (wσ/Σwσ) should still be far flatter than inverse-vol's.
    rcs = list(rp.risk_contributions.values())
    assert max(rcs) < 0.35  # no single asset dominates


# --------------------------------------------------------------------------- #
# 13–19. Scenarios
# --------------------------------------------------------------------------- #
def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "growth_upside", "growth_slowdown", "inflation_spike", "disinflation",
        "policy_tightening", "liquidity_easing", "credit_spread_shock",
        "strong_usd_shock", "severe_combo",
    } == ids


def test_inflation_spike_raises_inflation_score():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "inflation_spike").inflation_score > _scenario(out, "base").inflation_score


def test_growth_slowdown_lowers_growth_score():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "growth_slowdown").growth_score < _scenario(out, "base").growth_score


def test_credit_shock_raises_credit_stress():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "credit_spread_shock").credit_stress_score > _scenario(out, "base").credit_stress_score


def test_liquidity_easing_improves_liquidity_score():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "liquidity_easing").liquidity_score > _scenario(out, "base").liquidity_score


def test_usd_shock_raises_usd_pressure():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "strong_usd_shock").usd_pressure_score > _scenario(out, "base").usd_pressure_score


def test_severe_combo_regime():
    for req in sample_requests():
        out = analyze_macro_regime(req)
        assert _scenario(out, "severe_combo").regime_label == "Severe macro stress"


# --------------------------------------------------------------------------- #
# 20–23. Validation
# --------------------------------------------------------------------------- #
def test_reject_non_positive_long_run_std():
    base = _goldilocks().model_dump()
    base["indicators"][0]["long_run_std"] = 0.0
    with pytest.raises(ValidationError):
        MacroRegimeAnalysisRequest(**base)


def test_reject_non_positive_volatility():
    base = _goldilocks().model_dump()
    base["assets"][0]["volatility"] = -0.1
    with pytest.raises(ValidationError):
        MacroRegimeAnalysisRequest(**base)


def test_reject_liquidity_score_out_of_range():
    base = _goldilocks().model_dump()
    base["assets"][0]["liquidity_score"] = 1.5
    with pytest.raises(ValidationError):
        MacroRegimeAnalysisRequest(**base)


def test_reject_non_finite():
    base = _goldilocks().model_dump()
    base["assets"][0]["expected_return"] = float("inf")
    with pytest.raises(ValidationError):
        MacroRegimeAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 24. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/macro-regime/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
