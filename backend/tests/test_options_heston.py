"""
Tests for the Heston stochastic-volatility Monte Carlo engine v1.

Deterministic where it matters (fixed seeds): seed reproducibility (price +
preview), finiteness, standard-error behaviour, the xi→0 / v0=theta reduction to
Black-Scholes, non-negative variance, the Feller-condition warning, validation,
preview caps, and finiteness.  No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.options import black_scholes_price
from app.options_heston import (
    HestonInputError,
    feller_condition,
    price_heston_european_mc,
    validate_heston_inputs,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# Default Heston parameters (variance form).
_BASE = dict(
    S=100.0,
    K=100.0,
    T=1.0,
    r=0.05,
    q=0.0,
    v0=0.04,
    theta=0.04,
    kappa=2.0,
    xi=0.5,
    rho=-0.7,
    steps=252,
    simulations=10000,
    seed=42,
)


def _price(option_type="call", **overrides):
    params = {**_BASE, **overrides}
    return price_heston_european_mc(option_type, **params)


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
# Reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_identical_price():
    a = _price(simulations=5000, seed=123)
    b = _price(simulations=5000, seed=123)
    assert a["price"] == b["price"]
    assert a["standard_error"] == b["standard_error"]


def test_same_seed_identical_preview():
    a = _price(simulations=5000, seed=123)
    b = _price(simulations=5000, seed=123)
    assert a["path_preview"][0]["underlying"] == b["path_preview"][0]["underlying"]
    assert a["path_preview"][0]["variance"] == b["path_preview"][0]["variance"]


def test_different_seed_differs_but_finite():
    a = _price(simulations=5000, seed=1)
    b = _price(simulations=5000, seed=2)
    assert a["price"] != b["price"]
    assert math.isfinite(a["price"]) and math.isfinite(b["price"])


# ---------------------------------------------------------------------------
# Pricing / SE / CI
# ---------------------------------------------------------------------------


def test_call_price_finite():
    assert math.isfinite(_price("call")["price"])


def test_put_price_finite():
    assert math.isfinite(_price("put")["price"])


def test_standard_error_positive():
    assert _price(simulations=5000)["standard_error"] > 0


def test_confidence_interval_brackets_price():
    res = _price(simulations=5000)
    ci = res["confidence_interval_95"]
    assert ci["lower"] <= res["price"] <= ci["upper"]
    assert ci["upper"] - ci["lower"] == pytest.approx(2 * 1.96 * res["standard_error"], abs=1e-5)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_zero_vol_of_vol_reduces_to_black_scholes(option_type):
    # xi = 0 and v0 = theta -> variance is constant at theta -> GBM with sqrt(theta).
    res = _price(option_type, xi=0.0, v0=0.04, theta=0.04, simulations=50000, seed=42)
    bs = black_scholes_price(option_type, 100.0, 100.0, 1.0, 0.05, math.sqrt(0.04), 0.0)
    assert res["price"] == pytest.approx(bs, abs=0.2)
    assert res["black_scholes_reference"]["volatility_used"] == pytest.approx(0.20, abs=1e-6)


# ---------------------------------------------------------------------------
# Variance / Feller
# ---------------------------------------------------------------------------


def test_variance_paths_non_negative():
    res = _price(simulations=3000)
    assert res["summary"]["min_variance_observed"] >= 0
    for path in res["path_preview"]:
        assert all(v >= 0 for v in path["variance"])
        assert all(vol >= 0 for vol in path["volatility"])


def test_feller_violation_warns():
    # 2·kappa·theta = 0.16 < xi² = 0.25 → violated.
    res = _price(kappa=2.0, theta=0.04, xi=0.5, simulations=3000)
    assert res["feller"]["satisfied"] is False
    assert any("Feller" in w for w in res["warnings"])


def test_feller_satisfied_no_violation_warning():
    # 2·kappa·theta = 0.16 ≥ xi² = 0.01 → satisfied.
    res = _price(kappa=2.0, theta=0.04, xi=0.1, simulations=3000)
    assert res["feller"]["satisfied"] is True
    assert not any("Feller condition is violated" in w for w in res["warnings"])


def test_feller_condition_helper():
    satisfied, lhs, rhs = feller_condition(2.0, 0.04, 0.1)
    assert satisfied and lhs == pytest.approx(0.16) and rhs == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"rho": -1.5},
        {"rho": 1.5},
        {"v0": -0.04},
        {"theta": 0.0},
        {"kappa": 0.0},
        {"xi": -0.1},
        {"simulations": 10},
        {"simulations": 500000},
        {"steps": 0},
        {"steps": 5000},
        {"S": 0.0},
    ],
)
def test_invalid_inputs_rejected(overrides):
    with pytest.raises(HestonInputError):
        _price(**overrides)


@pytest.mark.parametrize("option_type", ["", "straddle"])
def test_invalid_option_type_rejected(option_type):
    with pytest.raises(HestonInputError):
        _price(option_type)


@pytest.mark.parametrize("seed", [-1, 2**32, 1.5])
def test_invalid_seed_rejected(seed):
    with pytest.raises(HestonInputError):
        _price(seed=seed)


def test_validate_returns_warnings_list():
    warnings = validate_heston_inputs(100, 100, 1, 0.05, 0, 0.04, 0.04, 2.0, 0.1, -0.7, 252, 10000)
    assert isinstance(warnings, list)
    assert any("Euler" in w for w in warnings)


# ---------------------------------------------------------------------------
# Path preview caps / finiteness
# ---------------------------------------------------------------------------


def test_path_preview_capped():
    res = _price(simulations=10000, steps=252)
    assert len(res["path_preview"]) <= 12
    for path in res["path_preview"]:
        assert len(path["underlying"]) <= 150
        assert len(path["variance"]) == len(path["underlying"]) == len(path["volatility"])
    assert len(res["preview_times"]) == len(res["path_preview"][0]["underlying"])
    assert res["preview_times"][0] == 0.0


def test_no_nan_inf_in_response():
    _assert_all_finite(_price(simulations=3000, steps=50))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _api_payload(**overrides):
    payload = {
        "option_type": "call",
        "underlying_price": 100,
        "strike": 100,
        "time_to_expiry": 1,
        "risk_free_rate": 0.05,
        "dividend_yield": 0,
        "initial_variance": 0.04,
        "long_run_variance": 0.04,
        "kappa": 2.0,
        "vol_of_vol": 0.5,
        "rho": -0.7,
        "steps": 252,
        "simulations": 10000,
        "seed": 42,
    }
    payload.update(overrides)
    return payload


def test_api_heston(client):
    body = client.post("/options/heston", json=_api_payload()).json()
    assert body["model"] == "heston_mc_full_truncation_euler"
    assert math.isfinite(body["price"]) and body["standard_error"] > 0
    assert body["black_scholes_reference"]["volatility_source"] == "sqrt(long_run_variance)"
    assert len(body["path_preview"]) <= 12


@pytest.mark.parametrize(
    "overrides",
    [
        {"rho": -1.5},
        {"initial_variance": -0.04},
        {"kappa": 0},
        {"simulations": 10},
        {"simulations": 500000},
        {"steps": 5000},
        {"underlying_price": -1},
        {"option_type": "straddle"},
    ],
)
def test_api_heston_validation_422(client, overrides):
    assert client.post("/options/heston", json=_api_payload(**overrides)).status_code == 422
