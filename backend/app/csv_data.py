"""
CSV upload data layer.

Parses a user-uploaded price CSV into a clean ``close`` price Series that the
existing strategy + backtest engine can consume unchanged.

Supported flexible column names (case-insensitive; spaces / hyphens are
treated as underscores):

* date   — ``date``, ``datetime``, ``timestamp``
* close  — ``close``, ``adj_close`` / ``adjusted_close``
           (also matches ``Adj Close`` / ``Adjusted Close``)

Optional ``open`` / ``high`` / ``low`` / ``volume`` columns are ignored for
this single-asset, close-only version.
"""

from __future__ import annotations

import io

import pandas as pd

# Accepted column names after normalisation (lower-case, spaces/hyphens → "_").
_DATE_CANDIDATES = ("date", "datetime", "timestamp")
# Preference order: a literal close column wins over an adjusted-close column.
_CLOSE_CANDIDATES = ("close", "adj_close", "adjusted_close")


def _normalize(name: object) -> str:
    """Normalise a column name for flexible, case-insensitive matching."""
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def parse_price_csv(content: bytes) -> pd.Series:
    """
    Parse raw CSV bytes into a clean daily ``close`` price Series.

    Returns
    -------
    pd.Series
        Float close prices indexed by a sorted, timezone-naive
        ``DatetimeIndex`` (named "Date"); the series itself is named "Close".

    Raises
    ------
    ValueError
        With a user-facing message when the file is empty, missing a required
        column, or contains no usable (date, close) rows.
    """
    if content is None or len(content) == 0:
        raise ValueError("Uploaded CSV file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # pandas raises a variety of parser errors
        raise ValueError(f"Could not parse CSV file: {exc}") from exc

    if df.shape[1] == 0 or len(df) == 0:
        raise ValueError("CSV file contains no data rows.")

    # Map each normalised column name to the first original column that uses it.
    norm_map: dict[str, str] = {}
    for col in df.columns:
        norm_map.setdefault(_normalize(col), col)

    date_col = next((norm_map[c] for c in _DATE_CANDIDATES if c in norm_map), None)
    if date_col is None:
        raise ValueError(
            "CSV must contain a date column. Accepted names: "
            "date, datetime, timestamp."
        )

    close_col = next((norm_map[c] for c in _CLOSE_CANDIDATES if c in norm_map), None)
    if close_col is None:
        raise ValueError(
            "CSV must contain a close price column. Accepted names: "
            "close, adj_close, adjusted_close (also 'Adj Close', "
            "'Adjusted Close')."
        )

    dates = pd.to_datetime(df[date_col], errors="coerce")
    closes = pd.to_numeric(df[close_col], errors="coerce")

    series = pd.Series(closes.to_numpy(), index=pd.DatetimeIndex(dates))
    series = series[~series.index.isna()]   # drop rows whose date failed to parse
    series = series.dropna()                # drop rows whose close is non-numeric

    if len(series) == 0:
        raise ValueError(
            "No valid (date, close) rows found after parsing. "
            "Check that the date and close columns contain valid values."
        )

    # Normalise the index to timezone-naive calendar dates (mirrors data.py).
    idx = pd.DatetimeIndex(series.index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    series.index = pd.to_datetime(idx.date)
    series.index.name = "Date"

    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]  # last value per date
    series = series.astype(float)
    series.name = "Close"

    if (series <= 0).any():
        raise ValueError(
            "Close prices must be positive; found zero or negative values."
        )

    if len(series) < 2:
        raise ValueError(
            "CSV must contain at least 2 valid rows to run a backtest."
        )

    return series
