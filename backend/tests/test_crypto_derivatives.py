"""
Tests for the Crypto Perpetual Futures Funding & Basis Lab (Phase 26.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.crypto_derivatives.models import CryptoDerivativesAnalysisRequest
from app.crypto_derivatives.sample import sample_requests
from app.crypto_derivatives.service import analyze_crypto_derivatives

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


def _btc():
    return sample_requests()[0]


def _analyze(req=None):
    return analyze_crypto_derivatives(req or _btc())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/crypto-derivatives/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    syms = {m["market"]["symbol"] for m in body["markets"]}
    assert syms == {"BTCUSDT_SAMPLE", "ETHUSDT_SAMPLE", "SOLUSDT_SAMPLE", "BTC_QUARTERLY_SAMPLE"}
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/crypto-derivatives/analyze", json=_btc().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "liquidation" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–8. Basis & funding formulas
# --------------------------------------------------------------------------- #
def test_perp_basis_formula():
    req = _btc()
    ba = _analyze(req).basis_analysis
    assert math.isclose(ba.perp_basis, req.market.perp_mark_price - req.market.spot_price, abs_tol=1e-6)


def test_perp_basis_bps_formula():
    req = _btc()
    ba = _analyze(req).basis_analysis
    expected = (req.market.perp_mark_price - req.market.spot_price) / req.market.spot_price * 10000.0
    assert math.isclose(ba.perp_basis_bps, expected, rel_tol=1e-9)


def test_dated_futures_basis_formula():
    req = _btc()
    out = _analyze(req)
    first = out.futures_curve[0]
    f0 = req.dated_futures[0]
    assert math.isclose(first.basis, f0.futures_price - req.market.spot_price, abs_tol=1e-6)
    assert math.isclose(first.basis_bps, (f0.futures_price / req.market.spot_price - 1.0) * 10000.0, rel_tol=1e-9)


def test_annualized_basis_formula():
    req = _btc()
    out = _analyze(req)
    f0 = req.dated_futures[0]
    expected = (f0.futures_price / req.market.spot_price - 1.0) * 365.0 / f0.maturity_days
    assert math.isclose(out.futures_curve[0].annualized_basis, expected, rel_tol=1e-9)


def test_funding_annualized_simple_formula():
    req = _btc()
    fa = _analyze(req).funding_analysis
    assert math.isclose(fa.funding_annualized_simple, req.market.funding_rate_8h * 3 * 365, rel_tol=1e-9)


def test_funding_annualized_compound_finite():
    for req in sample_requests():
        fa = analyze_crypto_derivatives(req).funding_analysis
        assert math.isfinite(fa.funding_annualized_compound)


# --------------------------------------------------------------------------- #
# 9–11. Funding P&L signs
# --------------------------------------------------------------------------- #
def test_positive_funding_long_negative_short_positive():
    out = _analyze()  # BTC has positive funding
    assert out.market_summary.funding_rate_8h > 0
    assert out.funding_analysis.long_funding_pnl_daily < 0
    assert out.funding_analysis.short_funding_pnl_daily > 0


def test_negative_funding_reverses_signs():
    quarterly = sample_requests()[3]  # negative funding
    out = analyze_crypto_derivatives(quarterly)
    assert out.market_summary.funding_rate_8h < 0
    assert out.funding_analysis.long_funding_pnl_daily > 0
    assert out.funding_analysis.short_funding_pnl_daily < 0


# --------------------------------------------------------------------------- #
# 12–17. Position risk / liquidation
# --------------------------------------------------------------------------- #
def test_long_pnl_formula():
    req = _btc()
    pr = _analyze(req).position_risk
    p = req.position
    expected = p.notional * (p.mark_price / p.entry_price - 1.0)
    assert math.isclose(pr.unrealized_pnl, expected, rel_tol=1e-9)


def test_short_pnl_formula():
    quarterly = sample_requests()[3]
    pr = analyze_crypto_derivatives(quarterly).position_risk
    p = quarterly.position
    expected = p.notional * (1.0 - p.mark_price / p.entry_price)
    assert math.isclose(pr.unrealized_pnl, expected, rel_tol=1e-9)


def test_initial_margin_formula():
    req = _btc()
    pr = _analyze(req).position_risk
    assert math.isclose(pr.initial_margin, req.position.notional / req.position.leverage, rel_tol=1e-9)


def test_maintenance_margin_formula():
    req = _btc()
    pr = _analyze(req).position_risk
    assert math.isclose(pr.maintenance_margin, req.position.notional * req.position.maintenance_margin_rate, rel_tol=1e-9)


def test_liquidation_price_and_distance_finite():
    for req in sample_requests():
        pr = analyze_crypto_derivatives(req).position_risk
        assert math.isfinite(pr.liquidation_price_approx) and pr.liquidation_price_approx >= 0.0
        assert math.isfinite(pr.liquidation_distance_bps) and pr.liquidation_distance_bps >= 0.0


def test_long_liquidation_below_short_above_entry():
    btc = _btc()  # long
    pr_long = analyze_crypto_derivatives(btc).position_risk
    assert pr_long.liquidation_price_approx < btc.position.entry_price
    quarterly = sample_requests()[3]  # short
    pr_short = analyze_crypto_derivatives(quarterly).position_risk
    assert pr_short.liquidation_price_approx > quarterly.position.entry_price


# --------------------------------------------------------------------------- #
# 18–23. Regime & scenarios
# --------------------------------------------------------------------------- #
def test_funding_regime_exists():
    reg = _analyze().funding_regime
    assert reg.regime_id and reg.regime_label and reg.explanation
    assert math.isfinite(reg.score)


def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "funding_spike_positive", "funding_turns_negative", "perp_premium_blowout",
        "perp_discount_shock", "spot_selloff", "spot_rally", "basis_convergence",
        "margin_stress", "volatility_shock",
    } == ids


def test_funding_spike_increases_annualized_funding():
    for req in sample_requests():
        out = analyze_crypto_derivatives(req)
        base = _scenario(out, "base")
        assert _scenario(out, "funding_spike_positive").funding_annualized > base.funding_annualized


def test_funding_turns_negative_decreases_annualized_funding():
    for req in sample_requests():
        out = analyze_crypto_derivatives(req)
        base = _scenario(out, "base")
        assert _scenario(out, "funding_turns_negative").funding_annualized < base.funding_annualized


def test_basis_convergence_lowers_absolute_futures_basis():
    for req in sample_requests():
        out = analyze_crypto_derivatives(req)
        base = _scenario(out, "base")
        assert abs(_scenario(out, "basis_convergence").annualized_basis) <= abs(base.annualized_basis) + 1e-9


def test_margin_stress_lowers_liquidation_buffer():
    for req in sample_requests():
        out = analyze_crypto_derivatives(req)
        base = _scenario(out, "base")
        assert _scenario(out, "margin_stress").liquidation_distance_bps < base.liquidation_distance_bps


def test_spot_selloff_hurts_long():
    out = _analyze()  # long
    base = _scenario(out, "base")
    assert _scenario(out, "spot_selloff").position_pnl < base.position_pnl


# --------------------------------------------------------------------------- #
# 24–27. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_spot():
    base = _btc().model_dump()
    base["market"]["spot_price"] = -1.0
    with pytest.raises(ValidationError):
        CryptoDerivativesAnalysisRequest(**base)


def test_reject_non_positive_leverage():
    base = _btc().model_dump()
    base["position"]["leverage"] = 0.0
    with pytest.raises(ValidationError):
        CryptoDerivativesAnalysisRequest(**base)


def test_reject_bad_margin_rates():
    base = _btc().model_dump()
    # initial < maintenance violates the cross-field validator.
    base["position"]["initial_margin_rate"] = 0.02
    base["position"]["maintenance_margin_rate"] = 0.05
    with pytest.raises(ValidationError):
        CryptoDerivativesAnalysisRequest(**base)


def test_reject_margin_rate_above_one():
    base = _btc().model_dump()
    base["position"]["initial_margin_rate"] = 1.5
    with pytest.raises(ValidationError):
        CryptoDerivativesAnalysisRequest(**base)


def test_reject_non_finite():
    base = _btc().model_dump()
    base["market"]["funding_rate_8h"] = float("nan")
    with pytest.raises(ValidationError):
        CryptoDerivativesAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 28. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/crypto-derivatives/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
