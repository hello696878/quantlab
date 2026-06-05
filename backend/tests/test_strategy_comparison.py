"""
API tests for the strategy comparison endpoint.

All tests monkeypatch the data-fetch layer to avoid network calls.

The synthetic price series (500 bars ≈ 2 years) is long enough to satisfy
the 102-bar minimum imposed by SMA Crossover (slow=100).
"""

import numpy as np
import pandas as pd
import pytest

from app.backtest import run_backtest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_STRATEGY_IDS = {
    "sma_crossover",
    "rsi_mean_reversion",
    "bollinger_band",
    "momentum",
    "volatility_breakout",
}

EXPECTED_DISPLAY_NAMES = {
    "SMA Crossover",
    "RSI Mean Reversion",
    "Bollinger Band",
    "Momentum",
    "Volatility Breakout",
}

METRIC_FIELDS = (
    "total_return",
    "cagr",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "volatility",
    "calmar_ratio",
    "win_rate",
    "num_days",
)

_BASE_PAYLOAD = {
    "ticker": "SPY",
    "start_date": "2010-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 100_000.0,
    "transaction_cost_bps": 10.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_df(n: int = 500, start: str = "2010-01-01") -> pd.DataFrame:
    """Deterministic synthetic price series (n bars starting at *start*)."""
    rng = np.random.default_rng(42)
    returns = rng.normal(4e-4, 0.01, n)
    prices = 100.0 * (1 + returns).cumprod()
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_comparison_smoke(monkeypatch):
    """Valid request returns 200 with all required top-level keys."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "ticker", "start_date", "end_date",
        "initial_capital", "transaction_cost_bps",
        "strategies", "benchmark", "benchmark_metrics", "ranking",
    ):
        assert key in body, f"Missing top-level key: {key!r}"


def test_comparison_all_five_strategies_present(monkeypatch):
    """Response must include exactly five strategies with correct identifiers."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    assert len(body["strategies"]) == 5
    ids = {s["strategy"] for s in body["strategies"]}
    assert ids == EXPECTED_STRATEGY_IDS
    assert "pairs" not in ids


def test_comparison_strategy_order_is_fixed(monkeypatch):
    """Frontend chart/table can rely on the documented five-strategy order."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    assert [s["strategy"] for s in body["strategies"]] == [
        "sma_crossover",
        "rsi_mean_reversion",
        "bollinger_band",
        "momentum",
        "volatility_breakout",
    ]


def test_comparison_display_names(monkeypatch):
    """Each strategy result must carry the correct human-readable display name."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    display_names = {s["display_name"] for s in body["strategies"]}
    assert display_names == EXPECTED_DISPLAY_NAMES


def test_comparison_metrics_shape(monkeypatch):
    """Every strategy result must contain a metrics object with all required fields."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    for strat in body["strategies"]:
        m = strat["metrics"]
        for field in METRIC_FIELDS:
            assert field in m, (
                f"Metric field {field!r} missing for strategy {strat['strategy']!r}"
            )


def test_comparison_equity_curves_non_empty(monkeypatch):
    """Every strategy equity curve must be non-empty."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    for strat in body["strategies"]:
        assert len(strat["equity_curve"]) > 0, (
            f"Empty equity curve for {strat['strategy']!r}"
        )


def test_comparison_benchmark_non_empty(monkeypatch):
    """Benchmark equity curve must be non-empty."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    assert len(body["benchmark"]) > 0


def test_comparison_benchmark_metrics_present(monkeypatch):
    """benchmark_metrics must contain all standard metric fields."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    for field in METRIC_FIELDS:
        assert field in body["benchmark_metrics"], (
            f"benchmark_metrics missing field {field!r}"
        )


def test_comparison_ranking_valid_display_names(monkeypatch):
    """All four ranking fields must refer to known strategy display names."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    ranking = body["ranking"]

    for field in ("best_by_sharpe", "best_by_cagr", "best_by_calmar", "lowest_drawdown"):
        assert ranking[field] in EXPECTED_DISPLAY_NAMES, (
            f"ranking.{field} = {ranking[field]!r} is not a known display name"
        )


def test_comparison_ranking_best_sharpe_is_correct(monkeypatch):
    """best_by_sharpe must be the display name of the strategy with max Sharpe ratio."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    strategies = body["strategies"]

    expected = max(strategies, key=lambda s: s["metrics"]["sharpe_ratio"])["display_name"]
    assert body["ranking"]["best_by_sharpe"] == expected


def test_comparison_ranking_lowest_drawdown_is_correct(monkeypatch):
    """lowest_drawdown must be the strategy whose max_drawdown is closest to 0."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    strategies = body["strategies"]

    # max_drawdown is negative; highest value = least negative = smallest absolute DD
    expected = max(strategies, key=lambda s: s["metrics"]["max_drawdown"])["display_name"]
    assert body["ranking"]["lowest_drawdown"] == expected


def test_comparison_ranking_best_cagr_is_correct(monkeypatch):
    """best_by_cagr must be the display name of the strategy with highest CAGR."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    strategies = body["strategies"]

    expected = max(strategies, key=lambda s: s["metrics"]["cagr"])["display_name"]
    assert body["ranking"]["best_by_cagr"] == expected


def test_comparison_ranking_best_calmar_is_correct(monkeypatch):
    """best_by_calmar must be the display name of the strategy with highest Calmar."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    strategies = body["strategies"]

    expected = max(strategies, key=lambda s: s["metrics"]["calmar_ratio"])["display_name"]
    assert body["ranking"]["best_by_calmar"] == expected


def test_comparison_ranking_ties_are_deterministic(monkeypatch):
    """When metrics tie, ranking keeps the fixed strategy order."""
    df = make_df()

    def flat_metrics(_equity):
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe_ratio": 1.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "calmar_ratio": 1.0,
            "win_rate": 0.0,
            "num_days": len(df),
        }

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    monkeypatch.setattr(main_module, "compute_metrics", flat_metrics)
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    assert body["ranking"]["best_by_sharpe"] == "SMA Crossover"
    assert body["ranking"]["best_by_cagr"] == "SMA Crossover"
    assert body["ranking"]["best_by_calmar"] == "SMA Crossover"
    assert body["ranking"]["lowest_drawdown"] == "SMA Crossover"


def test_comparison_params_echoed(monkeypatch):
    """Top-level identity fields must echo the request values."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    assert body["ticker"] == "SPY"
    assert body["start_date"] == _BASE_PAYLOAD["start_date"]
    assert body["end_date"] == _BASE_PAYLOAD["end_date"]
    assert body["initial_capital"] == _BASE_PAYLOAD["initial_capital"]
    assert body["transaction_cost_bps"] == _BASE_PAYLOAD["transaction_cost_bps"]


def test_comparison_default_strategy_params(monkeypatch):
    """Each strategy uses the reviewed fixed default parameters."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    params = {s["strategy"]: s["params"] for s in body["strategies"]}

    # Demo-friendly defaults (mirror the calibrated single-strategy schema
    # defaults — Phase 9.4 / 9.4.1).
    assert params["sma_crossover"] == {"fast_window": 20, "slow_window": 100}
    assert params["rsi_mean_reversion"] == {
        "rsi_window": 14,
        "oversold_threshold": 35.0,
        "exit_threshold": 55.0,
    }
    assert params["bollinger_band"] == {
        "bb_window": 20,
        "num_std": 1.8,
        "exit_band": "middle",
    }
    assert params["momentum"] == {
        "momentum_window": 63,
        "entry_threshold": 0.0,
        "exit_threshold": 0.0,
    }
    assert params["volatility_breakout"] == {
        "lookback_window": 20,
        "breakout_multiplier": 0.3,
        "exit_window": 10,
    }


def test_comparison_uses_requested_date_range_only(monkeypatch):
    """Rows outside start/end must not enter strategy or benchmark curves."""
    df = make_df(n=700, start="2009-01-01")
    start_date = str(df.index[100].date())
    end_date = str(df.index[599].date())

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    body = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "start_date": start_date, "end_date": end_date},
    ).json()

    expected_len = int(
        ((df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))).sum()
    )
    assert len(body["benchmark"]) == expected_len
    assert body["benchmark"][0]["date"] == start_date
    assert body["benchmark"][-1]["date"] == end_date
    for strategy in body["strategies"]:
        assert len(strategy["equity_curve"]) == expected_len
        assert strategy["equity_curve"][0]["date"] == start_date
        assert strategy["equity_curve"][-1]["date"] == end_date


def test_comparison_benchmark_matches_buy_and_hold(monkeypatch):
    """Benchmark must be same-ticker buy-and-hold with same capital and dates."""
    df = make_df()
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()
    close = df["Close"]
    flat_position = pd.Series(0, index=close.index)
    _strategy, benchmark, _trades = run_backtest(
        close,
        flat_position,
        transaction_cost_bps=_BASE_PAYLOAD["transaction_cost_bps"],
        initial_capital=_BASE_PAYLOAD["initial_capital"],
    )

    assert body["benchmark"][0]["strategy"] == pytest.approx(round(float(benchmark.iloc[0]), 2))
    assert body["benchmark"][-1]["strategy"] == pytest.approx(round(float(benchmark.iloc[-1]), 2))
    assert body["benchmark"][0]["benchmark"] == body["benchmark"][0]["strategy"]
    assert body["benchmark"][-1]["benchmark"] == body["benchmark"][-1]["strategy"]


def test_comparison_all_strategies_use_same_cost_and_capital(monkeypatch):
    """Every compared strategy should run through run_backtest with request settings."""
    df = make_df()
    calls = []
    original = main_module.run_backtest

    def recording_run_backtest(*, close, position, transaction_cost_bps, initial_capital):
        calls.append((transaction_cost_bps, initial_capital, len(close)))
        return original(
            close=close,
            position=position,
            transaction_cost_bps=transaction_cost_bps,
            initial_capital=initial_capital,
        )

    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: df)
    monkeypatch.setattr(main_module, "run_backtest", recording_run_backtest)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "transaction_cost_bps": 7.0, "initial_capital": 12_345.0},
    )

    assert resp.status_code == 200
    assert len(calls) == 5
    assert all(call == (7.0, 12_345.0, len(df)) for call in calls)


def test_comparison_ticker_uppercased(monkeypatch):
    """ticker is normalised to uppercase in the response."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "ticker": "spy"},
    ).json()

    assert body["ticker"] == "SPY"


