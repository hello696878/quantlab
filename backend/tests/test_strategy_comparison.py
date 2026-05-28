"""
API tests for the strategy comparison endpoint.

All tests monkeypatch the data-fetch layer to avoid network calls.

The synthetic price series (500 bars ≈ 2 years) is long enough to satisfy
the 202-bar minimum imposed by SMA Crossover (slow=200).
"""

import numpy as np
import pandas as pd
import pytest

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
    """Fewer than 202 trading days → 422 (SMA 50/200 cannot run)."""
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
