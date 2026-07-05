"""
Macro Regime & Cross-Asset Allocation Lab API routes (Phase 31.0).

    GET  /macro-regime/sample    — deterministic sample macro states
    POST /macro-regime/analyze   — scoring / regime / allocation analytics

Static illustrative sample data only — no live macro or market data (no FRED,
no yfinance, no scraping), no API keys, no network calls, no trading or order
submission, and no investment / trading / asset-allocation advice. Validation
errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.macro_regime.models import (
    MacroRegimeAnalysisRequest,
    MacroRegimeAnalysisResponse,
    MacroRegimeSampleResponse,
)
from app.macro_regime.sample import build_sample_response
from app.macro_regime.service import analyze_macro_regime

router = APIRouter(prefix="/macro-regime", tags=["macro-regime"])


@router.get(
    "/sample",
    response_model=MacroRegimeSampleResponse,
    summary="Deterministic sample macro states",
    description=(
        "Return the static illustrative sample macro states (goldilocks growth, "
        "inflation shock, recession/credit stress, stagflation, liquidity easing, "
        "strong-USD tightening) with indicator sets and a shared cross-asset "
        "assumption set. Educational only — not advice, not live data."
    ),
)
def get_sample() -> MacroRegimeSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=MacroRegimeAnalysisResponse,
    summary="Analyse a macro-regime sample",
    description=(
        "Compute indicator z-scores and category scores, a composite macro score "
        "and regime classification, regime-adjusted cross-asset assumptions, and "
        "inverse-volatility / risk-parity-style / regime-tilted educational "
        "allocations with risk contributions and macro stress scenarios. Static "
        "sample data; not investment, trading, or asset-allocation advice."
    ),
)
def analyze(request: MacroRegimeAnalysisRequest) -> MacroRegimeAnalysisResponse:
    return analyze_macro_regime(request)
