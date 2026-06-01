"""
Unit tests for app.portfolio.factor_analysis (OLS factor regression).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.portfolio import factor_analysis


def _prices_from_returns(returns: dict, start="2018-01-01") -> pd.DataFrame:
    """Build a price frame from per-ticker daily-return arrays."""
    n = len(next(iter(returns.values()))) + 1
    idx = pd.date_range(start, periods=n, freq="B")
    data = {}
    for t, rets in returns.items():
        prices = [100.0]
        for r in rets:
            prices.append(prices[-1] * (1.0 + r))
        data[t] = prices
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Known-beta recovery on deterministic data
# ---------------------------------------------------------------------------


def test_recovers_known_betas_and_alpha():
    rng = np.random.default_rng(0)
    n = 600
    f1 = rng.normal(0.0004, 0.01, n)
    f2 = rng.normal(0.0002, 0.008, n)
    noise = rng.normal(0.0, 0.0005, n)
    alpha = 0.0003
    # True relationship: r_p = alpha + 0.8*f1 - 0.3*f2 + noise
    rp = alpha + 0.8 * f1 - 0.3 * f2 + noise

    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2})
    port = prices[["PORT"]]
    factors = prices[["F1", "F2"]]

    d = factor_analysis(port, factors, {"PORT": 1.0}, ["F1", "F2"])
    assert d["betas"]["F1"] == pytest.approx(0.8, abs=0.03)
    assert d["betas"]["F2"] == pytest.approx(-0.3, abs=0.03)
    assert d["alpha_daily"] == pytest.approx(alpha, abs=2e-4)
    assert d["alpha_annualized"] == pytest.approx(d["alpha_daily"] * 252, abs=1e-12)
    assert 0.9 <= d["r_squared"] <= 1.0


def test_perfect_fit_high_r_squared():
    rng = np.random.default_rng(1)
    n = 400
    f1 = rng.normal(0.0005, 0.012, n)
    rp = 0.6 * f1  # exact, no noise, no alpha
    prices = _prices_from_returns({"PORT": rp, "F1": f1})
    d = factor_analysis(prices[["PORT"]], prices[["F1"]], {"PORT": 1.0}, ["F1"])
    assert d["betas"]["F1"] == pytest.approx(0.6, abs=1e-6)
    assert d["r_squared"] == pytest.approx(1.0, abs=1e-9)
    assert d["residual_volatility"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


def test_output_fields_and_curves():
    rng = np.random.default_rng(2)
    n = 300
    f1 = rng.normal(0.0004, 0.01, n)
    f2 = rng.normal(0.0001, 0.009, n)
    rp = 0.5 * f1 + 0.2 * f2 + rng.normal(0, 0.0008, n)
    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2})
    d = factor_analysis(prices[["PORT"]], prices[["F1", "F2"]], {"PORT": 1.0}, ["F1", "F2"])

    assert set(d["betas"]) == {"F1", "F2"}
    assert d["residual_volatility"] >= 0
    # Curves anchored at capital, length = obs + 1.
    assert d["actual_equity_curve"][0]["value"] == pytest.approx(100_000.0)
    assert d["fitted_equity_curve"][0]["value"] == pytest.approx(100_000.0)
    assert len(d["actual_equity_curve"]) == len(d["regression_points"]) + 1
    # Residual = actual − fitted.
    for p in d["regression_points"][:20]:
        assert p["residual"] == pytest.approx(p["actual_return"] - p["fitted_return"], abs=1e-12)


def test_equity_curves_anchor_before_first_return_without_duplicate_date():
    rng = np.random.default_rng(20)
    n = 50
    f1 = rng.normal(0.0004, 0.01, n)
    rp = 0.7 * f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1})

    d = factor_analysis(prices[["PORT"]], prices[["F1"]], {"PORT": 1.0}, ["F1"])

    assert d["actual_equity_curve"][0]["date"] == str(prices.index[0].date())
    assert d["fitted_equity_curve"][0]["date"] == str(prices.index[0].date())
    assert d["actual_equity_curve"][1]["date"] == str(prices.index[1].date())
    assert d["actual_equity_curve"][0]["date"] != d["actual_equity_curve"][1]["date"]
    assert d["regression_points"][0]["date"] == str(prices.index[1].date())


def test_factor_correlation_matrix():
    rng = np.random.default_rng(3)
    n = 300
    f1 = rng.normal(0, 0.01, n)
    f2 = rng.normal(0, 0.01, n)
    rp = 0.4 * f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2})
    d = factor_analysis(prices[["PORT"]], prices[["F1", "F2"]], {"PORT": 1.0}, ["F1", "F2"])
    corr = d["factor_correlation_matrix"]
    assert corr["F1"]["F1"] == pytest.approx(1.0, abs=1e-9)
    assert corr["F1"]["F2"] == pytest.approx(corr["F2"]["F1"], abs=1e-9)


def test_factor_correlation_matrix_zero_variance_is_finite_with_unit_diagonal():
    rng = np.random.default_rng(30)
    n = 120
    f1 = rng.normal(0, 0.01, n)
    f2 = np.zeros(n)
    rp = 0.5 * f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2})

    d = factor_analysis(prices[["PORT"]], prices[["F1", "F2"]], {"PORT": 1.0}, ["F1", "F2"])
    corr = d["factor_correlation_matrix"]
    for a in ("F1", "F2"):
        assert corr[a][a] == pytest.approx(1.0)
        for b in ("F1", "F2"):
            assert math.isfinite(corr[a][b])
    assert corr["F1"]["F2"] == pytest.approx(0.0)
    assert corr["F2"]["F1"] == pytest.approx(0.0)


def test_diagnostics():
    rng = np.random.default_rng(4)
    n = 400
    f1 = rng.normal(0, 0.01, n)
    f2 = rng.normal(0, 0.01, n)
    rp = 0.9 * f1 - 0.4 * f2 + rng.normal(0, 0.0006, n)
    prices = _prices_from_returns({"PORT": rp, "MKT": f1, "BOND": f2})
    d = factor_analysis(prices[["PORT"]], prices[["MKT", "BOND"]], {"PORT": 1.0}, ["MKT", "BOND"])
    diag = d["diagnostics"]
    assert diag["strongest_positive_factor"] == "MKT"
    assert diag["strongest_negative_factor"] == "BOND"
    assert diag["absolute_largest_exposure"] == "MKT"
    assert diag["multicollinearity_warning"] is False


# ---------------------------------------------------------------------------
# Multicollinearity
# ---------------------------------------------------------------------------


def test_multicollinearity_warning_on_duplicate_factor():
    rng = np.random.default_rng(5)
    n = 300
    f1 = rng.normal(0, 0.01, n)
    rp = 0.5 * f1 + rng.normal(0, 0.0006, n)
    prices = _prices_from_returns({"PORT": rp, "F1": f1})
    # F2 is an exact copy of F1 → rank-deficient design.
    factors = pd.DataFrame({"F1": prices["F1"], "F2": prices["F1"]})
    d = factor_analysis(prices[["PORT"]], factors, {"PORT": 1.0}, ["F1", "F2"])
    assert d["diagnostics"]["multicollinearity_warning"] is True


def test_multicollinearity_warning_on_nearly_duplicate_factor():
    rng = np.random.default_rng(8)
    n = 300
    f1 = rng.normal(0, 0.01, n)
    f2 = f1 + rng.normal(0, 1e-12, n)
    rp = 0.5 * f1 + rng.normal(0, 0.0006, n)
    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2})

    d = factor_analysis(prices[["PORT"]], prices[["F1", "F2"]], {"PORT": 1.0}, ["F1", "F2"])
    assert d["diagnostics"]["multicollinearity_warning"] is True


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_too_few_observations_raises():
    rng = np.random.default_rng(6)
    n = 4  # fewer than factors + 2
    f1 = rng.normal(0, 0.01, n)
    f2 = rng.normal(0, 0.01, n)
    f3 = rng.normal(0, 0.01, n)
    rp = f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1, "F2": f2, "F3": f3})
    with pytest.raises(ValueError, match="Not enough"):
        factor_analysis(prices[["PORT"]], prices[["F1", "F2", "F3"]], {"PORT": 1.0}, ["F1", "F2", "F3"])


def test_invalid_weights_raise_clear_errors():
    rng = np.random.default_rng(9)
    n = 80
    f1 = rng.normal(0, 0.01, n)
    p1 = 0.6 * f1
    p2 = 0.3 * f1
    prices = _prices_from_returns({"P1": p1, "P2": p2, "F1": f1})
    port = prices[["P1", "P2"]]
    factors = prices[["F1"]]

    with pytest.raises(ValueError, match="exactly"):
        factor_analysis(port, factors, {"P1": 1.0}, ["F1"])
    with pytest.raises(ValueError, match="non-negative"):
        factor_analysis(port, factors, {"P1": 1.2, "P2": -0.2}, ["F1"])
    with pytest.raises(ValueError, match="sum to 1"):
        factor_analysis(port, factors, {"P1": 0.4, "P2": 0.4}, ["F1"])


def test_factor_prices_must_align_with_portfolio_prices():
    rng = np.random.default_rng(10)
    n = 80
    f1 = rng.normal(0, 0.01, n)
    rp = 0.6 * f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1})
    shifted_factors = prices[["F1"]].copy()
    shifted_factors.index = shifted_factors.index + pd.Timedelta(days=1)

    with pytest.raises(ValueError, match="same index"):
        factor_analysis(prices[["PORT"]], shifted_factors, {"PORT": 1.0}, ["F1"])


def test_missing_factor_column_raises():
    rng = np.random.default_rng(11)
    n = 80
    f1 = rng.normal(0, 0.01, n)
    rp = 0.6 * f1
    prices = _prices_from_returns({"PORT": rp, "F1": f1})

    with pytest.raises(ValueError, match="missing"):
        factor_analysis(prices[["PORT"]], prices[["F1"]], {"PORT": 1.0}, ["F2"])
