"""
Tests for the Volatility Surface & Variance Swap Lab (Phase 24.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.options import black_scholes_price, implied_volatility
from app.volatility.models import VolatilityAnalysisRequest
from app.volatility.sample import sample_request
from app.volatility.service import analyze_volatility

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


def _analyze():
    return analyze_volatility(sample_request())


def _mutate(**under):
    base = sample_request().model_dump()
    base["underlying"].update(under)
    return VolatilityAnalysisRequest(**base)


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/volatility/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert len(body["request"]["option_quotes"]) == 35  # 5 maturities x 7 strikes
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    req = sample_request().model_dump()
    res = client.post("/volatility/analyze", json=req)
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–9. Black-Scholes / implied vol / vega
# --------------------------------------------------------------------------- #
def test_bs_call_and_put_finite():
    c = black_scholes_price("call", 5000, 5000, 0.25, 0.045, 0.18, 0.015)
    p = black_scholes_price("put", 5000, 5000, 0.25, 0.045, 0.18, 0.015)
    assert math.isfinite(c) and c > 0
    assert math.isfinite(p) and p > 0


def test_put_call_parity():
    S, K, T, r, q, sig = 5000, 5000, 0.25, 0.045, 0.015, 0.18
    c = black_scholes_price("call", S, K, T, r, sig, q)
    p = black_scholes_price("put", S, K, T, r, sig, q)
    lhs = c - p
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert math.isclose(lhs, rhs, rel_tol=1e-6, abs_tol=1e-6)


def test_iv_recovers_call_vol():
    S, K, T, r, q, sig = 5000, 5200, 0.5, 0.045, 0.015, 0.22
    price = black_scholes_price("call", S, K, T, r, sig, q)
    iv, conv, _it, _w = implied_volatility("call", price, S, K, T, r, q)
    assert conv and iv is not None and math.isclose(iv, sig, abs_tol=1e-4)


def test_iv_recovers_put_vol():
    S, K, T, r, q, sig = 5000, 4500, 0.5, 0.045, 0.015, 0.25
    price = black_scholes_price("put", S, K, T, r, sig, q)
    iv, conv, _it, _w = implied_volatility("put", price, S, K, T, r, q)
    assert conv and iv is not None and math.isclose(iv, sig, abs_tol=1e-4)


def test_impossible_price_returns_none():
    # A price above the call upper bound (S) is not invertible.
    iv, conv, _it, warning = implied_volatility("call", 1e9, 5000, 5000, 0.5, 0.045, 0.015)
    assert iv is None and not conv and warning


def test_vega_positive():
    out = _analyze()
    atm = min(out.option_quotes, key=lambda a: abs(a.moneyness - 1.0))
    assert atm.vega > 0


# --------------------------------------------------------------------------- #
# 10–14. Smile / skew / term structure / surface / realized vol
# --------------------------------------------------------------------------- #
def test_realized_volatility_finite():
    out = _analyze()
    rv = out.realized_volatility
    assert math.isfinite(rv.realized_vol_annual) and rv.realized_vol_annual > 0
    assert math.isfinite(out.implied_realized_spread.spread)


def test_smile_and_term_and_skew_exist():
    out = _analyze()
    assert len(out.smile_points) > 10
    assert len(out.term_structure) == 5
    assert len(out.skew_metrics) == 5


def test_surface_summary_finite_and_skew_sign():
    out = _analyze()
    s = out.surface_summary
    for v in (s.atm_iv_30d, s.atm_iv_90d, s.atm_iv_1y, s.min_iv, s.max_iv, s.average_iv, s.term_structure_slope):
        assert math.isfinite(v)
    # Equity skew: 90% put IV richer than 110% call IV (downside skew).
    sk = out.skew_metrics[0]
    assert sk.put_90_iv > sk.call_110_iv
    assert sk.skew_slope < 0


# --------------------------------------------------------------------------- #
# 15–17. Variance swap & vega
# --------------------------------------------------------------------------- #
def test_variance_swap_finite_positive():
    out = _analyze()
    vs = out.variance_swap
    assert vs.variance_strike > 0 and vs.volatility_strike > 0
    assert math.isclose(vs.volatility_strike, math.sqrt(vs.variance_strike), rel_tol=1e-9)
    assert len(vs.strip_points) >= 3
    # Sanity: the educational vol strike is in a plausible band around ATM vol.
    assert 0.05 < vs.volatility_strike < 0.60


def test_vega_exposure_finite():
    out = _analyze()
    ve = out.vega_exposure
    assert math.isfinite(ve.total_vega) and ve.total_vega > 0
    assert len(ve.vega_by_maturity) == 5
    assert len(ve.vega_by_moneyness) >= 1


# --------------------------------------------------------------------------- #
# 18–20. Scenarios
# --------------------------------------------------------------------------- #
def test_scenarios_exist():
    out = _analyze()
    ids = {s.id for s in out.scenario_results}
    assert {
        "base", "parallel_vol_up", "parallel_vol_down", "skew_steepening",
        "skew_flattening", "short_dated_vol_spike", "long_dated_vol_repricing",
        "spot_selloff_vol_up",
    } == ids


def test_parallel_vol_up_increases_atm():
    out = _analyze()
    base = _scenario(out, "base")
    up = _scenario(out, "parallel_vol_up")
    assert up.shifted_atm_iv_30d > base.shifted_atm_iv_30d


def test_parallel_vol_down_decreases_atm():
    out = _analyze()
    base = _scenario(out, "base")
    down = _scenario(out, "parallel_vol_down")
    assert down.shifted_atm_iv_30d < base.shifted_atm_iv_30d


# --------------------------------------------------------------------------- #
# 21–25. Validation & JSON-safety
# --------------------------------------------------------------------------- #
def test_reject_negative_spot():
    with pytest.raises(ValidationError):
        _mutate(spot_price=-1.0)


def test_reject_negative_strike():
    base = sample_request().model_dump()
    base["option_quotes"][0]["strike"] = -10.0
    with pytest.raises(ValidationError):
        VolatilityAnalysisRequest(**base)


def test_reject_invalid_maturity():
    base = sample_request().model_dump()
    base["option_quotes"][0]["maturity_days"] = 0
    with pytest.raises(ValidationError):
        VolatilityAnalysisRequest(**base)


def test_reject_non_finite():
    with pytest.raises(ValidationError):
        _mutate(risk_free_rate=float("inf"))


def test_no_nan_or_infinity(client):
    req = sample_request().model_dump()
    req["underlying"]["spot_price"] = 4800.0  # off the generated grid → IV may vary
    res = client.post("/volatility/analyze", json=req)
    assert res.status_code == 200
    _assert_all_finite(res.json())
