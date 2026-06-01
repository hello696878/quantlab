"""
Unit tests for app.portfolio.run_walk_forward_optimization.

Deterministic synthetic price frames with genuine return variance so the
optimizer is well-posed; no network, no DB.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import app.portfolio as portfolio_module
from app.portfolio import (
    annualized_stats,
    optimize_weights,
    run_walk_forward_optimization,
)

_PARAMS = {
    "AAA": (0.0006, 0.012, 0.10),
    "BBB": (0.0004, 0.016, 0.13),
    "CCC": (0.0002, 0.008, 0.07),
}


def make_prices(n: int = 1200, tickers=("AAA", "BBB", "CCC")) -> pd.DataFrame:
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    data = {}
    for t in tickers:
        base, amp, freq = _PARAMS.get(t, (0.0003, 0.011, 0.09))
        prices = [100.0]
        for i in range(1, n):
            r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.29 * i)
            prices.append(prices[-1] * (1.0 + r))
        data[t] = prices
    return pd.DataFrame(data, index=idx)


def run(prices=None, **kw):
    params = dict(
        train_window_days=252,
        test_window_days=63,
        step_days=63,
        objective="max_sharpe",
        risk_free_rate=0.02,
        initial_capital=100_000.0,
        transaction_cost_bps=10.0,
    )
    params.update(kw)
    return run_walk_forward_optimization(prices if prices is not None else make_prices(), **params)


# ---------------------------------------------------------------------------
# Window counting
# ---------------------------------------------------------------------------


def test_correct_number_of_windows():
    n = 1000
    train, test, step = 252, 63, 63
    res = run(make_prices(n), train_window_days=train, test_window_days=test, step_days=step)
    expected = (n - train - test) // step + 1
    assert len(res.windows) == expected


def test_step_changes_window_count():
    prices = make_prices(1000)
    big_step = run(prices, step_days=126)
    small_step = run(prices, step_days=63)
    assert len(small_step.windows) > len(big_step.windows)


def test_insufficient_data_raises():
    prices = make_prices(200)
    with pytest.raises(ValueError, match="need at least"):
        run(prices, train_window_days=252, test_window_days=63)


@pytest.mark.parametrize("field", ["train_window_days", "test_window_days", "step_days"])
def test_non_positive_window_inputs_raise(field):
    with pytest.raises(ValueError, match=field):
        run(**{field: 0})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_capital", 0.0),
        ("transaction_cost_bps", -1.0),
        ("transaction_cost_bps", 10_000.0),
    ],
)
def test_invalid_capital_or_cost_inputs_raise(field, value):
    with pytest.raises(ValueError, match=field):
        run(**{field: value})


# ---------------------------------------------------------------------------
# Weight validity in every window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("objective", ["equal_weight", "min_volatility", "max_sharpe"])
def test_weights_valid_in_every_window(objective):
    res = run(objective=objective)
    for w in res.windows:
        total = sum(w["weights"].values())
        assert total == pytest.approx(1.0, abs=1e-6)
        for wi in w["weights"].values():
            assert wi >= -1e-9


def test_equal_weight_objective_uniform_every_window():
    res = run(objective="equal_weight")
    for w in res.windows:
        for wi in w["weights"].values():
            assert wi == pytest.approx(1.0 / 3, abs=1e-6)


# ---------------------------------------------------------------------------
# No data leakage — weights depend only on the training slice
# ---------------------------------------------------------------------------


def test_no_leakage_weights_match_training_only():
    prices = make_prices(1000)
    train, test, step = 252, 63, 63
    res = run(prices, train_window_days=train, test_window_days=test, step_days=step)

    # Independently recompute the first two windows' weights from training data.
    for k in range(2):
        train_start = k * step
        train_slice = prices.iloc[train_start : train_start + train]
        mu, cov = annualized_stats(train_slice)
        expected = optimize_weights(mu, cov, "max_sharpe", 0.02)
        got = res.windows[k]["weights"]
        for t in expected:
            assert got[t] == pytest.approx(expected[t], abs=1e-9)


def test_weights_change_when_only_future_data_changes():
    """Mutating data strictly AFTER a window's training slice must not alter
    that window's weights (proves no look-ahead)."""
    prices = make_prices(1000)
    base = run(prices, train_window_days=252, test_window_days=63, step_days=63)

    # Corrupt the last 100 rows (well after window 0's training slice 0:252).
    corrupted = prices.copy()
    corrupted.iloc[-100:] = corrupted.iloc[-100:] * 1.5
    after = run(corrupted, train_window_days=252, test_window_days=63, step_days=63)

    assert base.windows[0]["weights"] == pytest.approx(after.windows[0]["weights"])


# ---------------------------------------------------------------------------
# Turnover & transaction cost
# ---------------------------------------------------------------------------


def test_first_window_turnover_is_full_entry():
    res = run()
    # Entry from cash → turnover == sum(weights) == 1.0 (fully invested).
    assert res.windows[0]["turnover"] == pytest.approx(1.0, abs=1e-6)


def test_turnover_in_valid_range():
    res = run()
    for w in res.windows:
        assert 0.0 - 1e-9 <= w["turnover"] <= 2.0 + 1e-9


