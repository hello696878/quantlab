"""
Unit tests for app.portfolio.risk_dashboard.

Deterministic synthetic price frames with genuine return variance; no network.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.portfolio import risk_dashboard

_PARAMS = {
    "AAA": (0.0006, 0.012, 0.10),
    "BBB": (0.0004, 0.016, 0.13),
    "CCC": (0.0002, 0.008, 0.07),
    "DDD": (0.0001, 0.006, 0.05),
}


def make_prices(n: int = 400, tickers=("AAA", "BBB", "CCC", "DDD")) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for t in tickers:
        base, amp, freq = _PARAMS.get(t, (0.0003, 0.011, 0.09))
        prices = [100.0]
        for i in range(1, n):
            r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.29 * i)
            prices.append(prices[-1] * (1.0 + r))
        data[t] = prices
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Per-asset stats
# ---------------------------------------------------------------------------


def test_asset_returns_and_vols_present():
    d = risk_dashboard(make_prices())
    tickers = d["tickers"]
    assert set(d["asset_annual_returns"]) == set(tickers)
    assert set(d["asset_annual_volatilities"]) == set(tickers)
    for v in d["asset_annual_volatilities"].values():
        assert v >= 0


def test_asset_stats_match_manual_annualization():
    prices = make_prices()
    d = risk_dashboard(prices)
    daily = prices.pct_change(fill_method=None).dropna(how="any")
    for t in prices.columns:
        assert d["asset_annual_returns"][t] == pytest.approx(
            float(daily[t].mean() * 252), abs=1e-9
        )
        assert d["asset_annual_volatilities"][t] == pytest.approx(
            float(daily[t].std() * math.sqrt(252)), abs=1e-9
        )


# ---------------------------------------------------------------------------
# Correlation / covariance matrices
# ---------------------------------------------------------------------------


def test_correlation_matrix_symmetric_and_unit_diagonal():
    d = risk_dashboard(make_prices())
    corr = d["correlation_matrix"]
    tickers = d["tickers"]
    for a in tickers:
        assert corr[a][a] == pytest.approx(1.0, abs=1e-9)
        for b in tickers:
            assert corr[a][b] == pytest.approx(corr[b][a], abs=1e-9)
            assert -1.0 - 1e-9 <= corr[a][b] <= 1.0 + 1e-9


def test_covariance_matrix_symmetric_positive_diagonal():
    d = risk_dashboard(make_prices())
    cov = d["covariance_matrix"]
    for a in d["tickers"]:
        assert cov[a][a] > 0
        for b in d["tickers"]:
            assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-9)


# ---------------------------------------------------------------------------
# Equal-weight portfolio
# ---------------------------------------------------------------------------


def test_equal_weight_portfolio_metrics():
    d = risk_dashboard(make_prices())
    ew = d["equal_weight_portfolio"]
    assert set(ew["weights"]) == set(d["tickers"])
    for w in ew["weights"].values():
        assert w == pytest.approx(1.0 / len(d["tickers"]), abs=1e-9)
    assert ew["volatility"] >= 0
    # Diversification ratio ≥ 1 when assets aren't perfectly correlated.
    assert ew["diversification_ratio"] >= 1.0 - 1e-6


def test_equal_weight_portfolio_metrics_match_formula():
    prices = make_prices()
    d = risk_dashboard(prices)
    tickers = d["tickers"]
    n = len(tickers)
    w = np.full(n, 1.0 / n)
    annual_returns = np.array([d["asset_annual_returns"][t] for t in tickers])
    annual_vols = np.array([d["asset_annual_volatilities"][t] for t in tickers])
    covariance = np.array(
        [[d["covariance_matrix"][a][b] for b in tickers] for a in tickers]
    )
    expected_return = float(w @ annual_returns)
    volatility = float(math.sqrt(max(w @ covariance @ w, 0.0)))
    diversification_ratio = float((w @ annual_vols) / volatility)

    ew = d["equal_weight_portfolio"]
    assert ew["expected_return"] == pytest.approx(expected_return, abs=1e-9)
    assert ew["volatility"] == pytest.approx(volatility, abs=1e-9)
    assert ew["diversification_ratio"] == pytest.approx(diversification_ratio, abs=1e-9)


# ---------------------------------------------------------------------------
# Correlation diagnostics
# ---------------------------------------------------------------------------


def test_correlation_diagnostics():
    d = risk_dashboard(make_prices())
    diag = d["correlation_diagnostics"]
    assert diag["min_pairwise_correlation"] <= diag["average_pairwise_correlation"] + 1e-9
    assert diag["average_pairwise_correlation"] <= diag["max_pairwise_correlation"] + 1e-9
    assert len(diag["most_correlated_pair"]) == 2
    assert len(diag["least_correlated_pair"]) == 2
    # The most-correlated pair really has the highest off-diagonal correlation.
    a, b = diag["most_correlated_pair"]
    assert d["correlation_matrix"][a][b] == pytest.approx(
        diag["max_pairwise_correlation"], abs=1e-9
    )
    pair_values = []
    tickers = d["tickers"]
    for i, a in enumerate(tickers):
        for b in tickers[i + 1:]:
            pair_values.append(d["correlation_matrix"][a][b])
    assert diag["average_pairwise_correlation"] == pytest.approx(
        float(np.mean(pair_values)), abs=1e-9
    )


# ---------------------------------------------------------------------------
# Risk contribution
# ---------------------------------------------------------------------------


def test_risk_contribution_sums_to_one():
    d = risk_dashboard(make_prices())
    rc = d["risk_contribution"]
    assert set(rc) == set(d["tickers"])
    assert sum(rc.values()) == pytest.approx(1.0, abs=1e-6)


def test_risk_contribution_matches_formula():
    prices = make_prices()
    d = risk_dashboard(prices)
    tickers = d["tickers"]
    n = len(tickers)
    w = np.full(n, 1.0 / n)
    sigma = np.array(
        [[d["covariance_matrix"][a][b] for b in tickers] for a in tickers]
    )
    port_vol = math.sqrt(w @ sigma @ w)
    marginal = sigma @ w / port_vol
    component = w * marginal
    percent = component / port_vol
    for i, t in enumerate(tickers):
        assert d["risk_contribution"][t] == pytest.approx(float(percent[i]), abs=1e-6)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_single_asset_no_pairs():
    d = risk_dashboard(make_prices(tickers=("AAA",)))
    diag = d["correlation_diagnostics"]
    assert diag["most_correlated_pair"] is None
    assert diag["least_correlated_pair"] is None
    assert d["risk_contribution"]["AAA"] == pytest.approx(1.0, abs=1e-6)


def test_zero_variance_assets_return_finite_matrices_and_equal_risk_fallback():
    idx = pd.date_range("2020-01-01", periods=6, freq="B")
    prices = pd.DataFrame(
        {
            "AAA": [100.0] * len(idx),
            "BBB": [50.0] * len(idx),
            "CCC": [25.0] * len(idx),
        },
        index=idx,
    )

    d = risk_dashboard(prices)
    for a in d["tickers"]:
        assert d["asset_annual_returns"][a] == pytest.approx(0.0)
        assert d["asset_annual_volatilities"][a] == pytest.approx(0.0)
        assert d["correlation_matrix"][a][a] == pytest.approx(1.0)
        for b in d["tickers"]:
            assert math.isfinite(d["correlation_matrix"][a][b])
            assert math.isfinite(d["covariance_matrix"][a][b])
            if a != b:
                assert d["correlation_matrix"][a][b] == pytest.approx(0.0)
    assert d["equal_weight_portfolio"]["volatility"] == pytest.approx(0.0)
    assert d["equal_weight_portfolio"]["diversification_ratio"] == pytest.approx(0.0)
    assert sum(d["risk_contribution"].values()) == pytest.approx(1.0)


def test_too_short_raises():
    prices = make_prices(2)  # only 1 daily return
    with pytest.raises(ValueError, match="at least 2 daily returns"):
        risk_dashboard(prices)
