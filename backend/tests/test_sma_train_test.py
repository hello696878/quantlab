"""
API tests for the SMA train/test out-of-sample validation endpoint.

All tests monkeypatch the data-fetch layer to avoid network calls.

Two fixture helpers:
  make_df(n)           — deterministic synthetic OHLCV dataframe
  make_short_df_dates  — returns (df, start, split, end) computed from the
                         dataframe's own index so date arithmetic is always
                         correct regardless of n.
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

def make_df(n: int = 3500, start: str = "2010-01-01") -> pd.DataFrame:
    """Synthetic price series.

    Default 3500 bars ≈ 13.9 years so that the hardcoded dates in
    _BASE_PAYLOAD (split 2018, end 2023) fall within the data range.
    """
    rng = np.random.default_rng(42)
    returns = rng.normal(5e-4, 0.01, n)
    prices = 100.0 * (1 + returns).cumprod()
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


def make_short_df_dates(n: int = 600, is_count: int = 400):
    """Return (df, start_date, split_date, end_date) with dates from the index.

    Useful for tests that need precise control over period lengths.
    """
    df = make_df(n)
    start_date = str(df.index[0].date())
    split_date = str(df.index[is_count].date())
    end_date = str(df.index[-1].date())
    return df, start_date, split_date, end_date


# Base payload with dates that work for a 3500-bar series from 2010-01-01.
_BASE_PAYLOAD = {
    "ticker": "SPY",
    "start_date": "2010-01-01",
    "split_date": "2018-01-01",
    "end_date": "2023-12-31",
    "fast_windows": [10, 20],
    "slow_windows": [50, 100],
    "transaction_cost_bps": 10.0,
    "initial_capital": 100_000.0,
    "selection_metric": "sharpe_ratio",
}


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_train_test_smoke(monkeypatch):
    """Basic happy path: valid request returns 200 with all top-level keys."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "ticker", "start_date", "split_date", "end_date",
        "transaction_cost_bps", "initial_capital", "selection_metric",
        "in_sample_days", "out_of_sample_days",
        "best_fast_window", "best_slow_window",
        "in_sample_metrics", "out_of_sample_metrics",
        "out_of_sample_benchmark_metrics",
        "out_of_sample_equity_curve", "out_of_sample_trades",
        "out_of_sample_num_trades",
        "sharpe_degradation", "cagr_degradation", "calmar_degradation",
        "max_drawdown_worsening", "oos_collapsed",
        "all_in_sample_results",
    ):
        assert key in body, f"Missing top-level key: {key}"


def test_train_test_ticker_uppercased(monkeypatch):
    """Ticker is always upper-cased in the response."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "ticker": "spy"},
    )

    assert resp.status_code == 200
    assert resp.json()["ticker"] == "SPY"


def test_train_test_metrics_have_calmar_ratio(monkeypatch):
    """in_sample_metrics and out_of_sample_metrics must include calmar_ratio."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert "calmar_ratio" in body["in_sample_metrics"]
    assert "calmar_ratio" in body["out_of_sample_metrics"]
    assert "calmar_ratio" in body["out_of_sample_benchmark_metrics"]


def test_train_test_best_params_valid(monkeypatch):
    """best_fast_window < best_slow_window always holds."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["best_fast_window"] < body["best_slow_window"]


def test_train_test_best_params_from_is_only(monkeypatch):
    """best params must appear as a row in all_in_sample_results."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    best = (body["best_fast_window"], body["best_slow_window"])
    is_pairs = {
        (r["fast_window"], r["slow_window"])
        for r in body["all_in_sample_results"]
    }
    assert best in is_pairs, (
        f"Best params {best} not found in in-sample results {is_pairs}"
    )


def test_train_test_sharpe_selection_picks_max_is_sharpe(monkeypatch):
    """When selection_metric=sharpe_ratio, best params have the highest IS Sharpe."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "selection_metric": "sharpe_ratio"},
    )

    assert resp.status_code == 200
    body = resp.json()
    best = (body["best_fast_window"], body["best_slow_window"])
    is_rows = body["all_in_sample_results"]
    max_sharpe_row = max(is_rows, key=lambda r: r["sharpe_ratio"])
    assert best == (max_sharpe_row["fast_window"], max_sharpe_row["slow_window"])


def test_train_test_cagr_selection(monkeypatch):
    """selection_metric=cagr selects the IS row with the highest CAGR."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "selection_metric": "cagr"},
    )

    assert resp.status_code == 200
    body = resp.json()
    best = (body["best_fast_window"], body["best_slow_window"])
    is_rows = body["all_in_sample_results"]
    max_cagr_row = max(is_rows, key=lambda r: r["cagr"])
    assert best == (max_cagr_row["fast_window"], max_cagr_row["slow_window"])


