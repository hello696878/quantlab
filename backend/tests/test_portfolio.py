"""
Unit tests for app.portfolio (pure equal-weight portfolio logic).

All inputs are deterministic synthetic price frames — no network, no DB.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.portfolio import (
    align_prices,
    drawdown_series,
    run_equal_weight_portfolio,
)


def make_prices(n: int = 260, start: str = "2018-01-01", trends=None) -> pd.DataFrame:
    """Build an N-row price frame; each ticker grows at its own daily rate."""
    trends = trends or {"AAA": 0.0010, "BBB": 0.0005, "CCC": -0.0002}
    idx = pd.date_range(start, periods=n, freq="B")
    data = {}
    for ticker, rate in trends.items():
        data[ticker] = [100.0 * ((1.0 + rate) ** i) for i in range(n)]
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


def test_align_prices_keeps_common_dates_only():
    idx_a = pd.date_range("2020-01-01", periods=10, freq="B")
    idx_b = pd.date_range("2020-01-03", periods=10, freq="B")  # starts 2 days later
    a = pd.Series(range(10), index=idx_a, dtype=float)
    b = pd.Series(range(10), index=idx_b, dtype=float)

    aligned = align_prices({"A": a, "B": b})
    assert list(aligned.columns) == ["A", "B"]
    assert aligned.index.equals(idx_a.intersection(idx_b))
    assert not aligned.isna().any().any()


def test_align_prices_preserves_ticker_order():
    p = make_prices(20, trends={"ZZZ": 0.001, "AAA": 0.001})
    aligned = align_prices({"ZZZ": p["ZZZ"], "AAA": p["AAA"]})
    assert list(aligned.columns) == ["ZZZ", "AAA"]


# ---------------------------------------------------------------------------
# Equity / weights basics
# ---------------------------------------------------------------------------


def test_equity_starts_at_initial_capital():
    res = run_equal_weight_portfolio(make_prices(), initial_capital=100_000.0)
    assert res.equity.iloc[0] == pytest.approx(100_000.0)
    assert len(res.equity) == 260


def test_initial_weights_are_equal():
    res = run_equal_weight_portfolio(make_prices(), rebalance_frequency="none")
    first = res.weights[0]["weights"]
    assert set(first) == {"AAA", "BBB", "CCC"}
    for w in first.values():
        assert w == pytest.approx(1.0 / 3, abs=1e-6)


def test_weights_per_day_present():
    res = run_equal_weight_portfolio(make_prices())
    assert len(res.weights) == len(res.equity)
    # Weights on each day sum to ~1.
    for wp in res.weights:
        assert sum(wp["weights"].values()) == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# No-rebalance behaviour (drift)
# ---------------------------------------------------------------------------


def test_no_rebalance_has_no_events_and_drifts():
    res = run_equal_weight_portfolio(make_prices(), rebalance_frequency="none")
    assert res.rebalance_events == []
    # With divergent trends the final weights must have drifted away from equal.
    final = res.weights[-1]["weights"]
    assert abs(final["AAA"] - 1.0 / 3) > 1e-3


def test_no_rebalance_matches_buy_and_hold_basket():
    """No-rebalance equity equals holding the initial equal-dollar basket."""
    prices = make_prices(120)
    res = run_equal_weight_portfolio(
        prices, initial_capital=90_000.0, rebalance_frequency="none"
    )
    # Buy-and-hold: 30k in each asset, value = sum over assets of 30k * price/price0.
    expected = sum(
        30_000.0 * (prices[t] / prices[t].iloc[0]) for t in prices.columns
    )
    assert res.equity.iloc[-1] == pytest.approx(float(expected.iloc[-1]), rel=1e-9)


# ---------------------------------------------------------------------------
# Rebalancing behaviour
# ---------------------------------------------------------------------------


def test_monthly_rebalance_generates_events():
    res = run_equal_weight_portfolio(
        make_prices(260), rebalance_frequency="monthly", transaction_cost_bps=10
    )
    # ~12 month boundaries over ~12 months of business days.
    assert len(res.rebalance_events) >= 10
    for ev in res.rebalance_events:
        assert ev["turnover"] >= 0.0
        assert ev["cost"] >= 0.0


def test_rebalance_resets_weights_to_equal():
    res = run_equal_weight_portfolio(make_prices(260), rebalance_frequency="monthly")
    rebal_dates = {ev["date"] for ev in res.rebalance_events}
    for wp in res.weights:
        if wp["date"] in rebal_dates:
            for w in wp["weights"].values():
                assert w == pytest.approx(1.0 / 3, abs=1e-6)


def test_quarterly_fewer_events_than_monthly():
    monthly = run_equal_weight_portfolio(make_prices(260), rebalance_frequency="monthly")
    quarterly = run_equal_weight_portfolio(
        make_prices(260), rebalance_frequency="quarterly"
    )
    yearly = run_equal_weight_portfolio(make_prices(260), rebalance_frequency="yearly")
    assert len(quarterly.rebalance_events) < len(monthly.rebalance_events)
    assert len(yearly.rebalance_events) <= len(quarterly.rebalance_events)


# ---------------------------------------------------------------------------
# Transaction cost from turnover
# ---------------------------------------------------------------------------


def test_transaction_cost_reduces_equity():
    prices = make_prices(260)
    free = run_equal_weight_portfolio(
        prices, rebalance_frequency="monthly", transaction_cost_bps=0
    )
    costly = run_equal_weight_portfolio(
        prices, rebalance_frequency="monthly", transaction_cost_bps=50
    )
    assert costly.equity.iloc[-1] < free.equity.iloc[-1]
    # Zero-cost rebalances still record events but with zero cost.
    assert all(ev["cost"] == 0.0 for ev in free.rebalance_events)
    assert any(ev["cost"] > 0.0 for ev in costly.rebalance_events)


def test_identical_assets_have_zero_turnover():
    """If all assets move identically, weights never drift → ~zero turnover."""
    idx = pd.date_range("2018-01-01", periods=260, freq="B")
    series = pd.Series([100.0 * (1.001 ** i) for i in range(260)], index=idx)
    prices = pd.DataFrame({"AAA": series, "BBB": series.copy(), "CCC": series.copy()})
    res = run_equal_weight_portfolio(
        prices, rebalance_frequency="monthly", transaction_cost_bps=100
    )
    for ev in res.rebalance_events:
        assert ev["turnover"] == pytest.approx(0.0, abs=1e-9)
        assert ev["cost"] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Drawdown helper
# ---------------------------------------------------------------------------


def test_drawdown_series_non_positive_and_zero_at_peak():
    equity = pd.Series(
        [100.0, 110.0, 99.0, 120.0],
        index=pd.date_range("2020-01-01", periods=4, freq="B"),
    )
    dd = drawdown_series(equity)
    assert (dd <= 1e-12).all()
    assert dd.iloc[0] == pytest.approx(0.0)
    assert dd.iloc[1] == pytest.approx(0.0)  # new peak
    assert dd.iloc[2] == pytest.approx((99.0 - 110.0) / 110.0)
    assert dd.iloc[3] == pytest.approx(0.0)  # new peak
