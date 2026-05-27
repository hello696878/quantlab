"""
API tests for the SMA parameter sweep endpoint.

All tests monkeypatch the data-fetch layer to avoid network calls.
"""

import numpy as np
import pandas as pd
import pytest

from app.backtest import run_backtest
from app.metrics import compute_metrics
from app.strategies import sma_crossover_signals

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_df(n: int = 300, start: str = "2015-01-01") -> pd.DataFrame:
    """Simulated price series long enough for window up to 200."""
    rng = np.random.default_rng(0)
    returns = rng.normal(5e-4, 0.01, n)
    prices = 100.0 * (1 + returns).cumprod()
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


_BASE_PAYLOAD = {
    "ticker": "SPY",
    "start_date": "2015-01-01",
    "end_date": "2023-12-31",
    "transaction_cost_bps": 10.0,
    "initial_capital": 100_000.0,
}


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_sweep_returns_200_for_valid_request(monkeypatch):
    """Smoke test: valid 2×2 grid → 200 with 4 result rows."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [10, 20], "slow_windows": [50, 100]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "SPY"
    assert body["num_combinations"] == 4
    assert len(body["results"]) == 4


def test_sweep_result_rows_have_all_metric_fields(monkeypatch):
    """Every result row must contain all required metric keys."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [20], "slow_windows": [100]},
    )

    assert resp.status_code == 200
    row = resp.json()["results"][0]
    for key in (
        "fast_window", "slow_window", "total_return", "cagr",
        "sharpe_ratio", "sortino_ratio", "max_drawdown", "volatility",
        "num_trades",
    ):
        assert key in row, f"Missing field: {key}"


def test_sweep_row_matches_direct_sma_backtest(monkeypatch):
    """A sweep row should equal running the same shifted SMA backtest directly."""
    df = make_df(300)
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    fast = 20
    slow = 100
    cost = 5.0
    capital = 50_000.0
    resp = client.post(
        "/research/sma-parameter-sweep",
        json={
            **_BASE_PAYLOAD,
            "fast_windows": [fast],
            "slow_windows": [slow],
            "transaction_cost_bps": cost,
            "initial_capital": capital,
        },
    )

    assert resp.status_code == 200
    row = resp.json()["results"][0]
    position = sma_crossover_signals(df["Close"], fast_window=fast, slow_window=slow)
    strategy_equity, _benchmark, trades = run_backtest(
        df["Close"],
        position,
        transaction_cost_bps=cost,
        initial_capital=capital,
    )
    expected = compute_metrics(strategy_equity)

    assert row["total_return"] == pytest.approx(expected["total_return"])
    assert row["cagr"] == pytest.approx(expected["cagr"])
    assert row["sharpe_ratio"] == pytest.approx(expected["sharpe_ratio"])
    assert row["sortino_ratio"] == pytest.approx(expected["sortino_ratio"])
    assert row["max_drawdown"] == pytest.approx(expected["max_drawdown"])
    assert row["volatility"] == pytest.approx(expected["volatility"])
    assert row["num_trades"] == len(trades)


def test_sweep_fetches_price_data_once(monkeypatch):
    """The sweep should fetch OHLCV once, then reuse that series for all rows."""
    calls = 0

    def fake_fetch(ticker, start, end):
        nonlocal calls
        calls += 1
        return make_df(300)

    monkeypatch.setattr(main_module, "_fetch", fake_fetch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [10, 20], "slow_windows": [50, 100]},
    )

    assert resp.status_code == 200
    assert resp.json()["num_combinations"] == 4
    assert calls == 1


def test_sweep_ticker_always_uppercased(monkeypatch):
    """Ticker is always returned upper-cased."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "ticker": "spy", "fast_windows": [10], "slow_windows": [50]},
    )

    assert resp.status_code == 200
    assert resp.json()["ticker"] == "SPY"


def test_sweep_skips_fast_ge_slow_silently(monkeypatch):
    """Combinations where fast >= slow are dropped, no error raised."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    # fast=100, slow=50 → invalid (skipped).  fast=10, slow=50 → valid.
    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [10, 100], "slow_windows": [50]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["num_combinations"] == 1
    assert body["results"][0]["fast_window"] == 10
    assert body["results"][0]["slow_window"] == 50


def test_sweep_all_combinations_invalid_returns_empty(monkeypatch):
    """All (fast, slow) pairs where fast >= slow → empty results list."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [100, 200], "slow_windows": [50]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["num_combinations"] == 0
    assert body["results"] == []


def test_sweep_no_runnable_valid_combinations_returns_422(monkeypatch):
    """If fast < slow pairs exist but data is too short, return a useful error."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(40))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [10, 20], "slow_windows": [50, 100]},
    )

    assert resp.status_code == 422
    assert "no valid SMA combination can run" in resp.json()["detail"]


def test_sweep_results_ordered_fast_then_slow(monkeypatch):
    """Results are ordered by (fast_window, slow_window) ascending."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={
            **_BASE_PAYLOAD,
            "fast_windows": [30, 10],   # reversed order on purpose
            "slow_windows": [100, 50],  # reversed order on purpose
        },
    )

    assert resp.status_code == 200
    rows = resp.json()["results"]
    pairs = [(r["fast_window"], r["slow_window"]) for r in rows]
    assert pairs == sorted(pairs), "Results are not sorted by (fast, slow)."


def test_sweep_echoes_params(monkeypatch):
    """start_date, end_date, cost and capital are echoed back correctly."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df(300))
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={
            "ticker": "AAPL",
            "start_date": "2018-01-01",
            "end_date": "2022-12-31",
            "fast_windows": [10],
            "slow_windows": [50],
            "transaction_cost_bps": 5.0,
            "initial_capital": 50_000.0,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["start_date"] == "2018-01-01"
    assert body["end_date"] == "2022-12-31"
    assert body["transaction_cost_bps"] == pytest.approx(5.0)
    assert body["initial_capital"] == pytest.approx(50_000.0)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_sweep_rejects_fast_window_below_2():
    """fast_windows containing a value < 2 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [1, 20], "slow_windows": [50]},
    )

    assert resp.status_code == 422


def test_sweep_rejects_slow_window_below_2():
    """slow_windows containing a value < 2 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "fast_windows": [10], "slow_windows": [1, 50]},
    )

    assert resp.status_code == 422


def test_sweep_rejects_too_many_fast_windows():
    """More than 10 fast_windows → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={
            **_BASE_PAYLOAD,
            "fast_windows": list(range(2, 14)),  # 12 values
            "slow_windows": [50],
        },
    )

    assert resp.status_code == 422


def test_sweep_rejects_combinations_over_100():
    """len(fast) × len(slow) > 100 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={
            **_BASE_PAYLOAD,
            "fast_windows": list(range(2, 12)),     # 10 values
            "slow_windows": list(range(20, 32)),    # 12 values → 120 > 100
        },
    )

    assert resp.status_code == 422


def test_sweep_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "start_date": "2022-01-01", "end_date": "2020-01-01",
              "fast_windows": [10], "slow_windows": [50]},
    )

    assert resp.status_code == 422


def test_sweep_rejects_empty_ticker():
    """Blank ticker → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-parameter-sweep",
        json={**_BASE_PAYLOAD, "ticker": "   ", "fast_windows": [10], "slow_windows": [50]},
    )

    assert resp.status_code == 422
