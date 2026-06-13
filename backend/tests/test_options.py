"""
Tests for the Options & Volatility Lab v1 (Black–Scholes, Greeks, IV, payoff).

Deterministic known-value checks against textbook Black–Scholes plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.options import (
    black_scholes_greeks,
    black_scholes_price,
    implied_volatility,
    no_arbitrage_bounds,
    normal_cdf,
    strategy_payoff,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# Canonical example: S=100, K=100, T=1, r=0.05, sigma=0.20, q=0.
_S, _K, _T, _R, _SIG, _Q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.0


# ---------------------------------------------------------------------------
# Black–Scholes math
# ---------------------------------------------------------------------------


def test_normal_cdf_known_points():
    assert normal_cdf(0.0) == pytest.approx(0.5)
    assert normal_cdf(-10.0) == pytest.approx(0.0, abs=1e-9)
    assert normal_cdf(10.0) == pytest.approx(1.0, abs=1e-9)


def test_atm_call_price():
    assert black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q) == pytest.approx(10.4506, abs=1e-3)


def test_atm_put_price():
    assert black_scholes_price("put", _S, _K, _T, _R, _SIG, _Q) == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity():
    c = black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q)
    p = black_scholes_price("put", _S, _K, _T, _R, _SIG, _Q)
    # C - P = S e^{-qT} - K e^{-rT}
    expected = _S * math.exp(-_Q * _T) - _K * math.exp(-_R * _T)
    assert (c - p) == pytest.approx(expected, abs=1e-9)


def test_call_delta_in_unit_interval():
    g = black_scholes_greeks("call", _S, _K, _T, _R, _SIG, _Q)
    assert 0.0 < g["delta"] < 1.0
    assert g["delta"] == pytest.approx(0.6368, abs=1e-3)


def test_put_delta_in_negative_unit_interval():
    g = black_scholes_greeks("put", _S, _K, _T, _R, _SIG, _Q)
    assert -1.0 < g["delta"] < 0.0


def test_gamma_and_vega_positive_and_match_spec():
    g = black_scholes_greeks("call", _S, _K, _T, _R, _SIG, _Q)
    assert g["gamma"] > 0
    assert g["vega"] > 0
    assert g["vega"] == pytest.approx(37.524, abs=1e-2)
    assert g["theta_annual"] == pytest.approx(-6.414, abs=1e-2)
    assert g["theta_daily"] == pytest.approx(g["theta_annual"] / 365.0, abs=1e-5)
    assert g["rho"] == pytest.approx(53.232, abs=1e-2)


def test_call_put_gamma_vega_equal():
    cg = black_scholes_greeks("call", _S, _K, _T, _R, _SIG, _Q)
    pg = black_scholes_greeks("put", _S, _K, _T, _R, _SIG, _Q)
    assert cg["gamma"] == pytest.approx(pg["gamma"])
    assert cg["vega"] == pytest.approx(pg["vega"])


# ---------------------------------------------------------------------------
# Implied volatility
# ---------------------------------------------------------------------------


def test_iv_recovers_call_vol():
    price = black_scholes_price("call", _S, _K, _T, _R, 0.20, _Q)
    iv, converged, iters, warning = implied_volatility("call", price, _S, _K, _T, _R, _Q)
    assert converged and warning is None
    assert iv == pytest.approx(0.20, abs=1e-4)
    assert iters > 0


def test_iv_recovers_put_vol():
    price = black_scholes_price("put", _S, _K, _T, _R, 0.35, _Q)
    iv, converged, _i, _w = implied_volatility("put", price, _S, _K, _T, _R, _Q)
    assert converged and iv == pytest.approx(0.35, abs=1e-4)


def test_iv_price_above_bounds_warns_no_crash():
    # A call can never be worth more than S; 200 > 100 violates the upper bound.
    iv, converged, iters, warning = implied_volatility("call", 200.0, _S, _K, _T, _R, _Q)
    assert iv is None and converged is False and iters == 0
    assert warning and "no-arbitrage" in warning


def test_iv_near_intrinsic_is_low_vol():
    # A deep-ITM call priced just above intrinsic implies a low volatility.
    lb, _ub = no_arbitrage_bounds("call", 120.0, 100.0, _T, _R, _Q)
    iv, converged, _i, _w = implied_volatility(
        "call", lb + 0.05, 120.0, 100.0, _T, _R, _Q
    )
    assert converged and iv is not None and iv < 0.15


# ---------------------------------------------------------------------------
# Payoff engine
# ---------------------------------------------------------------------------


def _curve_at(result, price):
    return next(p["payoff"] for p in result["payoff_curve"] if abs(p["underlying_price"] - price) < 1e-6)


def test_long_call_payoff():
    r = strategy_payoff(
        [{"instrument": "option", "option_type": "call", "side": "long", "strike": 100, "premium": 5, "quantity": 1}],
        50, 150, 101,
    )
    assert _curve_at(r, 90) == pytest.approx(-5.0)   # below strike → lose premium
    assert _curve_at(r, 120) == pytest.approx(15.0)  # 20 intrinsic − 5 premium
    assert r["max_loss"] == pytest.approx(-5.0)      # bounded loss
    assert r["max_profit"] is None                   # unbounded upside
    assert r["breakevens"] == [pytest.approx(105.0)]


def test_short_call_is_inverse():
    longc = strategy_payoff(
        [{"instrument": "option", "option_type": "call", "side": "long", "strike": 100, "premium": 5}],
        50, 150, 101,
    )
    shortc = strategy_payoff(
        [{"instrument": "option", "option_type": "call", "side": "short", "strike": 100, "premium": 5}],
        50, 150, 101,
    )
    for lp, sp in zip(longc["payoff_curve"], shortc["payoff_curve"]):
        assert lp["payoff"] == pytest.approx(-sp["payoff"])
    assert shortc["max_profit"] == pytest.approx(5.0) and shortc["max_loss"] is None


def test_long_put_payoff():
    r = strategy_payoff(
        [{"instrument": "option", "option_type": "put", "side": "long", "strike": 100, "premium": 4}],
        50, 150, 101,
    )
    assert _curve_at(r, 80) == pytest.approx(16.0)   # 20 intrinsic − 4 premium
    assert _curve_at(r, 120) == pytest.approx(-4.0)  # above strike → lose premium
    assert r["breakevens"] == [pytest.approx(96.0)]


def test_bull_call_spread_bounded_both_sides():
    r = strategy_payoff(
        [
            {"instrument": "option", "option_type": "call", "side": "long", "strike": 100, "premium": 5},
            {"instrument": "option", "option_type": "call", "side": "short", "strike": 110, "premium": 2},
        ],
        50, 160, 111,
    )
    assert r["max_loss"] == pytest.approx(-3.0)   # net debit
    assert r["max_profit"] == pytest.approx(7.0)  # spread width 10 − debit 3
    assert all(math.isfinite(p["payoff"]) for p in r["payoff_curve"])


def test_long_straddle_v_shape_no_nan():
    r = strategy_payoff(
        [
            {"instrument": "option", "option_type": "call", "side": "long", "strike": 100, "premium": 6},
            {"instrument": "option", "option_type": "put", "side": "long", "strike": 100, "premium": 6},
        ],
        50, 150, 101,
    )
    assert _curve_at(r, 100) == pytest.approx(-12.0)  # both premiums lost at the strike
    assert r["max_profit"] is None and r["max_loss"] == pytest.approx(-12.0)
    assert all(math.isfinite(p["payoff"]) for p in r["payoff_curve"])
    assert len(r["breakevens"]) == 2


def test_covered_call_uses_stock_leg():
    r = strategy_payoff(
        [
            {"instrument": "stock", "side": "long", "entry_price": 100, "quantity": 1},
            {"instrument": "option", "option_type": "call", "side": "short", "strike": 110, "premium": 3},
        ],
        50, 160, 111,
    )
    # Capped upside above the short strike: (110-100) stock gain + 3 premium = 13.
    assert r["max_profit"] == pytest.approx(13.0)
    assert all(math.isfinite(p["payoff"]) for p in r["payoff_curve"])


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_black_scholes(client):
    body = client.post(
        "/options/black-scholes",
        json={"option_type": "call", "underlying_price": 100, "strike": 100,
              "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20},
    ).json()
    assert body["price"] == pytest.approx(10.4506, abs=1e-3)
    assert 0 < body["delta"] < 1
    for k in ("gamma", "vega", "theta_annual", "theta_daily", "rho", "d1", "d2"):
        assert math.isfinite(body[k])


def test_api_implied_vol(client):
    body = client.post(
        "/options/implied-volatility",
        json={"option_type": "call", "market_price": 10.4506, "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05},
    ).json()
    assert body["converged"] is True
    assert body["implied_volatility"] == pytest.approx(0.20, abs=1e-4)


def test_api_implied_vol_out_of_bounds(client):
    body = client.post(
        "/options/implied-volatility",
        json={"option_type": "call", "market_price": 200, "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05},
    ).json()
    assert body["converged"] is False and body["implied_volatility"] is None
    assert body["warning"]


def test_api_payoff(client):
    body = client.post(
        "/options/payoff",
        json={"legs": [{"instrument": "option", "option_type": "call", "side": "long",
                        "strike": 100, "premium": 5, "quantity": 1}],
              "price_min": 50, "price_max": 150, "points": 101},
    ).json()
    assert body["max_loss"] == pytest.approx(-5.0)
    assert body["max_profit"] is None
    assert len(body["payoff_curve"]) == 101


@pytest.mark.parametrize(
    "payload",
    [
        {"option_type": "call", "underlying_price": -1, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.2},
        {"option_type": "call", "underlying_price": 100, "strike": 100, "time_to_expiry": 0, "risk_free_rate": 0.05, "volatility": 0.2},
        {"option_type": "call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": -0.2},
        {"option_type": "swaption", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.2},
    ],
)
def test_api_black_scholes_validation(client, payload):
    assert client.post("/options/black-scholes", json=payload).status_code == 422


def test_api_payoff_validation(client):
    # option leg without a strike
    resp = client.post(
        "/options/payoff",
        json={"legs": [{"instrument": "option", "option_type": "call", "side": "long", "premium": 5}],
              "price_min": 50, "price_max": 150, "points": 101},
    )
    assert resp.status_code == 422
    # price_min >= price_max
    resp2 = client.post(
        "/options/payoff",
        json={"legs": [{"instrument": "option", "option_type": "call", "side": "long", "strike": 100, "premium": 5}],
              "price_min": 150, "price_max": 50, "points": 101},
    )
    assert resp2.status_code == 422
