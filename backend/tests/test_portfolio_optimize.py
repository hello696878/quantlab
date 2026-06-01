"""
Unit tests for the portfolio optimization helpers in app.portfolio.

Optimizer tests use hand-built expected-return / covariance inputs so the
optimum is analytically predictable and fully deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import app.portfolio as portfolio_module
from app.portfolio import (
    annualized_stats,
    buy_and_hold_equity,
    optimize_weights,
    portfolio_stats,
)


def mu_cov(returns: dict, variances: dict, corr: float = 0.0):
    """Build (expected_returns Series, covariance DataFrame) from diagonal vars."""
    tickers = list(returns)
    mu = pd.Series(returns)
    stds = {t: variances[t] ** 0.5 for t in tickers}
    cov = pd.DataFrame(index=tickers, columns=tickers, dtype=float)
    for a in tickers:
        for b in tickers:
            if a == b:
                cov.loc[a, b] = variances[a]
            else:
                cov.loc[a, b] = corr * stds[a] * stds[b]
    return mu, cov


# ---------------------------------------------------------------------------
# Constraints (apply to every objective)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("objective", ["equal_weight", "min_volatility", "max_sharpe"])
def test_weights_sum_to_one_and_nonnegative(objective):
    mu, cov = mu_cov(
        {"A": 0.10, "B": 0.06, "C": 0.03},
        {"A": 0.04, "B": 0.02, "C": 0.01},
        corr=0.1,
    )
    w = optimize_weights(mu, cov, objective=objective, risk_free_rate=0.02)
    assert set(w) == {"A", "B", "C"}
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
    for wi in w.values():
        assert wi >= -1e-9  # long-only


def test_equal_weight_objective_is_uniform():
    mu, cov = mu_cov({"A": 0.1, "B": 0.2, "C": 0.3}, {"A": 0.04, "B": 0.04, "C": 0.04})
    w = optimize_weights(mu, cov, objective="equal_weight")
    for wi in w.values():
        assert wi == pytest.approx(1.0 / 3, abs=1e-9)


def test_single_asset_gets_full_weight():
    mu, cov = mu_cov({"A": 0.1}, {"A": 0.04})
    for obj in ("equal_weight", "min_volatility", "max_sharpe"):
        w = optimize_weights(mu, cov, objective=obj)
        assert w == {"A": pytest.approx(1.0)}


# ---------------------------------------------------------------------------
# Min volatility — should tilt toward the lowest-variance asset
# ---------------------------------------------------------------------------


def test_min_volatility_favours_low_variance_asset():
    # Uncorrelated assets → min-var weights ∝ 1/variance.
    mu, cov = mu_cov(
        {"A": 0.05, "B": 0.05, "C": 0.05},
        {"A": 0.01, "B": 0.04, "C": 0.09},
        corr=0.0,
    )
    w = optimize_weights(mu, cov, objective="min_volatility")
    assert w["A"] > w["B"] > w["C"]
    # Closed form for uncorrelated case: w_i ∝ 1/var_i.
    inv = np.array([1 / 0.01, 1 / 0.04, 1 / 0.09])
    expected = inv / inv.sum()
    assert w["A"] == pytest.approx(expected[0], abs=2e-3)


def test_min_volatility_not_above_equal_weight_vol():
    mu, cov = mu_cov(
        {"A": 0.05, "B": 0.06, "C": 0.07},
        {"A": 0.01, "B": 0.04, "C": 0.09},
        corr=0.2,
    )
    w_min = optimize_weights(mu, cov, objective="min_volatility")
    w_eq = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    _, vol_min, _ = portfolio_stats(w_min, mu, cov)
    _, vol_eq, _ = portfolio_stats(w_eq, mu, cov)
    assert vol_min <= vol_eq + 1e-9


# ---------------------------------------------------------------------------
# Max Sharpe — should tilt toward the high-return / low-vol asset
# ---------------------------------------------------------------------------


def test_max_sharpe_favours_best_asset():
    # Equal variance, uncorrelated → highest expected return wins.
    mu, cov = mu_cov(
        {"A": 0.12, "B": 0.06, "C": 0.02},
        {"A": 0.04, "B": 0.04, "C": 0.04},
        corr=0.0,
    )
    w = optimize_weights(mu, cov, objective="max_sharpe", risk_free_rate=0.0)
    assert w["A"] == max(w.values())
    assert w["A"] > w["B"] > w["C"]


def test_max_sharpe_beats_equal_weight_sharpe():
    mu, cov = mu_cov(
        {"A": 0.12, "B": 0.06, "C": 0.03},
        {"A": 0.05, "B": 0.03, "C": 0.02},
        corr=0.1,
    )
    w_ms = optimize_weights(mu, cov, objective="max_sharpe", risk_free_rate=0.02)
    w_eq = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    _, _, sharpe_ms = portfolio_stats(w_ms, mu, cov, risk_free_rate=0.02)
    _, _, sharpe_eq = portfolio_stats(w_eq, mu, cov, risk_free_rate=0.02)
    assert sharpe_ms >= sharpe_eq - 1e-9


def test_max_sharpe_zero_volatility_falls_back_to_equal_weight():
    mu, cov = mu_cov({"A": 0.05, "B": 0.10}, {"A": 0.0, "B": 0.0})
    w = optimize_weights(mu, cov, objective="max_sharpe", risk_free_rate=0.02)
    assert w == {"A": pytest.approx(0.5), "B": pytest.approx(0.5)}


def test_optimizer_failure_raises_clear_error(monkeypatch):
    class FailedResult:
        success = False
        message = "synthetic failure"
        x = np.array([0.5, 0.5])

    monkeypatch.setattr(portfolio_module, "minimize", lambda *_a, **_k: FailedResult())
    mu, cov = mu_cov({"A": 0.1, "B": 0.08}, {"A": 0.04, "B": 0.02})

    with pytest.raises(ValueError, match="Portfolio optimization failed"):
        optimize_weights(mu, cov, objective="min_volatility")


def test_non_finite_optimizer_result_raises(monkeypatch):
    class BadResult:
        success = True
        message = "ok"
        x = np.array([np.nan, 1.0])

    monkeypatch.setattr(portfolio_module, "minimize", lambda *_a, **_k: BadResult())
    mu, cov = mu_cov({"A": 0.1, "B": 0.08}, {"A": 0.04, "B": 0.02})

    with pytest.raises(ValueError, match="non-finite weights"):
        optimize_weights(mu, cov, objective="min_volatility")


def test_invalid_objective_raises():
    mu, cov = mu_cov({"A": 0.1, "B": 0.1}, {"A": 0.04, "B": 0.04})
    with pytest.raises(ValueError):
        optimize_weights(mu, cov, objective="max_return")


# ---------------------------------------------------------------------------
# annualized_stats + buy_and_hold_equity
# ---------------------------------------------------------------------------


def make_prices(n=260, trends=None) -> pd.DataFrame:
    trends = trends or {"AAA": 0.0008, "BBB": 0.0003}
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {t: [100.0 * ((1.0 + r) ** i) for i in range(n)] for t, r in trends.items()},
        index=idx,
    )


def test_annualized_stats_shapes_and_values():
    prices = make_prices()
    mu, cov = annualized_stats(prices)
    assert list(mu.index) == ["AAA", "BBB"]
    assert cov.shape == (2, 2)
    # Constant-growth series → expected annual return ≈ daily_rate * 252.
    assert mu["AAA"] == pytest.approx(0.0008 * 252, rel=1e-6)
    # Covariance of a perfectly geometric series is ~0.
    assert abs(cov.loc["AAA", "AAA"]) < 1e-12


def test_annualized_stats_requires_two_returns():
    prices = make_prices(2)  # only 1 daily return after dropna
    with pytest.raises(ValueError, match="at least 2 daily returns"):
        annualized_stats(prices)


def test_annualized_stats_rejects_non_positive_prices():
    prices = make_prices(5)
    prices.iloc[2, 0] = 0.0
    with pytest.raises(ValueError, match="strictly positive"):
        annualized_stats(prices)


def test_annualized_stats_rejects_non_finite_prices():
    prices = make_prices(5)
    prices.iloc[2, 0] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        annualized_stats(prices)


def test_buy_and_hold_equity_starts_at_capital():
    prices = make_prices(120)
    eq = buy_and_hold_equity(prices, {"AAA": 0.5, "BBB": 0.5}, 100_000.0)
    assert eq.iloc[0] == pytest.approx(100_000.0)
    assert len(eq) == 120


def test_buy_and_hold_single_asset_tracks_price():
    prices = make_prices(60)
    eq = buy_and_hold_equity(prices, {"AAA": 1.0, "BBB": 0.0}, 50_000.0)
    expected_final = 50_000.0 * (prices["AAA"].iloc[-1] / prices["AAA"].iloc[0])
    assert eq.iloc[-1] == pytest.approx(expected_final, rel=1e-9)


def test_buy_and_hold_rejects_invalid_weights():
    prices = make_prices(60)
    with pytest.raises(ValueError, match="sum to 1"):
        buy_and_hold_equity(prices, {"AAA": 0.8, "BBB": 0.1}, 50_000.0)
    with pytest.raises(ValueError, match="non-negative"):
        buy_and_hold_equity(prices, {"AAA": 1.1, "BBB": -0.1}, 50_000.0)
