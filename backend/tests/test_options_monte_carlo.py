"""
Tests for the Monte Carlo options engine v1 (GBM; European / Asian / barrier).

Deterministic where it matters (fixed seeds): seed reproducibility, MC↔BS
agreement and CI containment for large sample sizes, standard-error behaviour,
Asian/barrier finiteness, barrier knock-out logic, validation, preview caps, and
finiteness.  No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.options import black_scholes_price
from app.options_monte_carlo import (
    MonteCarloInputError,
    price_monte_carlo,
    summarize_monte_carlo_payoffs,
    validate_monte_carlo_inputs,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# Canonical example: S=100, K=100, T=1, r=0.05, sigma=0.20, q=0.
_S, _K, _T, _R, _SIG, _Q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.0


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
    a = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 123)
    b = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 123)
    assert a["price"] == b["price"]
    assert a["standard_error"] == b["standard_error"]
    assert a["confidence_interval_95"] == b["confidence_interval_95"]


def test_same_seed_identical_path_preview():
    a = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 123)
    b = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 123)
    assert a["path_preview"] == b["path_preview"]


def test_different_seed_differs_but_finite():
    a = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 1)
    b = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10000, 2)
    assert a["price"] != b["price"]
    assert math.isfinite(a["price"]) and math.isfinite(b["price"])


def test_antithetic_is_reproducible():
    a = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 8000, 42, True)
    b = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 8000, 42, True)
    assert a["price"] == b["price"]
    assert a["antithetic"] is True


# ---------------------------------------------------------------------------
# European MC vs Black-Scholes
# ---------------------------------------------------------------------------


def test_european_call_near_black_scholes():
    bs = black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q)
    mc = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 50000, 42)
    assert mc["price"] == pytest.approx(bs, abs=0.2)
    assert mc["black_scholes_reference"] == pytest.approx(bs, abs=1e-4)


def test_european_put_near_black_scholes():
    bs = black_scholes_price("put", _S, _K, _T, _R, _SIG, _Q)
    mc = price_monte_carlo("european_put", _S, _K, _T, _R, _SIG, _Q, 252, 50000, 42)
    assert mc["price"] == pytest.approx(bs, abs=0.2)


def test_confidence_interval_contains_black_scholes_for_large_n():
    bs = black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q)
    mc = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 50000, 42)
    ci = mc["confidence_interval_95"]
    assert ci["lower"] <= bs <= ci["upper"]


def test_put_confidence_interval_contains_black_scholes():
    bs = black_scholes_price("put", _S, _K, _T, _R, _SIG, _Q)
    mc = price_monte_carlo("european_put", _S, _K, _T, _R, _SIG, _Q, 252, 50000, 42)
    ci = mc["confidence_interval_95"]
    assert ci["lower"] <= bs <= ci["upper"]


# ---------------------------------------------------------------------------
# Standard error
# ---------------------------------------------------------------------------


def test_standard_error_positive():
    mc = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 5000, 42)
    assert mc["standard_error"] > 0


def test_standard_error_decreases_with_more_simulations():
    small = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 2000, 7)
    large = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 20000, 7)
    assert large["standard_error"] < small["standard_error"]


def test_confidence_interval_brackets_price():
    mc = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 5000, 42)
    ci = mc["confidence_interval_95"]
    assert ci["lower"] < mc["price"] < ci["upper"]
    assert ci["upper"] - ci["lower"] == pytest.approx(2 * 1.96 * mc["standard_error"], abs=1e-5)


def test_summarize_zero_variance_payoffs_is_finite():
    import numpy as np

    summary = summarize_monte_carlo_payoffs(np.zeros(1000))
    assert summary["price"] == 0.0
    assert summary["standard_error"] == 0.0
    assert summary["confidence_interval_95"] == {"lower": 0.0, "upper": 0.0}


# ---------------------------------------------------------------------------
# Asian options
# ---------------------------------------------------------------------------


def test_asian_call_price_finite():
    mc = price_monte_carlo("asian_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 42)
    assert math.isfinite(mc["price"]) and mc["price"] >= 0
    assert mc["average_type"] == "arithmetic"
    assert mc["black_scholes_reference"] is None
    assert any("arithmetic average" in w for w in mc["warnings"])


def test_asian_put_price_finite():
    mc = price_monte_carlo("asian_put", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 42)
    assert math.isfinite(mc["price"]) and mc["price"] >= 0
    assert mc["average_type"] == "arithmetic"


def test_asian_call_cheaper_than_european_call():
    # Averaging lowers effective volatility → Asian call ≤ vanilla European call.
    asian = price_monte_carlo("asian_call", _S, _K, _T, _R, _SIG, _Q, 252, 40000, 42)
    euro = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 40000, 42)
    assert asian["price"] < euro["price"]


# ---------------------------------------------------------------------------
# Barrier options
# ---------------------------------------------------------------------------


def test_up_and_out_call_knocks_out_and_is_finite():
    mc = price_monte_carlo("up_and_out_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 42, False, 120.0)
    assert math.isfinite(mc["price"]) and mc["price"] >= 0
    # Knock-out caps value below the vanilla call.
    euro = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 42)
    assert mc["price"] < euro["price"]
    assert any("discrete" in w for w in mc["warnings"])


def test_down_and_out_put_is_finite():
    mc = price_monte_carlo("down_and_out_put", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 42, False, 80.0)
    assert math.isfinite(mc["price"]) and mc["price"] >= 0
    assert any("discrete" in w for w in mc["warnings"])


def test_barrier_already_breached_returns_zero_and_warns():
    # Up barrier below spot → every path starts breached → up-and-out payoff is 0.
    mc = price_monte_carlo("up_and_out_call", _S, _K, _T, _R, _SIG, _Q, 252, 5000, 42, False, 80.0)
    assert mc["price"] == 0.0
    assert any("breached" in w for w in mc["warnings"])


def test_down_barrier_already_breached_returns_zero_and_warns():
    # Down barrier above spot → every path starts breached → down-and-out payoff is 0.
    mc = price_monte_carlo("down_and_out_put", _S, _K, _T, _R, _SIG, _Q, 252, 5000, 42, False, 120.0)
    assert mc["price"] == 0.0
    assert any("breached" in w for w in mc["warnings"])


def test_barrier_in_out_parity():
    # in + out == vanilla (same seed, same paths).
    out = price_monte_carlo("up_and_out_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 9, False, 130.0)
    inn = price_monte_carlo("up_and_in_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 9, False, 130.0)
    vanilla = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 20000, 9)
    # Identical pre-rounding; only independent 6-dp rounding separates them.
    assert out["price"] + inn["price"] == pytest.approx(vanilla["price"], abs=1e-4)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_requires_barrier_for_barrier_payoffs():
    with pytest.raises(MonteCarloInputError):
        validate_monte_carlo_inputs(
            "up_and_out_call", _S, _K, _T, _R, _SIG, _Q, 100, 5000, None
        )


def test_validate_rejects_unknown_payoff():
    with pytest.raises(MonteCarloInputError):
        validate_monte_carlo_inputs(
            "rainbow_option", _S, _K, _T, _R, _SIG, _Q, 100, 5000, None
        )


@pytest.mark.parametrize("seed", [-1, 2**32, 1.5, "42"])
def test_price_rejects_invalid_direct_seed(seed):
    with pytest.raises(MonteCarloInputError):
        price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 5000, seed)


@pytest.mark.parametrize(
    "args",
    [
        ("european_call", 0.0, _K, _T, _R, _SIG, _Q, 100, 5000, None),
        ("european_call", _S, 0.0, _T, _R, _SIG, _Q, 100, 5000, None),
        ("european_call", _S, _K, 0.0, _R, _SIG, _Q, 100, 5000, None),
        ("european_call", _S, _K, _T, _R, 0.0, _Q, 100, 5000, None),
        ("european_call", _S, _K, _T, _R, _SIG, -0.01, 100, 5000, None),
        ("european_call", math.inf, _K, _T, _R, _SIG, _Q, 100, 5000, None),
        ("european_call", _S, _K, _T, math.nan, _SIG, _Q, 100, 5000, None),
        ("european_call", _S, _K, _T, _R, _SIG, _Q, 1.5, 5000, None),
        ("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10.5, None),
        ("european_call", _S, _K, _T, _R, _SIG, _Q, 0, 5000, None),
        ("european_call", _S, _K, _T, _R, _SIG, _Q, 100, 10, None),
        ("up_and_out_call", _S, _K, _T, _R, _SIG, _Q, 100, 5000, math.inf),
    ],
)
def test_validate_rejects_invalid_direct_inputs(args):
    with pytest.raises(MonteCarloInputError):
        validate_monte_carlo_inputs(*args)


# ---------------------------------------------------------------------------
# Path preview / finiteness
# ---------------------------------------------------------------------------


def test_path_preview_is_capped():
    mc = price_monte_carlo("european_call", _S, _K, _T, _R, _SIG, _Q, 252, 10000, 42)
    assert len(mc["path_preview"]) <= 12
    for path in mc["path_preview"]:
        assert len(path["points"]) <= 150
        assert path["points"][0]["time"] == 0.0
        assert path["points"][0]["price"] == pytest.approx(_S)
        assert all(pt["price"] > 0 for pt in path["points"])


def test_no_nan_inf_in_response():
    for ptype, barrier in [
        ("european_call", None),
        ("asian_put", None),
        ("up_and_out_call", 120.0),
        ("down_and_out_put", 80.0),
    ]:
        mc = price_monte_carlo(ptype, _S, _K, _T, _R, _SIG, _Q, 50, 3000, 42, False, barrier)
        _assert_all_finite(mc)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_monte_carlo_european_call(client):
    body = client.post(
        "/options/monte-carlo",
        json={"payoff_type": "european_call", "underlying_price": 100, "strike": 100,
              "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "steps": 252, "simulations": 10000, "seed": 42},
    ).json()
    assert body["model"] == "gbm_monte_carlo"
    assert body["price"] == pytest.approx(10.45, abs=0.5)
    assert body["standard_error"] > 0
    assert body["confidence_interval_95"]["lower"] < body["confidence_interval_95"]["upper"]
    assert len(body["path_preview"]) <= 12


def test_api_monte_carlo_barrier(client):
    resp = client.post(
        "/options/monte-carlo",
        json={"payoff_type": "up_and_out_call", "underlying_price": 100, "strike": 100,
              "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "steps": 100, "simulations": 8000, "seed": 42, "barrier_price": 120},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert math.isfinite(body["price"])
    assert any("discrete" in w for w in body["warnings"])
    assert body["barrier_price"] == pytest.approx(120.0)


@pytest.mark.parametrize(
    "payload",
    [
        # simulations below the minimum
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 10, "seed": 1},
        # simulations above the maximum
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 500000, "seed": 1},
        # steps = 0
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 0, "simulations": 5000, "seed": 1},
        # fractional steps are not silently truncated
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 1.5, "simulations": 5000, "seed": 1},
        # steps above cap
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 5000, "simulations": 5000, "seed": 1},
        # fractional simulations are not silently truncated
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 5000.5, "seed": 1},
        # seed above cap
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 5000, "seed": 2**32},
        # negative underlying
        {"payoff_type": "european_call", "underlying_price": -1, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 5000, "seed": 1},
        # zero volatility
        {"payoff_type": "european_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0, "steps": 100, "simulations": 5000, "seed": 1},
        # unknown payoff type
        {"payoff_type": "lookback_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 5000, "seed": 1},
        # barrier payoff missing barrier_price
        {"payoff_type": "up_and_out_call", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100, "simulations": 5000, "seed": 1},
    ],
)
def test_api_monte_carlo_validation_422(client, payload):
    assert client.post("/options/monte-carlo", json=payload).status_code == 422
