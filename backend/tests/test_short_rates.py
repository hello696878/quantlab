"""
Tests for the Short Rate Models Lab v1 (Vasicek / CIR).

Deterministic simulation (fixed seeds) + analytic zero-coupon checks + API
wiring. No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.short_rates import (
    ShortRateInputError,
    feller_condition,
    price_cir_zero_coupon,
    price_vasicek_zero_coupon,
    run_short_rate_model,
    validate_short_rate_inputs,
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


_BASE = dict(
    initial_rate=0.04,
    long_run_rate=0.035,
    kappa=0.8,
    sigma=0.015,
    horizon_years=5.0,
    steps=120,
    simulations=2000,
    seed=42,
)


def _run(model, **overrides):
    params = {**_BASE, **overrides}
    return run_short_rate_model(model, **params)


# ---------------------------------------------------------------------------
# Reproducibility (1, 2, 3)
# ---------------------------------------------------------------------------


def test_vasicek_same_seed_identical():
    assert _run("vasicek") == _run("vasicek")


def test_cir_same_seed_identical():
    assert _run("cir") == _run("cir")


def test_different_seed_finite_and_differs():
    a = _run("vasicek", seed=1)
    b = _run("vasicek", seed=2)
    _assert_all_finite(a)
    _assert_all_finite(b)
    assert a["summary"]["mean_terminal_rate"] != b["summary"]["mean_terminal_rate"]


# ---------------------------------------------------------------------------
# Path preview is capped (4, 5)
# ---------------------------------------------------------------------------


def test_vasicek_preview_capped():
    r = _run("vasicek", steps=2000, simulations=5000)
    assert len(r["path_preview"]) <= 12
    assert all(len(p["points"]) <= 150 for p in r["path_preview"])
    assert len(r["mean_path"]) <= 150


def test_cir_preview_capped():
    r = _run("cir", steps=2000, simulations=5000)
    assert len(r["path_preview"]) <= 12
    assert all(len(p["points"]) <= 150 for p in r["path_preview"])


# ---------------------------------------------------------------------------
# Vasicek negatives + warning (6)
# ---------------------------------------------------------------------------


def test_vasicek_negative_rates_and_warning():
    r = _run("vasicek", initial_rate=0.02, long_run_rate=0.02, kappa=0.5, sigma=0.20, seed=7)
    assert r["summary"]["negative_rate_probability"] > 0
    assert r["summary"]["min_terminal_rate"] < 0
    assert any("negative rates" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# CIR non-negative after truncation (7)
# ---------------------------------------------------------------------------


def test_cir_non_negative_after_truncation():
    r = _run("cir", initial_rate=0.01, long_run_rate=0.01, kappa=0.3, sigma=0.30, seed=9)
    assert r["summary"]["min_terminal_rate"] >= 0.0
    assert r["summary"]["negative_rate_probability"] == 0.0
    assert all(pt["rate"] >= 0.0 for p in r["path_preview"] for pt in p["points"])


# ---------------------------------------------------------------------------
# CIR Feller condition warning (8, 9)
# ---------------------------------------------------------------------------


def test_cir_feller_violated_warning():
    # 2*k*theta = 2*0.8*0.035 = 0.056 < sigma^2 = 0.16
    r = _run("cir", sigma=0.40, seed=2)
    assert r["feller"]["satisfied"] is False
    assert any("Feller" in w for w in r["warnings"])


def test_cir_feller_satisfied_no_warning():
    r = _run("cir", sigma=0.015, seed=2)
    assert r["feller"]["satisfied"] is True
    assert not any("Feller" in w for w in r["warnings"])


def test_feller_condition_helper():
    satisfied, lhs, rhs = feller_condition(0.8, 0.035, 0.015)
    assert satisfied is True
    assert lhs == pytest.approx(0.056)
    assert rhs == pytest.approx(0.000225)


# ---------------------------------------------------------------------------
# Zero-coupon prices (10, 11, 12)
# ---------------------------------------------------------------------------


def test_vasicek_zero_coupon_finite_bounded():
    zc = price_vasicek_zero_coupon(0.04, 0.8, 0.035, 0.015, 5)
    assert zc["price"] is not None
    assert 0.0 < zc["price"] <= 1.0
    assert math.isfinite(zc["implied_zero_rate"])


def test_cir_zero_coupon_finite_positive():
    zc = price_cir_zero_coupon(0.04, 0.8, 0.035, 0.015, 5)
    assert zc["price"] is not None
    assert zc["price"] > 0.0
    assert math.isfinite(zc["implied_zero_rate"])


def test_zero_coupon_implied_rate_finite_in_response():
    r = _run("vasicek")
    assert r["zero_coupon"]["price"] is not None
    assert math.isfinite(r["zero_coupon"]["implied_zero_rate"])


def test_zero_coupon_matches_deterministic_when_sigma_zero():
    # With sigma = 0 both models collapse to the same deterministic discount.
    v = price_vasicek_zero_coupon(0.04, 0.8, 0.035, 0.0, 5)["price"]
    c = price_cir_zero_coupon(0.04, 0.8, 0.035, 0.0, 5)["price"]
    assert v == pytest.approx(c, abs=1e-9)


def test_cir_zero_coupon_long_horizon_stable():
    # Large gamma*T must not overflow.
    zc = price_cir_zero_coupon(0.04, 0.8, 0.035, 0.015, 100)
    assert zc["price"] is not None and 0.0 < zc["price"] < 1.0


# ---------------------------------------------------------------------------
# sigma = 0 handled safely (13)
# ---------------------------------------------------------------------------


def test_sigma_zero_handled():
    for model in ("vasicek", "cir"):
        r = _run(model, sigma=0.0)
        _assert_all_finite(r)
        assert r["zero_coupon"]["price"] is not None
        # Deterministic: terminal rate has (near) zero dispersion.
        assert r["summary"]["final_rate_std"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Validation (14, 15, 16, 17)
# ---------------------------------------------------------------------------


def test_invalid_model_rejected():
    with pytest.raises(ShortRateInputError):
        run_short_rate_model("hull_white", **_BASE)


def test_invalid_negative_horizon_rejected():
    with pytest.raises(ShortRateInputError):
        _run("vasicek", horizon_years=-1)


def test_invalid_steps_rejected():
    with pytest.raises(ShortRateInputError):
        _run("vasicek", steps=0)
    with pytest.raises(ShortRateInputError):
        _run("vasicek", steps=5000)


def test_invalid_simulations_rejected():
    with pytest.raises(ShortRateInputError):
        _run("vasicek", simulations=10)
    with pytest.raises(ShortRateInputError):
        _run("vasicek", simulations=10_000_000)


def test_kappa_non_positive_rejected():
    with pytest.raises(ShortRateInputError):
        _run("vasicek", kappa=0.0)


def test_negative_sigma_rejected():
    with pytest.raises(ShortRateInputError):
        _run("vasicek", sigma=-0.01)


def test_cir_negative_initial_rate_rejected():
    with pytest.raises(ShortRateInputError):
        _run("cir", initial_rate=-0.01)


def test_vasicek_allows_negative_inputs():
    # Vasicek is a Gaussian model; negative rate levels are permitted.
    warnings = validate_short_rate_inputs("vasicek", -0.01, -0.01, 0.8, 0.01, 5, 100, 200, 42)
    assert isinstance(warnings, list)


# ---------------------------------------------------------------------------
# No NaN / Infinity (18)
# ---------------------------------------------------------------------------


def test_no_nan_in_response():
    _assert_all_finite(_run("vasicek"))
    _assert_all_finite(_run("cir"))
    _assert_all_finite(_run("vasicek", sigma=0.0))


def test_distribution_probabilities_sum_to_one():
    r = _run("vasicek")
    assert sum(b["probability"] for b in r["distribution"]) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_short_rate_vasicek(client):
    body = client.post(
        "/rates/short-rate",
        json={"model": "vasicek", "initial_rate": 0.04, "long_run_rate": 0.035, "kappa": 0.8,
              "sigma": 0.015, "horizon_years": 5, "steps": 120, "simulations": 2000, "seed": 42},
    ).json()
    assert body["model"] == "vasicek"
    assert body["zero_coupon"]["price"] is not None
    assert len(body["path_preview"]) <= 12
    assert body["distribution"]


def test_api_short_rate_cir_feller(client):
    body = client.post(
        "/rates/short-rate",
        json={"model": "cir", "initial_rate": 0.04, "long_run_rate": 0.035, "kappa": 0.8,
              "sigma": 0.40, "horizon_years": 5, "steps": 120, "simulations": 2000, "seed": 2},
    ).json()
    assert body["feller"]["satisfied"] is False
    assert body["summary"]["min_terminal_rate"] >= 0.0


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "nope", "horizon_years": 5},
        {"model": "vasicek", "horizon_years": -1},
        {"model": "vasicek", "steps": 0},
        {"model": "vasicek", "steps": 99999},
        {"model": "vasicek", "simulations": 10},
        {"model": "vasicek", "kappa": 0.0},
        {"model": "vasicek", "sigma": -0.01},
        {"model": "cir", "initial_rate": -0.01},
    ],
)
def test_api_short_rate_validation_422(client, payload):
    assert client.post("/rates/short-rate", json=payload).status_code == 422
