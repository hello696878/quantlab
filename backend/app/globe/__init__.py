"""
Global Markets Globe data layer (Phase 20.2).

A typed, static-sample country/market **dossier** data layer. No live data, no
network calls, no API keys — `adapters.py` defines the seams for future live
sources (FRED macro, delayed index/FX quotes, news/sentiment).
"""

from app.globe.adapters import (
    DelayedIndexQuoteAdapter,
    FredMacroAdapter,
    FxQuoteAdapter,
    NewsSentimentAdapter,
    PLANNED_ADAPTERS,
)
from app.globe.models import (
    MarketDossier,
    MarketsResponse,
    RegionCount,
    RegionsResponse,
)
from app.globe.service import (
    DATA_NOTICE,
    DATA_STATUS,
    get_all_markets,
    get_market,
    get_regions,
)

__all__ = [
    "MarketDossier",
    "MarketsResponse",
    "RegionCount",
    "RegionsResponse",
    "DATA_NOTICE",
    "DATA_STATUS",
    "get_all_markets",
    "get_market",
    "get_regions",
    "FredMacroAdapter",
    "DelayedIndexQuoteAdapter",
    "FxQuoteAdapter",
    "NewsSentimentAdapter",
    "PLANNED_ADAPTERS",
]
