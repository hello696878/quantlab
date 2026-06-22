"""
Optional delayed index & FX quote enrichment for the Global Markets Globe.

Phase 20.4 adds a cautious, **config-gated** delayed-quote layer that mirrors the
FRED macro adapter (Phase 20.3): **disabled by default**, **fails closed to
static sample data**, and never required for normal local development.

Honesty / safety constraints:
- Default app behaviour is unchanged: static illustrative sample data.
- Quotes are **delayed**, never real-time; the UI never claims live/real-time.
- No paid provider, no broker, no trading, no websocket/streaming, no scraping.
- The only real provider reuses the project's existing **yfinance** dependency
  (free, delayed). It is opt-in and bounded to a curated set of markets.
- Tests inject a fake provider; nothing here calls the network during tests.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from app.globe.models import MarketDossier

# ---------------------------------------------------------------------------
# Quote symbol mapping (curated, limited coverage)
# ---------------------------------------------------------------------------
# market_id → Yahoo Finance symbol for the PRIMARY index. Unmapped markets stay
# static and are never fetched / never claimed as delayed quotes.
INDEX_SYMBOL_MAP: Dict[str, str] = {
    "us": "^GSPC",
    "ca": "^GSPTSE",
    "uk": "^FTSE",
    "de": "^GDAXI",
    "fr": "^FCHI",
    "ch": "^SSMI",
    "jp": "^N225",
    "hk": "^HSI",
    "tw": "^TWII",
    "kr": "^KS11",
    "in": "^NSEI",
    "sg": "^STI",
    "au": "^AXJO",
    "br": "^BVSP",
}

# market_id → Yahoo Finance FX symbol matching the static fx[0].pair direction.
# (US uses a dollar index in the sample data, not a pair, so it is omitted.)
FX_SYMBOL_MAP: Dict[str, str] = {
    "ca": "CAD=X",       # USD/CAD
    "uk": "GBPUSD=X",    # GBP/USD
    "de": "EURUSD=X",    # EUR/USD
    "fr": "EURUSD=X",    # EUR/USD
    "ch": "CHF=X",       # USD/CHF
    "jp": "JPY=X",       # USD/JPY
    "cn": "CNY=X",       # USD/CNY
    "hk": "HKD=X",       # USD/HKD
    "tw": "TWD=X",       # USD/TWD
    "kr": "KRW=X",       # USD/KRW
    "in": "INR=X",       # USD/INR
    "sg": "SGD=X",       # USD/SGD
    "au": "AUDUSD=X",    # AUD/USD
    "br": "BRL=X",       # USD/BRL
}

PROVIDER_UNAVAILABLE_WARNING = (
    "Globe quote adapter enabled but quote provider unavailable; using static "
    "sample data."
)

MAX_QUOTE_TIMEOUT_SECONDS = 30.0
MAX_QUOTE_CACHE_TTL_SECONDS = 86_400
_TRUE = {"1", "true", "yes", "on"}


@dataclass
class QuoteResult:
    """A single delayed quote (never real-time)."""

    symbol: str
    name: str
    value: float  # index level or FX rate
    change_pct: float  # percent (0.42 == +0.42%)
    as_of: str
    source: str
    is_delayed: bool = True


@dataclass
class GlobeQuotesConfig:
    """Runtime configuration for the delayed-quote adapter (read from env)."""

    enabled: bool = False
    provider: str = "yfinance"
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 900

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "GlobeQuotesConfig":
        import os

        e = env if env is not None else os.environ
        enabled = str(e.get("GLOBE_QUOTES_ENABLED", "")).strip().lower() in _TRUE
        provider = (e.get("GLOBE_QUOTES_PROVIDER") or "yfinance").strip().lower()
        try:
            timeout = float(e.get("GLOBE_QUOTES_TIMEOUT_SECONDS") or 5.0)
        except (TypeError, ValueError):
            timeout = 5.0
        if not math.isfinite(timeout) or timeout <= 0:
            timeout = 5.0
        try:
            ttl = int(e.get("GLOBE_QUOTES_CACHE_TTL_SECONDS") or 900)
        except (TypeError, ValueError):
            ttl = 900
        return cls(
            enabled=enabled,
            provider=provider,
            timeout_seconds=min(max(0.5, timeout), MAX_QUOTE_TIMEOUT_SECONDS),
            cache_ttl_seconds=min(max(0, ttl), MAX_QUOTE_CACHE_TTL_SECONDS),
        )


class QuoteProvider(Protocol):
    """Provider interface — a future real source plugs in here."""

    def fetch_index_quote(self, symbol: str) -> Optional[QuoteResult]: ...

    def fetch_fx_quote(self, symbol: str) -> Optional[QuoteResult]: ...


def _finite(value: object) -> Optional[float]:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


class YfinanceQuoteProvider:
    """
    Delayed-quote provider reusing the project's existing **yfinance** dependency.

    yfinance close prices are **delayed**, not real-time. Construction lazily
    imports yfinance so the rest of the app never depends on it; if the import
    fails the provider cannot be constructed and the adapter reports the source
    as unavailable (static fallback).
    """

    name = "yfinance"

    def __init__(self, timeout_seconds: float = 5.0):
        import yfinance  # noqa: F401 — lazy import; raises if unavailable

        self._yf = yfinance
        self.timeout_seconds = timeout_seconds

    def _latest(self, symbol: str) -> Optional[Tuple[float, float, str]]:
        try:
            hist = self._yf.Ticker(symbol).history(period="5d")
        except Exception:
            return None
        if hist is None or getattr(hist, "empty", True) or "Close" not in hist:
            return None
        closes = [c for c in (_finite(x) for x in hist["Close"].tolist()) if c is not None]
        if not closes:
            return None
        last = closes[-1]
        prev = closes[-2] if len(closes) >= 2 else last
        change_pct = ((last / prev) - 1.0) * 100.0 if prev else 0.0
        if not math.isfinite(change_pct):
            change_pct = 0.0
        try:
            as_of = str(hist.index[-1].date())
        except Exception:
            as_of = "unknown"
        return (last, change_pct, as_of)

    def fetch_index_quote(self, symbol: str) -> Optional[QuoteResult]:
        r = self._latest(symbol)
        if r is None:
            return None
        value, change_pct, as_of = r
        return QuoteResult(symbol=symbol, name=symbol, value=value, change_pct=change_pct, as_of=as_of, source=self.name)

    def fetch_fx_quote(self, symbol: str) -> Optional[QuoteResult]:
        return self.fetch_index_quote(symbol)


# Module-level TTL cache: {(provider, symbol): (expires_at, QuoteResult)}.
_QUOTE_CACHE: Dict[Tuple[str, str], Tuple[float, QuoteResult]] = {}


def clear_quote_cache() -> None:
    """Reset the in-memory quote cache (used by tests)."""
    _QUOTE_CACHE.clear()


def resolve_quote_provider(config: GlobeQuotesConfig) -> Optional[QuoteProvider]:
    """
    Return a provider instance, or None when quotes are disabled / the provider
    is unknown / the dependency is unavailable. Never raises.
    """
    if not config.enabled:
        return None
    if config.provider in {"yfinance", "existing"}:
        try:
            return YfinanceQuoteProvider(timeout_seconds=config.timeout_seconds)
        except Exception:
            return None
    # "mock"/unknown providers are not wired with a real source in v1.
    return None


class _BaseQuoteAdapter:
    def __init__(self, config: GlobeQuotesConfig, provider: Optional[QuoteProvider] = None):
        self.config = config
        self.provider = provider

    def available(self) -> bool:
        return bool(self.config.enabled and self.provider is not None)

    def _cached(self, symbol: str, fetch: Callable[[str], Optional[QuoteResult]]) -> Optional[QuoteResult]:
        if not self.available():
            return None
        key = (self.config.provider, symbol)
        now = time.time()
        hit = _QUOTE_CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]
        try:
            result = fetch(symbol)
        except Exception:
            return None
        if result is None:
            return None
        value = _finite(result.value)
        change = _finite(result.change_pct)
        if value is None or change is None:
            return None
        result.value = value
        result.change_pct = change
        if self.config.cache_ttl_seconds > 0:
            _QUOTE_CACHE[key] = (now + self.config.cache_ttl_seconds, result)
        return result


class DelayedIndexQuoteAdapter(_BaseQuoteAdapter):
    """Optional delayed equity-index quote adapter (fail-closed)."""

    name = "delayed-index-quotes"

    def fetch_index_quote(self, market_id: str) -> Optional[QuoteResult]:
        symbol = INDEX_SYMBOL_MAP.get((market_id or "").lower())
        if not symbol or self.provider is None:
            return None
        return self._cached(symbol, self.provider.fetch_index_quote)


class FxQuoteAdapter(_BaseQuoteAdapter):
    """Optional delayed FX quote adapter (fail-closed)."""

    name = "fx-quotes"

    def fetch_fx_quote(self, market_id: str) -> Optional[QuoteResult]:
        symbol = FX_SYMBOL_MAP.get((market_id or "").lower())
        if not symbol or self.provider is None:
            return None
        return self._cached(symbol, self.provider.fetch_fx_quote)


def enrich_market_with_quotes(
    dossier: MarketDossier,
    config: GlobeQuotesConfig,
    index_adapter: Optional[DelayedIndexQuoteAdapter] = None,
    fx_adapter: Optional[FxQuoteAdapter] = None,
) -> Tuple[MarketDossier, str, str, List[str]]:
    """
    Return (dossier, indices_state, fx_state, warnings).

    States ∈ {static_sample, delayed_quote, quote_unavailable}. Never raises.
    Unmapped markets stay static_sample and are never fetched.
    """
    if not config.enabled:
        return (dossier, "static_sample", "static_sample", [])

    if index_adapter is None or fx_adapter is None:
        provider = resolve_quote_provider(config)
        index_adapter = index_adapter or DelayedIndexQuoteAdapter(config, provider)
        fx_adapter = fx_adapter or FxQuoteAdapter(config, provider)

    warnings: List[str] = []
    updates: Dict[str, object] = {}
    status_updates: Dict[str, str] = {}

    # ── Index ──────────────────────────────────────────────────────────────
    index_supported = dossier.id in INDEX_SYMBOL_MAP
    indices_state = "static_sample"
    if index_supported:
        if not index_adapter.available():
            indices_state = "quote_unavailable"
            warnings.append(PROVIDER_UNAVAILABLE_WARNING)
        else:
            quote = index_adapter.fetch_index_quote(dossier.id)
            if quote is not None:
                primary = dossier.indices[0].model_copy(
                    update={
                        "level": quote.value,
                        "change_pct": quote.change_pct,
                        "is_sample": False,
                        "as_of_date": quote.as_of if quote.as_of != "unknown" else None,
                    }
                )
                updates["indices"] = [primary, *dossier.indices[1:]]
                indices_state = "delayed_quote"
            else:
                indices_state = "quote_unavailable"
                warnings.append(
                    f"Delayed index quote for '{dossier.id}' unavailable; using static sample data."
                )
    if indices_state != "static_sample":
        status_updates["indices"] = indices_state

    # ── FX ─────────────────────────────────────────────────────────────────
    fx_supported = dossier.id in FX_SYMBOL_MAP
    fx_state = "static_sample"
    if fx_supported:
        if not fx_adapter.available():
            fx_state = "quote_unavailable"
            if PROVIDER_UNAVAILABLE_WARNING not in warnings:
                warnings.append(PROVIDER_UNAVAILABLE_WARNING)
        else:
            quote = fx_adapter.fetch_fx_quote(dossier.id)
            if quote is not None:
                primary_fx = dossier.fx[0].model_copy(
                    update={
                        "rate": quote.value,
                        "change_pct": quote.change_pct,
                        "is_sample": False,
                        "as_of_date": quote.as_of if quote.as_of != "unknown" else None,
                    }
                )
                updates["fx"] = [primary_fx, *dossier.fx[1:]]
                fx_state = "delayed_quote"
            else:
                fx_state = "quote_unavailable"
                warnings.append(
                    f"Delayed FX quote for '{dossier.id}' unavailable; using static sample data."
                )
    if fx_state != "static_sample":
        status_updates["fx"] = fx_state

    if status_updates:
        updates["source_status"] = dossier.source_status.model_copy(update=status_updates)
    if updates:
        dossier = dossier.model_copy(update=updates)
    return (dossier, indices_state, fx_state, warnings)
