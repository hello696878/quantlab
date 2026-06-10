"""
Market-data provider abstraction + data-quality diagnostics (research v1).

QuantLab fetches daily price data from one of a small set of providers:

* ``yfinance``   — Yahoo Finance via the yfinance package (the default).
  ``Close`` is **auto-adjusted** (splits/dividends) by ``data.fetch_ohlcv``.
* ``csv_upload`` — user-uploaded CSV files (the CSV Backtest workspace).
* ``synthetic``  — deterministic test fixtures (tests only, never in the UI).

Future providers (local parquet, Polygon, Tiingo, Alpaca, Binance, …) should
slot in behind the same seam: fetch → normalized close series → quality
assessment.  v1 deliberately keeps this thin — the assessment *observes* the
series the engine actually uses; it never mutates prices or blocks a backtest
(unusable data already fails earlier, in the fetch/parse layer).
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from app.schemas import DataQuality

DEFAULT_PROVIDER = "yfinance"

# Calendar gaps longer than this many days are counted as "large" (a normal
# Fri→Mon weekend is 3; long holiday weekends are 4).
_LARGE_GAP_DAYS = 5

# Tolerance before warning that the actual range is narrower than requested —
# avoids noisy warnings for weekends/holidays at the range edges.
_EDGE_TOLERANCE_DAYS = 7


def _finite_price(value: object) -> Optional[float]:
    """Return a rounded finite float for JSON, or None for NaN/inf/non-numeric."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, 6) if math.isfinite(f) else None


def _metadata_int(close: pd.Series, key: str, fallback: int) -> int:
    """Read a non-negative integer diagnostic override from Series attrs."""
    try:
        value = int(close.attrs.get(key, fallback))
    except (TypeError, ValueError):
        return fallback
    return max(value, 0)


def _metadata_warnings(close: pd.Series) -> list[str]:
    raw = close.attrs.get("data_quality_warnings", [])
    if not isinstance(raw, list):
        return []
    return [str(w) for w in raw if str(w).strip()]


def _infer_frequency(idx: pd.DatetimeIndex) -> str:
    """Lightweight frequency guess from the date index."""
    if len(idx) < 3:
        return "unknown"
    diffs = idx.to_series().diff().dropna().dt.days
    median = float(diffs.median())
    if median <= 1.5:
        # Daily data: 24/7 series include weekends, exchange series do not.
        has_weekend = bool((idx.dayofweek >= 5).any())
        return "calendar_day" if has_weekend else "business_day"
    if median <= 8:
        return "weekly"
    if median <= 32:
        return "monthly"
    return "unknown"


def assess_data_quality(
    close: pd.Series,
    *,
    ticker: str,
    requested_start_date: str,
    requested_end_date: str,
    provider: str = DEFAULT_PROVIDER,
    price_column_used: str = "Close",
    adjusted: bool = True,
) -> DataQuality:
    """Diagnose the close series actually fed into the backtest engine.

    Purely observational: warnings are informative, never blocking, and the
    series is not modified (so results are bit-identical with or without the
    diagnostics).
    """
    warnings: list[str] = []
    row_count = int(len(close))

    if row_count == 0:
        return DataQuality(
            provider=provider,
            ticker=ticker,
            requested_start_date=requested_start_date,
            requested_end_date=requested_end_date,
            actual_start_date=None,
            actual_end_date=None,
            row_count=0,
            missing_value_count=0,
            duplicate_date_count=0,
            inferred_frequency="unknown",
            calendar_gap_count=0,
            first_price=None,
            last_price=None,
            price_column_used=price_column_used,
            adjusted=adjusted,
            warnings=["No data returned for the requested ticker / date range."],
        )

    idx = pd.DatetimeIndex(close.index)
    current_missing = int(close.isna().sum())
    current_duplicates = int(idx.duplicated().sum())
    missing = _metadata_int(close, "source_missing_value_count", current_missing)
    duplicates = _metadata_int(close, "source_duplicate_date_count", current_duplicates)
    price_column_used = str(close.attrs.get("price_column_used", price_column_used))
    adjusted = bool(close.attrs.get("adjusted", adjusted))

    actual_start = idx[0]
    actual_end = idx[-1]
    diffs = idx.to_series().diff().dropna().dt.days
    gap_count = int((diffs > _LARGE_GAP_DAYS).sum())

    warnings.extend(_metadata_warnings(close))
    if missing > 0:
        if "source_missing_value_count" in close.attrs:
            warnings.append(
                f"{missing} missing or non-numeric close value(s) were dropped "
                "before backtesting."
            )
        else:
            warnings.append(f"{missing} missing close value(s) found in the data.")
    if duplicates > 0:
        if "source_duplicate_date_count" in close.attrs:
            warnings.append(
                f"{duplicates} duplicate date(s) were removed before backtesting."
            )
        else:
            warnings.append(f"{duplicates} duplicate date(s) found in the data.")
    if not idx.is_monotonic_increasing:
        warnings.append("Dates are not sorted ascending.")
    nonfinite_count = sum(
        1
        for value in close
        if pd.notna(value) and _finite_price(value) is None
    )
    if nonfinite_count > 0:
        warnings.append(f"{nonfinite_count} non-finite close value(s) found in the data.")
    first_price = _finite_price(close.iloc[0])
    last_price = _finite_price(close.iloc[-1])
    if (pd.notna(close.iloc[0]) and first_price is None) or (
        pd.notna(close.iloc[-1]) and last_price is None
    ):
        warnings.append("Non-finite first or last close price found in the data.")

    try:
        req_start = pd.Timestamp(requested_start_date)
        req_end = pd.Timestamp(requested_end_date)
        if (actual_start - req_start).days > _EDGE_TOLERANCE_DAYS:
            warnings.append(
                f"Data starts {str(actual_start.date())}, later than the requested "
                f"{requested_start_date} — the provider has no earlier history."
            )
        if (req_end - actual_end).days > _EDGE_TOLERANCE_DAYS:
            warnings.append(
                f"Data ends {str(actual_end.date())}, earlier than the requested "
                f"{requested_end_date}."
            )
    except (ValueError, TypeError):
        pass  # non-date-formatted requests (e.g. CSV label ranges) — skip edge checks

    if gap_count > 0:
        warnings.append(
            f"{gap_count} calendar gap(s) longer than {_LARGE_GAP_DAYS} days detected "
            "(holidays, halts, or missing data)."
        )

    return DataQuality(
        provider=provider,
        ticker=ticker,
        requested_start_date=requested_start_date,
        requested_end_date=requested_end_date,
        actual_start_date=str(actual_start.date()),
        actual_end_date=str(actual_end.date()),
        row_count=row_count,
        missing_value_count=missing,
        duplicate_date_count=duplicates,
        inferred_frequency=_infer_frequency(idx),
        calendar_gap_count=gap_count,
        first_price=first_price,
        last_price=last_price,
        price_column_used=price_column_used,
        adjusted=adjusted,
        warnings=warnings,
    )
