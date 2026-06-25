"""
Volatility Surface & Variance Swap Lab API routes (Phase 24.0).

    GET  /volatility/sample    — deterministic sample option chain + surface
    POST /volatility/analyze   — implied vols, smile/skew/term structure, surface,
                                 realized vol, variance swap, vega, scenarios

Static illustrative sample data only — no live option chains or market data, no
network calls, no trading, no investment / trading advice, and not official VIX /
exchange methodology. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.volatility.models import (
    VolatilityAnalysisRequest,
    VolatilityAnalysisResponse,
    VolatilitySampleResponse,
)
from app.volatility.sample import build_sample_response
from app.volatility.service import analyze_volatility

router = APIRouter(prefix="/volatility", tags=["volatility"])


@router.get(
    "/sample",
    response_model=VolatilitySampleResponse,
    summary="Deterministic sample option chain",
    description=(
        "Return the static illustrative SPX-like sample option chain (Black-"
        "Scholes-generated mid prices). Educational only — not advice."
    ),
)
def get_sample() -> VolatilitySampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=VolatilityAnalysisResponse,
    summary="Analyse a volatility surface",
    description=(
        "Invert implied vols, build the smile / skew / term structure / surface, "
        "compare realized vol, approximate a variance-swap fair strike, compute "
        "vega exposure, and run volatility scenarios. Static sample data; not "
        "investment or trading advice, and not official VIX methodology."
    ),
)
def analyze(request: VolatilityAnalysisRequest) -> VolatilityAnalysisResponse:
    return analyze_volatility(request)
