"""
API tests for the pairs trading endpoint.

These tests monkeypatch the data-fetch layer so they run without network calls.
"""

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_series(values: list[float], name: str = "Y",
                start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name=name, dtype=float)


def flat_pair(n: int = 120) -> tuple[pd.Series, pd.Series]:
    """Two flat series — no divergence, easy to work with."""
    close_y = make_series([100.0] * n, name="KO")
    close_x = make_series([100.0] * n, name="PEP")
    return close_y, close_x


def diverging_pair(n: int = 150) -> tuple[pd.Series, pd.Series]:
    """Y diverges from X mid-series to guarantee at least one entry."""
    y_vals = [100.0] * 50 + [130.0] * 50 + [100.0] * (n - 100)
    x_vals = [100.0] * n
    return make_series(y_vals, name="KO"), make_series(x_vals, name="PEP")


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_pairs_endpoint_returns_unified_response(monkeypatch):
    """Smoke test: valid request → 200, all strategy fields correct."""
    close_y, close_x = diverging_pair()
    monkeypatch.setattr(
        main_module, "fetch_pairs_close",
        lambda y, x, start, end: (close_y, close_x),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "ko",
            "asset_x": "pep",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 1.5,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "pairs"
    # Ticker is the slash-separated pair (upper-cased).
    assert body["ticker"] == "KO/PEP"
    # SMA fields zeroed for non-SMA.
    assert body["fast_window"] == 0
    assert body["slow_window"] == 0
    # Single-asset strategy fields are null.
    assert body["rsi_window"] is None
    assert body["oversold_threshold"] is None
    assert body["exit_threshold"] is None
    assert body["bb_window"] is None
    assert body["bb_num_std"] is None
    assert body["bb_exit_band"] is None
    assert body["momentum_window"] is None
    assert body["momentum_entry_threshold"] is None
    assert body["momentum_exit_threshold"] is None
    assert body["vb_lookback_window"] is None
    assert body["vb_breakout_multiplier"] is None
    assert body["vb_exit_window"] is None
    # Pairs-specific fields echoed back.
    assert body["pairs_asset_y"] == "KO"
    assert body["pairs_asset_x"] == "PEP"
    assert body["pairs_lookback_window"] == 30
    assert body["pairs_entry_z_score"] == pytest.approx(1.5)
    assert body["pairs_exit_z_score"] == pytest.approx(0.5)
    # Equity curve matches injected series length.
    assert len(body["equity_curve"]) == len(close_y)
    # Required metric keys present.
    assert set(body["strategy_metrics"]).issuperset(
        {"total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"}
    )


def test_pairs_endpoint_ticker_uppercased(monkeypatch):
    """asset_y / asset_x are always upper-cased in the response."""
    close_y, close_x = flat_pair()
    monkeypatch.setattr(
        main_module, "fetch_pairs_close",
        lambda y, x, start, end: (close_y, close_x),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "ko",
            "asset_x": "pep",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "KO/PEP"
    assert body["pairs_asset_y"] == "KO"
    assert body["pairs_asset_x"] == "PEP"


def test_pairs_endpoint_params_echoed(monkeypatch):
    """Custom lookback, entry_z, exit_z are echoed back correctly."""
    close_y, close_x = flat_pair()
    monkeypatch.setattr(
        main_module, "fetch_pairs_close",
        lambda y, x, start, end: (close_y, close_x),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 45,
            "entry_z_score": 1.8,
            "exit_z_score": 0.3,
            "transaction_cost_bps": 5.0,
            "initial_capital": 50_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pairs_lookback_window"] == 45
    assert body["pairs_entry_z_score"] == pytest.approx(1.8)
    assert body["pairs_exit_z_score"] == pytest.approx(0.3)
    assert body["transaction_cost_bps"] == pytest.approx(5.0)
    assert body["initial_capital"] == pytest.approx(50_000.0)


def test_pairs_endpoint_equity_curve_length(monkeypatch):
    """Equity curve must have the same length as the injected price series."""
    n = 200
    close_y, close_x = flat_pair(n)
    monkeypatch.setattr(
        main_module, "fetch_pairs_close",
        lambda y, x, start, end: (close_y, close_x),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2022-12-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["equity_curve"]) == n


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_pairs_endpoint_rejects_equal_z_scores():
    """entry_z_score == exit_z_score → 422 (cross-field validator)."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 1.0,
            "exit_z_score": 1.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_rejects_inverted_z_scores():
    """entry_z_score < exit_z_score → 422 (cross-field validator)."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 0.5,
            "exit_z_score": 1.0,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_rejects_same_tickers():
    """asset_y == asset_x → 422 (assets-differ validator)."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "KO",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_rejects_empty_asset_y():
    """Blank asset_y → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "   ",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_rejects_empty_asset_x():
    """Blank asset_x → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "   ",
            "start_date": "2020-01-01",
            "end_date": "2021-12-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2021-01-01",
            "end_date": "2020-01-01",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422


def test_pairs_endpoint_too_few_bars(monkeypatch):
    """Fewer common trading days than lookback_window + 5 → 422."""
    # 10 bars, but lookback=30 + 5 = 35 required.
    close_y = make_series([100.0] * 10, name="KO")
    close_x = make_series([100.0] * 10, name="PEP")
    monkeypatch.setattr(
        main_module, "fetch_pairs_close",
        lambda y, x, start, end: (close_y, close_x),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/backtest/pairs",
        json={
            "asset_y": "KO",
            "asset_x": "PEP",
            "start_date": "2020-01-01",
            "end_date": "2020-03-31",
            "lookback_window": 30,
            "entry_z_score": 2.0,
            "exit_z_score": 0.5,
            "transaction_cost_bps": 10.0,
            "initial_capital": 100_000.0,
        },
    )

    assert response.status_code == 422
    assert "trading days" in response.json()["detail"].lower()
