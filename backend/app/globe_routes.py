"""
Global Markets Globe API routes (Phase 20.2).

Read-only endpoints over the static sample dossier dataset:

    GET /globe/markets             — all market dossiers + data status
    GET /globe/markets/{market_id} — a single market dossier (friendly 404)
    GET /globe/regions             — region → count rollups

**Static illustrative sample data only** — no live data, no network calls, no
real-time claims. The response `data_status` is always ``static_sample`` and
every dossier's `source_status` is ``static_sample``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.globe.models import MarketDossier, MarketsResponse, RegionsResponse
from app.globe.service import (
    DATA_NOTICE,
    DATA_STATUS,
    get_all_markets,
    get_market,
    get_regions,
)

router = APIRouter(prefix="/globe", tags=["globe"])


@router.get(
    "/markets",
    response_model=MarketsResponse,
    summary="List all sample market dossiers",
    description=(
        "Return all 15 static sample country/market dossiers. "
        "Static illustrative data — not real-time, not live market data."
    ),
)
def list_markets() -> MarketsResponse:
    markets = get_all_markets()
    return MarketsResponse(
        markets=markets,
        count=len(markets),
        data_status=DATA_STATUS,
        notice=DATA_NOTICE,
    )


@router.get(
    "/regions",
    response_model=RegionsResponse,
    summary="List regions and market counts",
    description="Return region → market-count rollups for the static sample dataset.",
)
def list_regions() -> RegionsResponse:
    return RegionsResponse(
        regions=get_regions(),
        data_status=DATA_STATUS,
        notice=DATA_NOTICE,
    )


@router.get(
    "/markets/{market_id}",
    response_model=MarketDossier,
    summary="Get a single market dossier",
    description=(
        "Return one static sample market dossier by id (e.g. 'us', 'jp', 'tw'). "
        "Returns a friendly 404 if the market id is unknown."
    ),
)
def get_market_endpoint(market_id: str) -> MarketDossier:
    market = get_market(market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    return market
