"""
Tests for the benchmark / active-performance analytics engine (research v1).

Layers:
  * pure math (`app.benchmark.compute_active_metrics`) on deterministic series —
    beta / alpha / correlation / tracking error / information ratio, plus the
    zero-variance and zero-tracking-error guards;
  * the API — defaults, custom-ticker fetch through the provider seam
    (monkeypatched), alignment, mode none, invalid benchmark, comparison
    integration, and backward compatibility.

All synthetic / monkeypatched — no live yfinance.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.benchmark import compute_active_metrics
from app.schemas import BenchmarkConfig

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _eq(values, start="2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx)


# ---------------------------------------------------------------------------
# Pure active-metric math
# ---------------------------------------------------------------------------


def test_beta_two_on_scaled_returns():
    # Strategy daily return is exactly 2× the benchmark's → beta = 2, corr = 1.
    rng = np.random.default_rng(11)
    bench_ret = rng.normal(0.001, 0.01, 60)
    bench_eq = _eq(100 * np.cumprod(1 + bench_ret))
    strat_eq = _eq(100 * np.cumprod(1 + 2 * bench_ret))
    active, warnings = compute_active_metrics(strat_eq, bench_eq, 252)
    assert active.beta == pytest.approx(2.0, abs=0.05)
    assert active.correlation == pytest.approx(1.0, abs=1e-6)
    assert warnings == []


def test_alpha_positive_for_constant_outperformance():
    # Strategy = benchmark return + 10 bps/day → beta 1, alpha ≈ 0.001 × 252.
    rng = np.random.default_rng(12)
    bench_ret = rng.normal(0.0, 0.01, 120)
    bench_eq = _eq(100 * np.cumprod(1 + bench_ret))
    strat_eq = _eq(100 * np.cumprod(1 + bench_ret + 0.001))
    active, _ = compute_active_metrics(strat_eq, bench_eq, 252)
    assert active.beta == pytest.approx(1.0, abs=0.05)
    assert active.alpha == pytest.approx(0.001 * 252, rel=0.15)


def test_excess_total_return():
    bench_eq = _eq([100, 110])  # +10%
    strat_eq = _eq([100, 121])  # +21%
    # Too few points for full active metrics, so use longer series instead.
    bench_eq = _eq([100 * 1.001**i for i in range(50)])
    strat_eq = _eq([100 * 1.002**i for i in range(50)])
    active, _ = compute_active_metrics(strat_eq, bench_eq, 252)
    expected = (1.002**49 - 1) - (1.001**49 - 1)
    # Response values are rounded to 6 decimals for JSON.
    assert active.excess_total_return == pytest.approx(expected, abs=1e-5)


def test_tracking_error_and_information_ratio():
    # Constant active return a → std(active)=0 edge; use alternating instead.
    bench_ret = np.full(100, 0.001)
    act = np.where(np.arange(100) % 2 == 0, 0.002, -0.001)  # mean 5 bps, sd 15 bps
    bench_eq = _eq(100 * np.cumprod(1 + bench_ret))
    strat_eq = _eq(100 * np.cumprod(1 + bench_ret + act))
    active, _ = compute_active_metrics(strat_eq, bench_eq, 252)
    # Compare against directly computed aligned active returns.
    sr = strat_eq.pct_change().dropna()
    br = bench_eq.pct_change().dropna()
    a = sr - br
    te = float(a.std()) * math.sqrt(252)
    # Response values are rounded (6 / 4 decimals) for JSON.
    assert active.tracking_error == pytest.approx(te, abs=1e-5)
    assert active.information_ratio == pytest.approx(float(a.mean()) * 252 / te, abs=1e-3)


def test_zero_benchmark_variance_nulls_beta_with_warning():
    bench_eq = _eq([100.0] * 60)  # flat benchmark → zero variance
    rng = np.random.default_rng(13)
    strat_eq = _eq(100 * np.cumprod(1 + rng.normal(0.001, 0.01, 60)))
    active, warnings = compute_active_metrics(strat_eq, bench_eq, 252)
    assert active.beta is None
    assert active.alpha is None
    assert active.correlation is None
    assert any("zero variance" in w for w in warnings)
    # Excess return still computable.
    assert active.excess_total_return is not None


def test_zero_tracking_error_nulls_information_ratio_with_warning():
    eq = _eq([100 * 1.001**i for i in range(60)])
    active, warnings = compute_active_metrics(eq, eq.copy(), 252)
    assert active.tracking_error == 0.0
    assert active.information_ratio is None
    assert any("Tracking error is zero" in w for w in warnings)


def test_insufficient_overlap_returns_nulls_with_warning():
    strat_eq = _eq([100, 101, 102, 103, 104], start="2020-01-01")
    bench_eq = _eq([100, 101, 102, 103, 104], start="2021-06-01")  # no overlap
    active, warnings = compute_active_metrics(strat_eq, bench_eq, 252)
    assert active.beta is None and active.excess_total_return is None
    assert active.aligned_points == 0
    assert any("aligned data point" in w for w in warnings)


def test_benchmark_config_validation():
    with pytest.raises(ValueError):
        BenchmarkConfig(mode="custom_ticker")  # missing ticker
    with pytest.raises(ValueError):
        BenchmarkConfig(mode="custom_ticker", ticker="   ")
    c = BenchmarkConfig(mode="custom_ticker", ticker=" qqq ")
    assert c.ticker == "QQQ"
    # ticker ignored for non-custom modes
    assert BenchmarkConfig(mode="none", ticker="SPY").ticker is None
    assert BenchmarkConfig(mode="buy_and_hold_same_asset", ticker="SPY").ticker is None


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=400, freq="B")


def _series_for(ticker: str) -> list[float]:
    prices = [100.0]
    # Different deterministic shapes per ticker so benchmarks differ from SPY.
    shift = 0.1 if ticker.upper() == "QQQ" else 0.0
    for i in range(1, len(_DATES)):
        r = 0.012 * math.sin(0.045 * i + shift) + 0.004 * math.cos(0.23 * i + shift)
        prices.append(prices[-1] * (1.0 + r))
    return prices


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    if ticker.upper() == "EMPTY":
        raise main_module.HTTPException(status_code=404, detail=f"No data returned for ticker '{ticker}'.")
    return pd.DataFrame({"Close": _series_for(ticker)}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_old_request_gets_default_buy_and_hold_block(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    b = body["benchmark_analytics"]
    assert b["mode"] == "buy_and_hold_same_asset"
    assert b["ticker"] == "SPY"
    assert b["metrics"]["total_return"] == body["benchmark_metrics"]["total_return"]
    assert b["active_metrics"]["beta"] is not None
    assert b["equity_curve"] is None  # same-asset curve already on equity_curve
    # Legacy fields unchanged.
    assert "benchmark_metrics" in body and len(body["equity_curve"]) == len(_DATES)


def test_api_benchmark_does_not_change_strategy_results(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"benchmark": {"mode": "none"}}
    ).json()
    c = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    ).json()
    assert a["equity_curve"] == b["equity_curve"] == c["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"] == c["strategy_metrics"]
    assert a["num_trades"] == b["num_trades"] == c["num_trades"]


def test_api_mode_none_omits_block_keeps_legacy_fields(client):
    body = client.post(
        "/backtest/sma-crossover", json={"benchmark": {"mode": "none"}}
    ).json()
    assert body["benchmark_analytics"] is None
    assert "benchmark_metrics" in body  # legacy field preserved


def test_api_custom_ticker_fetches_aligns_and_reports(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    ).json()
    b = body["benchmark_analytics"]
    assert b["mode"] == "custom_ticker"
    assert b["ticker"] == "QQQ"
    assert b["display_name"] == "Buy & Hold QQQ"
    assert b["data_provider"] == "yfinance"
    assert b["data_quality"]["ticker"] == "QQQ"
    assert b["metrics"]["total_return"] is not None
    assert b["active_metrics"]["aligned_points"] == len(_DATES)
    # Custom benchmark equity curve present, normalized to initial capital.
    assert b["equity_curve"][0]["equity"] == pytest.approx(100_000.0)
    for k in ("alpha", "beta", "correlation", "tracking_error", "information_ratio"):
        assert b["active_metrics"][k] is not None


def test_api_invalid_custom_benchmark_warns_strategy_still_runs(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "EMPTY"}},
    ).json()
    assert body["strategy_metrics"]["total_return"] is not None  # strategy ran
    b = body["benchmark_analytics"]
    assert b["metrics"] is None and b["active_metrics"] is None
    assert any("could not be fetched" in w for w in b["warnings"])


def test_api_custom_benchmark_validation_422(client):
    resp = client.post(
        "/backtest/sma-crossover", json={"benchmark": {"mode": "custom_ticker"}}
    )
    assert resp.status_code == 422
    resp2 = client.post(
        "/backtest/sma-crossover", json={"benchmark": {"mode": "nonsense"}}
    )
    assert resp2.status_code == 422


def test_api_annualization_changes_active_metrics_not_equity(client):
    a = client.post(
        "/backtest/sma-crossover",
        json={"annualization_mode": "trading_days_252"},
    ).json()
    b = client.post(
        "/backtest/sma-crossover",
        json={"annualization_mode": "crypto_365"},
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    am_a = a["benchmark_analytics"]["active_metrics"]
    am_b = b["benchmark_analytics"]["active_metrics"]
    assert am_a["excess_total_return"] == am_b["excess_total_return"]
    assert am_a["tracking_error"] != am_b["tracking_error"]  # √ppy scaling


def test_api_same_asset_custom_ticker_reuses_data(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "SPY"}},
    ).json()
    b = body["benchmark_analytics"]
    # Buy & hold of the strategy's own asset ⇒ matches the legacy benchmark.
    assert b["metrics"]["total_return"] == pytest.approx(
        body["benchmark_metrics"]["total_return"], abs=1e-9
    )


def test_api_comparison_accepts_benchmark_and_adds_active_metrics(client):
    body = client.post(
        "/research/strategy-comparison",
        json={"benchmark": {"mode": "buy_and_hold_same_asset"}},
    ).json()
    b = body["benchmark_analytics"]
    assert b["mode"] == "buy_and_hold_same_asset"
    assert b["metrics"]["total_return"] == body["benchmark_metrics"]["total_return"]
    for s in body["strategies"]:
        assert s["active_metrics"] is not None
        assert s["active_metrics"]["excess_total_return"] is not None


def test_api_comparison_custom_benchmark(client):
    body = client.post(
        "/research/strategy-comparison",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    ).json()
    b = body["benchmark_analytics"]
    assert b["ticker"] == "QQQ"
    assert b["data_quality"]["ticker"] == "QQQ"
    assert all(s["active_metrics"] is not None for s in body["strategies"])


def test_api_comparison_mode_none(client):
    body = client.post(
        "/research/strategy-comparison", json={"benchmark": {"mode": "none"}}
    ).json()
    assert body["benchmark_analytics"] is None
    assert all(s["active_metrics"] is None for s in body["strategies"])
    assert "benchmark_metrics" in body  # legacy comparison fields intact


def test_api_comparison_invalid_custom_benchmark_warns(client):
    body = client.post(
        "/research/strategy-comparison",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "EMPTY"}},
    ).json()
    b = body["benchmark_analytics"]
    assert b["metrics"] is None
    assert any("could not be fetched" in w for w in b["warnings"])
    assert all(s["active_metrics"] is None for s in body["strategies"])
    assert len(body["strategies"]) == 5  # strategies still ran


# ---------------------------------------------------------------------------
# Visualization data (Phase 12.6.1) — curves the frontend charts consume
# ---------------------------------------------------------------------------


def test_api_buy_and_hold_curve_on_response_aligns_with_strategy(client):
    """The legacy equity_curve carries the same-asset benchmark, date-aligned."""
    body = client.post("/backtest/sma-crossover", json={}).json()
    curve = body["equity_curve"]
    assert len(curve) == len(_DATES)
    for p in curve:
        assert "strategy" in p and "benchmark" in p and "date" in p
    # Both series start at initial capital (same normalization).
    assert curve[0]["strategy"] == pytest.approx(100_000.0, rel=1e-6)
    assert curve[0]["benchmark"] == pytest.approx(100_000.0, rel=1e-6)


def test_api_custom_benchmark_curve_dates_subset_of_strategy_dates(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    ).json()
    strat_dates = {p["date"] for p in body["equity_curve"]}
    bench_curve = body["benchmark_analytics"]["equity_curve"]
    assert len(bench_curve) >= 2
    assert all(p["date"] in strat_dates for p in bench_curve)
    # Dates ascend (chartable without re-sorting).
    dates = [p["date"] for p in bench_curve]
    assert dates == sorted(dates)


def test_api_benchmark_drawdown_computable_from_curve(client):
    """Drawdown derived from the returned benchmark curve is finite, <= 0, and
    its minimum matches the reported benchmark max drawdown."""
    body = client.post(
        "/backtest/sma-crossover",
        json={"benchmark": {"mode": "custom_ticker", "ticker": "QQQ"}},
    ).json()
    b = body["benchmark_analytics"]
    values = [p["equity"] for p in b["equity_curve"]]
    peak = values[0]
    dds = []
    for v in values:
        peak = max(peak, v)
        dds.append(v / peak - 1.0)
    assert all(math.isfinite(d) and d <= 1e-12 for d in dds)
    assert min(dds) == pytest.approx(b["metrics"]["max_drawdown"], abs=1e-3)


def test_api_mode_none_has_no_benchmark_chart_payload(client):
    body = client.post(
        "/backtest/sma-crossover", json={"benchmark": {"mode": "none"}}
    ).json()
    assert body["benchmark_analytics"] is None  # nothing for the charts
    # Legacy response shape still serializes safely (old-frontend compatible).
    assert len(body["equity_curve"]) == len(_DATES)
    assert "benchmark_metrics" in body
