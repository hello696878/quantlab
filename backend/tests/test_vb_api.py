"""
API tests for the volatility breakout endpoint.

These tests monkeypatch the data-fetch layer so they run without network calls.
"""

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_df(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=idx)


def spike_values(n_stable: int = 30, n_after: int = 60) -> list[float]:
    """Flat baseline, one 10 % spike, flat recovery — gives at least one trade."""
    spike = 100.0 * 1.10
    return [100.0] * n_stable + [spike] + [spike] * n_after


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_vb_endpoint_returns_unified_response(monkeypatch):
    """Smoke test: valid request → 200, all strategy fields correct."""
    df = make_df(spike_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "spy",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 10,
            "breakout_multiplier": 1.0,
            "exit_window": 5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "volatility_breakout"
    # Ticker upper-cased.
    assert body["ticker"] == "SPY"
    # SMA fields zeroed for non-SMA.
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
    # Momentum fields null.
    assert body["momentum_window"] is None
    assert body["momentum_entry_threshold"] is None
    assert body["momentum_exit_threshold"] is None
    # VB fields echoed back.
    assert body["vb_lookback_window"] == 10
    assert body["vb_breakout_multiplier"] == pytest.approx(1.0)
    assert body["vb_exit_window"] == 5
    # Equity curve matches injected DataFrame length.
    assert len(body["equity_curve"]) == len(df)
    # Required metric keys present.
    assert set(body["strategy_metrics"]).issuperset(
        {"total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"}
    )


def test_vb_endpoint_ticker_uppercased(monkeypatch):
    """Ticker is always upper-cased in the response."""
    df = make_df(spike_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 10,
            "breakout_multiplier": 1.0,
            "exit_window": 5,
            "transaction_cost_bps": 0.0,
            "initial_capital": 50_000.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


def test_vb_endpoint_params_echoed(monkeypatch):
    """Custom breakout_multiplier and exit_window are echoed back correctly."""
    df = make_df(spike_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 15,
            "breakout_multiplier": 2.5,
            "exit_window": 8,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vb_lookback_window"] == 15
    assert body["vb_breakout_multiplier"] == pytest.approx(2.5)
    assert body["vb_exit_window"] == 8


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_vb_endpoint_rejects_zero_breakout_multiplier():
    """breakout_multiplier gt=0; zero → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 20,
            "breakout_multiplier": 0.0,
            "exit_window": 10,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_vb_endpoint_rejects_lookback_window_of_one():
    """lookback_window ge=2; value of 1 → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 1,
            "breakout_multiplier": 1.0,
            "exit_window": 10,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_vb_endpoint_rejects_zero_exit_window():
    """exit_window ge=1; zero → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 20,
            "breakout_multiplier": 1.0,
            "exit_window": 0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_vb_endpoint_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2021-01-01",
            "end_date": "2020-01-01",
            "lookback_window": 20,
            "breakout_multiplier": 1.0,
            "exit_window": 10,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_vb_endpoint_too_few_bars(monkeypatch):
    """Fewer bars than lookback_window + exit_window + 5 → 422."""
    # 5 rows, but lookback=20 + exit=10 + 5 = 35 required.
    df = make_df([100.0] * 5)
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/volatility-breakout",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "lookback_window": 20,
            "breakout_multiplier": 1.0,
            "exit_window": 10,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
    assert "trading days" in response.json()["detail"].lower()
