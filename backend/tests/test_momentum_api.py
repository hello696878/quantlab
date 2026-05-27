"""
API tests for the time-series momentum endpoint.

These tests monkeypatch the data-fetch layer so they run without network calls.
"""

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_df(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=idx)


def uptrend_values(n: int = 200, step: float = 0.5) -> list[float]:
    """Monotone uptrend — momentum is always positive after warm-up."""
    return [100.0 + i * step for i in range(n)]


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_momentum_endpoint_returns_unified_response(monkeypatch):
    """Smoke test: valid request → 200, all strategy fields correct."""
    df = make_df(uptrend_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "spy",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "momentum"
    # Ticker must be upper-cased.
    assert body["ticker"] == "SPY"
    # SMA fields zeroed out for non-SMA strategies.
    assert body["fast_window"] == 0
    assert body["slow_window"] == 0
    # RSI fields null.
    assert body["rsi_window"] is None
    assert body["oversold_threshold"] is None
    assert body["exit_threshold"] is None
    # BB fields null.
    assert body["bb_window"] is None
    assert body["bb_num_std"] is None
    assert body["bb_exit_band"] is None
    # Momentum fields echoed back.
    assert body["momentum_window"] == 20
    assert body["momentum_entry_threshold"] == 0.0
    assert body["momentum_exit_threshold"] == 0.0
    # Equity curve length matches injected DataFrame.
    assert len(body["equity_curve"]) == len(df)
    # Required metric keys present.
    assert set(body["strategy_metrics"]).issuperset(
        {"total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"}
    )


def test_momentum_endpoint_ticker_uppercased(monkeypatch):
    """Ticker in the response is always upper-cased regardless of input."""
    df = make_df(uptrend_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 0.0,
            "initial_capital": 50_000.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


def test_momentum_endpoint_nonzero_thresholds(monkeypatch):
    """Custom entry/exit thresholds are echoed back correctly."""
    df = make_df(uptrend_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.05,
            "exit_threshold": -0.02,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["momentum_entry_threshold"] == pytest.approx(0.05)
    assert body["momentum_exit_threshold"] == pytest.approx(-0.02)


def test_momentum_endpoint_equal_thresholds_allowed(monkeypatch):
    """entry_threshold == exit_threshold (no hysteresis) is valid."""
    df = make_df(uptrend_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.02,
            "exit_threshold": 0.02,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_momentum_endpoint_rejects_inverted_thresholds():
    """entry_threshold < exit_threshold → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": -0.1,
            "exit_threshold": 0.1,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_momentum_endpoint_rejects_window_of_zero():
    """momentum_window ge=1; value of 0 → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 0,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_momentum_endpoint_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2021-01-01",
            "end_date": "2020-01-01",
            "momentum_window": 20,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_momentum_endpoint_too_few_bars(monkeypatch):
    """Fewer bars than momentum_window + 5 → 422 with informative message."""
    # Only 10 rows but momentum_window=20 requires 25.
    df = make_df([100.0 + i * 0.5 for i in range(10)])
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
    assert "trading days" in response.json()["detail"].lower()


def test_momentum_endpoint_rejects_empty_ticker():
    """Empty ticker string → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/momentum",
        json={
            "ticker": "   ",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "momentum_window": 20,
            "entry_threshold": 0.0,
            "exit_threshold": 0.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
