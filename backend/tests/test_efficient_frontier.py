"""
Unit tests for the efficient-frontier helpers in app.portfolio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.portfolio import (
    efficient_frontier_points,
    optimize_weights,
    portfolio_point,
    portfolio_stats,
    random_portfolios,
)


def mu_cov(returns: dict, variances: dict, corr: float = 0.1):
    tickers = list(returns)
    mu = pd.Series(returns)
    stds = {t: variances[t] ** 0.5 for t in tickers}
    cov = pd.DataFrame(index=tickers, columns=tickers, dtype=float)
    for a in tickers:
        for b in tickers:
            cov.loc[a, b] = variances[a] if a == b else corr * stds[a] * stds[b]
    return mu, cov


# ---------------------------------------------------------------------------
# Random portfolios
# ---------------------------------------------------------------------------


def test_random_portfolios_count_and_constraints():
    mu, cov = mu_cov({"A": 0.10, "B": 0.07, "C": 0.04}, {"A": 0.04, "B": 0.03, "C": 0.02})
    ports = random_portfolios(mu, cov, num_portfolios=500, risk_free_rate=0.02)
    assert len(ports) == 500
    for p in ports:
        assert set(p["weights"]) == {"A", "B", "C"}
        assert sum(p["weights"].values()) == pytest.approx(1.0, abs=1e-9)
        for w in p["weights"].values():
            assert w >= -1e-12
        assert p["volatility"] >= 0


def test_random_portfolios_deterministic_seed():
    mu, cov = mu_cov({"A": 0.1, "B": 0.05}, {"A": 0.04, "B": 0.02})
    a = random_portfolios(mu, cov, 200, seed=42)
    b = random_portfolios(mu, cov, 200, seed=42)
    c = random_portfolios(mu, cov, 200, seed=7)
    assert a[0]["weights"] == b[0]["weights"]
    assert a[10]["weights"] == b[10]["weights"]
    assert a[0]["weights"] != c[0]["weights"]


def test_random_portfolio_stats_consistent():
    mu, cov = mu_cov({"A": 0.12, "B": 0.06}, {"A": 0.05, "B": 0.02})
    ports = random_portfolios(mu, cov, 50, risk_free_rate=0.0)
    for p in ports:
        ret, vol, sharpe = portfolio_point(p["weights"], mu, cov)["expected_return"], None, None
        # Recompute return directly and compare.
        w = np.array([p["weights"]["A"], p["weights"]["B"]])
        assert p["expected_return"] == pytest.approx(float(w @ mu.to_numpy()), abs=1e-9)


def test_random_portfolios_zero_volatility_sharpe_is_finite():
    mu = pd.Series({"A": 0.05, "B": 0.05})
    cov = pd.DataFrame(0.0, index=mu.index, columns=mu.index)
    ports = random_portfolios(mu, cov, 25, risk_free_rate=0.02)
    for p in ports:
        assert p["volatility"] == pytest.approx(0.0)
        assert p["sharpe"] == pytest.approx(0.0)
        assert np.isfinite(p["expected_return"])


@pytest.mark.parametrize("num", [0, -1])
def test_random_portfolios_rejects_invalid_count(num):
    mu, cov = mu_cov({"A": 0.1, "B": 0.05}, {"A": 0.04, "B": 0.02})
    with pytest.raises(ValueError, match="num_portfolios"):
        random_portfolios(mu, cov, num)


def test_random_portfolios_rejects_misaligned_covariance():
    mu = pd.Series({"A": 0.1, "B": 0.05})
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.02]], index=["A", "C"], columns=["A", "C"])
    with pytest.raises(ValueError, match="align"):
        random_portfolios(mu, cov, 10)


# ---------------------------------------------------------------------------
# Frontier curve
# ---------------------------------------------------------------------------


def test_frontier_points_monotone_and_bounded():
    mu, cov = mu_cov(
        {"A": 0.12, "B": 0.08, "C": 0.03}, {"A": 0.05, "B": 0.03, "C": 0.015}, corr=0.2
    )
    pts = efficient_frontier_points(mu, cov, num_points=30)
    assert len(pts) >= 5
    # Sorted by volatility (non-decreasing).
    vols = [p["volatility"] for p in pts]
    assert vols == sorted(vols)
    for p in pts:
        assert p["volatility"] >= 0


def test_frontier_starts_at_min_volatility_portfolio():
    mu, cov = mu_cov(
        {"A": 0.12, "B": 0.08, "C": 0.03}, {"A": 0.05, "B": 0.03, "C": 0.015}, corr=0.2
    )
    min_w = optimize_weights(mu, cov, "min_volatility")
    min_ret, min_vol, _ = portfolio_stats(min_w, mu, cov)

    pts = efficient_frontier_points(mu, cov, num_points=30)
    assert pts[0]["volatility"] == pytest.approx(min_vol, abs=1e-8)
    assert pts[0]["expected_return"] == pytest.approx(min_ret, abs=1e-8)


def test_frontier_single_asset():
    mu, cov = mu_cov({"A": 0.1}, {"A": 0.04})
    pts = efficient_frontier_points(mu, cov)
    assert len(pts) == 1
    assert pts[0]["expected_return"] == pytest.approx(0.1)
    assert pts[0]["volatility"] == pytest.approx(0.2, abs=1e-9)


def test_frontier_equal_returns_degenerates_to_point():
    mu, cov = mu_cov({"A": 0.05, "B": 0.05, "C": 0.05}, {"A": 0.04, "B": 0.02, "C": 0.01})
    pts = efficient_frontier_points(mu, cov)
    assert len(pts) == 1  # all returns equal → single min-vol point


def test_frontier_min_vol_not_exceeding_random_min():
    """The frontier's lowest-volatility point should be ≤ the best random vol."""
    mu, cov = mu_cov(
        {"A": 0.12, "B": 0.08, "C": 0.03}, {"A": 0.05, "B": 0.03, "C": 0.015}, corr=0.2
    )
    pts = efficient_frontier_points(mu, cov, num_points=40)
    randoms = random_portfolios(mu, cov, 2000, seed=1)
    frontier_min_vol = min(p["volatility"] for p in pts)
    random_min_vol = min(p["volatility"] for p in randoms)
    assert frontier_min_vol <= random_min_vol + 1e-6


def test_frontier_rejects_non_symmetric_covariance():
    mu = pd.Series({"A": 0.1, "B": 0.05})
    cov = pd.DataFrame([[0.04, 0.03], [0.0, 0.02]], index=mu.index, columns=mu.index)
    with pytest.raises(ValueError, match="symmetric"):
        efficient_frontier_points(mu, cov)
