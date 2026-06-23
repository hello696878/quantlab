"""
Optional news-sentiment scaffold for the Global Markets Globe (Phase 20.5).

This is a **safe scaffold only** — NOT live news. v1 always serves the static
sample headlines already bundled in each dossier. There is **no live news fetch,
no scraping, no external news/LLM API, and no API key** anywhere in this module.

Behaviour:
- Disabled (default) → static sample headlines, ``source_status.news`` stays
  ``static_sample``, no warning.
- Enabled with the default ``static`` provider → still static sample (the static
  provider is the legitimate v1 source), no warning.
- Enabled with any *other* provider → no real provider is wired in v1, so the
  headlines stay static and ``source_status.news`` becomes ``news_unavailable``
  with a non-blocking warning. Still no external call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.globe.models import MarketDossier

NEWS_UNAVAILABLE_WARNING = (
    "Globe news adapter is not configured; using static sample headlines."
)

_TRUE = {"1", "true", "yes", "on"}


@dataclass
class GlobeNewsConfig:
    """Runtime configuration for the news-sentiment scaffold (read from env)."""

    enabled: bool = False
    provider: str = "static"

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "GlobeNewsConfig":
        import os

        e = env if env is not None else os.environ
        enabled = str(e.get("GLOBE_NEWS_ENABLED", "")).strip().lower() in _TRUE
        provider = (e.get("GLOBE_NEWS_PROVIDER") or "static").strip().lower()
        return cls(enabled=enabled, provider=provider)


def _with_news_state(dossier: MarketDossier, news_state: str) -> MarketDossier:
    """Return a copy with source_status.news set (headlines unchanged)."""
    new_status = dossier.source_status.model_copy(update={"news": news_state})
    return dossier.model_copy(update={"source_status": new_status})


def enrich_market_with_news(
    dossier: MarketDossier,
    config: GlobeNewsConfig,
) -> Tuple[MarketDossier, str, List[str]]:
    """
    Return (dossier, news_state, warnings). Never raises, never calls out.

    news_state ∈ {static_sample, news_unavailable}. Headlines are always the
    bundled static sample data — this scaffold only annotates provenance.
    """
    if not config.enabled or config.provider == "static":
        return (dossier, "static_sample", [])

    # A non-static provider was requested but none is implemented in v1.
    return (
        _with_news_state(dossier, "news_unavailable"),
        "news_unavailable",
        [NEWS_UNAVAILABLE_WARNING],
    )
