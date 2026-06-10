"""
Data layer: fetch OHLCV price data from Yahoo Finance via yfinance.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf


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
