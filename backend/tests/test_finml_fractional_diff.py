"""
Tests for AFML Fractional Differentiation v1.

Deterministic, pure-function fixtures + the synthetic-data orchestrator + API.
No live data, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.finml import FinmlInputError, get_fracdiff_weights, run_fractional_diff_demo
from app.finml.fractional_diff import first_difference, frac_diff_fixed_width

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _assert_all_finite(obj):
    if obj is None:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj)


# ---------------------------------------------------------------------------
# Weights (1, 2, 3, 4)
# ---------------------------------------------------------------------------


def test_weights_d_half_match_expected():
    w = get_fracdiff_weights(0.5, 200, 1e-9)
    assert w[0] == pytest.approx(1.0)
    assert w[1] == pytest.approx(-0.5)
    assert w[2] == pytest.approx(-0.125)
    assert w[3] == pytest.approx(-0.0625)


def test_weights_d_zero_first_one_rest_negligible():
    w = get_fracdiff_weights(0.0, 200, 0.001)
    assert w[0] == pytest.approx(1.0)
    assert all(abs(x) < 1e-9 for x in w[1:])  # only w0 survives (next is 0)


def test_weights_d_one_is_first_difference():
    w = get_fracdiff_weights(1.0, 200, 0.001)
    assert w == pytest.approx([1.0, -1.0])


def test_weights_stop_by_threshold():
    loose = get_fracdiff_weights(0.5, 200, 0.05)
    tight = get_fracdiff_weights(0.5, 200, 0.001)
    assert len(loose) < len(tight)
    assert abs(loose[-1]) >= 0.05  # last kept weight is above threshold


def test_weights_capped_by_max_size():
    w = get_fracdiff_weights(0.5, 5, 1e-12)
    assert len(w) == 5


# ---------------------------------------------------------------------------
# Fixed-width transform (5, 6, 7, 8)
# ---------------------------------------------------------------------------


def test_fracdiff_fixed_width_finite():
    series = np.cumsum(np.ones(50)) + 100.0
    w = get_fracdiff_weights(0.5, 50, 0.001)
    fd, warmup = frac_diff_fixed_width(series, w)
    assert np.all(np.isfinite(fd[warmup:]))


def test_d_zero_returns_original():
    series = (100.0 + np.cumsum(np.linspace(0.1, 0.3, 60))).astype(float)
    w = get_fracdiff_weights(0.0, 60, 0.001)
    fd, warmup = frac_diff_fixed_width(series, w)
    assert warmup == 0
    assert np.allclose(fd, series)


def test_d_one_returns_first_difference():
    series = (100.0 + np.cumsum(np.linspace(0.1, 0.3, 60))).astype(float)
    w = get_fracdiff_weights(1.0, 60, 0.001)
    fd, warmup = frac_diff_fixed_width(series, w)
    fdiff = first_difference(series)
    assert warmup == 1
    assert np.allclose(fd[warmup:], fdiff[warmup:])


def test_warmup_equals_weight_count_minus_one():
    res = run_fractional_diff_demo()
    assert res["summary"]["warmup_period"] == res["summary"]["weight_count"] - 1


# ---------------------------------------------------------------------------
# Diagnostics (9, 10, 11)
# ---------------------------------------------------------------------------


def test_memory_retention_finite_and_fracdiff_preserves_more():
    res = run_fractional_diff_demo(d=0.5)
    s = res["summary"]
    assert math.isfinite(s["fracdiff_correlation"])
    assert math.isfinite(s["firstdiff_correlation"])
    # For d in (0,1), fractional differencing keeps more memory than first diff.
    assert s["fracdiff_correlation"] > s["firstdiff_correlation"]


def test_d_zero_memory_correlation_near_one():
    res = run_fractional_diff_demo(d=0.0)
    assert res["summary"]["fracdiff_correlation"] == pytest.approx(1.0, abs=1e-6)


def test_stationarity_diagnostics_finite():
    d = run_fractional_diff_demo()["diagnostics"]
    for key in (
        "original_lag1_autocorr", "fracdiff_lag1_autocorr", "firstdiff_lag1_autocorr",
        "original_trend_slope", "fracdiff_trend_slope", "firstdiff_trend_slope",
    ):
        assert d[key] is None or math.isfinite(d[key])
    # Original price is highly autocorrelated; first difference much less so.
    assert d["original_lag1_autocorr"] > d["firstdiff_lag1_autocorr"]


# ---------------------------------------------------------------------------
# Validation (12, 13, 14, 15) + no NaN (16)
# ---------------------------------------------------------------------------


def test_invalid_d_rejected():
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(d=-0.5)
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(d=3.0)


def test_invalid_threshold_rejected():
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(weight_threshold=0.0)
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(weight_threshold=1.5)


def test_invalid_max_weights_rejected():
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(max_weights=1)
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(max_weights=5000)


def test_invalid_n_days_rejected():
    with pytest.raises(FinmlInputError):
        run_fractional_diff_demo(n_days=10)


def test_no_nan_in_response_and_deterministic():
    a = run_fractional_diff_demo()
    b = run_fractional_diff_demo()
    assert a == b
    _assert_all_finite(a)


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_fractional_diff(client):
    body = client.post(
        "/finml/fractional-diff-demo",
        json={"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
              "d": 0.5, "weight_threshold": 0.001, "max_weights": 200},
    ).json()
    assert body["summary"]["d"] == 0.5
    assert body["weights"] and body["series"]["original"] and body["series"]["fractional_difference"]
    assert body["summary"]["warmup_period"] == body["summary"]["weight_count"] - 1


@pytest.mark.parametrize(
    "payload",
    [
        {"d": -0.5},
        {"d": 3.0},
        {"weight_threshold": 0.0},
        {"weight_threshold": 1.5},
        {"max_weights": 1},
        {"n_days": 10},
    ],
)
def test_api_fractional_diff_validation_422(client, payload):
    base = {"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
            "d": 0.5, "weight_threshold": 0.001, "max_weights": 200}
    base.update(payload)
    assert client.post("/finml/fractional-diff-demo", json=base).status_code == 422
