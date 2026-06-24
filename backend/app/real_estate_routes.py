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

from app.real_estate.mbs import analyze_mbs
from app.real_estate.models import (
    MbsSampleResponse,
    MortgageMbsAnalysisResponse,
    MortgageMbsRequest,
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
    SampleResponse,
)
from app.real_estate.sample import build_mbs_sample_response, build_sample_response
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


@router.get(
    "/mbs/sample",
    response_model=MbsSampleResponse,
    summary="Deterministic sample agency MBS pool",
    description=(
        "Return the static illustrative sample MBS pool + prepayment + valuation "
        "inputs. Educational only — not advice."
    ),
)
def get_mbs_sample() -> MbsSampleResponse:
    return build_mbs_sample_response()


@router.post(
    "/mbs/analyze",
    response_model=MortgageMbsAnalysisResponse,
    summary="Analyse a mortgage pool / MBS",
    description=(
        "Project mortgage cash flows with CPR/SMM/PSA prepayments, decompose MBS "
        "cash flows, and compute price, WAL, duration, convexity, and rate / "
        "prepayment-speed stress scenarios. Static sample data; not advice."
    ),
)
def analyze_mbs_route(request: MortgageMbsRequest) -> MortgageMbsAnalysisResponse:
    return analyze_mbs(request)
