"""
Tests for the Credit Risk Lab v1 (Merton / hazard / CDS / risky bond).

Deterministic, pure-math tests against textbook relationships plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.credit import (
    CreditInputError,
    compute_cds_spread,
    compute_credit_spread_from_prices,
    compute_distance_to_default,
    compute_hazard_survival_curve,
    compute_merton_default_probability,
    compute_simple_cds_spread,
    price_merton_credit,
    price_risky_bond,
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
# Merton structural model (1, 2, 3, 4, 5, 6)
# ---------------------------------------------------------------------------


def test_merton_equity_value_positive():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    assert r["equity_value"] is not None and r["equity_value"] > 0


def test_merton_debt_value_positive():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    assert r["debt_value"] is not None and r["debt_value"] > 0
    # Accounting identity: equity + debt == asset value.
    assert r["equity_value"] + r["debt_value"] == pytest.approx(120, abs=1e-4)


def test_merton_default_probability_in_unit_interval():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    pd = r["risk_neutral_default_probability"]
    assert 0.0 <= pd <= 1.0


def test_merton_higher_leverage_higher_default_probability():
    low_lev = price_merton_credit(200, 100, 0.25, 0.04, 1, 0.4)["risk_neutral_default_probability"]
    high_lev = price_merton_credit(80, 100, 0.25, 0.04, 1, 0.4)["risk_neutral_default_probability"]
    assert high_lev > low_lev


def test_merton_credit_spread_finite():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    assert math.isfinite(r["credit_spread"])
    assert math.isfinite(r["credit_spread_bps"])


def test_distance_to_default_finite():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    assert math.isfinite(r["distance_to_default"])
    # With drift = r, DD equals d2.
    assert r["distance_to_default"] == pytest.approx(r["d2"], abs=1e-6)


def test_distance_to_default_uses_expected_return_when_supplied():
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4, expected_asset_return=0.10)
    assert r["dd_drift_used"] == "expected_asset_return"
    dd = compute_distance_to_default(120, 100, 0.25, 0.10, 1)
    assert r["distance_to_default"] == pytest.approx(dd, abs=1e-6)


def test_merton_pd_helper_matches():
    pd = compute_merton_default_probability(120, 100, 0.25, 0.04, 1)
    r = price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4)
    assert pd == pytest.approx(r["risk_neutral_default_probability"], abs=1e-6)


# ---------------------------------------------------------------------------
# Hazard / survival (7, 8, 9)
# ---------------------------------------------------------------------------


def test_hazard_survival_equals_exp_minus_lambda_t():
    r = compute_hazard_survival_curve(0.02, 0.4, 5, 0.04)
    assert r["survival_probability_at_maturity"] == pytest.approx(math.exp(-0.02 * 5), abs=1e-6)
    # Every curve point obeys Q(t) = exp(-λt).
    for pt in r["curve"]:
        assert pt["survival_probability"] == pytest.approx(math.exp(-0.02 * pt["time"]), abs=1e-6)


def test_hazard_default_equals_one_minus_survival():
    r = compute_hazard_survival_curve(0.03, 0.4, 5, 0.04)
    for pt in r["curve"]:
        assert pt["default_probability"] == pytest.approx(1.0 - pt["survival_probability"], abs=1e-9)


def test_hazard_expected_loss_equals_lgd_times_pd():
    r = compute_hazard_survival_curve(0.03, 0.4, 5, 0.04)
    lgd = 0.6
    for pt in r["curve"]:
        assert pt["expected_loss"] == pytest.approx(lgd * pt["default_probability"], abs=1e-6)


# ---------------------------------------------------------------------------
# CDS spread (10, 11, 12)
# ---------------------------------------------------------------------------


def test_simple_cds_spread_equals_hazard_times_lgd():
    assert compute_simple_cds_spread(0.02, 0.4) == pytest.approx(0.02 * 0.6, abs=1e-12)


def test_cds_detailed_fair_spread_finite_positive():
    r = compute_cds_spread(0.02, 0.4, 5, 0.04, 4, 1_000_000)
    assert r["fair_spread"] > 0 and math.isfinite(r["fair_spread"])
    assert r["protection_leg_pv"] > 0 and r["risky_pv01"] > 0


def test_cds_fair_spread_near_hazard_times_lgd():
    r = compute_cds_spread(0.02, 0.4, 5, 0.04, 4, 1_000_000)
    # Detailed discrete spread should be close to the credit-triangle 120 bps.
    assert r["fair_spread_bps"] == pytest.approx(120.0, abs=5.0)


# ---------------------------------------------------------------------------
# Risky bond (13, 14, 15)
# ---------------------------------------------------------------------------


def test_risky_bond_price_positive():
    r = price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.02, 0.4)
    assert r["risky_bond_price"] > 0 and math.isfinite(r["risky_bond_price"])


def test_risky_bond_le_risk_free_bond():
    r = price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.02, 0.4)
    assert r["risky_bond_price"] <= r["risk_free_bond_price"]


def test_risky_bond_credit_spread_non_negative():
    r = price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.02, 0.4)
    assert r["credit_spread_bps"] is not None
    assert math.isfinite(r["credit_spread_bps"]) and r["credit_spread_bps"] >= 0


def test_risky_bond_zero_hazard_matches_risk_free():
    r = price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.0, 0.4)
    assert r["risky_bond_price"] == pytest.approx(r["risk_free_bond_price"], abs=1e-6)
    assert r["credit_spread_bps"] == pytest.approx(0.0, abs=1e-2)


def test_risky_bond_cashflow_table_reconciles():
    r = price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.02, 0.4)
    total = sum(c["present_value"] for c in r["cash_flows"]) + sum(c["recovery_pv"] for c in r["cash_flows"])
    assert total == pytest.approx(r["risky_bond_price"], abs=1e-2)


def test_credit_spread_from_prices_helper():
    cfs = [(1.0, 50.0), (2.0, 1050.0)]
    # Price at a known flat yield, then recover the spread.
    y = 0.06
    price = sum(cf * math.exp(-y * t) for t, cf in cfs)
    spread = compute_credit_spread_from_prices(cfs, price, 0.04)
    assert spread == pytest.approx(0.02, abs=1e-6)


# ---------------------------------------------------------------------------
# Validation (16, 17, 18, 19)
# ---------------------------------------------------------------------------


def test_recovery_out_of_range_rejected():
    with pytest.raises(CreditInputError):
        price_merton_credit(120, 100, 0.25, 0.04, 1, 1.5)
    with pytest.raises(CreditInputError):
        compute_hazard_survival_curve(0.02, -0.1, 5, 0.04)


def test_negative_hazard_rejected():
    with pytest.raises(CreditInputError):
        compute_hazard_survival_curve(-0.01, 0.4, 5, 0.04)
    with pytest.raises(CreditInputError):
        price_risky_bond(1000, 0.05, 5, 2, 0.04, -0.01, 0.4)


def test_invalid_maturity_rejected():
    with pytest.raises(CreditInputError):
        price_merton_credit(120, 100, 0.25, 0.04, -1, 0.4)
    with pytest.raises(CreditInputError):
        compute_cds_spread(0.02, 0.4, 0, 0.04, 4, 1_000_000)


def test_invalid_volatility_rejected():
    with pytest.raises(CreditInputError):
        price_merton_credit(120, 100, 0.0, 0.04, 1, 0.4)


def test_invalid_asset_value_rejected():
    with pytest.raises(CreditInputError):
        price_merton_credit(-1, 100, 0.25, 0.04, 1, 0.4)


# ---------------------------------------------------------------------------
# No NaN / Infinity (20)
# ---------------------------------------------------------------------------


def test_no_nan_in_results():
    _assert_all_finite(price_merton_credit(120, 100, 0.25, 0.04, 1, 0.4))
    _assert_all_finite(compute_hazard_survival_curve(0.02, 0.4, 5, 0.04))
    _assert_all_finite(compute_cds_spread(0.02, 0.4, 5, 0.04, 4, 1_000_000))
    _assert_all_finite(price_risky_bond(1000, 0.05, 5, 2, 0.04, 0.02, 0.4))


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_credit_merton(client):
    body = client.post(
        "/credit/merton",
        json={"asset_value": 120, "debt_face_value": 100, "asset_volatility": 0.25,
              "risk_free_rate": 0.04, "time_to_maturity": 1, "recovery_rate": 0.4},
    ).json()
    assert body["equity_value"] > 0 and 0 <= body["risk_neutral_default_probability"] <= 1


def test_api_credit_hazard(client):
    body = client.post(
        "/credit/hazard",
        json={"hazard_rate": 0.02, "recovery_rate": 0.4, "maturity_years": 5, "risk_free_rate": 0.04},
    ).json()
    assert body["survival_probability_at_maturity"] == pytest.approx(math.exp(-0.1), abs=1e-6)
    assert len(body["curve"]) > 1


def test_api_credit_cds(client):
    body = client.post(
        "/credit/cds",
        json={"hazard_rate": 0.02, "recovery_rate": 0.4, "maturity_years": 5,
              "risk_free_rate": 0.04, "payment_frequency": 4, "notional": 1_000_000},
    ).json()
    assert body["fair_spread_bps"] == pytest.approx(120.0, abs=5.0)


def test_api_credit_risky_bond(client):
    body = client.post(
        "/credit/risky-bond",
        json={"face_value": 1000, "coupon_rate": 0.05, "maturity_years": 5, "coupon_frequency": 2,
              "risk_free_rate": 0.04, "hazard_rate": 0.02, "recovery_rate": 0.4},
    ).json()
    assert body["risky_bond_price"] <= body["risk_free_bond_price"]
    assert len(body["cash_flows"]) == 10


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/credit/merton", {"asset_value": 120, "debt_face_value": 100, "asset_volatility": 0.25, "risk_free_rate": 0.04, "time_to_maturity": 1, "recovery_rate": 1.5}),
        ("/credit/merton", {"asset_value": -1, "debt_face_value": 100, "asset_volatility": 0.25, "risk_free_rate": 0.04, "time_to_maturity": 1, "recovery_rate": 0.4}),
        ("/credit/merton", {"asset_value": 120, "debt_face_value": 100, "asset_volatility": 0.0, "risk_free_rate": 0.04, "time_to_maturity": 1, "recovery_rate": 0.4}),
        ("/credit/hazard", {"hazard_rate": -0.01, "recovery_rate": 0.4, "maturity_years": 5, "risk_free_rate": 0.04}),
        ("/credit/cds", {"hazard_rate": 0.02, "recovery_rate": 0.4, "maturity_years": -1, "risk_free_rate": 0.04, "payment_frequency": 4, "notional": 1_000_000}),
        ("/credit/risky-bond", {"face_value": 1000, "coupon_rate": 0.05, "maturity_years": 5, "coupon_frequency": 2, "risk_free_rate": 0.04, "hazard_rate": 0.02, "recovery_rate": 1.5}),
    ],
)
def test_api_credit_validation_422(client, path, payload):
    assert client.post(path, json=payload).status_code == 422