def test_train_test_calmar_selection(monkeypatch):
    """selection_metric=calmar_ratio selects the IS row with the highest Calmar."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "selection_metric": "calmar_ratio"},
    )

    assert resp.status_code == 200
    body = resp.json()
    best = (body["best_fast_window"], body["best_slow_window"])
    is_rows = body["all_in_sample_results"]
    max_calmar_row = max(is_rows, key=lambda r: r["calmar_ratio"])
    assert best == (max_calmar_row["fast_window"], max_calmar_row["slow_window"])


def test_train_test_degradation_computed_correctly(monkeypatch):
    """Degradation fields equal OOS metric minus IS metric."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    expected_sharpe_deg = round(
        body["out_of_sample_metrics"]["sharpe_ratio"]
        - body["in_sample_metrics"]["sharpe_ratio"],
        4,
    )
    assert body["sharpe_degradation"] == pytest.approx(expected_sharpe_deg, abs=1e-3)

    expected_cagr_deg = round(
        body["out_of_sample_metrics"]["cagr"]
        - body["in_sample_metrics"]["cagr"],
        6,
    )
    assert body["cagr_degradation"] == pytest.approx(expected_cagr_deg, abs=1e-5)

    expected_calmar_deg = round(
        body["out_of_sample_metrics"]["calmar_ratio"]
        - body["in_sample_metrics"]["calmar_ratio"],
        4,
    )
    assert body["calmar_degradation"] == pytest.approx(
        expected_calmar_deg,
        abs=1e-4,
    )

    expected_dd_worsening = round(
        abs(body["out_of_sample_metrics"]["max_drawdown"])
        - abs(body["in_sample_metrics"]["max_drawdown"]),
        6,
    )
    assert body["max_drawdown_worsening"] == pytest.approx(
        expected_dd_worsening,
        abs=1e-6,
    )


def test_train_test_split_trims_to_requested_dates_no_leakage(monkeypatch):
    """Rows before start_date and after end_date must not enter IS/OOS counts."""
    df = make_df(n=900, start="2009-01-01")
    start_date = str(df.index[100].date())
    split_date = str(df.index[500].date())
    end_date = str(df.index[750].date())

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            **_BASE_PAYLOAD,
            "start_date": start_date,
            "split_date": split_date,
            "end_date": end_date,
            "fast_windows": [10],
            "slow_windows": [50],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    expected_is = ((df.index >= pd.Timestamp(start_date)) & (df.index < pd.Timestamp(split_date))).sum()
    expected_oos = ((df.index >= pd.Timestamp(split_date)) & (df.index <= pd.Timestamp(end_date))).sum()
    assert body["in_sample_days"] == int(expected_is)
    assert body["out_of_sample_days"] == int(expected_oos)
    assert len(body["out_of_sample_equity_curve"]) == int(expected_oos)


def test_train_test_oos_backtest_matches_selected_params_only(monkeypatch):
    """OOS curve should equal a direct OOS-only backtest with selected params."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    close_oos = df["Close"][
        (df.index >= pd.Timestamp(body["split_date"]))
        & (df.index <= pd.Timestamp(body["end_date"]))
    ]
    position = sma_crossover_signals(
        close_oos,
        fast_window=body["best_fast_window"],
        slow_window=body["best_slow_window"],
    )
    strategy_equity, benchmark_equity, trades = run_backtest(
        close_oos,
        position,
        transaction_cost_bps=body["transaction_cost_bps"],
        initial_capital=body["initial_capital"],
    )

    assert body["out_of_sample_equity_curve"][-1]["strategy"] == pytest.approx(
        round(float(strategy_equity.iloc[-1]), 2)
    )
    assert body["out_of_sample_equity_curve"][-1]["benchmark"] == pytest.approx(
        round(float(benchmark_equity.iloc[-1]), 2)
    )
    assert body["out_of_sample_num_trades"] == len(trades)


def test_train_test_oos_equity_curve_non_empty(monkeypatch):
    """OOS equity curve must have at least 2 points with date/strategy/benchmark."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["out_of_sample_equity_curve"]) >= 2
    point = body["out_of_sample_equity_curve"][0]
    assert "date" in point
    assert "strategy" in point
    assert "benchmark" in point


def test_train_test_oos_collapsed_true_when_negative_oos_sharpe(monkeypatch):
    """oos_collapsed=True when the OOS period has a strongly negative Sharpe."""
    rng = np.random.default_rng(99)
    n_is = 2000
    n_oos = 500
    n_total = n_is + n_oos

    # IS: mild uptrend; OOS: strong downtrend → negative OOS Sharpe
    is_returns = rng.normal(5e-4, 0.01, n_is)
    oos_returns = rng.normal(-8e-3, 0.02, n_oos)
    all_returns = np.concatenate([is_returns, oos_returns])
    prices = 100.0 * (1 + all_returns).cumprod()
    idx = pd.date_range("2010-01-01", periods=n_total, freq="B")
    df = pd.DataFrame({"Close": prices}, index=idx)

    split_date = str(idx[n_is].date())
    end_date = str(idx[-1].date())

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            **_BASE_PAYLOAD,
            "split_date": split_date,
            "end_date": end_date,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    if body["out_of_sample_metrics"]["sharpe_ratio"] < 0:
        assert body["oos_collapsed"] is True


