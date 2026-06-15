"""
Tests for the Event-Driven / Arbitrage Lab v1 (event study + merger arb).

Deterministic, synthetic-data only — no live yfinance.  The pure functions are
tested directly on constructed price series; the API is tested with a
monkeypatched ``main._fetch`` (the app's data seam).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.event_study import (
    EventInputError,
    compute_abnormal_returns,
    compute_car,
    compute_merger_arb_metrics,
    compute_returns,
    run_multi_event_study,
    run_single_event_study,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _geom_series(name: str, daily: float, periods: int = 200) -> pd.Series:
    """Close series whose simple daily return is exactly `daily` each day."""
    idx = pd.bdate_range("2024-01-01", periods=periods)
    return pd.Series(100.0 * (1.0 + daily) ** np.arange(periods), index=idx, name=name)


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj)


# ---------------------------------------------------------------------------
# Abnormal-return models (pure)
# ---------------------------------------------------------------------------


def test_market_adjusted_is_asset_minus_benchmark():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(asset, bench, asset.index[120].date().isoformat(), model="market_adjusted")
    for row in res["rows"]:
        assert row["abnormal_return"] == pytest.approx(
            row["asset_return"] - row["benchmark_return"], abs=1e-9
        )
        assert row["abnormal_return"] == pytest.approx(0.006, abs=1e-6)


def test_percentage_return_calculation_is_simple_return():
    idx = pd.bdate_range("2024-01-01", periods=3)
    close = pd.Series([100.0, 110.0, 99.0], index=idx, name="AAPL")
    returns = compute_returns(close)
    assert list(returns.index) == [idx[1], idx[2]]
    assert returns.iloc[0] == pytest.approx(0.10)
    assert returns.iloc[1] == pytest.approx(-0.10)


def test_compute_returns_sorts_and_keeps_last_duplicate_date():
    idx = pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02", "2024-01-02"])
    close = pd.Series([121.0, 100.0, 105.0, 110.0], index=idx, name="AAPL")
    returns = compute_returns(close)
    assert list(returns.index) == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    assert returns.iloc[0] == pytest.approx(0.10)
    assert returns.iloc[1] == pytest.approx(0.10)


@pytest.mark.parametrize(
    "values",
    [
        [100.0, 0.0, 101.0],
        [100.0, -1.0, 101.0],
        [100.0, float("inf"), 101.0],
    ],
)
def test_compute_returns_rejects_non_positive_or_non_finite_prices(values):
    idx = pd.bdate_range("2024-01-01", periods=3)
    with pytest.raises(EventInputError):
        compute_returns(pd.Series(values, index=idx, name="AAPL"))


def test_mean_adjusted_subtracts_estimation_mean():
    # Constant-return asset → estimation mean equals the return → AR ≈ 0.
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(asset, bench, asset.index[150].date().isoformat(), model="mean_adjusted")
    for row in res["rows"]:
        assert row["abnormal_return"] == pytest.approx(0.0, abs=1e-9)


def test_car_is_cumulative_sum_of_abnormal_returns():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(asset, bench, asset.index[120].date().isoformat(), model="market_adjusted")
    ars = [r["abnormal_return"] for r in res["rows"]]
    cars = [r["cumulative_abnormal_return"] for r in res["rows"]]
    running = 0.0
    for ar, car in zip(ars, cars):
        running += ar
        assert car == pytest.approx(running, abs=1e-6)
    # total_car matches the last cumulative value
    assert res["summary"]["total_car"] == pytest.approx(cars[-1], abs=1e-9)


def test_compute_car_helper():
    assert compute_car([0.01, -0.02, 0.03]) == pytest.approx([0.01, -0.01, 0.02])


def test_market_model_returns_alpha_beta():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2024-01-01", periods=200)
    bench = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 200)), index=idx, name="SPY")
    asset = pd.Series(100 * np.cumprod(1 + rng.normal(0.0005, 0.015, 200)), index=idx, name="AAPL")
    res = run_single_event_study(asset, bench, idx[150].date().isoformat(), model="market_model")
    assert res["model_used"] in ("market_model", "market_adjusted")
    if res["model_used"] == "market_model":
        assert res["alpha"] is not None and res["beta"] is not None


def test_market_model_estimates_known_alpha_beta():
    idx = pd.bdate_range("2024-01-01", periods=220)
    bench_returns = pd.Series(0.001 + 0.0002 * np.sin(np.arange(219)), index=idx[1:], name="SPY")
    asset_returns = 0.0005 + 1.75 * bench_returns
    bench = pd.Series(
        100.0 * np.cumprod(np.r_[1.0, 1.0 + bench_returns.to_numpy()]),
        index=idx,
        name="SPY",
    )
    asset = pd.Series(
        100.0 * np.cumprod(np.r_[1.0, 1.0 + asset_returns.to_numpy()]),
        index=idx,
        name="AAPL",
    )
    res = run_single_event_study(
        asset,
        bench,
        idx[170].date().isoformat(),
        pre_event_days=5,
        post_event_days=5,
        estimation_window_days=120,
        model="market_model",
    )
    assert res["model_used"] == "market_model"
    assert res["alpha"] == pytest.approx(0.0005, abs=1e-6)
    assert res["beta"] == pytest.approx(1.75, abs=1e-6)


# ---------------------------------------------------------------------------
# Event window behaviour
# ---------------------------------------------------------------------------


def test_non_trading_day_maps_to_next_with_warning():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    # 2024-05-04 is a Saturday.
    res = run_single_event_study(asset, bench, "2024-05-04", model="market_adjusted")
    assert any("not a trading day" in w for w in res["warnings"])
    assert res["summary"]["actual_event_date"] != "2024-05-04"


def test_event_day_row_is_relative_day_zero():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    event_date = asset.index[120].date().isoformat()
    res = run_single_event_study(asset, bench, event_date, pre_event_days=2, post_event_days=2)
    event_rows = [row for row in res["rows"] if row["relative_day"] == 0]
    assert len(event_rows) == 1
    assert event_rows[0]["date"] == event_date
    assert res["summary"]["event_day_abnormal_return"] == pytest.approx(event_rows[0]["abnormal_return"])


def test_pre_and_post_car_convention_excludes_event_day_from_post_car():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(
        asset,
        bench,
        asset.index[120].date().isoformat(),
        pre_event_days=2,
        post_event_days=2,
        model="market_adjusted",
    )
    assert [r["relative_day"] for r in res["rows"]] == [-2, -1, 0, 1, 2]
    assert res["summary"]["event_day_abnormal_return"] == pytest.approx(0.006, abs=1e-6)
    assert res["summary"]["pre_event_car"] == pytest.approx(0.012, abs=1e-6)
    assert res["summary"]["post_event_car"] == pytest.approx(0.012, abs=1e-6)
    assert res["summary"]["total_car"] == pytest.approx(0.030, abs=1e-6)


def test_zero_length_pre_post_window_is_event_day_only():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(
        asset,
        bench,
        asset.index[120].date().isoformat(),
        pre_event_days=0,
        post_event_days=0,
        estimation_window_days=1,
    )
    assert [r["relative_day"] for r in res["rows"]] == [0]
    assert res["summary"]["pre_event_car"] == pytest.approx(0.0)
    assert res["summary"]["post_event_car"] == pytest.approx(0.0)
    assert res["summary"]["total_car"] == pytest.approx(res["summary"]["event_day_abnormal_return"])


def test_event_after_data_range_raises_clear_error():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    with pytest.raises(EventInputError, match="after the available price history"):
        run_single_event_study(asset, bench, "2030-01-01")


def test_event_before_data_range_maps_to_first_available_with_warning():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    res = run_single_event_study(asset, bench, "2020-01-01", pre_event_days=5, post_event_days=5)
    assert any("before the available return history" in w for w in res["warnings"])
    assert res["summary"]["actual_event_date"] == asset.index[1].date().isoformat()


def test_insufficient_pre_event_data_warns_not_crashes():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    # Event very early in the series → fewer than pre_event_days before it.
    res = run_single_event_study(asset, bench, asset.index[3].date().isoformat(), pre_event_days=10, post_event_days=5)
    assert any("before the event" in w for w in res["warnings"])
    assert math.isfinite(res["summary"]["total_car"])


def test_missing_benchmark_falls_back_safely():
    asset = _geom_series("AAPL", 0.01)
    res = run_single_event_study(asset, None, asset.index[120].date().isoformat(), model="market_adjusted")
    assert res["model_used"] == "mean_adjusted"
    assert any("Benchmark" in w for w in res["warnings"])
    assert math.isfinite(res["summary"]["total_car"])


def test_non_overlapping_benchmark_dates_are_ignored_with_warning():
    asset = _geom_series("AAPL", 0.01)
    bench = pd.Series(
        100.0 * (1.004) ** np.arange(200),
        index=pd.bdate_range("2025-01-01", periods=200),
        name="SPY",
    )
    res = run_single_event_study(asset, bench, asset.index[120].date().isoformat(), model="market_adjusted")
    assert res["model_used"] == "mean_adjusted"
    assert any("too few common dates" in w for w in res["warnings"])


def test_no_nan_inf_in_result():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    _assert_all_finite(run_single_event_study(asset, bench, asset.index[120].date().isoformat()))


# ---------------------------------------------------------------------------
# Multi-event (CAAR)
# ---------------------------------------------------------------------------


def test_multi_event_caar_average():
    asset = _geom_series("AAPL", 0.01)
    bench = _geom_series("SPY", 0.004)
    r1 = run_single_event_study(asset, bench, asset.index[100].date().isoformat(), model="market_adjusted", event_name="a")
    r2 = run_single_event_study(asset, bench, asset.index[140].date().isoformat(), model="market_adjusted", event_name="b")
    agg = run_multi_event_study([r1, r2])
    assert agg["event_count"] == 2
    assert len(agg["aar_curve"]) == 21
    # Both events have constant AR 0.006 → AAR is 0.006 at every relative day.
    for pt in agg["aar_curve"]:
        assert pt["average_abnormal_return"] == pytest.approx(0.006, abs=1e-6)
        assert pt["event_count"] == 2
    assert agg["average_total_car"] == pytest.approx(0.126, abs=1e-4)


def test_multi_event_caar_averages_available_car_by_relative_day():
    r1 = {
        "event_name": "a",
        "ticker": "AAA",
        "summary": {"actual_event_date": "2024-01-02", "total_car": 0.06},
        "rows": [
            {"relative_day": -1, "abnormal_return": 0.01, "cumulative_abnormal_return": 0.01},
            {"relative_day": 0, "abnormal_return": 0.02, "cumulative_abnormal_return": 0.03},
            {"relative_day": 1, "abnormal_return": 0.03, "cumulative_abnormal_return": 0.06},
        ],
    }
    r2 = {
        "event_name": "b",
        "ticker": "BBB",
        "summary": {"actual_event_date": "2024-01-03", "total_car": 0.30},
        "rows": [
            {"relative_day": 0, "abnormal_return": 0.10, "cumulative_abnormal_return": 0.10},
            {"relative_day": 1, "abnormal_return": 0.20, "cumulative_abnormal_return": 0.30},
        ],
    }
    agg = run_multi_event_study([r1, r2])
    by_day = {row["relative_day"]: row for row in agg["aar_curve"]}
    assert by_day[-1]["average_abnormal_return"] == pytest.approx(0.01)
    assert by_day[-1]["average_cumulative_abnormal_return"] == pytest.approx(0.01)
    assert by_day[-1]["event_count"] == 1
    assert by_day[0]["average_abnormal_return"] == pytest.approx(0.06)
    assert by_day[0]["average_cumulative_abnormal_return"] == pytest.approx(0.065)
    assert by_day[0]["event_count"] == 2
    assert by_day[1]["average_cumulative_abnormal_return"] == pytest.approx(0.18)


# ---------------------------------------------------------------------------
# Merger arbitrage
# ---------------------------------------------------------------------------


def test_merger_spread_and_expected_return():
    m = compute_merger_arb_metrics(90, 100, 70, 0.8, 180)
    assert m["spread"] == pytest.approx(10.0)
    assert m["gross_upside_pct"] == pytest.approx(10.0 / 90.0, abs=1e-6)
    # expected exit = 0.8*100 + 0.2*70 = 94 → return = (94-90)/90
    assert m["expected_exit_price"] == pytest.approx(94.0)
    assert m["expected_return"] == pytest.approx(4.0 / 90.0, abs=1e-6)
    assert m["annualized_expected_return"] is not None and math.isfinite(m["annualized_expected_return"])


def test_merger_breakeven_probability():
    m = compute_merger_arb_metrics(90, 100, 70, 0.8, 180)
    # p* = (current - downside) / (offer - downside) = (90-70)/(100-70) = 2/3
    assert m["breakeven_probability"] == pytest.approx(2.0 / 3.0, abs=1e-6)


def test_merger_annualized_expected_return_formula():
    m = compute_merger_arb_metrics(90, 100, 70, 0.8, 180)
    expected_return = 4.0 / 90.0
    expected_annualized = (1.0 + expected_return) ** (365.0 / 180.0) - 1.0
    assert m["annualized_expected_return"] == pytest.approx(expected_annualized, abs=1e-6)


def test_merger_equal_offer_and_downside_warns_for_undefined_breakeven():
    m = compute_merger_arb_metrics(90, 100, 100, 0.8, 180)
    assert m["breakeven_probability"] is None
    assert any("undefined" in w.lower() for w in m["warnings"])


@pytest.mark.parametrize(
    "args",
    [
        (90, 100, 70, 1.5, 180),   # probability > 1
        (90, 100, 70, -0.1, 180),  # probability < 0
        (0, 100, 70, 0.8, 180),    # current_price <= 0
        (90, 0, 70, 0.8, 180),     # offer_price <= 0
        (90, 100, -1, 0.8, 180),   # downside < 0
        (90, 100, 70, 0.8, 0),     # days <= 0
    ],
)
def test_merger_invalid_inputs_rejected(args):
    with pytest.raises(EventInputError):
        compute_merger_arb_metrics(*args)


# ---------------------------------------------------------------------------
# API (monkeypatched data seam)
# ---------------------------------------------------------------------------


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(abs(hash(ticker)) % 10_000)
    close = 100.0 * np.cumprod(1 + rng.normal(0.0004, 0.012, len(idx)))
    return pd.DataFrame({"Close": close}, index=idx)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_event_study(client):
    body = client.post(
        "/events/study",
        json={"ticker": "AAPL", "benchmark_ticker": "SPY", "event_date": "2024-05-02",
              "event_name": "Sample", "model": "market_adjusted", "pre_event_days": 10, "post_event_days": 10},
    ).json()
    assert body["model_used"] == "market_adjusted"
    assert body["benchmark_ticker"] == "SPY"
    assert len(body["rows"]) == 21
    assert math.isfinite(body["summary"]["total_car"])


def test_api_event_study_mean_adjusted(client):
    resp = client.post(
        "/events/study",
        json={"ticker": "AAPL", "event_date": "2024-05-02", "model": "mean_adjusted"},
    )
    assert resp.status_code == 200


def test_api_event_study_bad_date(client):
    assert client.post("/events/study", json={"ticker": "AAPL", "event_date": "not-a-date"}).status_code == 422


def test_api_event_study_allows_event_day_only_window(client):
    resp = client.post(
        "/events/study",
        json={
            "ticker": "AAPL",
            "benchmark_ticker": "SPY",
            "event_date": "2024-05-02",
            "estimation_window_days": 1,
            "pre_event_days": 0,
            "post_event_days": 0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [row["relative_day"] for row in body["rows"]] == [0]


def test_api_multi_study(client):
    body = client.post(
        "/events/multi-study",
        json={"events": [
            {"ticker": "AAPL", "event_date": "2024-05-02", "event_name": "a"},
            {"ticker": "MSFT", "event_date": "2024-04-25", "event_name": "b"},
        ], "model": "market_adjusted"},
    ).json()
    assert body["event_count"] == 2
    assert len(body["aar_curve"]) >= 1


def test_api_merger_arb(client):
    body = client.post(
        "/events/merger-arb",
        json={"current_price": 90, "offer_price": 100, "downside_price": 70,
              "probability_close": 0.8, "expected_days_to_close": 180},
    ).json()
    assert body["spread"] == pytest.approx(10.0)
    assert body["breakeven_probability"] == pytest.approx(2.0 / 3.0, abs=1e-6)


@pytest.mark.parametrize(
    "payload",
    [
        {"current_price": 90, "offer_price": 100, "downside_price": 70, "probability_close": 1.5, "expected_days_to_close": 180},
        {"current_price": 0, "offer_price": 100, "downside_price": 70, "probability_close": 0.8, "expected_days_to_close": 180},
        {"current_price": 90, "offer_price": 100, "downside_price": 70, "probability_close": 0.8, "expected_days_to_close": 0},
    ],
)
def test_api_merger_arb_validation_422(client, payload):
    assert client.post("/events/merger-arb", json=payload).status_code == 422


def test_api_sample_events(client):
    body = client.get("/events/sample").json()
    assert len(body["events"]) >= 1
    assert "demo" in body["note"].lower()
