"""
Future data-source adapter stubs for the Global Markets Globe.

These intentionally **do not** fetch any live data, require any API key, make
any HTTP request, or scrape any website. They define the *seams* where a future
phase can integrate real sources (FRED macro, delayed index/FX quotes,
news/sentiment) without changing the dossier shape. Each `fetch_*` method raises
``NotImplementedError`` and each adapter reports ``source_state() == "planned"``.

Honesty constraint: the current phase is a **data-architecture** step, not a
live-data step. Nothing here connects to the outside world.
"""

from __future__ import annotations

from typing import Any


class _PlannedAdapter:
    """Base for not-yet-implemented adapters. No network, no keys, no fetch."""

    name = "planned-adapter"
    planned_phase = "future"

    def source_state(self) -> str:
        """Adapters are placeholders until a future phase wires real data."""
        return "planned"

    def is_live(self) -> bool:
        return False


class FredMacroAdapter(_PlannedAdapter):
    """
    Future adapter for country-level macro data (FRED).

    The current phase intentionally does not fetch live FRED data, and this
    adapter requires no API key. Live macro integration is planned for a later
    phase (Blueprint v5, Stage 2).
    """

    name = "fred-macro"

    def fetch_country_macro(self, country_id: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Live FRED macro integration is planned for a future phase."
        )


class DelayedIndexQuoteAdapter(_PlannedAdapter):
    """
    Future adapter for delayed (not real-time) equity-index quotes.

    No live fetch, no API key in this phase. Delayed quotes are planned for a
    later phase; nothing here implies real-time market coverage.
    """

    name = "delayed-index-quotes"

    def fetch_index_quotes(self, market_id: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Delayed index-quote integration is planned for a future phase."
        )


class FxQuoteAdapter(_PlannedAdapter):
    """
    Future adapter for FX quotes.

    No live fetch and no API key in this phase. FX quote integration is planned
    for a later phase.
    """

    name = "fx-quotes"

    def fetch_fx_quotes(self, base: str, quote: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "FX quote integration is planned for a future phase."
        )


class NewsSentimentAdapter(_PlannedAdapter):
    """
    Future adapter for market news + sentiment.

    No live fetch, no scraping, no API key in this phase. A news / sentiment
    pipeline is planned for a later phase; current headlines are static samples.
    """

    name = "news-sentiment"

    def fetch_headlines(self, market_id: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "News / sentiment integration is planned for a future phase."
        )


# Registry of the planned adapters (handy for tests + future wiring).
PLANNED_ADAPTERS = (
    FredMacroAdapter,
    DelayedIndexQuoteAdapter,
    FxQuoteAdapter,
    NewsSentimentAdapter,
)
