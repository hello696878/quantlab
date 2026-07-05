"""
Tests for the On-Chain Flow, Exchange Reserve & Whale Concentration Lab (29.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.onchain_analytics.models import OnChainAnalysisRequest
from app.onchain_analytics.sample import sample_requests
from app.onchain_analytics.service import analyze_onchain

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


def _flow():
    return sample_requests()[4]  # Exchange Inflow Stress sample


def _analyze(req=None):
    return analyze_onchain(req or _flow())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/onchain-analytics/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    syms = {n["network"]["symbol"] for n in body["networks"]}
    assert syms == {
        "BTC_ONCHAIN_SAMPLE", "ETH_ONCHAIN_SAMPLE", "L1_RESERVE_SAMPLE",
        "DEFI_WHALE_SAMPLE", "FLOW_SAMPLE",
    }
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/onchain-analytics/analyze", json=_flow().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "whale" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–11. Flow / activity / valuation formulas
# --------------------------------------------------------------------------- #
def test_market_cap_formula():
    req = _flow()
    vm = _analyze(req).valuation_metrics
    assert math.isclose(vm.market_cap, req.network.token_price * req.network.circulating_supply, rel_tol=1e-12)


def test_net_exchange_flow_formula():
    req = _flow()
    ef = _analyze(req).exchange_flow
    expected = req.network.exchange_inflow_tokens_24h - req.network.exchange_outflow_tokens_24h
    assert math.isclose(ef.net_exchange_flow_tokens, expected, rel_tol=1e-12)
    # Spec example: 18M − 9M = +9M.
    assert math.isclose(ef.net_exchange_flow_tokens, 9_000_000.0, rel_tol=1e-9)


def test_net_flow_pct_circulating_formula():
    req = _flow()
    ef = _analyze(req).exchange_flow
    assert math.isclose(
        ef.net_exchange_flow_pct_circulating,
        ef.net_exchange_flow_tokens / req.network.circulating_supply,
        rel_tol=1e-12,
    )


def test_exchange_reserve_ratio_formula():
    req = _flow()
    ef = _analyze(req).exchange_flow
    assert math.isclose(
        ef.exchange_reserve_ratio,
        req.network.exchange_reserve_tokens / req.network.circulating_supply,
        rel_tol=1e-12,
    )


def test_reserve_change_formula():
    ef = _analyze().exchange_flow
    assert math.isclose(ef.reserve_change_tokens, ef.net_exchange_flow_tokens, rel_tol=1e-12)


def test_transfer_value_formula():
    req = _flow()
    am = _analyze(req).activity_metrics
    assert math.isclose(
        am.transfer_volume_value_24h,
        req.network.token_price * req.network.transfer_volume_tokens_24h,
        rel_tol=1e-12,
    )


def test_token_velocity_formula():
    req = _flow()
    am = _analyze(req).activity_metrics
    assert math.isclose(
        am.token_velocity,
        req.network.transfer_volume_tokens_24h / req.network.circulating_supply,
        rel_tol=1e-12,
    )


def test_nvt_ratio_formula():
    req = _flow()
    out = _analyze(req)
    expected = out.valuation_metrics.market_cap / out.activity_metrics.transfer_volume_value_24h
    assert math.isclose(out.valuation_metrics.nvt_ratio, expected, rel_tol=1e-9)


def test_average_transaction_value_formula():
    req = _flow()
    am = _analyze(req).activity_metrics
    expected = req.network.transfer_volume_tokens_24h / req.network.transaction_count_24h
    assert math.isclose(am.average_transaction_value_tokens, expected, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 12–16. Whale / holder / concentration
# --------------------------------------------------------------------------- #
def test_whale_net_flow_formula():
    req = _flow()
    wa = _analyze(req).whale_analysis
    expected = req.whale_flow.whale_inflow_tokens_24h - req.whale_flow.whale_outflow_tokens_24h
    assert math.isclose(wa.whale_net_flow_tokens, expected, rel_tol=1e-12)


def test_whale_net_flow_pct_formula():
    req = _flow()
    wa = _analyze(req).whale_analysis
    assert math.isclose(
        wa.whale_net_flow_pct_circulating,
        wa.whale_net_flow_tokens / req.network.circulating_supply,
        rel_tol=1e-12,
    )


def test_holder_balance_shares_sum_to_one():
    # All five samples' cohorts are built to cover the circulating supply.
    for req in sample_requests():
        rows = analyze_onchain(req).holder_distribution
        assert math.isclose(sum(r.balance_share for r in rows), 1.0, abs_tol=1e-9)


def test_concentration_score_finite_bounded():
    for req in sample_requests():
        ca = analyze_onchain(req).concentration_analysis
        assert math.isfinite(ca.concentration_score)
        assert 0.0 <= ca.concentration_score <= 1.0


def test_gini_style_score_finite_bounded():
    for req in sample_requests():
        ca = analyze_onchain(req).concentration_analysis
        assert math.isfinite(ca.gini_style_score)
        assert 0.0 <= ca.gini_style_score <= 1.0


# --------------------------------------------------------------------------- #
# 17–24. Regime & scenarios
# --------------------------------------------------------------------------- #
def test_risk_regime_exists():
    for req in sample_requests():
        reg = analyze_onchain(req).risk_regime
        assert reg.regime_id and reg.regime_label and reg.explanation
        assert math.isfinite(reg.score) and 0.0 <= reg.score <= 1.0


def test_regime_variety_across_samples():
    regimes = [analyze_onchain(req).risk_regime.regime_id for req in sample_requests()]
    assert regimes == [
        "balanced_activity", "high_velocity_activity", "exchange_outflow_accumulation",
        "whale_concentration_risk", "exchange_inflow_pressure",
    ]


def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "exchange_inflow_spike", "exchange_outflow_wave", "whale_deposit_pressure",
        "whale_accumulation", "active_address_slowdown", "transfer_volume_collapse",
        "high_velocity_burst", "holder_concentration_shock", "severe_combo",
    } == ids


def test_inflow_spike_increases_net_flow():
    for req in sample_requests():
        out = analyze_onchain(req)
        assert _scenario(out, "exchange_inflow_spike").net_exchange_flow_tokens > _scenario(out, "base").net_exchange_flow_tokens


def test_outflow_wave_lowers_net_flow():
    for req in sample_requests():
        out = analyze_onchain(req)
        assert _scenario(out, "exchange_outflow_wave").net_exchange_flow_tokens < _scenario(out, "base").net_exchange_flow_tokens


def test_whale_deposit_pressure_increases_whale_net_flow():
    for req in sample_requests():
        out = analyze_onchain(req)
        base = _scenario(out, "base")
        assert _scenario(out, "whale_deposit_pressure").whale_net_flow_tokens > base.whale_net_flow_tokens
        assert _scenario(out, "whale_accumulation").whale_net_flow_tokens < base.whale_net_flow_tokens


def test_transfer_collapse_raises_nvt():
    for req in sample_requests():
        out = analyze_onchain(req)
        assert _scenario(out, "transfer_volume_collapse").nvt_ratio > _scenario(out, "base").nvt_ratio


def test_velocity_burst_raises_velocity():
    for req in sample_requests():
        out = analyze_onchain(req)
        assert _scenario(out, "high_velocity_burst").token_velocity > _scenario(out, "base").token_velocity


def test_concentration_shock_raises_score():
    for req in sample_requests():
        out = analyze_onchain(req)
        assert _scenario(out, "holder_concentration_shock").concentration_score > _scenario(out, "base").concentration_score


def test_severe_combo_regime():
    out = analyze_onchain(sample_requests()[3])  # DeFi whale sample → 3 triggers
    assert _scenario(out, "severe_combo").regime_label == "Severe on-chain stress"


# --------------------------------------------------------------------------- #
# 25–28. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_token_price():
    base = _flow().model_dump()
    base["network"]["token_price"] = -1.0
    with pytest.raises(ValidationError):
        OnChainAnalysisRequest(**base)


def test_reject_negative_circulating_supply():
    base = _flow().model_dump()
    base["network"]["circulating_supply"] = -100.0
    with pytest.raises(ValidationError):
        OnChainAnalysisRequest(**base)


def test_reject_invalid_concentration_shares():
    base = _flow().model_dump()
    base["whale_flow"]["top_10_holder_share"] = 1.5
    with pytest.raises(ValidationError):
        OnChainAnalysisRequest(**base)
    # Ordering violation: top_10 > top_50.
    base = _flow().model_dump()
    base["whale_flow"]["top_10_holder_share"] = 0.6
    base["whale_flow"]["top_50_holder_share"] = 0.4
    with pytest.raises(ValidationError):
        OnChainAnalysisRequest(**base)


def test_reject_non_finite():
    base = _flow().model_dump()
    base["network"]["transfer_volume_tokens_24h"] = float("inf")
    with pytest.raises(ValidationError):
        OnChainAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 29. JSON-safety (incl. the zero-transfer NVT cap)
# --------------------------------------------------------------------------- #
def test_zero_transfer_volume_nvt_capped_finite():
    base = _flow().model_dump()
    base["network"]["transfer_volume_tokens_24h"] = 0.0
    base["network"]["transaction_count_24h"] = 0.0
    req = OnChainAnalysisRequest(**base)
    out = analyze_onchain(req)
    assert math.isfinite(out.valuation_metrics.nvt_ratio)
    assert math.isfinite(out.activity_metrics.average_transaction_value_tokens)


def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/onchain-analytics/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
