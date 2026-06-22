"""
Data-source adapters for the Global Markets Globe.

Phase 20.3 adds the **first cautious real-data integration**: an *optional*,
config-gated FRED macro adapter (`FredMacroAdapter`). It is **disabled by
default**, requires no API key for normal local development, and **fails closed
to static sample data** on any problem. Index quotes, FX quotes, and news remain
inert planned stubs.

Honesty / safety constraints:
- Default app behaviour is unchanged: static illustrative sample data.
- No API key is committed; the key is read from the environment at runtime and
  is **never** placed in any API response.
- No external call happens unless FRED is explicitly enabled *and* a key is set.
- Tests inject a fake fetcher; nothing here calls the network during tests.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.globe.models import MarketDossier

# ---------------------------------------------------------------------------
# Planned (inert) adapters — unchanged from the data-layer phase
# ---------------------------------------------------------------------------


class _PlannedAdapter:
    """Base for not-yet-implemented adapters. No network, no keys, no fetch."""

    name = "planned-adapter"
    planned_phase = "future"

    def source_state(self) -> str:
        return "planned"

    def is_live(self) -> bool:
        return False


class DelayedIndexQuoteAdapter(_PlannedAdapter):
    """Future adapter for delayed (not real-time) equity-index quotes. Inert in this phase."""

    name = "delayed-index-quotes"

    def fetch_index_quotes(self, market_id: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Delayed index-quote integration is planned for a future phase."
        )


class FxQuoteAdapter(_PlannedAdapter):
    """Future adapter for FX quotes. Inert in this phase."""

    name = "fx-quotes"

    def fetch_fx_quotes(self, base: str, quote: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "FX quote integration is planned for a future phase."
        )


class NewsSentimentAdapter(_PlannedAdapter):
    """Future adapter for market news + sentiment. Inert in this phase (no scraping)."""

    name = "news-sentiment"

    def fetch_headlines(self, market_id: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "News / sentiment integration is planned for a future phase."
        )


# These three remain planned/inert.
PLANNED_ADAPTERS = (
    DelayedIndexQuoteAdapter,
    FxQuoteAdapter,
    NewsSentimentAdapter,
)


# ---------------------------------------------------------------------------
# FRED macro adapter (optional, config-gated)
# ---------------------------------------------------------------------------

DEFAULT_FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# v1 coverage: United States only. Each value is a FRED series id whose latest
# observation is already a percentage rate (no YoY math). `inflation` and
# `debt_to_gdp` are intentionally left to static sample data in v1 — partial,
# honest coverage. Extend this map (and document it) to add markets/fields.
FRED_SERIES_MAP: Dict[str, Dict[str, str]] = {
    "us": {
        "policy_rate": "FEDFUNDS",  # effective federal funds rate (%)
        "unemployment": "UNRATE",  # civilian unemployment rate (%)
        "gdp_growth": "A191RL1Q225SBEA",  # real GDP, % change (annualized)
    },
}

_TRUE = {"1", "true", "yes", "on"}


@dataclass
class FredMacroConfig:
    """Runtime configuration for the FRED macro adapter (read from env)."""

    enabled: bool = False
    api_key: Optional[str] = None
    base_url: str = DEFAULT_FRED_BASE_URL
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "FredMacroConfig":
        import os

        e = env if env is not None else os.environ
        enabled = str(e.get("GLOBE_FRED_ENABLED", "")).strip().lower() in _TRUE
        api_key = (e.get("FRED_API_KEY") or "").strip() or None
        base_url = (e.get("FRED_BASE_URL") or "").strip() or DEFAULT_FRED_BASE_URL
        try:
            timeout = float(e.get("FRED_TIMEOUT_SECONDS") or 5.0)
        except (TypeError, ValueError):
            timeout = 5.0
        try:
            ttl = int(e.get("GLOBE_FRED_CACHE_TTL_SECONDS") or 3600)
        except (TypeError, ValueError):
            ttl = 3600
        return cls(
            enabled=enabled,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=max(0.5, timeout),
            cache_ttl_seconds=max(0, ttl),
        )


# Module-level TTL cache: {(base_url, series_id): (expires_at, value, as_of_date)}.
# In-memory only — no persistent storage, no database.
_SERIES_CACHE: Dict[Tuple[str, str], Tuple[float, float, str]] = {}


def clear_fred_cache() -> None:
    """Reset the in-memory series cache (used by tests)."""
    _SERIES_CACHE.clear()


# A fetcher takes a URL + timeout and returns parsed JSON (a dict). Injectable so
# tests never touch the network.
Fetcher = Callable[[str, float], Any]


def _default_fetcher(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "QuantLab/globe-fred"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only, opt-in)
        return json.loads(resp.read().decode("utf-8"))


def _coerce_value(raw: Any) -> Optional[float]:
    """FRED missing values are '.'; coerce to a finite float or None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s == ".":
        return None
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


