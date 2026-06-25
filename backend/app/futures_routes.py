"""
Futures & Commodities Lab API routes (Phase 23.0).

    GET  /futures/sample    — deterministic sample commodities (crude/gold/gas/wheat)
    POST /futures/analyze   — full cost-of-carry + curve + margin analytics

Static illustrative sample data only — no live futures/commodity prices, no
network calls, no trading, no investment / trading advice. Validation errors
return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.futures.models import (
    FuturesAnalysisRequest,
    FuturesAnalysisResponse,
    FuturesSampleResponse,
)
from app.futures.sample import build_sample_response
from app.futures.service import analyze_futures

router = APIRouter(prefix="/futures", tags=["futures"])


@router.get(
    "/sample",
    response_model=FuturesSampleResponse,
    summary="Deterministic sample commodities",
    description=(
        "Return the static illustrative sample commodities (crude oil, gold, "
        "natural gas, wheat) with futures curves and a sample position. "
        "Educational only — not advice."
    ),
)
def get_sample() -> FuturesSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=FuturesAnalysisResponse,
    summary="Analyse a futures contract / curve",
    description=(
        "Compute cost-of-carry pricing, implied convenience yield, curve shape "
        "(contango/backwardation/mixed), roll yield, calendar spread, notional / "
        "margin / leverage P&L, and commodity scenario stress. Static sample "
        "data; not investment or trading advice."
    ),
)
def analyze(request: FuturesAnalysisRequest) -> FuturesAnalysisResponse:
    return analyze_futures(request)
