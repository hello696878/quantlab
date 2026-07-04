"""
Tests for the DeFi Yield, Stablecoin Peg & Lending Risk Lab (Phase 27.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.defi_risk.models import DeFiRiskAnalysisRequest
from app.defi_risk.sample import sample_requests
from app.defi_risk.service import analyze_defi_risk, kinked_borrow_rate, supply_rate

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


def _eth():
    return sample_requests()[3]  # ETH collateral borrowing sample


def _analyze(req=None):
    return analyze_defi_risk(req or _eth())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/defi-risk/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = {s["sample_id"] for s in body["samples"]}
    assert ids == {
        "USDC_LENDING_SAMPLE", "USDT_PEG_STRESS_SAMPLE", "DAI_CDP_SAMPLE",
        "ETH_COLLATERAL_SAMPLE", "WBTC_STRESS_SAMPLE",
    }
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/defi-risk/analyze", json=_eth().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "liquidation" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–8. Peg / utilization / rate-model formulas
# --------------------------------------------------------------------------- #
def test_peg_deviation_formula():
    req = _eth()
    peg = _analyze(req).stablecoin_peg
    expected = (req.stablecoin.market_price - req.stablecoin.target_peg) / req.stablecoin.target_peg
    assert math.isclose(peg.peg_deviation, expected, abs_tol=1e-12)


def test_peg_deviation_bps_formula():
    req = _eth()
    peg = _analyze(req).stablecoin_peg
    assert math.isclose(peg.peg_deviation_bps, peg.peg_deviation * 10000.0, abs_tol=1e-9)


def test_utilization_formula():
    req = _eth()
    ua = _analyze(req).utilization_analysis
    assert math.isclose(ua.utilization, req.market.total_borrowed / req.market.total_supplied, rel_tol=1e-12)


def test_kinked_rate_below_kink():
    # U ≤ U*: r = r0 + (U/U*)·s1
    r = kinked_borrow_rate(0.40, 0.01, 0.04, 0.60, 0.80)
    assert math.isclose(r, 0.01 + (0.40 / 0.80) * 0.04, rel_tol=1e-12)


def test_kinked_rate_above_kink():
    # U > U*: r = r0 + s1 + ((U−U*)/(1−U*))·s2
    r = kinked_borrow_rate(0.90, 0.01, 0.04, 0.60, 0.80)
    assert math.isclose(r, 0.01 + 0.04 + ((0.90 - 0.80) / 0.20) * 0.60, rel_tol=1e-12)


def test_supply_rate_formula():
    rb = kinked_borrow_rate(0.65, 0.01, 0.04, 0.60, 0.80)
    rs = supply_rate(rb, 0.65, 0.10)
    assert math.isclose(rs, rb * 0.65 * 0.90, rel_tol=1e-12)
    # And the analyze pipeline agrees.
    req = _eth()
    irm = _analyze(req).interest_rate_model
    u = req.market.total_borrowed / req.market.total_supplied
    assert math.isclose(irm.supply_apy_model, irm.borrow_apy_model * u * (1.0 - req.market.reserve_factor), rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 9–15. Collateral risk / net APY formulas
# --------------------------------------------------------------------------- #
def test_collateral_value_formula():
    req = _eth()
    cr = _analyze(req).collateral_risk
    assert math.isclose(cr.collateral_value, req.position.collateral_amount * req.position.collateral_price, rel_tol=1e-12)


def test_debt_value_formula():
    req = _eth()
    cr = _analyze(req).collateral_risk
    assert math.isclose(cr.debt_value, req.position.debt_amount * req.position.debt_price, rel_tol=1e-12)


def test_ltv_formula():
    req = _eth()
    cr = _analyze(req).collateral_risk
    assert math.isclose(cr.loan_to_value, cr.debt_value / cr.collateral_value, rel_tol=1e-12)


def test_health_factor_formula():
    req = _eth()
    cr = _analyze(req).collateral_risk
    expected = cr.collateral_value * req.position.liquidation_threshold / cr.debt_value
    assert math.isclose(cr.health_factor, expected, rel_tol=1e-9)
    # Spec example: 10 ETH @ 3500, 18000 USDC debt, θ = 0.80 → HF ≈ 1.5556.
    assert math.isclose(cr.health_factor, 35000.0 * 0.80 / 18000.0, rel_tol=1e-9)


def test_liquidation_price_formula_and_finite():
    req = _eth()
    cr = _analyze(req).collateral_risk
    expected = cr.debt_value / (req.position.collateral_amount * req.position.liquidation_threshold)
    assert math.isfinite(cr.liquidation_price_approx)
    assert math.isclose(cr.liquidation_price_approx, expected, rel_tol=1e-9)
    # Below the current collateral price for a solvent position.
    assert cr.liquidation_price_approx < req.position.collateral_price


def test_liquidation_distance_finite():
    for req in sample_requests():
        cr = analyze_defi_risk(req).collateral_risk
        assert math.isfinite(cr.liquidation_distance_bps)


def test_net_apy_formula():
    req = _eth()
    na = _analyze(req).net_apy_analysis
    assert math.isclose(na.net_apy, req.position.supply_apy - req.position.borrow_apy - req.fees_apy, abs_tol=1e-12)


# --------------------------------------------------------------------------- #
# 16–22. Regime & scenarios
# --------------------------------------------------------------------------- #
def test_risk_regime_exists():
    for req in sample_requests():
        reg = analyze_defi_risk(req).risk_regime
        assert reg.regime_id and reg.regime_label and reg.explanation
        assert math.isfinite(reg.score) and 0.0 <= reg.score <= 1.0


def test_regime_variety_across_samples():
    regimes = {analyze_defi_risk(req).risk_regime.regime_id for req in sample_requests()}
    assert {"healthy", "peg_stress", "elevated_utilization", "liquidation_watch"} <= regimes


def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "stable_mild_depeg", "stable_severe_depeg", "collateral_drawdown",
        "borrow_asset_rally", "utilization_spike", "liquidity_drought",
        "borrow_rate_shock", "liquidation_threshold_cut", "protocol_stress_combo",
    } == ids


def test_depeg_increases_peg_deviation():
    for req in sample_requests():
        out = analyze_defi_risk(req)
        base = _scenario(out, "base")
        assert abs(_scenario(out, "stable_mild_depeg").peg_deviation_bps) > abs(base.peg_deviation_bps)
        assert abs(_scenario(out, "stable_severe_depeg").peg_deviation_bps) > abs(_scenario(out, "stable_mild_depeg").peg_deviation_bps)


def test_collateral_drawdown_lowers_health_factor():
    for req in sample_requests():
        out = analyze_defi_risk(req)
        assert _scenario(out, "collateral_drawdown").health_factor < _scenario(out, "base").health_factor


def test_borrow_rally_lowers_health_factor():
    for req in sample_requests():
        out = analyze_defi_risk(req)
        assert _scenario(out, "borrow_asset_rally").health_factor < _scenario(out, "base").health_factor


def test_utilization_spike_raises_borrow_apy():
    for req in sample_requests():
        out = analyze_defi_risk(req)
        assert _scenario(out, "utilization_spike").borrow_apy > _scenario(out, "base").borrow_apy


def test_threshold_cut_lowers_health_factor():
    for req in sample_requests():
        out = analyze_defi_risk(req)
        assert _scenario(out, "liquidation_threshold_cut").health_factor < _scenario(out, "base").health_factor


# --------------------------------------------------------------------------- #
# 23–27. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_peg_price():
    base = _eth().model_dump()
    base["stablecoin"]["market_price"] = -1.0
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)


def test_reject_negative_collateral_price():
    base = _eth().model_dump()
    base["position"]["collateral_price"] = -100.0
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)


def test_reject_invalid_liquidation_threshold():
    base = _eth().model_dump()
    base["position"]["liquidation_threshold"] = 1.5
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)
    # And threshold below the collateral factor violates the cross-field check.
    base["position"]["liquidation_threshold"] = 0.5
    base["position"]["collateral_factor"] = 0.75
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)


def test_reject_invalid_utilization_inputs():
    base = _eth().model_dump()
    base["market"]["total_borrowed"] = base["market"]["total_supplied"] + 1.0
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)
    base = _eth().model_dump()
    base["market"]["kink_utilization"] = 1.5
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)


def test_reject_non_finite():
    base = _eth().model_dump()
    base["position"]["borrow_apy"] = float("inf")
    with pytest.raises(ValidationError):
        DeFiRiskAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 28. JSON-safety (incl. the zero-debt health-factor cap)
# --------------------------------------------------------------------------- #
def test_zero_debt_health_factor_capped_finite():
    base = _eth().model_dump()
    base["position"]["debt_amount"] = 0.0
    req = DeFiRiskAnalysisRequest(**base)
    cr = analyze_defi_risk(req).collateral_risk
    assert math.isfinite(cr.health_factor)
    assert cr.liquidation_price_approx == 0.0


def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/defi-risk/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
