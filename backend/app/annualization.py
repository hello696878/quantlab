"""
Annualization convention engine (research v1).

Annualized metrics (CAGR, volatility, Sharpe, Sortino, Calmar) depend on how
many return periods make up a year:

* ``trading_days_252`` — 252 trading days/year (equities, ETFs; the default and
  the historical behaviour).
* ``crypto_365``       — 365 days/year (24/7 crypto daily data).
* ``auto``             — infer from the ticker: recognized crypto → 365, else
  252 (with a warning when the asset class can't be confirmed).

Changing the convention only rescales annualized metrics — it never changes
trades, the equity curve, or total return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TRADING_DAYS_PER_YEAR: int = 252
CRYPTO_DAYS_PER_YEAR: int = 365

AnnualizationModeStr = str  # "trading_days_252" | "crypto_365" | "auto"

# Base symbols (Yahoo uses ``BASE-USD`` for crypto) that we treat as crypto.
_KNOWN_CRYPTO_BASES = frozenset(
    {
        "BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "LTC", "BCH", "BNB", "DOT",
        "AVAX", "MATIC", "LINK", "UNI", "ATOM", "XLM", "TRX", "ETC", "FIL",
        "APT", "ARB", "OP", "NEAR", "ALGO", "ICP", "AAVE", "MKR", "SAND",
        "MANA", "SHIB", "USDT", "USDC", "DAI", "CRO", "HBAR", "VET", "GRT",
    }
)

# Common equities / ETFs that ``auto`` recognises as 252 with no warning.
_KNOWN_EQUITY = frozenset(
    {
        "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "VEA", "VWO", "EFA", "EEM",
        "GLD", "SLV", "TLT", "IEF", "AGG", "BND", "LQD", "HYG", "XLF", "XLE",
        "XLK", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE",
        "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA",
        "BRK-B", "JPM", "JNJ", "V", "WMT", "PG", "DIS", "NFLX", "AMD", "INTC",
    }
)


@dataclass
class ResolvedAnnualization:
    """Resolution of an annualization request for a given ticker."""

    mode: str  # requested mode (echoed)
    mode_used: str  # concrete convention applied: trading_days_252 | crypto_365
    periods_per_year: int
    warning: Optional[str] = None


def _looks_like_crypto(ticker: str) -> bool:
    if not ticker:
        return False
    t = ticker.strip().upper()
    if t.endswith("-USD"):
        base = t[:-4]
        # Be conservative: only recognized crypto bases auto-resolve to 365.
        # Unknown ``*-USD`` symbols fall through to 252 with a warning instead
        # of silently applying a crypto convention to an unconfirmed ticker.
        return base in _KNOWN_CRYPTO_BASES
    return t in _KNOWN_CRYPTO_BASES


def _looks_like_equity(ticker: str) -> bool:
    if not ticker:
        return False
    return ticker.strip().upper() in _KNOWN_EQUITY


def resolve_annualization(
    ticker: Optional[str],
    mode: Optional[str],
) -> ResolvedAnnualization:
    """Resolve a requested annualization mode for a ticker (see module docstring).

    A missing/None mode is treated as ``trading_days_252`` (backward-compatible).
    """
    requested = mode or "trading_days_252"

    if requested == "trading_days_252":
        return ResolvedAnnualization(
            mode=requested, mode_used="trading_days_252",
            periods_per_year=TRADING_DAYS_PER_YEAR,
        )
    if requested == "crypto_365":
        return ResolvedAnnualization(
            mode=requested, mode_used="crypto_365",
            periods_per_year=CRYPTO_DAYS_PER_YEAR,
        )

    # auto
    if _looks_like_crypto(ticker or ""):
        return ResolvedAnnualization(
            mode="auto", mode_used="crypto_365",
            periods_per_year=CRYPTO_DAYS_PER_YEAR,
        )
    warning = None
    if not _looks_like_equity(ticker or ""):
        warning = (
            f"Auto annualization could not confirm the asset class for "
            f"'{ticker}'; defaulted to 252 trading days. Pick crypto (365) "
            f"explicitly for 24/7 assets."
        )
    return ResolvedAnnualization(
        mode="auto", mode_used="trading_days_252",
        periods_per_year=TRADING_DAYS_PER_YEAR, warning=warning,
    )


def annualization_label(mode_used: str, mode_requested: Optional[str] = None) -> str:
    """Human-readable label, e.g. 'Auto → Crypto 365' or 'Trading days 252'."""
    base = "Crypto 365" if mode_used == "crypto_365" else "Trading days 252"
    if mode_requested == "auto":
        return f"Auto → {base}"
    return base
