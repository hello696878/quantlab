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

from app.real_estate.mbs import analyze_mbs, cpr_to_smm, psa_cpr
from app.real_estate.models import (
    DebtInput,
    MortgageMbsAnalysisResponse,
    MortgageMbsRequest,
    MortgagePoolInput,
    PrepaymentInput,
    PropertyInput,
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
    ReitInput,
    ScenarioResult,
    ValuationInput,
)
from app.real_estate.sample import (
    build_mbs_sample_response,
    build_sample_response,
    sample_mbs_request,
    sample_request,
)
from app.real_estate.service import DISCLAIMER, analyze_real_estate

__all__ = [
    "DebtInput",
    "PropertyInput",
    "RealEstateAnalysisRequest",
    "RealEstateAnalysisResponse",
    "ReitInput",
    "ScenarioResult",
    "MortgagePoolInput",
    "PrepaymentInput",
    "ValuationInput",
    "MortgageMbsRequest",
    "MortgageMbsAnalysisResponse",
    "analyze_mbs",
    "cpr_to_smm",
    "psa_cpr",
    "build_sample_response",
    "build_mbs_sample_response",
    "sample_request",
    "sample_mbs_request",
    "DISCLAIMER",
    "analyze_real_estate",
]
