"""
API tests for POST /portfolio/optimize.

main._fetch is monkeypatched to deterministic synthetic prices with genuine
(non-zero) return variance, so the optimizer is well-posed and no network is
used.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# (base drift, amplitude, frequency) per ticker → oscillating returns with
# distinct means and variances so the covariance matrix is well-conditioned.
_PARAMS = {
    "SPY": (0.0005, 0.010, 0.10),
    "QQQ": (0.0007, 0.016, 0.13),
    "GLD": (0.0002, 0.008, 0.07),
    "TLT": (0.0001, 0.006, 0.05),
    "AAA": (0.0004, 0.012, 0.11),
    "BBB": (0.0003, 0.009, 0.17),
}


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    base, amp, freq = _PARAMS.get(ticker.upper(), (0.0003, 0.011, 0.09))
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    prices = [100.0]
    for i in range(1, len(idx)):
        r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.31 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=idx)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def base_request(**overrides) -> dict:
    req = {
        "tickers": ["SPY", "QQQ", "GLD", "TLT"],
        "start_date": "2018-01-01",
        "end_date": "2019-06-01",
        "initial_capital": 100000,
        "risk_free_rate": 0.02,
        "transaction_cost_bps": 10,
        "objective": "max_sharpe",
    }
    req.update(overrides)
    return req


def _assert_valid_weights(weights: dict, tickers):
    assert set(weights) == set(tickers)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)
    for w in weights.values():
        assert w >= -1e-9


# ---------------------------------------------------------------------------
# Happy paths per objective
# ---------------------------------------------------------------------------


def test_max_sharpe_optimization(client):
    resp = client.post("/portfolio/optimize", json=base_request(objective="max_sharpe"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["objective"] == "max_sharpe"
    _assert_valid_weights(data["weights"], data["tickers"])
    assert "in_sample_warning" in data and data["in_sample_warning"]


def test_min_volatility_optimization(client):
    resp = client.post(
        "/portfolio/optimize", json=base_request(objective="min_volatility")
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["objective"] == "min_volatility"
    _assert_valid_weights(data["weights"], data["tickers"])


def test_equal_weight_objective(client):
    data = client.post(
        "/portfolio/optimize", json=base_request(objective="equal_weight")
    ).json()
    for w in data["weights"].values():
        assert w == pytest.approx(0.25, abs=1e-6)


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_response_has_all_sections(client):
    data = client.post("/portfolio/optimize", json=base_request()).json()
    for key in (
        "weights", "expected_returns", "covariance_matrix",
        "portfolio_expected_return", "portfolio_volatility", "portfolio_sharpe",
        "metrics", "equal_weight_metrics", "equity_curve",
        "equal_weight_equity_curve", "drawdown",
    ):
        assert key in data, key


def test_expected_returns_and_covariance_generated(client):
    data = client.post("/portfolio/optimize", json=base_request()).json()
    tickers = data["tickers"]
    assert set(data["expected_returns"]) == set(tickers)
    cov = data["covariance_matrix"]
    assert set(cov) == set(tickers)
    for row in cov.values():
        assert set(row) == set(tickers)
    # Covariance is symmetric and has positive diagonal (real variance).
    for a in tickers:
        assert cov[a][a] > 0
        for b in tickers:
            assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-6)


def test_equity_curves_generated_and_aligned(client):
    data = client.post("/portfolio/optimize", json=base_request()).json()
    assert len(data["equity_curve"]) > 0
    assert len(data["equity_curve"]) == len(data["equal_weight_equity_curve"])
    assert len(data["drawdown"]) == len(data["equity_curve"])
    assert data["equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)
    assert data["equal_weight_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)


def test_metrics_and_equal_weight_metrics_present(client):
    data = client.post("/portfolio/optimize", json=base_request()).json()
    for block in (data["metrics"], data["equal_weight_metrics"]):
        for key in ("total_return", "cagr", "sharpe_ratio", "max_drawdown", "num_days"):
            assert key in block


def test_portfolio_scalar_stats_present(client):
    data = client.post("/portfolio/optimize", json=base_request()).json()
    assert isinstance(data["portfolio_expected_return"], (int, float))
    assert data["portfolio_volatility"] >= 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/optimize", json=base_request(tickers=["SPY", "spy"])
    )
    assert resp.status_code == 422


def test_invalid_objective_rejected(client):
    resp = client.post("/portfolio/optimize", json=base_request(objective="max_return"))
    assert resp.status_code == 422


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/optimize", json=base_request(tickers=[])).status_code == 422


def test_too_many_tickers_rejected(client):
    many = [f"T{i}" for i in range(21)]
    assert client.post("/portfolio/optimize", json=base_request(tickers=many)).status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/optimize",
        json=base_request(start_date="2019-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


def test_negative_risk_free_rate_rejected(client):
    assert client.post("/portfolio/optimize", json=base_request(risk_free_rate=-0.01)).status_code == 422


def test_zero_capital_rejected(client):
    assert client.post("/portfolio/optimize", json=base_request(initial_capital=0)).status_code == 422


# ---------------------------------------------------------------------------
# Common-date alignment / insufficient data
# ---------------------------------------------------------------------------


def test_insufficient_common_data_returns_422(client, monkeypatch):
    def disjoint_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "AAA":
            idx = pd.date_range("2018-01-01", periods=50, freq="B")
        else:
            idx = pd.date_range("2019-06-01", periods=50, freq="B")  # no overlap
        return pd.DataFrame({"Close": [100.0 + i for i in range(50)]}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", disjoint_fetch)
    resp = client.post("/portfolio/optimize", json=base_request(tickers=["AAA", "BBB"]))
    assert resp.status_code == 422
    assert "common trading day" in resp.json()["detail"]
