"""
Unit tests for app.metrics.compute_metrics.

All tests use synthetic equity curves so they run instantly without network calls.
"""

import numpy as np
import pandas as pd
import pytest

from app.metrics import TRADING_DAYS_PER_YEAR, compute_metrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_equity(returns: list, initial: float = 100_000.0) -> pd.Series:
    """Build a cumulative equity series from a list of daily returns."""
    r = pd.Series([0.0] + list(returns))  # prepend 0 so day-0 = initial
    return initial * (1 + r).cumprod()


def flat_equity(n: int = 252, initial: float = 100_000.0) -> pd.Series:
    return pd.Series([initial] * n)


# ---------------------------------------------------------------------------
# Basic return metrics
# ---------------------------------------------------------------------------

def test_total_return_doubles():
    equity = pd.Series([100_000.0, 200_000.0])
    m = compute_metrics(equity)
    assert abs(m["total_return"] - 1.0) < 1e-9


def test_total_return_flat():
    m = compute_metrics(flat_equity(252))
    assert abs(m["total_return"]) < 1e-9


def test_total_return_negative():
    equity = pd.Series([100_000.0, 80_000.0])
    m = compute_metrics(equity)
    assert abs(m["total_return"] - (-0.20)) < 1e-9


def test_cagr_approx_10_percent():
    """Equity that grows linearly to 110 % over exactly 252 bars → CAGR ≈ 10 %."""
    n = TRADING_DAYS_PER_YEAR
    equity = pd.Series([100_000.0 * (1.10 ** (i / n)) for i in range(n)])
    m = compute_metrics(equity)
    assert abs(m["cagr"] - 0.10) < 1e-3


def test_cagr_matches_total_return_roughly_one_year():
    """Over ~252 days CAGR and total_return should be close."""
    returns = [0.001] * TRADING_DAYS_PER_YEAR
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert abs(m["cagr"] - m["total_return"]) < 0.02


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown_non_positive():
    returns = [0.01, 0.02, -0.15, 0.01, 0.02]
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert m["max_drawdown"] <= 0.0


def test_max_drawdown_monotone_up():
    """A monotonically rising equity has zero drawdown."""
    equity = pd.Series([100_000.0 + i * 100 for i in range(100)])
    m = compute_metrics(equity)
    assert m["max_drawdown"] == 0.0


def test_max_drawdown_known_value():
    """
    Equity: 100 → 200 → 100 → 150
    Peak at 200, trough at 100 → max drawdown = (100−200)/200 = −0.50.
    """
    equity = pd.Series([100.0, 200.0, 100.0, 150.0])
    m = compute_metrics(equity)
    assert abs(m["max_drawdown"] - (-0.50)) < 1e-9


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

def test_volatility_non_negative():
    equity = make_equity([0.01, -0.01, 0.02, -0.02])
    m = compute_metrics(equity)
    assert m["volatility"] >= 0.0


def test_volatility_flat_is_zero():
    m = compute_metrics(flat_equity(252))
    assert m["volatility"] == 0.0


# ---------------------------------------------------------------------------
# Sharpe ratio
# ---------------------------------------------------------------------------

def test_sharpe_flat_equity():
    """Flat equity → all returns are zero → Sharpe = 0."""
    m = compute_metrics(flat_equity(252))
    assert m["sharpe_ratio"] == 0.0


def test_sharpe_positive_for_uptrend():
    # Alternating small returns so std > 0, mean > 0 → Sharpe > 0
    returns = [0.001 if i % 2 == 0 else 0.002 for i in range(252)]
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert m["sharpe_ratio"] > 0.0


def test_sharpe_negative_for_downtrend():
    # Alternating small negative returns so std > 0, mean < 0 → Sharpe < 0
    returns = [-0.001 if i % 2 == 0 else -0.002 for i in range(252)]
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert m["sharpe_ratio"] < 0.0


# ---------------------------------------------------------------------------
# Win rate
# ---------------------------------------------------------------------------

def test_win_rate_bounds():
    returns = [0.01, -0.01, 0.02, -0.02, 0.03]
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert 0.0 <= m["win_rate"] <= 1.0


def test_win_rate_all_positive():
    returns = [0.001] * 50
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert m["win_rate"] == pytest.approx(1.0)


def test_win_rate_all_negative():
    returns = [-0.001] * 50
    equity = make_equity(returns)
    m = compute_metrics(equity)
    assert m["win_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_too_short_raises():
    with pytest.raises(ValueError, match="at least 2"):
        compute_metrics(pd.Series([100_000.0]))


def test_two_points_works():
    m = compute_metrics(pd.Series([100_000.0, 110_000.0]))
    assert m["total_return"] == pytest.approx(0.10)


def test_num_days_correct():
    equity = flat_equity(100)
    m = compute_metrics(equity)
    assert m["num_days"] == 100
