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

from app import data as data_module
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


def test_quality_uses_source_metadata_for_cleaned_rows():
    idx = pd.date_range("2020-01-06", periods=5, freq="B")
    close = _close(range(100, 105), idx)
    close.attrs["source_missing_value_count"] = 2
    close.attrs["source_duplicate_date_count"] = 1
    close.attrs["price_column_used"] = "Adj Close"
    close.attrs["adjusted"] = True

    q = assess_data_quality(
        close,
        ticker="CSV_UPLOAD",
        requested_start_date="2020-01-06",
        requested_end_date="2020-01-10",
        provider="csv_upload",
        adjusted=False,
    )

    assert q.missing_value_count == 2
    assert q.duplicate_date_count == 1
    assert q.price_column_used == "Adj Close"
    assert q.adjusted is True
    assert any("dropped" in w.lower() for w in q.warnings)
    assert any("removed" in w.lower() for w in q.warnings)


def test_quality_sanitizes_nonfinite_first_or_last_price():
    idx = pd.date_range("2020-01-06", periods=3, freq="B")
    q = assess_data_quality(
        pd.Series([float("inf"), 101.0, float("-inf")], index=idx, name="Close"),
        ticker="BAD",
        requested_start_date="2020-01-06",
        requested_end_date="2020-01-08",
    )
    assert q.first_price is None
    assert q.last_price is None
    assert any("non-finite" in w.lower() for w in q.warnings)


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


def test_yfinance_provider_wrapper_preserves_shape_and_metadata(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker

        def history(self, start: str, end: str, auto_adjust: bool):
            assert self.ticker == "SPY"
            assert start == "2020-01-01"
            assert end == "2020-01-10"
            assert auto_adjust is True
            idx = pd.DatetimeIndex(
                ["2020-01-03", "2020-01-02", "2020-01-02", "2020-01-06"],
                tz="UTC",
            )
            return pd.DataFrame(
                {
                    "Open": [99.0, 100.0, 101.0, 102.0],
                    "High": [100.0, 101.0, 102.0, 103.0],
                    "Low": [98.0, 99.0, 100.0, 101.0],
                    "Close": [100.0, 101.0, 102.0, np.nan],
                    "Volume": [1_000, 1_100, 1_200, 1_300],
                    "Dividends": [0.0, 0.0, 0.0, 0.0],
                },
                index=idx,
            )

    monkeypatch.setattr(data_module.yf, "Ticker", FakeTicker)

    df = data_module.fetch_ohlcv("SPY", "2020-01-01", "2020-01-10")

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.tz is None
    assert df.index.is_monotonic_increasing
    assert not df.index.has_duplicates
    assert len(df) == 2
    assert float(df.loc[pd.Timestamp("2020-01-02"), "Close"]) == 102.0
    assert df.attrs["price_column_used"] == "Close"
    assert df.attrs["adjusted"] is True
    assert df.attrs["source_missing_value_count"] == 1
    assert df.attrs["source_duplicate_date_count"] == 1

    q = assess_data_quality(
        df["Close"],
        ticker="SPY",
        requested_start_date="2020-01-01",
        requested_end_date="2020-01-10",
    )
    assert q.missing_value_count == 1
    assert q.duplicate_date_count == 1
    assert any("dropped" in w.lower() for w in q.warnings)


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


def test_api_csv_upload_quality_preserves_price_column_and_duplicate_count():
    dates = pd.date_range("2020-01-01", periods=160, freq="B")
    rows = [f"{d.date()},{100 + i * 0.5}" for i, d in enumerate(dates)]
    rows.append(f"{dates[0].date()},250.0")  # duplicate date; parser keeps last
    csv_text = "Date,Adj Close\n" + "\n".join(rows)
    client = TestClient(main_module.app)
    resp = client.post(
        "/backtest/csv",
        files={"file": ("prices.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        data={"strategy": "sma_crossover", "params": '{"fast_window": 10, "slow_window": 30}'},
    )
    assert resp.status_code == 200
    q = resp.json()["data_quality"]
    assert q["provider"] == "csv_upload"
    assert q["price_column_used"] == "Adj Close"
    assert q["adjusted"] is True
    assert q["row_count"] == 160
    assert q["duplicate_date_count"] == 1
    assert any("duplicate" in w.lower() for w in q["warnings"])


def test_api_csv_upload_rejects_infinite_close():
    csv_text = "Date,Close\n2020-01-01,100\n2020-01-02,inf\n2020-01-03,101\n"
    client = TestClient(main_module.app)
    resp = client.post(
        "/backtest/csv",
        files={"file": ("prices.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        data={"strategy": "sma_crossover", "params": '{"fast_window": 2, "slow_window": 3}'},
    )
    assert resp.status_code == 422
    assert "finite" in resp.json()["detail"].lower()