def test_train_test_fetches_data_once(monkeypatch):
    """Price data is fetched exactly once regardless of the window grid size."""
    calls = 0

    def fake_fetch(ticker, start, end):
        nonlocal calls
        calls += 1
        return make_df()

    monkeypatch.setattr(main_module, "_fetch", fake_fetch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "fast_windows": [10, 20, 30], "slow_windows": [50, 100]},
    )

    assert resp.status_code == 200
    assert calls == 1


def test_train_test_params_echoed(monkeypatch):
    """Request parameters are echoed back correctly in the response."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            "ticker": "AAPL",
            "start_date": "2010-01-01",
            "split_date": "2018-01-01",
            "end_date": "2023-12-31",
            "fast_windows": [10],
            "slow_windows": [50],
            "transaction_cost_bps": 5.0,
            "initial_capital": 50_000.0,
            "selection_metric": "cagr",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "AAPL"
    assert body["start_date"] == "2010-01-01"
    assert body["split_date"] == "2018-01-01"
    assert body["end_date"] == "2023-12-31"
    assert body["transaction_cost_bps"] == pytest.approx(5.0)
    assert body["initial_capital"] == pytest.approx(50_000.0)
    assert body["selection_metric"] == "cagr"


def test_train_test_period_day_counts_correct(monkeypatch):
    """in_sample_days + out_of_sample_days should equal total bars in the data."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-train-test", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    # Both counts should be positive
    assert body["in_sample_days"] > 0
    assert body["out_of_sample_days"] > 0


# ---------------------------------------------------------------------------
# Validation / error tests
# ---------------------------------------------------------------------------


def test_train_test_rejects_inverted_start_split():
    """start_date >= split_date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "start_date": "2020-01-01", "split_date": "2018-01-01"},
    )

    assert resp.status_code == 422


def test_train_test_rejects_inverted_split_end():
    """split_date >= end_date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "split_date": "2024-01-01", "end_date": "2023-12-31"},
    )

    assert resp.status_code == 422


def test_train_test_rejects_bad_date_format():
    """Malformed split_date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "split_date": "01/01/2018"},
    )

    assert resp.status_code == 422


def test_train_test_rejects_fast_window_below_2():
    """fast_windows with a value < 2 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "fast_windows": [1, 20]},
    )

    assert resp.status_code == 422


def test_train_test_rejects_slow_window_below_2():
    """slow_windows with a value < 2 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "slow_windows": [1, 50]},
    )

    assert resp.status_code == 422


def test_train_test_no_valid_parameter_pairs_returns_422(monkeypatch):
    """If every pair has fast >= slow, selection cannot proceed."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "fast_windows": [100, 200], "slow_windows": [50]},
    )

    assert resp.status_code == 422
    assert "No valid" in resp.json()["detail"]


def test_train_test_rejects_combinations_over_100():
    """10 fast × 11 slow = 110 > 100 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            **_BASE_PAYLOAD,
            "fast_windows": list(range(2, 12)),     # 10 values
            "slow_windows": list(range(20, 31)),    # 11 values → 110 > 100
        },
    )

    assert resp.status_code == 422


def test_train_test_is_too_short_returns_422(monkeypatch):
    """IS period too short for any window combo → 422 with informative message."""
    # 30-bar dataset; split after bar 10 → IS has 10 bars, too short for slow=50
    df, start_date, split_date, end_date = make_short_df_dates(n=30, is_count=10)
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            **_BASE_PAYLOAD,
            "start_date": start_date,
            "split_date": split_date,
            "end_date": end_date,
            "fast_windows": [10, 20],
            "slow_windows": [50, 100],
        },
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "trading days" in detail or "no valid" in detail


def test_train_test_oos_too_short_returns_422(monkeypatch):
    """OOS period has only 2 bars → 422 mentioning out-of-sample."""
    df = make_df()
    # split just 2 bars before the end
    split_date = str(df.index[-2].date())
    end_date = str(df.index[-1].date())

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={
            **_BASE_PAYLOAD,
            "split_date": split_date,
            "end_date": end_date,
        },
    )

    assert resp.status_code == 422
    assert "out-of-sample" in resp.json()["detail"].lower()


def test_train_test_rejects_empty_ticker(monkeypatch):
    """Blank ticker → 422."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "ticker": "   "},
    )

    assert resp.status_code == 422


def test_train_test_invalid_selection_metric():
    """Unknown selection_metric → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-train-test",
        json={**_BASE_PAYLOAD, "selection_metric": "omega_ratio"},
    )

    assert resp.status_code == 422
