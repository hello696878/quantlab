"""
Global Markets Globe data layer.

A typed, static-sample country/market **dossier** data layer (Phase 20.2) with
*optional*, config-gated enrichment adapters that are all **disabled by default**
and **fail closed to static sample data**: a **FRED macro adapter** (Phase 20.3,
`adapters.py`), a **delayed index/FX quote adapter** (Phase 20.4, `quotes.py`),
and a **news-sentiment scaffold** (Phase 20.5, `news.py`) that always serves the
bundled static sample headlines. The only inert stub left in `adapters.py` is the
placeholder for a future *live* news provider; v1 never fetches live news.
"""

from app.globe.adapters import (
    FredMacroAdapter,
    FredMacroConfig,
    NewsSentimentAdapter,
    PLANNED_ADAPTERS,
    clear_fred_cache,
)
from app.globe.quotes import (
    DelayedIndexQuoteAdapter,
    FxQuoteAdapter,
    GlobeQuotesConfig,
    QuoteResult,
    YfinanceQuoteProvider,
    clear_quote_cache,
    enrich_market_with_quotes,
    resolve_quote_provider,
)
from app.globe.news import GlobeNewsConfig, enrich_market_with_news
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
    "GlobeQuotesConfig",
    "QuoteResult",
    "YfinanceQuoteProvider",
    "clear_quote_cache",
    "enrich_market_with_quotes",
    "resolve_quote_provider",
    "GlobeNewsConfig",
    "enrich_market_with_news",
    "NewsSentimentAdapter",
    "PLANNED_ADAPTERS",
]
