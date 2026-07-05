"""
Data layer: fetch OHLCV price data from Yahoo Finance via yfinance.

The live path uses yfinance for any user-supplied ticker.  A small,
deterministic, **network-free** static sample generator (``sample_pairs_close``)
is provided so the built-in *demo* pair (KO/PEP) stays reproducible offline —
this is clearly labelled sample data and never claims to be live.
"""
from __future__ import annotations

import math

import pandas as pd
import yfinance as yf

# The built-in demo/default pair for the pairs-trading endpoint.  Only this pair
# is eligible for the deterministic static fallback below.
DEMO_PAIR = ("KO", "PEP")


def is_demo_pair(ticker_y: str, ticker_x: str) -> bool:
    """True when the two tickers are the built-in demo pair (order-insensitive)."""
    return {ticker_y.strip().upper(), ticker_x.strip().upper()} == set(DEMO_PAIR)


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Download adjusted daily OHLCV data for *ticker* between *start* and *end*.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol (e.g. "SPY", "AAPL", "BTC-USD").
    start : str
        Start date in "YYYY-MM-DD" format (inclusive).
    end : str
        End date in "YYYY-MM-DD" format (exclusive in Yahoo Finance convention;
        the last trading day *before* this date is included).

    Returns
    -------
    pd.DataFrame
        DataFrame with a timezone-naive DatetimeIndex and columns:
        Open, High, Low, Close, Volume.

    Raises
    ------
    ValueError
        If Yahoo Finance returns no data for the requested ticker / date range.
    """
    t = yf.Ticker(ticker)
    df: pd.DataFrame = t.history(start=start, end=end, auto_adjust=True)

    if df.empty:
        raise ValueError(
            f"No data returned for ticker '{ticker}' between {start} and {end}. "
            "Check the ticker symbol and date range."
        )
    if "Close" not in df.columns:
        raise ValueError(
            f"Yahoo Finance did not return a Close column for ticker '{ticker}' "
            f"between {start} and {end}."
        )
    missing_close_count = int(df["Close"].isna().sum())

    # Normalise the index to timezone-naive dates (yfinance may return tz-aware).
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    df.index = pd.to_datetime(df.index.date)  # keep only the date part
    df.index.name = "Date"

    # Keep only standard OHLCV columns (drop Dividends, Stock Splits, etc.).
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[cols].copy()
    df.dropna(subset=["Close"], inplace=True)

    # Guarantee ascending dates (yfinance returns ascending; this is defensive).
    if not df.index.is_monotonic_increasing:
        df.sort_index(inplace=True)
    duplicate_date_count = int(df.index.duplicated().sum())
    if duplicate_date_count > 0:
        df = df[~df.index.duplicated(keep="last")]

    df.attrs["price_column_used"] = "Close"
    df.attrs["adjusted"] = True
    df.attrs["source_missing_value_count"] = missing_close_count
    df.attrs["source_duplicate_date_count"] = duplicate_date_count

    return df


def fetch_pairs_close(
    ticker_y: str,
    ticker_x: str,
    start: str,
    end: str,
) -> tuple[pd.Series, pd.Series]:
    """
    Download and align adjusted close prices for a pair of assets.

    Parameters
    ----------
    ticker_y, ticker_x : str
        Yahoo Finance ticker symbols for the two legs of the pair.
    start, end : str
        Date range in "YYYY-MM-DD" format (same semantics as *fetch_ohlcv*).

    Returns
    -------
    (close_y, close_x) : tuple of pd.Series
        Both series share the same DatetimeIndex (intersection of the two
        assets' trading calendars — typically identical for same-exchange pairs).
        Each series is named after its ticker.

    Raises
    ------
    ValueError
        If either ticker returns no data, or if the intersection of trading
        days contains fewer than 2 observations.
    """
    df_y = fetch_ohlcv(ticker_y, start, end)
    df_x = fetch_ohlcv(ticker_x, start, end)

    close_y = df_y["Close"].rename(ticker_y.upper())
    close_x = df_x["Close"].rename(ticker_x.upper())

    # Inner join — keep only dates where both assets have prices.
    close_y, close_x = close_y.align(close_x, join="inner")

    if len(close_y) < 2:
        raise ValueError(
            f"After aligning '{ticker_y}' and '{ticker_x}' only "
            f"{len(close_y)} common trading day(s) found — need at least 2."
        )

    return close_y, close_x


def sample_pairs_close(
    ticker_y: str,
    ticker_x: str,
    start: str,
    end: str,
) -> tuple[pd.Series, pd.Series]:
    """
    Deterministic, **network-free** static sample close series for the demo pair.

    Two co-moving series (shared trend + phase-shifted idiosyncratic wobble) whose
    log-ratio spread mean-reverts, so the pairs demo is fully reproducible offline
    and produces a sensible mean-reversion backtest.  Identical every run.

    This is illustrative sample data — **not** live Yahoo Finance data.  Callers
    that surface a data source should report it as ``static_sample`` (the returned
    series carry ``.attrs["data_status"] = "static_sample"``).

    Both series share a business-day ``DatetimeIndex`` over ``[start, end)`` and
    are named after their (upper-cased) tickers.
    """
    idx = pd.date_range(start=start, end=end, freq="B")
    if len(idx) < 2:  # degenerate/empty range — fall back to a fixed 300-day window
        idx = pd.date_range(start=start, periods=300, freq="B")

    y_vals: list[float] = []
    x_vals: list[float] = []
    price_y = 100.0
    price_x = 100.0
    for i in range(len(idx)):
        # Shared market trend keeps the two legs co-integrated…
        common = 0.0003 + 0.006 * math.sin(0.05 * i)
        # …while a small phase-shifted wobble makes the spread mean-revert ±.
        price_y *= 1.0 + common + 0.004 * math.sin(0.11 * i)
        price_x *= 1.0 + common + 0.004 * math.sin(0.11 * i + 0.9)
        y_vals.append(round(price_y, 6))
        x_vals.append(round(price_x, 6))

    close_y = pd.Series(y_vals, index=idx, name=ticker_y.strip().upper(), dtype=float)
    close_x = pd.Series(x_vals, index=idx, name=ticker_x.strip().upper(), dtype=float)
    close_y.attrs["data_status"] = "static_sample"
    close_x.attrs["data_status"] = "static_sample"
    return close_y, close_x
