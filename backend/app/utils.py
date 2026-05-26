"""
Shared utility helpers for QuantLab backend.
"""

from datetime import datetime


def validate_date_format(date_str: str) -> bool:
    """Return True if *date_str* is a valid YYYY-MM-DD string."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def bps_to_decimal(bps: float) -> float:
    """Convert basis points to a decimal fraction  (10 bps → 0.0010)."""
    return bps / 10_000.0


def annualisation_factor(n_trading_days: int, days_per_year: int = 252) -> float:
    """Return the annualisation factor for a given number of trading days."""
    return n_trading_days / days_per_year