def test_equal_weight_turnover_zero_after_entry():
    res = run(objective="equal_weight")
    # Equal-weight target never changes → no turnover after the first window.
    for w in res.windows[1:]:
        assert w["turnover"] == pytest.approx(0.0, abs=1e-9)


def test_transaction_cost_reduces_final_equity():
    prices = make_prices(1000)
    free = run(prices, transaction_cost_bps=0)
    costly = run(prices, transaction_cost_bps=100)
    assert costly.stitched_equity.iloc[-1] < free.stitched_equity.iloc[-1]


def test_transaction_cost_amount_and_window_metrics_include_entry_cost():
    idx = pd.date_range("2020-01-01", periods=12, freq="B")
    prices = pd.DataFrame({"AAA": 100.0, "BBB": 100.0}, index=idx)

    res = run(
        prices,
        train_window_days=5,
        test_window_days=3,
        step_days=3,
        objective="equal_weight",
        initial_capital=100_000.0,
        transaction_cost_bps=10.0,
    )

    assert res.windows[0]["turnover"] == pytest.approx(1.0)
    assert res.windows[0]["transaction_cost"] == pytest.approx(100.0)
    assert res.stitched_equity.iloc[1] == pytest.approx(99_900.0)
    assert res.windows[0]["test_metrics"]["total_return"] == pytest.approx(-0.001)


def test_turnover_cost_that_would_deplete_equity_raises(monkeypatch):
    prices = make_prices(400, tickers=("AAA", "BBB"))
    weight_sequence = [
        {"AAA": 1.0, "BBB": 0.0},
        {"AAA": 0.0, "BBB": 1.0},
    ]
    calls = {"n": 0}

    def fake_optimize_weights(mu, cov, objective, risk_free_rate=0.0):
        i = min(calls["n"], len(weight_sequence) - 1)
        calls["n"] += 1
        return weight_sequence[i]

    monkeypatch.setattr(portfolio_module, "optimize_weights", fake_optimize_weights)

    with pytest.raises(ValueError, match="would deplete portfolio equity"):
        run(
            prices,
            train_window_days=50,
            test_window_days=20,
            step_days=20,
            objective="max_sharpe",
            transaction_cost_bps=6000.0,
        )


# ---------------------------------------------------------------------------
# Stitched curves + benchmark + stability
# ---------------------------------------------------------------------------


def test_stitched_and_benchmark_anchored_at_capital():
    res = run(initial_capital=100_000.0)
    assert res.stitched_equity.iloc[0] == pytest.approx(100_000.0)
    assert res.benchmark_equity.iloc[0] == pytest.approx(100_000.0)
    assert res.stitched_equity.index.equals(res.benchmark_equity.index)
    assert len(res.stitched_equity) > 1


def test_overlapping_windows_rebalance_at_step_boundary(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=13, freq="B")
    prices = pd.DataFrame(
        {
            "AAA": [100.0 * (1.1 ** i) for i in range(len(idx))],
            "BBB": [100.0 for _ in range(len(idx))],
        },
        index=idx,
    )
    weight_sequence = [
        {"AAA": 1.0, "BBB": 0.0},
        {"AAA": 0.0, "BBB": 1.0},
        {"AAA": 1.0, "BBB": 0.0},
    ]
    calls = {"n": 0}

    def fake_optimize_weights(mu, cov, objective, risk_free_rate=0.0):
        i = min(calls["n"], len(weight_sequence) - 1)
        calls["n"] += 1
        return weight_sequence[i]

    monkeypatch.setattr(portfolio_module, "optimize_weights", fake_optimize_weights)

    res = run(
        prices,
        train_window_days=5,
        test_window_days=4,
        step_days=2,
        objective="max_sharpe",
        initial_capital=100.0,
        transaction_cost_bps=0.0,
    )

    # Window 0 contributes days 5-6 with AAA exposure; window 1 starts at day 7
    # and contributes BBB exposure, so day 7 should not receive AAA's +10% move.
    assert res.stitched_equity.loc[idx[5]] == pytest.approx(110.0)
    assert res.stitched_equity.loc[idx[6]] == pytest.approx(121.0)
    assert res.stitched_equity.loc[idx[7]] == pytest.approx(121.0)


def test_overlapping_windows_produce_unique_monotonic_stitched_dates():
    res = run(
        make_prices(500),
        train_window_days=100,
        test_window_days=60,
        step_days=20,
    )
    idx = res.stitched_equity.index
    assert idx.is_monotonic_increasing
    assert len(idx) == len(idx.unique())


def test_weight_stability_structure():
    res = run()
    stab = res.weight_stability
    assert set(stab["average_weight_by_asset"]) == {"AAA", "BBB", "CCC"}
    assert stab["max_turnover"] >= stab["average_turnover"] - 1e-9
    for t in ("AAA", "BBB", "CCC"):
        lo = stab["min_weight_by_asset"][t]
        hi = stab["max_weight_by_asset"][t]
        avg = stab["average_weight_by_asset"][t]
        assert lo - 1e-9 <= avg <= hi + 1e-9


def test_test_metrics_present_per_window():
    res = run()
    for w in res.windows:
        for key in ("total_return", "cagr", "sharpe_ratio", "max_drawdown", "num_days"):
            assert key in w["test_metrics"]
