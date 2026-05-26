"""
Data layer: fetch OHLCV price data from Yahoo Finance via yfinance.
"""

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

    return df
