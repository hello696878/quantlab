"""
API tests for POST /portfolio/risk-dashboard.

main._fetch is monkeypatched to deterministic synthetic prices; no network.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.portfolio import align_prices, risk_dashboard

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

_PARAMS = {
    "SPY": (0.0005, 0.010, 0.10),
    "QQQ": (0.0007, 0.016, 0.13),
    "GLD": (0.0002, 0.008, 0.07),
    "TLT": (0.0001, 0.006, 0.05),
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
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------


def test_valid_risk_dashboard(client):
    resp = client.post("/portfolio/risk-dashboard", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in (
        "asset_annual_returns", "asset_annual_volatilities",
        "correlation_matrix", "covariance_matrix", "equal_weight_portfolio",
        "correlation_diagnostics", "risk_contribution", "historical_note",
    ):
        assert key in data, key


def test_asset_stats_generated(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    tickers = data["tickers"]
    assert set(data["asset_annual_returns"]) == set(tickers)
    assert set(data["asset_annual_volatilities"]) == set(tickers)
    for v in data["asset_annual_volatilities"].values():
        assert v >= 0


def test_endpoint_metrics_match_aligned_daily_return_estimates(client):
    req = base_request()
    data = client.post("/portfolio/risk-dashboard", json=req).json()
    frames = {
        ticker: _fake_fetch(ticker, req["start_date"], req["end_date"])["Close"]
        for ticker in data["tickers"]
    }
    expected = risk_dashboard(align_prices(frames))

    for ticker in data["tickers"]:
        assert data["asset_annual_returns"][ticker] == pytest.approx(
            round(expected["asset_annual_returns"][ticker], 6), abs=1e-9
        )
        assert data["asset_annual_volatilities"][ticker] == pytest.approx(
            round(expected["asset_annual_volatilities"][ticker], 6), abs=1e-9
        )
        assert data["risk_contribution"][ticker] == pytest.approx(
            round(expected["risk_contribution"][ticker], 6), abs=1e-9
        )


def test_correlation_matrix_symmetric_unit_diagonal(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    corr = data["correlation_matrix"]
    tickers = data["tickers"]
    assert set(corr) == set(tickers)
    for a in tickers:
        assert corr[a][a] == pytest.approx(1.0, abs=1e-6)
        for b in tickers:
            assert corr[a][b] == pytest.approx(corr[b][a], abs=1e-6)


def test_covariance_matrix_symmetric(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    cov = data["covariance_matrix"]
    for a in data["tickers"]:
        assert cov[a][a] > 0
        for b in data["tickers"]:
            assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-6)


def test_equal_weight_portfolio(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    ew = data["equal_weight_portfolio"]
    for key in ("expected_return", "volatility", "diversification_ratio", "weights"):
        assert key in ew
    for w in ew["weights"].values():
        assert w == pytest.approx(0.25, abs=1e-6)
    assert ew["diversification_ratio"] >= 1.0 - 1e-6


def test_correlation_diagnostics(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    diag = data["correlation_diagnostics"]
    for key in (
        "average_pairwise_correlation", "max_pairwise_correlation",
        "min_pairwise_correlation", "most_correlated_pair", "least_correlated_pair",
    ):
        assert key in diag
    assert len(diag["most_correlated_pair"]) == 2
    assert len(diag["least_correlated_pair"]) == 2
    assert diag["min_pairwise_correlation"] <= diag["max_pairwise_correlation"] + 1e-9


def test_risk_contribution_sums_to_one(client):
    data = client.post("/portfolio/risk-dashboard", json=base_request()).json()
    rc = data["risk_contribution"]
    assert set(rc) == set(data["tickers"])
    assert sum(rc.values()) == pytest.approx(1.0, abs=1e-4)


def test_two_asset_dashboard(client):
    data = client.post(
        "/portfolio/risk-dashboard", json=base_request(tickers=["SPY", "TLT"])
    ).json()
    diag = data["correlation_diagnostics"]
    # With two assets the single pair is both most and least correlated.
    assert set(diag["most_correlated_pair"]) == {"SPY", "TLT"}
    assert set(diag["least_correlated_pair"]) == {"SPY", "TLT"}


def test_endpoint_aligns_common_dates_and_duplicate_dates(client, monkeypatch):
    def overlapping_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "AAA":
            idx = pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-03", "2020-01-06", "2020-01-07"]
            )
            close = [100.0, 101.0, 102.0, 105.0, 106.0, 107.0]
        else:
            idx = pd.to_datetime(["2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"])
            close = [50.0, 51.0, 53.0, 54.0]
        return pd.DataFrame({"Close": close}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", overlapping_fetch)
    req = base_request(tickers=["AAA", "BBB"])
    resp = client.post("/portfolio/risk-dashboard", json=req)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    frames = {
        ticker: overlapping_fetch(ticker, req["start_date"], req["end_date"])["Close"]
        for ticker in data["tickers"]
    }
    expected = risk_dashboard(align_prices(frames))
    for ticker in data["tickers"]:
        assert data["asset_annual_returns"][ticker] == pytest.approx(
            round(expected["asset_annual_returns"][ticker], 6), abs=1e-9
        )
        for other in data["tickers"]:
            assert data["correlation_matrix"][ticker][other] == pytest.approx(
                round(expected["correlation_matrix"][ticker][other], 6), abs=1e-9
            )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/risk-dashboard", json=base_request(tickers=[])).status_code == 422


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/risk-dashboard", json=base_request(tickers=["SPY", "spy"])
    )
    assert resp.status_code == 422


def test_too_many_tickers_rejected(client):
    many = [f"T{i}" for i in range(21)]
    assert client.post("/portfolio/risk-dashboard", json=base_request(tickers=many)).status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/risk-dashboard",
        json=base_request(start_date="2019-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


def test_insufficient_common_data_returns_422(client, monkeypatch):
    def disjoint_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "AAA":
            idx = pd.date_range("2018-01-01", periods=50, freq="B")
        else:
            idx = pd.date_range("2019-06-01", periods=50, freq="B")
        return pd.DataFrame({"Close": [100.0 + i for i in range(50)]}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", disjoint_fetch)
    resp = client.post(
        "/portfolio/risk-dashboard", json=base_request(tickers=["AAA", "BBB"])
    )
    assert resp.status_code == 422
    assert "common trading day" in resp.json()["detail"]
