"""
Tests for the Yield Curve Lab v1 (discount factors, forwards, shocks, bonds).

Deterministic, pure-math tests against textbook values plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.yield_curve import (
    CurveInputError,
    apply_curve_shock,
    bond_analytics,
    build_curve_analytics,
    compute_forward_rates,
    discount_factor_to_zero_rate,
    generate_sample_yield_curve,
    interpolate_zero_rate,
    shock_analytics,
    validate_curve_points,
    zero_rate_to_discount_factor,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

_CURVE = [
    {"maturity_years": 0.5, "zero_rate": 0.052},
    {"maturity_years": 1.0, "zero_rate": 0.049},
    {"maturity_years": 2.0, "zero_rate": 0.045},
    {"maturity_years": 5.0, "zero_rate": 0.041},
]


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
# Discount factors / zero rates
# ---------------------------------------------------------------------------


def test_continuous_discount_factor():
    assert zero_rate_to_discount_factor(0.05, 2, "continuous") == pytest.approx(math.exp(-0.10))


def test_annual_discount_factor():
    assert zero_rate_to_discount_factor(0.05, 2, "annual") == pytest.approx(1 / 1.05**2)


def test_semiannual_discount_factor():
    assert zero_rate_to_discount_factor(0.05, 2, "semiannual") == pytest.approx(1 / 1.025**4)


@pytest.mark.parametrize("comp", ["continuous", "annual", "semiannual"])
def test_discount_factor_roundtrip(comp):
    df = zero_rate_to_discount_factor(0.045, 3, comp)
    assert discount_factor_to_zero_rate(df, 3, comp) == pytest.approx(0.045, abs=1e-9)


def test_discount_factors_decline_with_maturity():
    curve = build_curve_analytics(_CURVE, "continuous", "linear_zero")["curve"]
    dfs = [c["discount_factor"] for c in curve]
    assert all(dfs[i] > dfs[i + 1] for i in range(len(dfs) - 1))


# ---------------------------------------------------------------------------
# Forward rates
# ---------------------------------------------------------------------------


def test_forward_rate_continuous():
    # f(1,2) = (r2*T2 - r1*T1)/(T2-T1) = (0.05*2 - 0.04*1)/1 = 0.06
    fwd = compute_forward_rates(
        [{"maturity_years": 1, "zero_rate": 0.04}, {"maturity_years": 2, "zero_rate": 0.05}],
        "continuous",
    )
    assert fwd[0]["forward_rate"] == pytest.approx(0.06, abs=1e-9)
    assert fwd[0]["start_year"] == 1 and fwd[0]["end_year"] == 2


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def test_linear_interpolation_on_zero_rates():
    pts = [{"maturity_years": 1, "zero_rate": 0.04}, {"maturity_years": 3, "zero_rate": 0.06}]
    rate, oor = interpolate_zero_rate(pts, 2)
    assert rate == pytest.approx(0.05) and oor is False


def test_interpolation_exact_match():
    pts = [{"maturity_years": 1, "zero_rate": 0.04}, {"maturity_years": 3, "zero_rate": 0.06}]
    assert interpolate_zero_rate(pts, 3)[0] == pytest.approx(0.06)


def test_interpolation_out_of_range_clamps_and_flags():
    pts = [{"maturity_years": 1, "zero_rate": 0.04}, {"maturity_years": 3, "zero_rate": 0.06}]
    rate, oor = interpolate_zero_rate(pts, 5)
    assert rate == pytest.approx(0.06) and oor is True


# ---------------------------------------------------------------------------
# Validation / sorting
# ---------------------------------------------------------------------------


def test_duplicate_maturities_rejected():
    with pytest.raises(CurveInputError):
        validate_curve_points(
            [{"maturity_years": 1, "zero_rate": 0.04}, {"maturity_years": 1, "zero_rate": 0.05}]
        )


def test_curve_points_sorted():
    pts = validate_curve_points(
        [{"maturity_years": 5, "zero_rate": 0.041}, {"maturity_years": 1, "zero_rate": 0.049}]
    )
    assert [p["maturity_years"] for p in pts] == [1, 5]


def test_too_few_points_rejected():
    with pytest.raises(CurveInputError):
        validate_curve_points([{"maturity_years": 1, "zero_rate": 0.04}])


# ---------------------------------------------------------------------------
# Curve shocks
# ---------------------------------------------------------------------------


def test_parallel_shock_adds_bps():
    pts = generate_sample_yield_curve()
    shocked = apply_curve_shock(pts, "parallel", 100)
    for o, s in zip(pts, shocked):
        assert s["zero_rate"] - o["zero_rate"] == pytest.approx(0.01)


def test_steepener_shifts_short_down_long_up():
    pts = generate_sample_yield_curve()
    shocked = apply_curve_shock(pts, "steepener", 100)
    assert shocked[0]["zero_rate"] < pts[0]["zero_rate"]   # short end down
    assert shocked[-1]["zero_rate"] > pts[-1]["zero_rate"]  # long end up


def test_flattener_shifts_short_up_long_down():
    pts = generate_sample_yield_curve()
    shocked = apply_curve_shock(pts, "flattener", 100)
    assert shocked[0]["zero_rate"] > pts[0]["zero_rate"]    # short end up
    assert shocked[-1]["zero_rate"] < pts[-1]["zero_rate"]  # long end down


def test_shock_analytics_change_bps():
    res = shock_analytics(_CURVE, "parallel", 50, "continuous")
    for ch in res["changes"]:
        assert ch["change_bps"] == pytest.approx(50.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Bond pricing / risk
# ---------------------------------------------------------------------------


def test_fixed_coupon_bond_price_from_ytm():
    # Par bond: YTM == coupon → price == face.
    b = bond_analytics(1000, 0.05, 5, 2, "ytm", 0.05, None, "annual", "linear_zero")
    assert b["price"] == pytest.approx(1000.0, abs=1e-6)


def test_premium_bond_when_coupon_above_ytm():
    b = bond_analytics(1000, 0.05, 5, 2, "ytm", 0.045, None, "annual", "linear_zero")
    assert b["price"] > 1000.0


def test_zero_coupon_bond_price():
    b = bond_analytics(1000, 0.0, 5, 1, "ytm", 0.04, None, "annual", "linear_zero")
    assert b["price"] == pytest.approx(1000.0 / 1.04**5, abs=1e-6)


def test_duration_convexity_finite_positive():
    b = bond_analytics(1000, 0.05, 5, 2, "ytm", 0.045, None, "annual", "linear_zero")
    assert b["macaulay_duration"] > 0 and math.isfinite(b["macaulay_duration"])
    assert b["modified_duration"] > 0 and math.isfinite(b["modified_duration"])
    assert b["dv01"] > 0 and math.isfinite(b["dv01"])
    assert b["convexity"] > 0 and math.isfinite(b["convexity"])
    # Modified < Macaulay for positive yield.
    assert b["modified_duration"] < b["macaulay_duration"]


def test_curve_discounted_bond_finite():
    b = bond_analytics(1000, 0.05, 5, 2, "curve", None, _CURVE, "annual", "linear_zero")
    assert math.isfinite(b["price"]) and b["price"] > 0
    assert b["macaulay_duration"] > 0
    assert b["modified_duration"] is not None and b["modified_duration"] > 0
    assert b["dv01"] is not None and b["dv01"] > 0
    assert b["convexity"] is not None and b["convexity"] > 0


def test_invalid_negative_maturity_rejected():
    with pytest.raises(CurveInputError):
        bond_analytics(1000, 0.05, -1, 2, "ytm", 0.045, None, "annual", "linear_zero")


def test_invalid_coupon_frequency_rejected():
    with pytest.raises(CurveInputError):
        bond_analytics(1000, 0.05, 5, 3, "ytm", 0.045, None, "annual", "linear_zero")


def test_no_nan_inf_in_analytics():
    _assert_all_finite(build_curve_analytics(_CURVE, "semiannual", "linear_zero"))
    _assert_all_finite(bond_analytics(1000, 0.05, 5, 2, "ytm", 0.045, None, "annual", "linear_zero"))
    _assert_all_finite(bond_analytics(1000, 0.05, 5, 2, "curve", None, _CURVE, "annual", "linear_zero"))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_curve(client):
    body = client.post(
        "/rates/curve",
        json={"curve_points": _CURVE, "compounding": "continuous", "interpolation": "linear_zero"},
    ).json()
    assert len(body["curve"]) == 4
    assert len(body["forward_rates"]) == 3


def test_api_shock(client):
    body = client.post(
        "/rates/shock",
        json={"curve_points": _CURVE, "shock_type": "parallel", "shock_bps": 100, "compounding": "continuous"},
    ).json()
    assert all(c["change_bps"] == pytest.approx(100.0, abs=1e-3) for c in body["changes"])


def test_api_bond_ytm(client):
    body = client.post(
        "/rates/bond",
        json={"face_value": 1000, "coupon_rate": 0.05, "maturity_years": 5, "coupon_frequency": 2,
              "pricing_mode": "ytm", "yield_to_maturity": 0.045},
    ).json()
    assert body["price"] > 1000.0
    assert body["dv01"] > 0 and body["convexity"] > 0


def test_api_sample_curve(client):
    body = client.get("/rates/sample").json()
    assert len(body["curve_points"]) == 7
    assert "education" in body["note"].lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"face_value": 1000, "coupon_rate": 0.05, "maturity_years": -1, "coupon_frequency": 2, "pricing_mode": "ytm", "yield_to_maturity": 0.045},
        {"face_value": 1000, "coupon_rate": 0.05, "maturity_years": 5, "coupon_frequency": 3, "pricing_mode": "ytm", "yield_to_maturity": 0.045},
        {"face_value": -1, "coupon_rate": 0.05, "maturity_years": 5, "coupon_frequency": 2, "pricing_mode": "ytm", "yield_to_maturity": 0.045},
    ],
)
def test_api_bond_validation_422(client, payload):
    assert client.post("/rates/bond", json=payload).status_code == 422


def test_api_curve_validation_422(client):
    assert client.post("/rates/curve", json={"curve_points": [{"maturity_years": 1, "zero_rate": 0.04}]}).status_code == 422
