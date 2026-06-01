"""
Unit tests for app.portfolio.stress_test.

Deterministic synthetic price frames; no network.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.portfolio import align_prices, stress_test

_PARAMS = {
    "AAA": (0.0006, 0.012, 0.10),
    "BBB": (0.0004, 0.016, 0.13),
    "CCC": (0.0002, 0.008, 0.07),
    "SPY": (0.0005, 0.010, 0.11),
}


def make_prices(n: int = 400, start: str = "2018-01-01", tickers=("AAA", "BBB", "CCC", "SPY")):
    idx = pd.date_range(start, periods=n, freq="B")
    data = {}
    for t in tickers:
        base, amp, freq = _PARAMS.get(t, (0.0003, 0.011, 0.09))
        prices = [100.0]
        for i in range(1, n):
            r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.29 * i)
            prices.append(prices[-1] * (1.0 + r))
        data[t] = prices
    return pd.DataFrame(data, index=idx)


def split(prices: pd.DataFrame, benchmark="SPY"):
    tickers = [c for c in prices.columns if c != benchmark]
    return prices[tickers], prices[benchmark]


def equal_weights(tickers):
    return {t: 1.0 / len(tickers) for t in tickers}


def date_str(prices, i):
    return str(prices.index[i].date())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_full_period_and_scenarios_generated():
    prices = make_prices(400)
    assets, bench = split(prices)
    scn = [{"name": "Window A", "start_date": date_str(prices, 50), "end_date": date_str(prices, 120)}]
    d = stress_test(assets, bench, equal_weights(list(assets.columns)), scn)

    assert "full_period_metrics" in d and "benchmark_full_period_metrics" in d
    assert len(d["full_equity_curve"]) == len(prices)
    assert len(d["benchmark_equity_curve"]) == len(prices)
    assert d["full_equity_curve"][0]["value"] == pytest.approx(100_000.0)
    assert d["benchmark_equity_curve"][0]["value"] == pytest.approx(100_000.0)
    assert len(d["scenarios"]) == 1


def test_scenario_metrics_fields():
    prices = make_prices(400)
    assets, bench = split(prices)
    scn = [{"name": "W", "start_date": date_str(prices, 60), "end_date": date_str(prices, 130)}]
    s = stress_test(assets, bench, equal_weights(list(assets.columns)), scn)["scenarios"][0]
    for key in (
        "total_return", "max_drawdown", "annualized_volatility",
        "worst_day_return", "best_day_return", "benchmark_total_return",
        "benchmark_max_drawdown", "excess_return", "correlation_matrix",
        "portfolio_equity_curve", "benchmark_equity_curve",
    ):
        assert key in s, key
    assert s["worst_day_return"] <= s["best_day_return"]
    assert s["max_drawdown"] <= 1e-9  # drawdowns are ≤ 0
    assert s["annualized_volatility"] >= 0


def test_excess_return_is_portfolio_minus_benchmark():
    prices = make_prices(400)
    assets, bench = split(prices)
    scn = [{"name": "W", "start_date": date_str(prices, 40), "end_date": date_str(prices, 100)}]
    s = stress_test(assets, bench, equal_weights(list(assets.columns)), scn)["scenarios"][0]
    assert s["excess_return"] == pytest.approx(
        s["total_return"] - s["benchmark_total_return"], abs=1e-9
    )


def test_total_return_matches_compounded_window_returns():
    prices = make_prices(300)
    assets, bench = split(prices)
    w = equal_weights(list(assets.columns))
    i0, i1 = 80, 140
    scn = [{"name": "W", "start_date": date_str(prices, i0), "end_date": date_str(prices, i1)}]
    s = stress_test(assets, bench, w, scn)["scenarios"][0]

    # Recompute: constant-weight daily returns over [i0..i1] (the move into the
    # first scenario day, from the prior close, is included), compounded.
    wv = np.array([w[t] for t in assets.columns])
    asset_ret = assets.pct_change(fill_method=None)
    port_ret = (asset_ret.to_numpy() @ wv)
    factor = np.prod(1.0 + port_ret[i0 : i1 + 1])
    assert s["total_return"] == pytest.approx(factor - 1.0, abs=1e-9)


def test_correlation_matrix_during_scenario():
    prices = make_prices(400)
    assets, bench = split(prices)
    scn = [{"name": "W", "start_date": date_str(prices, 50), "end_date": date_str(prices, 150)}]
    s = stress_test(assets, bench, equal_weights(list(assets.columns)), scn)["scenarios"][0]
    corr = s["correlation_matrix"]
    tickers = list(assets.columns)
    assert set(corr) == set(tickers)
    for a in tickers:
        assert corr[a][a] == pytest.approx(1.0, abs=1e-6)
        for b in tickers:
            assert corr[a][b] == pytest.approx(corr[b][a], abs=1e-6)


def test_custom_weights_respected():
    prices = make_prices(300)
    assets, bench = split(prices)
    tickers = list(assets.columns)
    # Put all weight on the first asset → portfolio == that asset.
    w = {t: (1.0 if i == 0 else 0.0) for i, t in enumerate(tickers)}
    scn = [{"name": "W", "start_date": date_str(prices, 50), "end_date": date_str(prices, 120)}]
    s = stress_test(assets, bench, w, scn)["scenarios"][0]

    asset_ret = assets[tickers[0]].pct_change(fill_method=None)
    factor = float(np.prod(1.0 + asset_ret.iloc[50:121].to_numpy()))
    assert s["total_return"] == pytest.approx(factor - 1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_scenario_outside_data_raises():
    prices = make_prices(200, start="2018-01-01")
    assets, bench = split(prices)
    scn = [{"name": "Way Future", "start_date": "2030-01-01", "end_date": "2030-06-01"}]
    with pytest.raises(ValueError, match="does not overlap"):
        stress_test(assets, bench, equal_weights(list(assets.columns)), scn)


def test_multiple_scenarios():
    prices = make_prices(400)
    assets, bench = split(prices)
    scn = [
        {"name": "A", "start_date": date_str(prices, 30), "end_date": date_str(prices, 80)},
        {"name": "B", "start_date": date_str(prices, 200), "end_date": date_str(prices, 260)},
    ]
    res = stress_test(assets, bench, equal_weights(list(assets.columns)), scn)
    assert [s["name"] for s in res["scenarios"]] == ["A", "B"]