def test_comparison_each_strategy_has_nonempty_params(monkeypatch):
    """Every strategy result must include a non-empty params dict."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    for strat in body["strategies"]:
        assert isinstance(strat["params"], dict), (
            f"params is not a dict for {strat['strategy']!r}"
        )
        assert len(strat["params"]) > 0, (
            f"params is empty for {strat['strategy']!r}"
        )


def test_comparison_num_trades_nonnegative(monkeypatch):
    """num_trades must be >= 0 for every strategy."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    body = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD).json()

    for strat in body["strategies"]:
        assert strat["num_trades"] >= 0, (
            f"Negative num_trades for {strat['strategy']!r}"
        )


def test_comparison_fetch_called_once(monkeypatch):
    """_fetch must be called exactly once — all strategies share one data pull."""
    fetch_calls = {"n": 0}
    df = make_df()

    def counting_fetch(ticker, start, end):
        fetch_calls["n"] += 1
        return df

    monkeypatch.setattr(main_module, "_fetch", counting_fetch)
    client = TestClient(main_module.app)
    resp = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    assert fetch_calls["n"] == 1, (
        f"Expected _fetch to be called once, got {fetch_calls['n']}"
    )


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_comparison_too_short_returns_422(monkeypatch):
    """Fewer than 102 trading days → 422 (SMA 20/100 cannot run)."""
    short_df = make_df(n=100)
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: short_df)
    client = TestClient(main_module.app)

    resp = client.post("/research/strategy-comparison", json=_BASE_PAYLOAD)

    assert resp.status_code == 422


def test_comparison_invalid_ticker_returns_404(monkeypatch):
    """_fetch raising HTTPException(404) results in a 404 response."""
    from fastapi import HTTPException as _HTTPException

    def raise_not_found(ticker, start, end):
        raise _HTTPException(status_code=404, detail=f"No price data found for {ticker}.")

    monkeypatch.setattr(main_module, "_fetch", raise_not_found)
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "ticker": "INVALID99"},
    )

    assert resp.status_code == 404


def test_comparison_bad_date_format_returns_422(monkeypatch):
    """Malformed start_date is rejected at schema validation (422), before _fetch."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "start_date": "01/01/2010"},
    )

    assert resp.status_code == 422


def test_comparison_start_after_end_returns_422(monkeypatch):
    """start_date >= end_date is rejected at schema validation."""
    monkeypatch.setattr(main_module, "_fetch", lambda t, s, e: make_df())
    client = TestClient(main_module.app)

    resp = client.post(
        "/research/strategy-comparison",
        json={**_BASE_PAYLOAD, "start_date": "2023-01-01", "end_date": "2015-01-01"},
    )

    assert resp.status_code == 422
