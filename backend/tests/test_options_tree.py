"""
Tests for tree-based option pricing v1 (CRR binomial, European + American).

Deterministic checks: European convergence to Black-Scholes, put-call parity,
American >= European, early-exercise diagnostics, input validation, finiteness,
and small/large lattice behaviour.  No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.options import black_scholes_price
from app.options_tree import (
    LATTICE_MAX_STEPS,
    TreeInputError,
    binomial_tree_price,
    build_binomial_lattice,
    compare_tree_to_black_scholes,
    validate_tree_inputs,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# Canonical example: S=100, K=100, T=1, r=0.05, sigma=0.20, q=0.
_S, _K, _T, _R, _SIG, _Q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.0


# ---------------------------------------------------------------------------
# European convergence to Black-Scholes
# ---------------------------------------------------------------------------


def test_european_call_converges_to_black_scholes():
    bs = black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q)
    tree = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 500)
    assert tree["price"] == pytest.approx(bs, abs=0.02)
    assert tree["convergence"]["black_scholes_price"] == pytest.approx(bs, abs=1e-4)
    assert tree["convergence"]["is_european_reference"] is False


def test_european_put_converges_to_black_scholes():
    bs = black_scholes_price("put", _S, _K, _T, _R, _SIG, _Q)
    tree = binomial_tree_price("put", "european", _S, _K, _T, _R, _SIG, _Q, 500)
    assert tree["price"] == pytest.approx(bs, abs=0.02)


def test_european_convergence_improves_with_steps():
    bs = black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q)
    coarse = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 10)
    fine = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 500)
    assert abs(fine["price"] - bs) <= abs(coarse["price"] - bs) + 1e-9


def test_european_put_call_parity_binomial():
    c = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 200)["price"]
    p = binomial_tree_price("put", "european", _S, _K, _T, _R, _SIG, _Q, 200)["price"]
    expected = _S * math.exp(-_Q * _T) - _K * math.exp(-_R * _T)
    assert (c - p) == pytest.approx(expected, abs=1e-3)


# ---------------------------------------------------------------------------
# American exercise
# ---------------------------------------------------------------------------


def test_american_put_geq_european_put():
    am = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 200)["price"]
    eu = binomial_tree_price("put", "european", _S, _K, _T, _R, _SIG, _Q, 200)["price"]
    assert am >= eu - 1e-9
    # Early exercise adds value for an ATM American put, so it is strictly higher.
    assert am > eu


def test_american_call_no_dividend_equals_european():
    am = binomial_tree_price("call", "american", _S, _K, _T, _R, _SIG, _Q, 200)
    eu = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 200)
    # No-dividend American call == European call (never optimal to exercise early).
    assert am["price"] == pytest.approx(eu["price"], abs=1e-6)
    assert am["price"] >= eu["price"] - 1e-9


def test_american_call_no_dividend_no_early_exercise():
    am = binomial_tree_price("call", "american", _S, _K, _T, _R, _SIG, _Q, 200)
    assert am["early_exercise"]["detected"] is False
    assert am["early_exercise"]["first_step"] is None
    assert am["early_exercise"]["boundary"] == []


def test_american_put_deep_itm_detects_early_exercise():
    deep = binomial_tree_price("put", "american", 50.0, 100.0, _T, _R, _SIG, _Q, 100)
    ee = deep["early_exercise"]
    assert ee["detected"] is True
    assert ee["first_step"] is not None and 0 <= ee["first_step"] <= 100
    assert ee["first_time"] is not None and math.isfinite(ee["first_time"])
    for pt in ee["boundary"]:
        assert math.isfinite(pt["boundary_price"]) and pt["boundary_price"] > 0
        assert math.isfinite(pt["time"])


def test_american_put_atm_detects_early_exercise():
    am = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 100)
    assert am["early_exercise"]["detected"] is True
    assert am["convergence"]["is_european_reference"] is True


def test_american_call_with_dividend_can_exercise_early():
    # A high continuous dividend yield can make early call exercise optimal.
    am = binomial_tree_price("call", "american", 100.0, 80.0, 1.0, 0.05, 0.20, 0.15, 200)
    eu = binomial_tree_price("call", "european", 100.0, 80.0, 1.0, 0.05, 0.20, 0.15, 200)
    assert am["price"] >= eu["price"] - 1e-9
    assert am["early_exercise"]["detected"] is True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_rejects_zero_steps():
    with pytest.raises(TreeInputError):
        validate_tree_inputs(_S, _K, _T, _R, _SIG, _Q, 0)


def test_validate_rejects_p_outside_unit_interval():
    # Large rate vs tiny vol with a single big step pushes p outside [0, 1].
    with pytest.raises(TreeInputError):
        validate_tree_inputs(_S, _K, 1.0, 0.9, 0.01, 0.0, 1)


def test_low_step_warning_is_informational_not_fatal():
    res = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, 2)
    assert math.isfinite(res["price"])
    assert any("coarse" in w for w in res["warnings"])


# ---------------------------------------------------------------------------
# Finiteness / no NaN-Inf
# ---------------------------------------------------------------------------


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj)


def test_tree_price_is_finite():
    res = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 100)
    assert math.isfinite(res["price"])


def test_no_nan_inf_anywhere_in_response():
    res = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 5)
    _assert_all_finite(res)


# ---------------------------------------------------------------------------
# Lattice generation (small vs large)
# ---------------------------------------------------------------------------


def test_small_lattice_is_generated():
    res = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 5)
    assert res["lattice"] is not None
    # (N+1)(N+2)/2 nodes in a recombining tree of N steps.
    assert len(res["lattice"]["nodes"]) == (5 + 1) * (5 + 2) // 2
    assert res["lattice_note"] is None
    node = res["lattice"]["nodes"][0]
    for key in ("step", "index", "underlying_price", "option_value", "intrinsic_value", "early_exercise"):
        assert key in node


def test_lattice_cap_constant_boundary():
    at_cap = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, LATTICE_MAX_STEPS)
    assert at_cap["lattice"] is not None
    over_cap = binomial_tree_price("call", "european", _S, _K, _T, _R, _SIG, _Q, LATTICE_MAX_STEPS + 1)
    assert over_cap["lattice"] is None


def test_large_lattice_not_generated():
    res = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 200)
    assert res["lattice"] is None
    assert res["lattice_note"] and "limited" in res["lattice_note"]


def test_include_lattice_false_omits_lattice():
    res = binomial_tree_price("put", "american", _S, _K, _T, _R, _SIG, _Q, 5, include_lattice=False)
    assert res["lattice"] is None


def test_build_binomial_lattice_helper():
    lat = build_binomial_lattice("put", "american", _S, _K, _T, _R, _SIG, _Q, 4)
    assert lat is not None and lat["steps"] == 4
    assert build_binomial_lattice("put", "american", _S, _K, _T, _R, _SIG, _Q, 50) is None


# ---------------------------------------------------------------------------
# Convergence helper
# ---------------------------------------------------------------------------


def test_convergence_sweep_shape():
    conv = compare_tree_to_black_scholes(
        "call", "european", _S, _K, _T, _R, _SIG, _Q, [5, 10, 25, 50, 100, 200]
    )
    assert conv["black_scholes_price"] == pytest.approx(
        black_scholes_price("call", _S, _K, _T, _R, _SIG, _Q), abs=1e-4
    )
    assert [p["steps"] for p in conv["points"]] == [5, 10, 25, 50, 100, 200]
    for p in conv["points"]:
        assert math.isfinite(p["price"]) and math.isfinite(p["difference_vs_black_scholes"])


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_binomial_european_call(client):
    body = client.post(
        "/options/binomial",
        json={"option_type": "call", "exercise_style": "european", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "steps": 200},
    ).json()
    assert body["model"] == "crr_binomial"
    assert body["price"] == pytest.approx(10.45, abs=0.05)
    assert body["early_exercise"]["detected"] is False


def test_api_binomial_american_put(client):
    resp = client.post(
        "/options/binomial",
        json={"option_type": "put", "exercise_style": "american", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "dividend_yield": 0, "steps": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price"] > 5.55  # > European put
    assert body["early_exercise"]["detected"] is True
    assert body["convergence"]["is_european_reference"] is True


def test_api_binomial_small_lattice(client):
    body = client.post(
        "/options/binomial",
        json={"option_type": "put", "exercise_style": "american", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "steps": 5},
    ).json()
    assert body["lattice"] is not None
    assert len(body["lattice"]["nodes"]) == 21


def test_api_binomial_large_lattice_hidden(client):
    body = client.post(
        "/options/binomial",
        json={"option_type": "call", "exercise_style": "european", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "steps": 100},
    ).json()
    assert body["lattice"] is None
    assert body["lattice_note"]


def test_api_tree_convergence(client):
    body = client.post(
        "/options/tree-convergence",
        json={"option_type": "call", "exercise_style": "european", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "step_values": [5, 10, 25, 50, 100, 200]},
    ).json()
    assert body["black_scholes_price"] == pytest.approx(10.4506, abs=1e-3)
    assert len(body["points"]) == 6
    assert body["points"][-1]["steps"] == 200


@pytest.mark.parametrize(
    "payload",
    [
        # steps = 0 (below the minimum)
        {"option_type": "call", "exercise_style": "european", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 0},
        # steps above the cap
        {"option_type": "call", "exercise_style": "european", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 1001},
        # negative underlying
        {"option_type": "call", "exercise_style": "european", "underlying_price": -1, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100},
        # zero volatility
        {"option_type": "call", "exercise_style": "european", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0, "steps": 100},
        # unknown exercise style
        {"option_type": "call", "exercise_style": "bermudan", "underlying_price": 100, "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20, "steps": 100},
    ],
)
def test_api_binomial_validation_422(client, payload):
    assert client.post("/options/binomial", json=payload).status_code == 422


def test_api_binomial_p_out_of_bounds_422(client):
    # Large rate vs tiny vol with one big step → p outside [0, 1] → 422.
    resp = client.post(
        "/options/binomial",
        json={"option_type": "call", "exercise_style": "european", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.9, "volatility": 0.01,
              "steps": 1},
    )
    assert resp.status_code == 422


def test_api_tree_convergence_validation_422(client):
    # step value above 1000 inside the list
    resp = client.post(
        "/options/tree-convergence",
        json={"option_type": "call", "exercise_style": "european", "underlying_price": 100,
              "strike": 100, "time_to_expiry": 1, "risk_free_rate": 0.05, "volatility": 0.20,
              "step_values": [5, 10, 5000]},
    )
    assert resp.status_code == 422
