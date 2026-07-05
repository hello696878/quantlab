"""
Tests for the Tokenomics, Unlock Schedule & Treasury Risk Lab (Phase 28.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.tokenomics.models import TokenomicsAnalysisRequest
from app.tokenomics.sample import sample_requests
from app.tokenomics.service import analyze_tokenomics

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


def _lfhv():
    return sample_requests()[4]  # Low Float High FDV sample


def _analyze(req=None):
    return analyze_tokenomics(req or _lfhv())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/tokenomics/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    syms = {t["market"]["symbol"] for t in body["tokens"]}
    assert syms == {
        "L1_SAMPLE", "DEFI_GOV_SAMPLE", "GAMING_UNLOCK_SAMPLE",
        "STABLE_GOV_SAMPLE", "LFHV_SAMPLE",
    }
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/tokenomics/analyze", json=_lfhv().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "venture" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–9. Valuation & unlock formulas
# --------------------------------------------------------------------------- #
def test_market_cap_formula():
    req = _lfhv()
    v = _analyze(req).valuation_metrics
    assert math.isclose(v.market_cap, req.market.price * req.market.circulating_supply, rel_tol=1e-12)


def test_fdv_formula():
    req = _lfhv()
    v = _analyze(req).valuation_metrics
    assert math.isclose(v.fully_diluted_valuation, req.market.price * req.market.total_supply, rel_tol=1e-12)


def test_fdv_ratio_formula():
    req = _lfhv()
    v = _analyze(req).valuation_metrics
    assert math.isclose(v.fdv_to_market_cap, v.fully_diluted_valuation / v.market_cap, rel_tol=1e-12)
    # Spec example: 1B total / 100M circ → 10×.
    assert math.isclose(v.fdv_to_market_cap, 10.0, rel_tol=1e-9)


def test_float_ratio_formula():
    req = _lfhv()
    v = _analyze(req).valuation_metrics
    assert math.isclose(v.float_ratio, req.market.circulating_supply / req.market.total_supply, rel_tol=1e-12)


def test_unlock_value_formula():
    req = _lfhv()
    out = _analyze(req)
    first = out.unlock_schedule[0]
    src = sorted(req.unlock_events, key=lambda e: e.days_until)[0]
    assert math.isclose(first.unlock_value, req.market.price * src.tokens, rel_tol=1e-12)


def test_unlock_pct_formula():
    req = _lfhv()
    out = _analyze(req)
    first = out.unlock_schedule[0]
    src = sorted(req.unlock_events, key=lambda e: e.days_until)[0]
    assert math.isclose(first.unlock_pct_circulating, src.tokens / req.market.circulating_supply, rel_tol=1e-12)


def test_cumulative_unlock_pressure_formula():
    req = _lfhv()
    up = _analyze(req).unlock_pressure
    expected_180 = sum(e.tokens for e in req.unlock_events if e.days_until <= 180.0)
    assert math.isclose(up.next_180d_tokens, expected_180, rel_tol=1e-12)
    assert math.isclose(up.next_180d_pct_circulating, expected_180 / req.market.circulating_supply, rel_tol=1e-12)
    # Buckets are cumulative in horizon: 30d ⊆ 90d ⊆ 180d ⊆ 365d.
    assert up.next_30d_tokens <= up.next_90d_tokens <= up.next_180d_tokens <= up.next_365d_tokens


# --------------------------------------------------------------------------- #
# 10–16. Emission / staking / treasury / concentration
# --------------------------------------------------------------------------- #
def test_annual_emission_tokens_formula():
    req = _lfhv()
    em = _analyze(req).emission_analysis
    assert math.isclose(em.annual_emission_tokens, req.market.circulating_supply * req.market.emission_rate_annual, rel_tol=1e-12)


def test_emission_inflation_formula():
    req = _lfhv()
    em = _analyze(req).emission_analysis
    assert math.isclose(em.emission_inflation, em.annual_emission_tokens / req.market.circulating_supply, rel_tol=1e-12)


def test_real_yield_formula():
    req = _lfhv()
    out = _analyze(req)
    assert math.isclose(
        out.staking_analysis.real_yield_approx,
        req.market.staking_yield - out.emission_analysis.emission_inflation,
        abs_tol=1e-12,
    )


def test_treasury_value_formula():
    req = _lfhv()
    tr = _analyze(req).treasury_analysis
    expected = req.market.price * (req.market.treasury_tokens or 0.0) + (req.market.treasury_stables or 0.0)
    assert math.isclose(tr.treasury_total_value, expected, rel_tol=1e-12)
    # Spec example: 2·120M + 25M = 265M.
    assert math.isclose(tr.treasury_total_value, 265_000_000.0, rel_tol=1e-9)


def test_runway_months_formula():
    req = _lfhv()
    tr = _analyze(req).treasury_analysis
    assert math.isclose(tr.runway_months, tr.treasury_total_value / req.market.monthly_burn_usd, rel_tol=1e-9)


def test_revenue_adjusted_runway_finite():
    for req in sample_requests():
        tr = analyze_tokenomics(req).treasury_analysis
        assert math.isfinite(tr.revenue_adjusted_runway_months)
        # Net burn ≤ gross burn → the adjusted runway is never shorter.
        assert tr.revenue_adjusted_runway_months >= tr.runway_months - 1e-9


def test_concentration_score_finite():
    for req in sample_requests():
        hc = analyze_tokenomics(req).holder_concentration
        assert math.isfinite(hc.concentration_score)
        assert 0.0 <= hc.concentration_score <= 1.0


# --------------------------------------------------------------------------- #
# 17–24. Regime & scenarios
# --------------------------------------------------------------------------- #
def test_risk_regime_exists():
    for req in sample_requests():
        reg = analyze_tokenomics(req).risk_regime
        assert reg.regime_id and reg.regime_label and reg.explanation
        assert math.isfinite(reg.score) and 0.0 <= reg.score <= 1.0


def test_regime_variety_across_samples():
    regimes = [analyze_tokenomics(req).risk_regime.regime_id for req in sample_requests()]
    assert regimes == [
        "balanced", "emission_pressure", "unlock_pressure",
        "treasury_runway_risk", "low_float_high_fdv",
    ]


def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "price_drawdown", "unlock_acceleration", "emission_increase",
        "treasury_asset_drawdown", "burn_increase", "concentration_shock",
        "revenue_decline", "low_float_repricing", "severe_combo",
    } == ids


def test_price_drawdown_lowers_market_cap():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        base = _scenario(out, "base")
        shocked = _scenario(out, "price_drawdown")
        assert shocked.market_cap < base.market_cap
        assert shocked.treasury_value <= base.treasury_value + 1e-9


def test_unlock_acceleration_raises_pressure():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        assert _scenario(out, "unlock_acceleration").next_180d_unlock_pressure > _scenario(out, "base").next_180d_unlock_pressure


def test_emission_increase_lowers_real_yield():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        assert _scenario(out, "emission_increase").real_yield_approx < _scenario(out, "base").real_yield_approx


def test_treasury_drawdown_lowers_runway():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        assert _scenario(out, "treasury_asset_drawdown").runway_months < _scenario(out, "base").runway_months


def test_burn_increase_lowers_runway():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        assert _scenario(out, "burn_increase").runway_months < _scenario(out, "base").runway_months


def test_concentration_shock_raises_score():
    for req in sample_requests():
        out = analyze_tokenomics(req)
        assert _scenario(out, "concentration_shock").concentration_score > _scenario(out, "base").concentration_score


def test_severe_combo_regime():
    out = _analyze()  # LFHV
    assert _scenario(out, "severe_combo").regime_label == "Severe tokenomics stress"


# --------------------------------------------------------------------------- #
# 25–28. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_price():
    base = _lfhv().model_dump()
    base["market"]["price"] = -1.0
    with pytest.raises(ValidationError):
        TokenomicsAnalysisRequest(**base)


def test_reject_total_below_circulating():
    base = _lfhv().model_dump()
    base["market"]["total_supply"] = base["market"]["circulating_supply"] / 2.0
    with pytest.raises(ValidationError):
        TokenomicsAnalysisRequest(**base)


def test_reject_invalid_holder_shares():
    base = _lfhv().model_dump()
    base["holder_concentration"]["top_1_holder_share"] = 1.5
    with pytest.raises(ValidationError):
        TokenomicsAnalysisRequest(**base)
    # Ordering violation: top_1 > top_5.
    base = _lfhv().model_dump()
    base["holder_concentration"]["top_1_holder_share"] = 0.5
    base["holder_concentration"]["top_5_holder_share"] = 0.3
    with pytest.raises(ValidationError):
        TokenomicsAnalysisRequest(**base)


def test_reject_non_finite():
    base = _lfhv().model_dump()
    base["market"]["staking_yield"] = float("nan")
    with pytest.raises(ValidationError):
        TokenomicsAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 29. JSON-safety (incl. the zero-burn runway cap)
# --------------------------------------------------------------------------- #
def test_zero_burn_runway_capped_finite():
    base = _lfhv().model_dump()
    base["market"]["monthly_burn_usd"] = 0.0
    req = TokenomicsAnalysisRequest(**base)
    tr = analyze_tokenomics(req).treasury_analysis
    assert math.isfinite(tr.runway_months)
    assert math.isfinite(tr.revenue_adjusted_runway_months)


def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/tokenomics/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
