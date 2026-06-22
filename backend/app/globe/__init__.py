"""
Global Markets Globe data layer.

A typed, static-sample country/market **dossier** data layer (Phase 20.2) with an
*optional*, config-gated **FRED macro adapter** (Phase 20.3) that is disabled by
default and fails closed to static sample data. `adapters.py` also holds inert
stubs for future delayed index/FX quotes and news/sentiment.
"""

from app.globe.adapters import (
    DelayedIndexQuoteAdapter,
    FredMacroAdapter,
    FredMacroConfig,
    FxQuoteAdapter,
    NewsSentimentAdapter,
    PLANNED_ADAPTERS,
    clear_fred_cache,
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
    MARKETS_NOTICE,
    build_markets_response,
    build_single_market,
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
    "MARKETS_NOTICE",
    "get_all_markets",
    "get_market",
    "get_regions",
    "build_markets_response",
    "build_single_market",
    "FredMacroAdapter",
    "FredMacroConfig",
    "clear_fred_cache",
    "DelayedIndexQuoteAdapter",
    "FxQuoteAdapter",
    "NewsSentimentAdapter",
    "PLANNED_ADAPTERS",
]
