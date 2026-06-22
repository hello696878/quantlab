"""
Global Markets Globe API routes (Phase 20.2).

Read-only endpoints over the static sample dossier dataset:

    GET /globe/markets             — all market dossiers + data status
    GET /globe/markets/{market_id} — a single market dossier (friendly 404)
    GET /globe/regions             — region → count rollups

By default this is **static illustrative sample data** — no live data, no
network calls, no real-time claims. An *optional*, config-gated FRED macro
adapter (disabled unless ``GLOBE_FRED_ENABLED=true`` and ``FRED_API_KEY`` are
set) may enrich the macro block of supported markets, and a separate
disabled-by-default quote adapter (``GLOBE_QUOTES_ENABLED=true``) may enrich the
primary index/FX rows of supported markets with **delayed** (never real-time)
quotes; market structure and news always stay static sample. Both adapters fail
closed to static data and no API key is ever returned to clients.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.globe.adapters import FredMacroConfig
from app.globe.models import MarketDossier, MarketsResponse, RegionsResponse
from app.globe.quotes import GlobeQuotesConfig
from app.globe.service import (
    DATA_NOTICE,
    DATA_STATUS,
    build_markets_response,
    build_single_market,
    get_market,
    get_regions,
)

router = APIRouter(prefix="/globe", tags=["globe"])


@router.get(
    "/markets",
    response_model=MarketsResponse,
    summary="List all sample market dossiers",
    description=(
        "Return all 15 sample country/market dossiers. Static illustrative data "
        "by default; optional FRED macro enrichment when configured."
    ),
)
def list_markets() -> MarketsResponse:
    markets, data_status, notice, warnings = build_markets_response(
        FredMacroConfig.from_env(),
        quotes_config=GlobeQuotesConfig.from_env(),
    )
    return MarketsResponse(
        markets=markets,
        count=len(markets),
        data_status=data_status,
        notice=notice,
        warnings=warnings,
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
    if get_market(market_id) is None:
        raise HTTPException(status_code=404, detail="Market not found.")
    dossier = build_single_market(
        market_id,
        FredMacroConfig.from_env(),
        quotes_config=GlobeQuotesConfig.from_env(),
    )
    if dossier is None:  # pragma: no cover — guarded above
        raise HTTPException(status_code=404, detail="Market not found.")
    return dossier
