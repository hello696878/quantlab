"""
Service layer for the Global Markets Globe data layer.

Phase 20.2 added static accessors. Phase 20.3 adds an *optional* FRED macro
enrichment pass (`build_markets_response` / `build_single_market`) that is
**disabled by default** and **fails closed to static sample data**. Index and FX
fields may be optionally enriched with delayed quotes; all others stay static.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.globe.adapters import FredMacroAdapter, FredMacroConfig
from app.globe.models import MarketDossier, RegionCount
from app.globe.quotes import (
    DelayedIndexQuoteAdapter,
    FxQuoteAdapter,
    GlobeQuotesConfig,
    enrich_market_with_quotes,
    resolve_quote_provider,
)
from app.globe.sample_markets import SAMPLE_MARKETS, STATIC_DATA_NOTICE

DATA_STATUS = "static_sample"
DATA_NOTICE = STATIC_DATA_NOTICE

# Markets-endpoint notice: honest about what is (and is not) live.
MARKETS_NOTICE = (
    "Static illustrative data remains the default. Optional FRED macro and "
    "delayed index/FX quote adapters can enrich supported fields when "
    "configured. News integration is planned. Not real-time market data and "
    "not investment advice."
)


def _combine_data_status(any_fred: bool, any_quote: bool) -> str:
    if any_fred and any_quote:
        return "mixed_static_fred_quotes"
    if any_fred:
        return "mixed_static_and_fred"
    if any_quote:
        return "mixed_static_and_quotes"
    return "static_sample"

_REGION_ORDER = ("Americas", "Europe", "Asia-Pacific")


def get_all_markets() -> List[MarketDossier]:
    """Return all static sample market dossiers (no enrichment)."""
    return list(SAMPLE_MARKETS)


def get_market(market_id: str) -> Optional[MarketDossier]:
    """Return one static dossier by id (case-insensitive), or None."""
    key = (market_id or "").strip().lower()
    for m in SAMPLE_MARKETS:
        if m.id == key:
            return m
    return None


def get_regions() -> List[RegionCount]:
    """Return region → market-count rollups (static sample)."""
    counts = {r: 0 for r in _REGION_ORDER}
    for m in SAMPLE_MARKETS:
        counts[m.region] = counts.get(m.region, 0) + 1
    return [RegionCount(region=r, count=counts[r]) for r in _REGION_ORDER]


# ---------------------------------------------------------------------------
# Optional FRED macro enrichment (Phase 20.3)
# ---------------------------------------------------------------------------


def build_markets_response(
    config: Optional[FredMacroConfig] = None,
    adapter: Optional[FredMacroAdapter] = None,
    quotes_config: Optional[GlobeQuotesConfig] = None,
    index_adapter: Optional[DelayedIndexQuoteAdapter] = None,
    fx_adapter: Optional[FxQuoteAdapter] = None,
) -> Tuple[List[MarketDossier], str, str, List[str]]:
    """
    Return (markets, data_status, notice, warnings) with optional FRED macro and
    optional delayed index/FX quote enrichment. With both disabled (default) this
    is pure static sample data and performs no external calls.
    """
    cfg = config or FredMacroConfig()
    adp = adapter or FredMacroAdapter(cfg)
    qcfg = quotes_config or GlobeQuotesConfig()
    if qcfg.enabled and (index_adapter is None or fx_adapter is None):
        quote_provider = resolve_quote_provider(qcfg)
        index_adapter = index_adapter or DelayedIndexQuoteAdapter(qcfg, quote_provider)
        fx_adapter = fx_adapter or FxQuoteAdapter(qcfg, quote_provider)

    enriched: List[MarketDossier] = []
    warnings: List[str] = []
    any_fred = False
    any_quote = False

    for market in SAMPLE_MARKETS:
        dossier, macro_state, warns = adp.enrich_market_with_fred_macro(market)
        dossier, idx_state, fx_state, quote_warns = enrich_market_with_quotes(
            dossier, qcfg, index_adapter, fx_adapter
        )
        enriched.append(dossier)
        if macro_state == "fred_live":
            any_fred = True
        if idx_state == "delayed_quote" or fx_state == "delayed_quote":
            any_quote = True
        for w in (*warns, *quote_warns):
            if w not in warnings:
                warnings.append(w)

    data_status = _combine_data_status(any_fred, any_quote)
    return (enriched, data_status, MARKETS_NOTICE, warnings)


def build_single_market(
    market_id: str,
    config: Optional[FredMacroConfig] = None,
    adapter: Optional[FredMacroAdapter] = None,
    quotes_config: Optional[GlobeQuotesConfig] = None,
    index_adapter: Optional[DelayedIndexQuoteAdapter] = None,
    fx_adapter: Optional[FxQuoteAdapter] = None,
) -> Optional[MarketDossier]:
    """Return one dossier (optionally FRED + delayed-quote enriched), or None."""
    base = get_market(market_id)
    if base is None:
        return None
    cfg = config or FredMacroConfig()
    adp = adapter or FredMacroAdapter(cfg)
    qcfg = quotes_config or GlobeQuotesConfig()
    if qcfg.enabled and (index_adapter is None or fx_adapter is None):
        quote_provider = resolve_quote_provider(qcfg)
        index_adapter = index_adapter or DelayedIndexQuoteAdapter(qcfg, quote_provider)
        fx_adapter = fx_adapter or FxQuoteAdapter(qcfg, quote_provider)
    dossier, _state, _warns = adp.enrich_market_with_fred_macro(base)
    dossier, _idx, _fx, _qwarns = enrich_market_with_quotes(
        dossier, qcfg, index_adapter, fx_adapter
    )
    return dossier
