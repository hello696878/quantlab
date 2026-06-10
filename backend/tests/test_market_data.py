"""
Tests for the market-data abstraction + data-quality diagnostics (research v1).

Two layers:
  * pure assessment (`app.market_data.assess_data_quality`) on synthetic series;
  * API integration — single backtest, strategy comparison, and CSV upload
    responses carry `data_provider` / `data_quality`, and old behaviour is
    unchanged (diagnostics observe; they never mutate results).

All synthetic / monkeypatched — no live yfinance.
"""

from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd
import pytest

from app.market_data import assess_data_quality

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _close(values, idx) -> pd.Series:
    return pd.Series([float(v) if v is not None else np.nan for v in values], index=idx, name="Close")


# ---------------------------------------------------------------------------
# Pure assessment
# ---------------------------------------------------------------------------


def test_quality_row_count_and_dates():
    idx = pd.date_range("2020-01-06", periods=10, freq="B")
    q = assess_data_quality(
        _close(range(100, 110), idx),
        ticker="SPY",
        requested_start_date="2020-01-06",
        requested_end_date="2020-01-17",
    )
    assert q.provider == "yfinance"
    assert q.row_count == 10
    assert q.actual_start_date == "2020-01-06"
    assert q.actual_end_date == "2020-01-17"
    assert q.inferred_frequency == "business_day"
    assert q.missing_value_count == 0
    assert q.duplicate_date_count == 0
    assert q.first_price == 100.0
    assert q.last_price == 109.0
    assert q.price_column_used == "Close"
    assert q.adjusted is True
    assert q.warnings == []


def test_quality_detects_missing_values():
    idx = pd.date_range("2020-01-06", periods=6, freq="B")
    q = assess_data_quality(
        _close([100, None, 102, 103, None, 105], idx),
        ticker="SPY",
        requested_start_date="2020-01-06",
        requested_end_date="2020-01-13",
    )
    assert q.missing_value_count == 2
    assert any("missing" in w.lower() for w in q.warnings)


def test_quality_detects_duplicate_dates():
    idx = pd.DatetimeIndex(["2020-01-06", "2020-01-07", "2020-01-07", "2020-01-08"])
    q = assess_data_quality(
        _close([100, 101, 101, 102], idx),
        ticker="SPY",
        requested_start_date="2020-01-06",
        requested_end_date="2020-01-08",
    )
    assert q.duplicate_date_count == 1
    assert any("duplicate" in w.lower() for w in q.warnings)


def test_quality_detects_truncated_range():
    # Requested from 2019 but data starts 2020-03 → warning.
    idx = pd.date_range("2020-03-02", periods=20, freq="B")
    q = assess_data_quality(
        _close(range(100, 120), idx),
        ticker="NEWIPO",
        requested_start_date="2019-01-01",
        requested_end_date="2020-03-27",
    )
    assert any("no earlier history" in w for w in q.warnings)


def test_quality_no_edge_warning_for_weekend_tolerance():
    # Requested Jan 1 (holiday) with data from Jan 2 → inside tolerance, no warning.
    idx = pd.date_range("2020-01-02", periods=30, freq="B")
    q = assess_data_quality(
        _close(range(100, 130), idx),
        ticker="SPY",
        requested_start_date="2020-01-01",
        requested_end_date=str(idx[-1].date()),
    )
    assert q.warnings == []


def test_quality_empty_series():
    q = assess_data_quality(
        pd.Series([], dtype=float),
        ticker="FAKE",
        requested_start_date="2020-01-01",
        requested_end_date="2020-12-31",
    )
    assert q.row_count == 0
    assert q.actual_start_date is None and q.last_price is None
    assert any("No data" in w for w in q.warnings)


def test_quality_calendar_day_frequency_for_crypto_style_data():
    idx = pd.date_range("2020-01-01", periods=60, freq="D")  # includes weekends
    q = assess_data_quality(
        _close(range(100, 160), idx),
        ticker="BTC-USD",
        requested_start_date="2020-01-01",
        requested_end_date=str(idx[-1].date()),
    )
    assert q.inferred_frequency == "calendar_day"


def test_quality_detects_large_gaps():
    idx = pd.DatetimeIndex(
        list(pd.date_range("2020-01-06", periods=10, freq="B"))
        + list(pd.date_range("2020-03-02", periods=10, freq="B"))
    )
    q = assess_data_quality(
        _close(range(100, 120), idx),
        ticker="HALTED",
        requested_start_date="2020-01-06",
        requested_end_date="2020-03-13",
    )
    assert q.calendar_gap_count >= 1
    assert any("gap" in w.lower() for w in q.warnings)


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=400, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = 0.012 * math.sin(0.045 * i) + 0.004 * math.cos(0.23 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_backtest_includes_data_provider_and_quality(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["data_provider"] == "yfinance"
    q = body["data_quality"]
    assert q["provider"] == "yfinance"
    assert q["ticker"] == "SPY"
    assert q["row_count"] == len(_DATES)
    assert q["actual_start_date"] == str(_DATES[0].date())
    assert q["actual_end_date"] == str(_DATES[-1].date())
    assert q["price_column_used"] == "Close"
    assert q["inferred_frequency"] == "business_day"


def test_api_quality_does_not_change_results(client):
    """Diagnostics are observational: metrics/curve identical to pre-12.5 runs."""
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["strategy_metrics"]["total_return"] is not None
    assert len(body["equity_curve"]) == len(_DATES)
    assert body["num_trades"] >= 0


def test_api_invalid_ticker_clear_error(monkeypatch):
    def _empty_fetch(ticker, start, end):
        raise ValueError(
            f"No data returned for ticker '{ticker}' between {start} and {end}. "
            "Check the ticker symbol and date range."
        )

    monkeypatch.setattr(main_module, "fetch_ohlcv", _empty_fetch)
    client = TestClient(main_module.app)
    resp = client.post("/backtest/sma-crossover", json={"ticker": "FAKE123XYZ"})
    assert resp.status_code == 404
    assert "Check the ticker symbol" in resp.json()["detail"]


def test_api_comparison_includes_shared_data_quality(client):
    body = client.post(
        "/research/strategy-comparison",
        json={"start_date": "2015-01-01", "end_date": "2016-12-30"},
    ).json()
    assert body["data_provider"] == "yfinance"
    q = body["data_quality"]
    assert q["provider"] == "yfinance"
    assert q["row_count"] > 0
    # Quality reflects the trimmed shared series used by all five strategies.
    assert q["actual_end_date"] <= "2016-12-30"


def test_api_csv_upload_quality_is_csv_provider():
    csv_text = "Date,Close\n" + "\n".join(
        f"{d.date()},{100 + i * 0.5}" for i, d in enumerate(pd.date_range("2020-01-01", periods=160, freq="B"))
    )
    client = TestClient(main_module.app)
    resp = client.post(
        "/backtest/csv",
        files={"file": ("prices.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        data={"strategy": "sma_crossover", "params": '{"fast_window": 10, "slow_window": 30}'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_provider"] == "csv_upload"
    assert body["data_quality"]["provider"] == "csv_upload"
    assert body["data_quality"]["adjusted"] is False
    assert body["data_quality"]["row_count"] == 160
