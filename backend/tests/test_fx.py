"""
Tests for the FX Lab v1 (forward / IRP, carry, PPP, exposure, Garman-Kohlhagen).

Deterministic, pure-math tests against textbook values plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.fx import (
    FxInputError,
    compute_currency_exposure,
    compute_fx_carry,
    compute_fx_forward,
    compute_ppp_deviation,
    price_garman_kohlhagen,
)

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
        assert math.isfinite(obj)


# ---------------------------------------------------------------------------
# Forward / interest rate parity (1, 2, 3, 4)
# ---------------------------------------------------------------------------


def test_continuous_forward_formula():
    r = compute_fx_forward(150, 0.01, 0.05, 1, "continuous")
    assert r["forward_rate"] == pytest.approx(150 * math.exp(-0.04), abs=1e-4)
    assert r["forward_rate"] == pytest.approx(144.1184, abs=1e-3)


def test_annual_forward_formula():
    r = compute_fx_forward(150, 0.01, 0.05, 1, "annual")
    assert r["forward_rate"] == pytest.approx(150 * (1.01 / 1.05) ** 1, abs=1e-6)


def test_forward_points_equal_forward_minus_spot():
    r = compute_fx_forward(150, 0.01, 0.05, 1, "continuous")
    assert r["forward_points"] == pytest.approx(r["forward_rate"] - r["spot_rate"], abs=1e-6)


def test_forward_rate_differential():
    r = compute_fx_forward(150, 0.01, 0.05, 1, "continuous")
    assert r["rate_differential"] == pytest.approx(-0.04, abs=1e-9)
    # r_d < r_f -> forward discount (forward < spot)
    assert r["forward_rate"] < r["spot_rate"]


# ---------------------------------------------------------------------------
# Carry (5)
# ---------------------------------------------------------------------------


def test_carry_long_foreign_simple_case():
    r = compute_fx_carry(150, 0.01, 0.05, 150, 1, 1_000_000, "long_foreign")
    # long foreign: earn r_f, pay r_d -> +0.04; expected spot == spot -> no FX move
    assert r["interest_differential"] == pytest.approx(0.04, abs=1e-9)
    assert r["expected_fx_return"] == pytest.approx(0.0, abs=1e-9)
    assert r["total_expected_return"] == pytest.approx(0.04, abs=1e-9)
    assert r["pnl_estimate"] == pytest.approx(40_000.0, abs=1e-3)


def test_carry_direction_flips_sign():
    lf = compute_fx_carry(150, 0.01, 0.05, 155, 1, 1_000_000, "long_foreign")
    ld = compute_fx_carry(150, 0.01, 0.05, 155, 1, 1_000_000, "long_domestic")
    assert lf["interest_differential"] == pytest.approx(-ld["interest_differential"], abs=1e-9)
    assert lf["expected_fx_return"] == pytest.approx(-ld["expected_fx_return"], abs=1e-9)


def test_carry_is_not_free_money_warning():
    r = compute_fx_carry(150, 0.01, 0.05, 150, 1, 1_000_000, "long_foreign")
    assert any("not free money" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# PPP (6, 7)
# ---------------------------------------------------------------------------


def test_ppp_implied_spot_formula():
    r = compute_ppp_deviation(150, 120, 110, 105)
    assert r["ppp_implied_spot"] == pytest.approx(120 * (110 / 105), abs=1e-6)


def test_ppp_deviation_formula():
    r = compute_ppp_deviation(150, 120, 110, 105)
    implied = 120 * (110 / 105)
    assert r["deviation"] == pytest.approx((150 - implied) / implied, abs=1e-6)
    assert "overvalued" in r["valuation"]


def test_ppp_near_fair_value_label():
    implied = 120 * (110 / 105)
    r = compute_ppp_deviation(implied, 120, 110, 105)
    assert "fair value" in r["valuation"]


# ---------------------------------------------------------------------------
# Currency exposure (8, 9)
# ---------------------------------------------------------------------------


_EXPOSURES = [
    {"currency": "USD", "amount": 100_000, "spot_to_base": 1.0},
    {"currency": "JPY", "amount": 1_000_000, "spot_to_base": 0.0067},
    {"currency": "EUR", "amount": 50_000, "spot_to_base": 1.08},
]


def test_exposure_total_base_value():
    r = compute_currency_exposure(_EXPOSURES, "USD", 0.1)
    assert r["total_exposure"] == pytest.approx(100_000 + 6_700 + 54_000, abs=1e-3)
    assert r["gross_exposure"] == pytest.approx(100_000 + 6_700 + 54_000, abs=1e-3)


def test_exposure_stress_pnl():
    r = compute_currency_exposure(_EXPOSURES, "USD", 0.1)
    # Base USD has no FX risk; non-base base-value = 6700 + 54000 = 60700; 10% = 6070.
    assert r["stress_pnl_up"] == pytest.approx(6_070.0, abs=1e-3)
    assert r["stress_pnl_down"] == pytest.approx(-6_070.0, abs=1e-3)
    usd = next(row for row in r["rows"] if row["currency"] == "USD")
    assert usd["stress_pnl_up"] == 0.0
    assert usd["stress_pnl_down"] == 0.0


def test_exposure_weights_sum_to_one():
    r = compute_currency_exposure(_EXPOSURES, "USD", 0.1)
    assert sum(row["weight_pct"] for row in r["rows"]) == pytest.approx(1.0, abs=1e-6)
    assert sum(row["gross_weight_pct"] for row in r["rows"]) == pytest.approx(1.0, abs=1e-6)


def test_exposure_near_zero_net_suppresses_net_weights():
    r = compute_currency_exposure(
        [
            {"currency": "EUR", "amount": 100.0, "spot_to_base": 1.2},
            {"currency": "JPY", "amount": -120.0, "spot_to_base": 1.0},
        ],
        "USD",
        0.1,
    )
    assert r["total_exposure"] == pytest.approx(0.0, abs=1e-9)
    assert r["gross_exposure"] == pytest.approx(240.0, abs=1e-9)
    assert [row["weight_pct"] for row in r["rows"]] == [0.0, 0.0]
    assert sum(row["gross_weight_pct"] for row in r["rows"]) == pytest.approx(1.0, abs=1e-9)
    assert any("Net exposure is near zero" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# Garman-Kohlhagen (10, 11, 12, 13, 14, 15)
# ---------------------------------------------------------------------------


def test_gk_call_price_finite():
    r = price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    assert math.isfinite(r["price"]) and r["price"] > 0


def test_gk_put_price_finite():
    r = price_garman_kohlhagen("put", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    assert math.isfinite(r["price"]) and r["price"] > 0


def test_gk_put_call_parity():
    S, K, r_d, r_f, sig, T = 1.10, 1.05, 0.04, 0.02, 0.12, 1.0
    c = price_garman_kohlhagen("call", S, K, r_d, r_f, sig, T)["price"]
    p = price_garman_kohlhagen("put", S, K, r_d, r_f, sig, T)["price"]
    rhs = S * math.exp(-r_f * T) - K * math.exp(-r_d * T)
    assert (c - p) == pytest.approx(rhs, abs=1e-4)


def test_gk_delta_finite():
    c = price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    p = price_garman_kohlhagen("put", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    assert math.isfinite(c["delta"]) and c["delta"] > 0
    assert math.isfinite(p["delta"]) and p["delta"] < 0


def test_gk_gamma_finite_positive():
    r = price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    assert math.isfinite(r["gamma"]) and r["gamma"] > 0


def test_gk_vega_finite_positive():
    r = price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 1)
    assert math.isfinite(r["vega"]) and r["vega"] > 0


def test_gk_matches_black_scholes_with_foreign_as_dividend():
    from app.options import black_scholes_price

    gk = price_garman_kohlhagen("call", 1.10, 1.05, 0.04, 0.02, 0.12, 1)["price"]
    bs = black_scholes_price("call", 1.10, 1.05, 1, 0.04, 0.12, q=0.02)
    assert gk == pytest.approx(bs, abs=1e-6)


# ---------------------------------------------------------------------------
# Validation (16, 17, 18, 19)
# ---------------------------------------------------------------------------


def test_invalid_spot_rejected():
    with pytest.raises(FxInputError):
        compute_fx_forward(-1, 0.01, 0.05, 1, "continuous")
    with pytest.raises(FxInputError):
        price_garman_kohlhagen("call", -1, 1.10, 0.04, 0.02, 0.12, 1)


def test_invalid_volatility_rejected():
    with pytest.raises(FxInputError):
        price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.0, 1)


def test_invalid_time_rejected():
    with pytest.raises(FxInputError):
        price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 0)
    with pytest.raises(FxInputError):
        compute_fx_forward(150, 0.01, 0.05, -1, "continuous")


def test_invalid_option_type_rejected():
    with pytest.raises(FxInputError):
        price_garman_kohlhagen("straddle", 1.10, 1.10, 0.04, 0.02, 0.12, 1)


def test_invalid_compounding_rejected():
    with pytest.raises(FxInputError):
        compute_fx_forward(150, 0.01, 0.05, 1, "monthly")


def test_ppp_invalid_index_rejected():
    with pytest.raises(FxInputError):
        compute_ppp_deviation(150, 120, -1, 105)


def test_exposure_invalid_spot_rejected():
    with pytest.raises(FxInputError):
        compute_currency_exposure([{"currency": "USD", "amount": 100, "spot_to_base": -1}], "USD", 0.1)


def test_carry_non_finite_output_rejected():
    with pytest.raises(FxInputError):
        compute_fx_carry(1e-300, 0.01, 0.05, 1e12, 1, 1_000_000, "long_foreign")


def test_ppp_non_finite_deviation_rejected():
    with pytest.raises(FxInputError):
        compute_ppp_deviation(1e12, 1e-300, 100, 100)


# ---------------------------------------------------------------------------
# No NaN / Infinity (20)
# ---------------------------------------------------------------------------


def test_no_nan_in_results():
    _assert_all_finite(compute_fx_forward(150, 0.01, 0.05, 1, "continuous"))
    _assert_all_finite(compute_fx_carry(150, 0.01, 0.05, 155, 1, 1_000_000, "long_foreign"))
    _assert_all_finite(compute_ppp_deviation(150, 120, 110, 105))
    _assert_all_finite(compute_currency_exposure(_EXPOSURES, "USD", 0.1))
    _assert_all_finite(price_garman_kohlhagen("call", 1.10, 1.10, 0.04, 0.02, 0.12, 1))


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_fx_forward(client):
    body = client.post(
        "/fx/forward",
        json={"spot_rate": 150, "domestic_rate": 0.01, "foreign_rate": 0.05,
              "time_to_maturity": 1, "compounding": "continuous"},
    ).json()
    assert body["forward_rate"] < body["spot_rate"]


def test_api_fx_carry(client):
    body = client.post(
        "/fx/carry",
        json={"spot_rate": 150, "domestic_rate": 0.01, "foreign_rate": 0.05,
              "expected_spot": 150, "horizon_years": 1, "notional": 1_000_000, "direction": "long_foreign"},
    ).json()
    assert body["pnl_estimate"] == pytest.approx(40_000.0, abs=1e-3)


def test_api_fx_ppp(client):
    body = client.post(
        "/fx/ppp",
        json={"current_spot": 150, "base_spot": 120, "domestic_price_index": 110, "foreign_price_index": 105},
    ).json()
    assert body["ppp_implied_spot"] == pytest.approx(125.714286, abs=1e-3)


def test_api_fx_exposure(client):
    body = client.post(
        "/fx/exposure",
        json={"exposures": _EXPOSURES, "base_currency": "USD", "shock_pct": 0.1},
    ).json()
    assert body["stress_pnl_up"] == pytest.approx(6_070.0, abs=1e-3)
    assert body["gross_exposure"] == pytest.approx(160_700.0, abs=1e-3)


def test_api_fx_option(client):
    body = client.post(
        "/fx/option",
        json={"option_type": "call", "spot_rate": 1.10, "strike": 1.10,
              "domestic_rate": 0.04, "foreign_rate": 0.02, "volatility": 0.12, "time_to_expiry": 1},
    ).json()
    assert body["price"] > 0 and body["gamma"] > 0 and body["vega"] > 0


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/fx/forward", {"spot_rate": -1, "domestic_rate": 0.01, "foreign_rate": 0.05, "time_to_maturity": 1, "compounding": "continuous"}),
        ("/fx/option", {"option_type": "call", "spot_rate": 1.1, "strike": 1.1, "domestic_rate": 0.04, "foreign_rate": 0.02, "volatility": 0.0, "time_to_expiry": 1}),
        ("/fx/option", {"option_type": "straddle", "spot_rate": 1.1, "strike": 1.1, "domestic_rate": 0.04, "foreign_rate": 0.02, "volatility": 0.12, "time_to_expiry": 1}),
        ("/fx/ppp", {"current_spot": 150, "base_spot": 120, "domestic_price_index": -1, "foreign_price_index": 105}),
        ("/fx/exposure", {"exposures": [], "base_currency": "USD", "shock_pct": 0.1}),
    ],
)
def test_api_fx_validation_422(client, path, payload):
    assert client.post(path, json=payload).status_code == 422
