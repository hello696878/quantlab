"""
API tests for the RSI mean-reversion endpoint.

These tests monkeypatch the data fetch layer, so they do not make network calls.
"""

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_df(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=idx)


def v_shape_values(n_fall: int = 30, n_rise: int = 30) -> list[float]:
    fall = [100.0 * (0.975**i) for i in range(n_fall)]
    rise = [fall[-1] * (1.025**i) for i in range(n_rise)]
    return fall + rise


def test_rsi_endpoint_returns_unified_response(monkeypatch):
    df = make_df(v_shape_values())
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: df)
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/rsi-mean-reversion",
        json={
            "ticker": "spy",
            "start_date": "2020-01-01",
            "end_date": "2020-04-01",
            "rsi_window": 14,
            "oversold_threshold": 30.0,
            "exit_threshold": 50.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "rsi_mean_reversion"
    assert body["ticker"] == "SPY"
    assert body["fast_window"] == 0
    assert body["slow_window"] == 0
    assert body["rsi_window"] == 14
    assert body["oversold_threshold"] == 30.0
    assert body["exit_threshold"] == 50.0
    assert len(body["equity_curve"]) == len(df)
    assert set(body["strategy_metrics"]).issuperset(
        {"total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"}
    )


def test_rsi_endpoint_rejects_invalid_threshold_order():
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/rsi-mean-reversion",
        json={
            "ticker": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2020-04-01",
            "rsi_window": 14,
            "oversold_threshold": 60.0,
            "exit_threshold": 50.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
    assert "oversold_threshold" in response.text
