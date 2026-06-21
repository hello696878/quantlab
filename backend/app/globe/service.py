"""
Service layer for the Global Markets Globe data layer (Phase 20.2).

Pure, synchronous accessors over the static sample dataset. **No network
calls, no live data.** Everything returned is static illustrative sample data
(`data_status == "static_sample"`).
"""

from __future__ import annotations

from typing import List, Optional

from app.globe.models import MarketDossier, RegionCount
from app.globe.sample_markets import SAMPLE_MARKETS, STATIC_DATA_NOTICE

DATA_STATUS = "static_sample"
DATA_NOTICE = STATIC_DATA_NOTICE

# Ordered regions for stable region rollups.
_REGION_ORDER = ("Americas", "Europe", "Asia-Pacific")


def get_all_markets() -> List[MarketDossier]:
    """Return all static sample market dossiers."""
    return list(SAMPLE_MARKETS)


def get_market(market_id: str) -> Optional[MarketDossier]:
    """Return one dossier by id (case-insensitive), or None if not found."""
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
