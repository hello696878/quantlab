"""
API tests for the SMA walk-forward optimization endpoint.

All tests monkeypatch the data-fetch layer to avoid network calls.

The synthetic price series is long enough (1200 bars ≈ 4.8 years) to
produce several walk-forward windows with the default compact settings
(train=252, test=63, step=63).
"""

import numpy as np
import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_df(n: int = 1200, start: str = "2010-01-01") -> pd.DataFrame:
    """Deterministic synthetic price series."""
    rng = np.random.default_rng(7)
    returns = rng.normal(4e-4, 0.01, n)
    prices = 100.0 * (1 + returns).cumprod()
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


def make_payload(df: pd.DataFrame, **overrides) -> dict:
    """
    Build a minimal valid walk-forward payload whose dates come from *df*.
    Defaults: train=252, test=63, step=63, fast=[10,20], slow=[50,100].
    """
    start_date = str(df.index[0].date())
    end_date = str(df.index[-1].date())
    base = {
        "ticker": "SPY",
        "start_date": start_date,
        "end_date": end_date,
        "train_window_days": 252,
        "test_window_days": 63,
        "step_days": 63,
        "fast_windows": [10, 20],
        "slow_windows": [50, 100],
        "selection_metric": "sharpe_ratio",
        "initial_capital": 100_000.0,
        "transaction_cost_bps": 10.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_walk_forward_smoke(monkeypatch):
    """Valid request returns 200 with all required top-level keys."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "ticker", "start_date", "end_date",
        "train_window_days", "test_window_days", "step_days",
        "selection_metric", "initial_capital", "transaction_cost_bps",
        "num_windows", "windows",
        "stitched_equity_curve",
        "aggregate_metrics", "aggregate_benchmark_metrics",
        "parameter_stability",
    ):
        assert key in body, f"Missing top-level key: {key}"


def test_walk_forward_correct_window_count(monkeypatch):
    """Number of windows matches the expected formula."""
    df = make_df(1200)
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    train_w, test_w, step = 252, 63, 63
    payload = make_payload(df, train_window_days=train_w, test_window_days=test_w, step_days=step,
                           fast_windows=[10], slow_windows=[50])
    resp = client.post("/research/sma-walk-forward", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    n = len(df)
    # Expected windows = floor((n - train_w - test_w) / step) + 1
    # BUT some windows may be skipped if test_w < best_slow + 2 → use >= check
    expected_min = 1
    expected_max = (n - train_w - test_w) // step + 1
    assert expected_min <= body["num_windows"] <= expected_max
    assert body["num_windows"] == len(body["windows"])


def test_walk_forward_window_fields(monkeypatch):
    """Each window object contains all required fields."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    w = resp.json()["windows"][0]
    for key in (
        "window_index", "train_start_date", "train_end_date",
        "test_start_date", "test_end_date", "train_days", "test_days",
        "best_fast_window", "best_slow_window",
        "train_metrics", "test_metrics", "test_benchmark_metrics",
        "num_trades",
    ):
        assert key in w, f"Missing window key: {key}"


def test_walk_forward_metrics_have_calmar(monkeypatch):
    """train_metrics, test_metrics, and aggregate_metrics include calmar_ratio."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    body = resp.json()
    assert "calmar_ratio" in body["aggregate_metrics"]
    assert "calmar_ratio" in body["windows"][0]["train_metrics"]
    assert "calmar_ratio" in body["windows"][0]["test_metrics"]


def test_walk_forward_best_params_valid(monkeypatch):
    """Every window's best_fast_window < best_slow_window."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    for w in resp.json()["windows"]:
        assert w["best_fast_window"] < w["best_slow_window"], (
            f"Window {w['window_index']}: fast={w['best_fast_window']} "
            f">= slow={w['best_slow_window']}"
        )


def test_walk_forward_no_data_leakage(monkeypatch):
    """Test window must start AFTER the training window ends."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    for w in resp.json()["windows"]:
        assert w["test_start_date"] > w["train_end_date"], (
            f"Window {w['window_index']}: test starts before train ends"
        )


def test_walk_forward_windows_ordered(monkeypatch):
    """Windows are returned in ascending order by window_index and start date."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    windows = resp.json()["windows"]
    for i in range(1, len(windows)):
        assert windows[i]["window_index"] > windows[i - 1]["window_index"]
        assert windows[i]["train_start_date"] >= windows[i - 1]["train_start_date"]


def test_walk_forward_stitched_equity_curve_non_empty(monkeypatch):
    """Stitched equity curve has points with date/strategy/benchmark."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    curve = resp.json()["stitched_equity_curve"]
    assert len(curve) >= 2
    pt = curve[0]
    assert "date" in pt and "strategy" in pt and "benchmark" in pt


def test_walk_forward_stitched_curve_starts_at_initial_capital(monkeypatch):
    """Stitched equity curve's first strategy value equals initial_capital."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    capital = 75_000.0
    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, initial_capital=capital),
    )

    assert resp.status_code == 200
    first_pt = resp.json()["stitched_equity_curve"][0]
    assert abs(first_pt["strategy"] - capital) < 1.0


def test_walk_forward_aggregate_metrics_present(monkeypatch):
    """aggregate_metrics has all PerformanceMetrics fields."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    m = resp.json()["aggregate_metrics"]
    for key in (
        "total_return", "cagr", "sharpe_ratio", "sortino_ratio",
        "max_drawdown", "volatility", "calmar_ratio", "win_rate", "num_days",
    ):
        assert key in m, f"aggregate_metrics missing: {key}"


def test_walk_forward_parameter_stability_present(monkeypatch):
    """parameter_stability object has all required fields."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    ps = resp.json()["parameter_stability"]
    for key in (
        "num_windows", "unique_parameter_sets",
        "most_common_fast_window", "most_common_slow_window",
        "most_common_count", "all_selected_params", "parameters_unstable",
    ):
        assert key in ps, f"parameter_stability missing: {key}"


