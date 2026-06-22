"""
Service layer for the Global Markets Globe data layer.

Phase 20.2 added static accessors. Phase 20.3 adds an *optional* FRED macro
enrichment pass (`build_markets_response` / `build_single_market`) that is
**disabled by default** and **fails closed to static sample data**. Indices, FX,
market structure, and news always remain static sample data in this phase.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.globe.adapters import FredMacroAdapter, FredMacroConfig
from app.globe.models import MarketDossier, RegionCount
from app.globe.sample_markets import SAMPLE_MARKETS, STATIC_DATA_NOTICE

DATA_STATUS = "static_sample"
DATA_NOTICE = STATIC_DATA_NOTICE

# Markets-endpoint notice: honest about what is (and is not) live.
MARKETS_NOTICE = (
    "Static illustrative data for indices, FX, market structure, and headlines. "
    "FRED macro integration is optional; delayed index/FX quotes and news "
    "integration are planned. Not real-time market data and not investment advice."
)

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
) -> Tuple[List[MarketDossier], str, str, List[str]]:
    """
    Return (markets, data_status, notice, warnings) with optional FRED macro
    enrichment. With FRED disabled (default) this is pure static sample data and
    performs no external calls.
    """
    cfg = config or FredMacroConfig()
    adp = adapter or FredMacroAdapter(cfg)

    enriched: List[MarketDossier] = []
    warnings: List[str] = []
    any_fred = False

    for market in SAMPLE_MARKETS:
        dossier, macro_state, warns = adp.enrich_market_with_fred_macro(market)
        enriched.append(dossier)
        if macro_state == "fred_live":
            any_fred = True
        for w in warns:
            if w not in warnings:
                warnings.append(w)

    data_status = "mixed_static_and_fred" if any_fred else "static_sample"
    return (enriched, data_status, MARKETS_NOTICE, warnings)


def build_single_market(
    market_id: str,
    config: Optional[FredMacroConfig] = None,
    adapter: Optional[FredMacroAdapter] = None,
) -> Optional[MarketDossier]:
    """Return one dossier (optionally FRED-enriched), or None if unknown."""
    base = get_market(market_id)
    if base is None:
        return None
    cfg = config or FredMacroConfig()
    adp = adapter or FredMacroAdapter(cfg)
    dossier, _state, _warns = adp.enrich_market_with_fred_macro(base)
    return dossier
