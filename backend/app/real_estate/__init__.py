"""
Real Estate Lab (Phase 22.0).

A self-contained, **deterministic static-sample** real-estate analytics lab:
income-property valuation (NOI, cap rate), mortgage amortization, leverage
metrics (LTV, DSCR), levered cash flow (cash-on-cash, IRR, equity multiple),
rent / vacancy / cap-rate / interest-rate stress scenarios, and a simple REIT
NAV discount/premium example.

It never fetches live property or REIT data, makes no network calls, and is
educational only — not investment, tax, legal, lending, or appraisal advice.
"""

from app.real_estate.models import (
    DebtInput,
    PropertyInput,
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
    ReitInput,
    ScenarioResult,
)
from app.real_estate.sample import build_sample_response, sample_request
from app.real_estate.service import DISCLAIMER, analyze_real_estate

__all__ = [
    "DebtInput",
    "PropertyInput",
    "RealEstateAnalysisRequest",
    "RealEstateAnalysisResponse",
    "ReitInput",
    "ScenarioResult",
    "build_sample_response",
    "sample_request",
    "DISCLAIMER",
    "analyze_real_estate",
]
