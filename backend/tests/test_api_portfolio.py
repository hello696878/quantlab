"""
API tests for POST /portfolio/backtest.

The single-asset fetch layer (main._fetch) is monkeypatched to deterministic
synthetic data, so no network calls are made.  SPY is fetchable too, so the
benchmark path is exercised even when SPY is not in the basket.
"""

from __future__ import annotations

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# Per-ticker daily growth rates for the synthetic fetch.
_TRENDS = {
    "SPY": 0.0006,
    "QQQ": 0.0009,
    "GLD": 0.0002,
    "TLT": -0.0001,
    "AAA": 0.0005,
    "BBB": 0.0004,
}


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    rate = _TRENDS.get(ticker.upper(), 0.0003)
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    closes = [100.0 * ((1.0 + rate) ** i) for i in range(len(idx))]
    return pd.DataFrame({"Close": closes}, index=idx)


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
        "rebalance_frequency": "monthly",
        "transaction_cost_bps": 10,
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------


def test_valid_equal_weight_portfolio(client):
    resp = client.post("/portfolio/backtest", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["strategy"] == "equal_weight_portfolio"
    assert data["rebalance_frequency"] == "monthly"
    assert data["tickers"] == ["SPY", "QQQ", "GLD", "TLT"]
    assert data["benchmark_ticker"] == "SPY"

    # Core sections present.
    for key in (
        "metrics", "benchmark_metrics", "equity_curve",
        "drawdown", "weights", "rebalance_events",
    ):
        assert key in data, key

    assert len(data["equity_curve"]) > 0
    assert data["equity_curve"][0]["portfolio"] == pytest.approx(100000, abs=1.0)
    assert data["equity_curve"][0]["benchmark"] == pytest.approx(100000, abs=1.0)


def test_initial_equal_weights(client):
    data = client.post("/portfolio/backtest", json=base_request()).json()
    first = data["weights"][0]["weights"]
    assert set(first) == {"SPY", "QQQ", "GLD", "TLT"}
    for w in first.values():
        assert w == pytest.approx(0.25, abs=1e-6)


def test_weights_and_equity_same_length(client):
    data = client.post("/portfolio/backtest", json=base_request()).json()
    assert len(data["weights"]) == len(data["equity_curve"])
    assert len(data["drawdown"]) == len(data["equity_curve"])


def test_rebalance_events_generated(client):
    data = client.post("/portfolio/backtest", json=base_request()).json()
    assert len(data["rebalance_events"]) >= 10
    ev = data["rebalance_events"][0]
    assert {"date", "turnover", "cost"} <= ev.keys()
    assert ev["cost"] > 0  # 10 bps cost on non-trivial turnover


def test_no_rebalance_has_no_events(client):
    data = client.post(
        "/portfolio/backtest", json=base_request(rebalance_frequency="none")
    ).json()
    assert data["rebalance_events"] == []
    # Weights drift away from equal by the end.
    final = data["weights"][-1]["weights"]
    assert abs(final["QQQ"] - 0.25) > 1e-3


def test_benchmark_when_spy_not_in_basket(client):
    """SPY is fetched separately and used as benchmark even if not held."""
    data = client.post(
        "/portfolio/backtest", json=base_request(tickers=["QQQ", "GLD", "TLT"])
    ).json()
    assert data["benchmark_ticker"] == "SPY"
    assert len(data["equity_curve"]) > 0


def test_benchmark_does_not_backfill_future_spy_data(client, monkeypatch):
    """If separately fetched SPY starts late, do not bfill future prices backward."""

    def late_spy_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "SPY":
            idx = pd.date_range("2018-03-01", periods=80, freq="B")
        else:
            idx = pd.date_range("2018-01-01", periods=120, freq="B")
        closes = [100.0 * (1.001 ** i) for i in range(len(idx))]
        return pd.DataFrame({"Close": closes}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", late_spy_fetch)
    data = client.post(
        "/portfolio/backtest",
        json=base_request(tickers=["QQQ", "GLD"], rebalance_frequency="none"),
    ).json()

    assert data["benchmark_ticker"] == "QQQ"
    assert data["equity_curve"][0]["benchmark"] == pytest.approx(100000, abs=1.0)


def test_benchmark_metrics_present(client):
    data = client.post("/portfolio/backtest", json=base_request()).json()
    m = data["benchmark_metrics"]
    for key in ("total_return", "cagr", "sharpe_ratio", "max_drawdown", "num_days"):
        assert key in m


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/backtest", json=base_request(tickers=[])).status_code == 422


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/backtest", json=base_request(tickers=["SPY", "spy", "QQQ"])
    )
    assert resp.status_code == 422


def test_blank_ticker_rejected(client):
    resp = client.post(
        "/portfolio/backtest", json=base_request(tickers=["SPY", "  ", "QQQ"])
    )
    assert resp.status_code == 422


def test_too_many_tickers_rejected(client):
    many = [f"T{i}" for i in range(21)]
    assert client.post("/portfolio/backtest", json=base_request(tickers=many)).status_code == 422


def test_invalid_rebalance_frequency_rejected(client):
    resp = client.post(
        "/portfolio/backtest", json=base_request(rebalance_frequency="weekly")
    )
    assert resp.status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/backtest",
        json=base_request(start_date="2019-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


def test_zero_capital_rejected(client):
    assert client.post("/portfolio/backtest", json=base_request(initial_capital=0)).status_code == 422


def test_negative_cost_rejected(client):
    resp = client.post("/portfolio/backtest", json=base_request(transaction_cost_bps=-1))
    assert resp.status_code == 422


def test_non_positive_price_returns_422(client, monkeypatch):
    def bad_price_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        idx = pd.date_range("2018-01-01", periods=5, freq="B")
        closes = [100.0, 101.0, 0.0, 103.0, 104.0]
        return pd.DataFrame({"Close": closes}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", bad_price_fetch)
    resp = client.post(
        "/portfolio/backtest", json=base_request(tickers=["AAA", "BBB"])
    )
    assert resp.status_code == 422
    assert "strictly positive" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Common-date alignment / insufficient data
# ---------------------------------------------------------------------------


def test_insufficient_common_data_returns_422(client, monkeypatch):
    """Assets with disjoint date ranges → no common dates → 422."""

    def disjoint_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "AAA":
            idx = pd.date_range("2018-01-01", periods=50, freq="B")
        else:
            idx = pd.date_range("2019-06-01", periods=50, freq="B")  # no overlap
        return pd.DataFrame({"Close": [100.0 + i for i in range(50)]}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", disjoint_fetch)
    resp = client.post(
        "/portfolio/backtest", json=base_request(tickers=["AAA", "BBB"])
    )
    assert resp.status_code == 422
    assert "common trading day" in resp.json()["detail"]


def test_transaction_cost_turnover_effect(client):
    """Higher bps → lower final portfolio value (cost drag from turnover)."""
    free = client.post(
        "/portfolio/backtest", json=base_request(transaction_cost_bps=0)
    ).json()
    costly = client.post(
        "/portfolio/backtest", json=base_request(transaction_cost_bps=50)
    ).json()
    assert costly["equity_curve"][-1]["portfolio"] < free["equity_curve"][-1]["portfolio"]
