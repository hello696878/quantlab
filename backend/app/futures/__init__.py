"""
Futures & Commodities Lab (Phase 23.0).

A self-contained, **deterministic static-sample** futures / commodities analytics
lab: cost-of-carry futures pricing, implied convenience yield, futures-curve
shape (contango / backwardation / mixed), roll yield, calendar spreads, contract
notional / margin / leverage P&L, and commodity scenario stress.

It never fetches live futures or commodity prices, makes no network calls, and is
educational only — not investment, trading, legal, tax, or risk-management advice.
"""

from app.futures.models import (
    FuturesAnalysisRequest,
    FuturesAnalysisResponse,
    FuturesContractInput,
    FuturesCurvePoint,
    FuturesPositionInput,
    FuturesSampleResponse,
)
from app.futures.sample import build_sample_response, sample_requests
from app.futures.service import DISCLAIMER, analyze_futures

__all__ = [
    "FuturesAnalysisRequest",
    "FuturesAnalysisResponse",
    "FuturesContractInput",
    "FuturesCurvePoint",
    "FuturesPositionInput",
    "FuturesSampleResponse",
    "build_sample_response",
    "sample_requests",
    "DISCLAIMER",
    "analyze_futures",
]