class FredMacroAdapter:
    """
    Optional adapter that enriches a market's macro block from FRED.

    Disabled by default. When enabled with a configured key it fetches the latest
    observation for a small set of mapped series; on *any* problem (disabled, no
    key, no mapping, network error, missing/invalid value) it returns the static
    sample dossier unchanged with an honest source state. The key is never
    returned to callers.
    """

    name = "fred-macro"

    def __init__(self, config: Optional[FredMacroConfig] = None, fetcher: Optional[Fetcher] = None):
        self.config = config or FredMacroConfig()
        self._fetcher = fetcher or _default_fetcher

    def is_live(self) -> bool:
        """True only when FRED is enabled *and* a key is configured."""
        return bool(self.config.enabled and self.config.api_key)

    def source_state(self) -> str:
        if not self.config.enabled:
            return "static_sample"
        return "fred_live" if self.config.api_key else "fred_unavailable"

    def fetch_series_latest(self, series_id: str) -> Optional[Tuple[float, str]]:
        """
        Return (value, observation_date) for the latest valid observation, or
        None. Never raises — fails closed. No call unless live.
        """
        if not self.is_live():
            return None
        cache_key = (self.config.base_url, series_id)
        now = time.time()
        cached = _SERIES_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return (cached[1], cached[2])
        try:
            params = urllib.parse.urlencode(
                {
                    "series_id": series_id,
                    "api_key": self.config.api_key or "",
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                }
            )
            url = f"{self.config.base_url}/series/observations?{params}"
            payload = self._fetcher(url, self.config.timeout_seconds)
            if not isinstance(payload, dict):
                return None
            observations = payload.get("observations")
            if not isinstance(observations, list) or not observations:
                return None
            obs = observations[0]
            if not isinstance(obs, dict):
                return None
            value = _coerce_value(obs.get("value"))
            if value is None:
                return None
            as_of = str(obs.get("date") or "").strip() or "unknown"
            if self.config.cache_ttl_seconds > 0:
                _SERIES_CACHE[cache_key] = (
                    now + self.config.cache_ttl_seconds,
                    value,
                    as_of,
                )
            return (value, as_of)
        except Exception:
            # Fail closed on any network / parse / unexpected error.
            return None

    def fetch_market_macro(self, market_id: str) -> Tuple[Dict[str, float], Optional[str]]:
        """Return ({macro_field: value}, latest_as_of_date) for mapped series."""
        mapping = FRED_SERIES_MAP.get((market_id or "").lower())
        if not mapping:
            return ({}, None)
        values: Dict[str, float] = {}
        as_of: Optional[str] = None
        for field, series_id in mapping.items():
            result = self.fetch_series_latest(series_id)
            if result is None:
                continue
            value, date = result
            values[field] = value
            if as_of is None or (date != "unknown" and date > as_of):
                as_of = date
        return (values, as_of)

    def enrich_market_with_fred_macro(
        self, dossier: MarketDossier
    ) -> Tuple[MarketDossier, str, List[str]]:
        """
        Return (dossier, macro_source_state, warnings).

        macro_source_state ∈ {static_sample, fred_live, fred_unavailable}.
        Never raises; always returns a valid dossier.
        """
        if not self.config.enabled:
            return (dossier, "static_sample", [])

        if not self.config.api_key:
            warning = (
                "FRED macro adapter enabled but no API key configured; using "
                "static sample data."
            )
            return (_with_macro_state(dossier, "fred_unavailable"), "fred_unavailable", [warning])

        if dossier.id not in FRED_SERIES_MAP:
            # No mapping for this market → keep static, do not claim live.
            return (dossier, "static_sample", [])

        try:
            values, as_of = self.fetch_market_macro(dossier.id)
        except Exception:
            values, as_of = {}, None

        if not values:
            warning = (
                f"FRED macro request for '{dossier.id}' returned no usable data; "
                "using static sample data."
            )
            return (_with_macro_state(dossier, "fred_unavailable"), "fred_unavailable", [warning])

        new_macro = dossier.macro.model_copy(
            update={**values, "is_sample": False, "as_of_date": as_of}
        )
        new_status = dossier.source_status.model_copy(update={"macro": "fred_live"})
        enriched = dossier.model_copy(
            update={"macro": new_macro, "source_status": new_status}
        )
        return (enriched, "fred_live", [])


def _with_macro_state(dossier: MarketDossier, macro_state: str) -> MarketDossier:
    """Return a copy of the dossier with source_status.macro set (data unchanged)."""
    new_status = dossier.source_status.model_copy(update={"macro": macro_state})
    return dossier.model_copy(update={"source_status": new_status})
