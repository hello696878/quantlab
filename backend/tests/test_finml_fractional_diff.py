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
from app.finml.fractional_diff import (
    compute_memory_retention,
    first_difference,
    frac_diff_fixed_width,
)

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
    assert w[4] == pytest.approx(-0.0390625)


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


@pytest.mark.parametrize(
    "d,max_size,threshold",
    [(-0.1, 20, 0.001), (2.1, 20, 0.001), (0.5, 1, 0.001), (0.5, 20, 0.0), (0.5, 20, 1.0)],
)
def test_weight_helper_rejects_invalid_inputs(d, max_size, threshold):
    with pytest.raises(FinmlInputError):
        get_fracdiff_weights(d, max_size, threshold)


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


def test_transform_helpers_reject_invalid_series_or_weights():
    with pytest.raises(FinmlInputError):
        frac_diff_fixed_width(np.array([1.0, np.nan]), [1.0])
    with pytest.raises(FinmlInputError):
        frac_diff_fixed_width(np.array([1.0, 2.0]), [])
    with pytest.raises(FinmlInputError):
        frac_diff_fixed_width(np.array([1.0, 2.0]), [1.0, -0.5, -0.1])
    with pytest.raises(FinmlInputError):
        first_difference(np.array([[1.0, 2.0]]))


# ---------------------------------------------------------------------------
# Diagnostics (9, 10, 11)
# ---------------------------------------------------------------------------


def test_memory_retention_correlations_are_finite_and_bounded():
    res = run_fractional_diff_demo(d=0.5)
    s = res["summary"]
    assert math.isfinite(s["fracdiff_correlation"])
    assert math.isfinite(s["firstdiff_correlation"])
    assert -1.0 <= s["fracdiff_correlation"] <= 1.0
    assert -1.0 <= s["firstdiff_correlation"] <= 1.0
    assert s["comparison_observations"] <= s["usable_observations"]


def test_d_zero_memory_correlation_near_one():
    res = run_fractional_diff_demo(d=0.0)
    assert res["summary"]["fracdiff_correlation"] == pytest.approx(1.0, abs=1e-6)


def test_d_one_correlations_and_series_match_first_difference():
    res = run_fractional_diff_demo(d=1.0)
    assert res["summary"]["fracdiff_correlation"] == pytest.approx(
        res["summary"]["firstdiff_correlation"], abs=1e-6
    )
    assert res["series"]["fractional_difference"] == res["series"]["first_difference"]


def test_comparison_series_use_identical_dates():
    res = run_fractional_diff_demo(n_days=1500, d=0.5)
    first_dates = [point["date"] for point in res["series"]["first_difference"]]
    frac_dates = [point["date"] for point in res["series"]["fractional_difference"]]
    assert first_dates == frac_dates
    assert len(first_dates) <= 1200


def test_memory_correlations_use_common_finite_mask():
    original = np.array([1.0, 2.0, 4.0, 8.0])
    fracdiff = np.array([np.nan, np.nan, 2.0, 4.0])
    firstdiff = np.array([np.nan, 1.0, 2.0, 4.0])
    result = compute_memory_retention(original, fracdiff, firstdiff, warmup=2)
    assert result["comparison_observations"] == 2
    assert result["fracdiff_correlation"] == pytest.approx(1.0)
    assert result["firstdiff_correlation"] == pytest.approx(1.0)


def test_stationarity_diagnostics_finite():
    d = run_fractional_diff_demo()["diagnostics"]
    for key in (
        "original_lag1_autocorr", "fracdiff_lag1_autocorr", "firstdiff_lag1_autocorr",
        "original_trend_slope", "fracdiff_trend_slope", "firstdiff_trend_slope",
        "original_rolling_mean_variability", "fracdiff_rolling_mean_variability",
        "firstdiff_rolling_mean_variability", "original_rolling_std_variability",
        "fracdiff_rolling_std_variability", "firstdiff_rolling_std_variability",
        "original_variance_ratio", "fracdiff_variance_ratio", "firstdiff_variance_ratio",
    ):
        assert d[key] is None or math.isfinite(d[key])
    # Original price is highly autocorrelated; first difference much less so.
    assert d["original_lag1_autocorr"] > d["firstdiff_lag1_autocorr"]


def test_d_one_is_more_difference_like_than_d_zero_on_same_path():
    d_zero = run_fractional_diff_demo(d=0.0)["diagnostics"]
    d_one = run_fractional_diff_demo(d=1.0)["diagnostics"]
    assert d_zero["fracdiff_lag1_autocorr"] > d_one["fracdiff_lag1_autocorr"]


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


def test_max_weights_larger_than_history_is_capped_safely():
    res = run_fractional_diff_demo(n_days=50, max_weights=200, weight_threshold=1e-8)
    assert res["summary"]["weight_count"] <= 49
    assert res["summary"]["usable_observations"] >= 2
    assert any("capped" in warning for warning in res["warnings"])


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
    assert [point["date"] for point in body["series"]["first_difference"]] == [
        point["date"] for point in body["series"]["fractional_difference"]
    ]


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
