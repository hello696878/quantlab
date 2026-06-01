"""
API tests for POST /portfolio/stress-test.

main._fetch is monkeypatched to deterministic synthetic prices; no network.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

_PARAMS = {
    "SPY": (0.0005, 0.010, 0.10),
    "QQQ": (0.0007, 0.016, 0.13),
    "GLD": (0.0002, 0.008, 0.07),
    "TLT": (0.0001, 0.006, 0.05),
}

# Synthetic data spans ~2018-01-01 .. ~2021-10 (1000 business days).
_DATES = pd.date_range("2018-01-01", periods=1000, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    base, amp, freq = _PARAMS.get(ticker.upper(), (0.0003, 0.011, 0.09))
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.31 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def _scn_dates(i0: int, i1: int):
    return str(_DATES[i0].date()), str(_DATES[i1].date())


def base_request(**overrides) -> dict:
    s0, e0 = _scn_dates(100, 180)
    s1, e1 = _scn_dates(400, 480)
    req = {
        "tickers": ["SPY", "QQQ", "GLD", "TLT"],
        "start_date": "2018-01-01",
        "end_date": "2021-12-31",
        "initial_capital": 100000,
        "transaction_cost_bps": 0,
        "benchmark_ticker": "SPY",
        "scenarios": [
            {"name": "Window A", "start_date": s0, "end_date": e0},
            {"name": "Window B", "start_date": s1, "end_date": e1},
        ],
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_valid_stress_test_equal_weight(client):
    resp = client.post("/portfolio/stress-test", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in (
        "weights", "full_period_metrics", "benchmark_full_period_metrics",
        "full_equity_curve", "benchmark_equity_curve", "scenarios", "historical_note",
    ):
        assert key in data, key
    # Equal weight by default.
    for w in data["weights"].values():
        assert w == pytest.approx(0.25, abs=1e-6)
    assert len(data["scenarios"]) == 2


def test_valid_stress_test_custom_weights(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(weights={"SPY": 0.4, "QQQ": 0.3, "GLD": 0.2, "TLT": 0.1}),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["weights"]["SPY"] == pytest.approx(0.4, abs=1e-6)


def test_scenario_metrics_and_curves(client):
    data = client.post("/portfolio/stress-test", json=base_request()).json()
    s = data["scenarios"][0]
    for key in (
        "total_return", "max_drawdown", "annualized_volatility",
        "worst_day_return", "best_day_return", "benchmark_total_return",
        "benchmark_max_drawdown", "excess_return", "correlation_matrix",
        "portfolio_equity_curve", "benchmark_equity_curve",
    ):
        assert key in s, key
    assert s["excess_return"] == pytest.approx(
        s["total_return"] - s["benchmark_total_return"], abs=1e-6
    )
    assert s["worst_day_return"] <= s["best_day_return"]
    assert len(s["portfolio_equity_curve"]) > 1
    assert len(s["benchmark_equity_curve"]) == len(s["portfolio_equity_curve"])
    assert s["portfolio_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)


def test_correlation_matrix_present(client):
    data = client.post("/portfolio/stress-test", json=base_request()).json()
    corr = data["scenarios"][0]["correlation_matrix"]
    tickers = data["tickers"]
    assert set(corr) == set(tickers)
    for a in tickers:
        assert corr[a][a] == pytest.approx(1.0, abs=1e-6)


def test_full_equity_curve_generated(client):
    data = client.post("/portfolio/stress-test", json=base_request()).json()
    assert len(data["full_equity_curve"]) > 1
    assert data["full_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)
    assert data["benchmark_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)


def test_benchmark_not_in_tickers(client):
    """A benchmark outside the basket is fetched and aligned separately."""
    data = client.post(
        "/portfolio/stress-test",
        json=base_request(tickers=["QQQ", "GLD", "TLT"], benchmark_ticker="SPY"),
    ).json()
    assert data["benchmark_ticker"] == "SPY"
    assert set(data["weights"]) == {"QQQ", "GLD", "TLT"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/stress-test", json=base_request(tickers=[])).status_code == 422


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/stress-test", json=base_request(tickers=["SPY", "spy", "QQQ"])
    )
    assert resp.status_code == 422


def test_weights_sum_not_one_rejected(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(weights={"SPY": 0.5, "QQQ": 0.3, "GLD": 0.1, "TLT": 0.05}),
    )
    assert resp.status_code == 422


def test_negative_weights_rejected(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(weights={"SPY": 0.7, "QQQ": 0.5, "GLD": 0.0, "TLT": -0.2}),
    )
    assert resp.status_code == 422


def test_missing_ticker_weight_rejected(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(weights={"SPY": 0.5, "QQQ": 0.5}),
    )
    assert resp.status_code == 422


def test_empty_scenarios_rejected(client):
    assert client.post("/portfolio/stress-test", json=base_request(scenarios=[])).status_code == 422


def test_scenario_blank_name_rejected(client):
    s0, e0 = _scn_dates(100, 180)
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(scenarios=[{"name": "", "start_date": s0, "end_date": e0}]),
    )
    assert resp.status_code == 422


def test_scenario_bad_date_range_rejected(client):
    s0, e0 = _scn_dates(180, 100)  # start after end
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(scenarios=[{"name": "Bad", "start_date": s0, "end_date": e0}]),
    )
    assert resp.status_code == 422


def test_scenario_outside_data_returns_422(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(
            scenarios=[{"name": "Future", "start_date": "2030-01-01", "end_date": "2030-06-01"}]
        ),
    )
    assert resp.status_code == 422
    assert "does not overlap" in resp.json()["detail"]


def test_bad_outer_dates_rejected(client):
    resp = client.post(
        "/portfolio/stress-test",
        json=base_request(start_date="2021-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


def test_zero_capital_rejected(client):
    assert client.post("/portfolio/stress-test", json=base_request(initial_capital=0)).status_code == 422


def test_empty_benchmark_rejected(client):
    assert client.post("/portfolio/stress-test", json=base_request(benchmark_ticker="  ")).status_code == 422
