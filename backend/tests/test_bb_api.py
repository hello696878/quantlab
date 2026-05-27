"""
API tests for the Bollinger Band mean-reversion endpoint.

These tests monkeypatch the data-fetch layer so they run without network calls.
"""

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_df(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=idx)


def spike_v_values(
    n_stable: int = 30,
    stable_price: float = 100.0,
    spike_low: float = 75.0,
    n_recover: int = 60,
    recover_target: float = 110.0,
) -> list[float]:
    stable = [stable_price] * n_stable
    recovery = [
        spike_low + (recover_target - spike_low) * i / n_recover
        for i in range(n_recover)
    ]
    return stable + [spike_low] + recovery


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_bb_endpoint_returns_unified_response(monkeypatch):
    """Smoke test: valid request → 200, response fields correct."""
    df = make_df(spike_v_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "spy",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "middle",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "bollinger_band"
    assert body["ticker"] == "SPY"
    # SMA fields should be zeroed out.
    assert body["fast_window"] == 0
    assert body["slow_window"] == 0
    # RSI fields should be null.
    assert body["rsi_window"] is None
    assert body["oversold_threshold"] is None
    assert body["exit_threshold"] is None
    # BB fields should echo the request.
    assert body["bb_window"] == 20
    assert body["bb_num_std"] == 2.0
    assert body["bb_exit_band"] == "middle"
    # Equity curve length should match the injected DataFrame.
    assert len(body["equity_curve"]) == len(df)
    # All required metric keys present.
    assert set(body["strategy_metrics"]).issuperset(
        {"total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"}
    )


def test_bb_endpoint_upper_exit_band(monkeypatch):
    """exit_band='upper' is accepted and echoed back in the response."""
    df = make_df(spike_v_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "upper",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["bb_exit_band"] == "upper"


def test_bb_endpoint_ticker_uppercased(monkeypatch):
    """Ticker in the response should always be upper-cased."""
    df = make_df(spike_v_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "middle",
            "transaction_cost_bps": 0.0,
            "initial_capital": 50_000.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_bb_endpoint_rejects_invalid_exit_band():
    """exit_band must be 'middle' or 'upper'; other values → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "lower",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_bb_endpoint_rejects_zero_num_std():
    """num_std must be > 0; zero → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 0.0,
            "exit_band": "middle",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_bb_endpoint_rejects_bb_window_of_one():
    """bb_window ge=2; value of 1 → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 1,
            "num_std": 2.0,
            "exit_band": "middle",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_bb_endpoint_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2021-01-01",
            "end_date": "2020-01-01",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "middle",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_bb_endpoint_too_few_bars(monkeypatch):
    """Fewer bars than bb_window + 5 → 422 with informative message."""
    # Only 10 rows but bb_window=20 requires 25.
    df = make_df([100.0] * 10)
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/bollinger-band",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "bb_window": 20,
            "num_std": 2.0,
            "exit_band": "middle",
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
    assert "trading days" in response.json()["detail"].lower()
