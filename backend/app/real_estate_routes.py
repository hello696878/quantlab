"""
Real Estate Lab API routes (Phase 22.0).

    GET  /real-estate/sample    — deterministic sample property / debt / REIT
    POST /real-estate/analyze   — full income-property + REIT analytics

Static illustrative sample data only — no live property/REIT data, no network
calls, no trading, no investment / tax / legal / lending advice. Validation
errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.real_estate.models import (
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
    SampleResponse,
)
from app.real_estate.sample import build_sample_response
from app.real_estate.service import analyze_real_estate

router = APIRouter(prefix="/real-estate", tags=["real-estate"])


@router.get(
    "/sample",
    response_model=SampleResponse,
    summary="Deterministic sample property, debt, and REIT",
    description=(
        "Return the static illustrative sample inputs (urban apartment + mortgage "
        "+ REIT). Educational only — not advice."
    ),
)
def get_sample() -> SampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=RealEstateAnalysisResponse,
    summary="Analyse an income property + REIT",
    description=(
        "Compute NOI, cap rate, valuation, mortgage amortization, LTV/DSCR, "
        "levered cash flow (cash-on-cash, IRR, equity multiple), stress scenarios, "
        "and a simple REIT NAV discount/premium. Static sample data; not advice."
    ),
)
def analyze(request: RealEstateAnalysisRequest) -> RealEstateAnalysisResponse:
    return analyze_real_estate(request)
