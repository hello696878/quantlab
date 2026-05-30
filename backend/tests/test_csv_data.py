"""
Unit tests for app.csv_data.parse_price_csv.
"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from app.csv_data import parse_price_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_csv(
    n: int = 10,
    start: str = "2020-01-01",
    date_col: str = "date",
    close_col: str = "close",
    with_ohlcv: bool = False,
) -> bytes:
    dates = pd.date_range(start, periods=n, freq="B")
    closes = [100.0 + i for i in range(n)]
    data = {date_col: dates.strftime("%Y-%m-%d"), close_col: closes}
    if with_ohlcv:
        data["open"] = [c - 0.5 for c in closes]
        data["high"] = [c + 1.0 for c in closes]
        data["low"] = [c - 1.0 for c in closes]
        data["volume"] = [1_000_000 + i for i in range(n)]
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_basic_parse():
    s = parse_price_csv(make_csv(n=10))
    assert isinstance(s, pd.Series)
    assert isinstance(s.index, pd.DatetimeIndex)
    assert s.name == "Close"
    assert s.index.name == "Date"
    assert len(s) == 10
    assert s.iloc[0] == pytest.approx(100.0)
    assert s.dtype == float


def test_index_is_timezone_naive_and_sorted():
    s = parse_price_csv(make_csv(n=5))
    assert s.index.tz is None
    assert list(s.index) == sorted(s.index)


def test_optional_ohlcv_columns_ignored():
    s = parse_price_csv(make_csv(n=8, with_ohlcv=True))
    assert len(s) == 8
    # Result is a close-only Series, not a frame.
    assert isinstance(s, pd.Series)
    assert s.name == "Close"


# ---------------------------------------------------------------------------
# Flexible column names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("date_col", ["date", "Date", "datetime", "Datetime", "timestamp", "Timestamp"])
def test_flexible_date_column_names(date_col):
    s = parse_price_csv(make_csv(n=6, date_col=date_col))
    assert len(s) == 6


@pytest.mark.parametrize(
    "close_col",
    ["close", "Close", "adj_close", "Adj Close", "adjusted_close", "Adjusted Close"],
)
def test_flexible_close_column_names(close_col):
    s = parse_price_csv(make_csv(n=6, close_col=close_col))
    assert len(s) == 6


def test_plain_close_preferred_over_adjusted():
    df = pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-01-02"],
            "close": [100.0, 101.0],
            "adj_close": [90.0, 91.0],
        }
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert s.iloc[0] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Cleaning behaviour
# ---------------------------------------------------------------------------


def test_unparseable_dates_dropped():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "not-a-date", "2020-01-03"], "close": [10, 11, 12]}
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert len(s) == 2


def test_non_numeric_close_dropped():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-01-02", "2020-01-03"], "close": [10, "oops", 12]}
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert len(s) == 2


def test_duplicate_dates_keep_last():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-01-01", "2020-01-02"], "close": [10, 99, 20]}
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert len(s) == 2
    assert s.loc["2020-01-01"] == pytest.approx(99.0)


def test_unsorted_duplicate_dates_keep_last_uploaded_row():
    df = pd.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-01", "2020-01-02"],
            "close": [20.0, 10.0, 99.0],
        }
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert list(s.index.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-02"]
    assert s.loc["2020-01-02"] == pytest.approx(99.0)


def test_unsorted_dates_are_sorted():
    df = pd.DataFrame(
        {"date": ["2020-01-03", "2020-01-01", "2020-01-02"], "close": [30, 10, 20]}
    )
    s = parse_price_csv(df.to_csv(index=False).encode())
    assert list(s.values) == [10.0, 20.0, 30.0]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_empty_content_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_price_csv(b"")


def test_missing_date_column_raises():
    df = pd.DataFrame({"close": [10, 11], "volume": [1, 2]})
    with pytest.raises(ValueError, match="date column"):
        parse_price_csv(df.to_csv(index=False).encode())


def test_missing_close_column_raises():
    df = pd.DataFrame({"date": ["2020-01-01", "2020-01-02"], "volume": [1, 2]})
    with pytest.raises(ValueError, match="close price column"):
        parse_price_csv(df.to_csv(index=False).encode())


def test_all_invalid_rows_raises():
    df = pd.DataFrame({"date": ["x", "y"], "close": ["a", "b"]})
    with pytest.raises(ValueError):
        parse_price_csv(df.to_csv(index=False).encode())


def test_invalid_dates_do_not_emit_pandas_inference_warning():
    df = pd.DataFrame({"date": ["x", "y"], "close": [10, 11]})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError):
            parse_price_csv(df.to_csv(index=False).encode())

    assert not any("Could not infer format" in str(w.message) for w in caught)


def test_zero_close_raises():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-01-02"], "close": [100.0, 0.0]}
    )
    with pytest.raises(ValueError, match="positive"):
        parse_price_csv(df.to_csv(index=False).encode())


def test_negative_close_raises():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-01-02"], "close": [100.0, -5.0]}
    )
    with pytest.raises(ValueError, match="positive"):
        parse_price_csv(df.to_csv(index=False).encode())


def test_single_row_raises():
    df = pd.DataFrame({"date": ["2020-01-01"], "close": [100.0]})
    with pytest.raises(ValueError, match="at least 2"):
        parse_price_csv(df.to_csv(index=False).encode())
