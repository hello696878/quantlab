"""
Market Microstructure & Execution Lab API routes (Phase 25.0).

    GET  /microstructure/sample    — deterministic sample instruments
    POST /microstructure/analyze   — order-book + tape + execution analytics

Static illustrative sample data only — no live order books or trades, no network
calls, no order submission, no trading, and no investment / trading / order-routing
advice. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.microstructure.models import (
    MarketMicrostructureAnalysisRequest,
    MarketMicrostructureAnalysisResponse,
    MicrostructureSampleResponse,
)
from app.microstructure.sample import build_sample_response
from app.microstructure.service import analyze_microstructure

router = APIRouter(prefix="/microstructure", tags=["microstructure"])


@router.get(
    "/sample",
    response_model=MicrostructureSampleResponse,
    summary="Deterministic sample instruments",
    description=(
        "Return the static illustrative sample instruments (BTCUSDT, SPY, CL, TSM) "
        "with order books, trade tapes, parent orders, fills, and volume curves. "
        "Educational only — not advice."
    ),
)
def get_sample() -> MicrostructureSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=MarketMicrostructureAnalysisResponse,
    summary="Analyse an order book / execution",
    description=(
        "Compute order-book summary (spread, depth, imbalance, microprice), trade-"
        "tape analytics (VWAP/TWAP/imbalance), execution analytics (implementation "
        "shortfall, slippage, participation, market impact), a hypothetical "
        "execution-schedule comparison, and liquidity stress scenarios. Static "
        "sample data; not investment / trading / order-routing advice."
    ),
)
def analyze(request: MarketMicrostructureAnalysisRequest) -> MarketMicrostructureAnalysisResponse:
    return analyze_microstructure(request)