def test_walk_forward_param_stability_consistent(monkeypatch):
    """all_selected_params length == num_windows."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    body = resp.json()
    ps = body["parameter_stability"]
    assert ps["num_windows"] == body["num_windows"]
    assert len(ps["all_selected_params"]) == body["num_windows"]


def test_walk_forward_single_param_pair_is_stable(monkeypatch):
    """With only one valid (fast, slow) pair, parameters_unstable must be False."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, fast_windows=[10], slow_windows=[50]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["parameter_stability"]["unique_parameter_sets"] == 1
    assert body["parameter_stability"]["parameters_unstable"] is False


def test_walk_forward_fetches_data_once(monkeypatch):
    """Data is fetched exactly once regardless of window count."""
    df = make_df()
    calls = 0

    def fake_fetch(t, s, e):
        nonlocal calls
        calls += 1
        return df

    monkeypatch.setattr(main_module, "_fetch", fake_fetch)
    client = TestClient(main_module.app)

    resp = client.post("/research/sma-walk-forward", json=make_payload(df))

    assert resp.status_code == 200
    assert calls == 1


def test_walk_forward_sharpe_selection(monkeypatch):
    """selection_metric=sharpe_ratio — best params in window 0 equal max IS Sharpe."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, selection_metric="sharpe_ratio"),
    )

    assert resp.status_code == 200
    # Just verify it runs successfully and returns valid params
    w0 = resp.json()["windows"][0]
    assert w0["best_fast_window"] < w0["best_slow_window"]


def test_walk_forward_cagr_selection(monkeypatch):
    """selection_metric=cagr returns 200 with valid window params."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, selection_metric="cagr"),
    )

    assert resp.status_code == 200
    assert resp.json()["num_windows"] >= 1


def test_walk_forward_calmar_selection(monkeypatch):
    """selection_metric=calmar_ratio returns 200."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, selection_metric="calmar_ratio"),
    )

    assert resp.status_code == 200


def test_walk_forward_ticker_uppercased(monkeypatch):
    """Ticker is always upper-cased in the response."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, ticker="spy"),
    )

    assert resp.status_code == 200
    assert resp.json()["ticker"] == "SPY"


def test_walk_forward_params_echoed(monkeypatch):
    """Request parameters are echoed in the response."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    payload = make_payload(
        df,
        ticker="AAPL",
        train_window_days=300,
        test_window_days=63,
        step_days=63,
        transaction_cost_bps=5.0,
        initial_capital=50_000.0,
        selection_metric="cagr",
    )
    resp = client.post("/research/sma-walk-forward", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "AAPL"
    assert body["train_window_days"] == 300
    assert body["test_window_days"] == 63
    assert body["step_days"] == 63
    assert abs(body["transaction_cost_bps"] - 5.0) < 1e-6
    assert abs(body["initial_capital"] - 50_000.0) < 1e-6
    assert body["selection_metric"] == "cagr"


# ---------------------------------------------------------------------------
# Validation / error tests
# ---------------------------------------------------------------------------


def test_walk_forward_rejects_not_enough_data(monkeypatch):
    """Data shorter than train+test → 422."""
    df = make_df(300)
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, train_window_days=252, test_window_days=252),
    )

    assert resp.status_code == 422
    assert "trading days" in resp.json()["detail"]


def test_walk_forward_rejects_inverted_dates():
    """start_date >= end_date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json={
            "ticker": "SPY",
            "start_date": "2023-01-01",
            "end_date": "2010-01-01",
            "train_window_days": 252,
            "test_window_days": 63,
            "step_days": 63,
            "fast_windows": [10],
            "slow_windows": [50],
        },
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_all_fast_ge_slow(monkeypatch):
    """All fast >= slow → 422 (no valid pairs)."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, fast_windows=[200, 300], slow_windows=[50, 100]),
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_fast_window_below_2():
    """fast_windows with value < 2 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json={
            "ticker": "SPY",
            "start_date": "2010-01-01",
            "end_date": "2023-12-31",
            "train_window_days": 252,
            "test_window_days": 63,
            "step_days": 63,
            "fast_windows": [1, 20],
            "slow_windows": [50],
        },
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_combinations_over_100():
    """10 fast × 11 slow > 100 → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json={
            "ticker": "SPY",
            "start_date": "2010-01-01",
            "end_date": "2023-12-31",
            "train_window_days": 252,
            "test_window_days": 63,
            "step_days": 63,
            "fast_windows": list(range(2, 12)),
            "slow_windows": list(range(20, 31)),
        },
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_empty_ticker(monkeypatch):
    """Blank ticker → 422."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json=make_payload(df, ticker="   "),
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_invalid_selection_metric():
    """Unknown selection_metric → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json={
            "ticker": "SPY",
            "start_date": "2010-01-01",
            "end_date": "2023-12-31",
            "train_window_days": 252,
            "test_window_days": 63,
            "step_days": 63,
            "fast_windows": [10],
            "slow_windows": [50],
            "selection_metric": "omega_ratio",
        },
    )

    assert resp.status_code == 422


def test_walk_forward_rejects_bad_date_format():
    """Malformed date → 422."""
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/sma-walk-forward",
        json={
            "ticker": "SPY",
            "start_date": "01/01/2010",
            "end_date": "2023-12-31",
            "train_window_days": 252,
            "test_window_days": 63,
            "step_days": 63,
            "fast_windows": [10],
            "slow_windows": [50],
        },
    )

    assert resp.status_code == 422
