"""
Tokenomics, Unlock Schedule & Treasury Risk Lab API routes (Phase 28.0).

    GET  /tokenomics/sample    — deterministic sample tokens
    POST /tokenomics/analyze   — valuation / unlock / treasury / regime analytics

Static illustrative sample data only — no live token prices, no live on-chain
data, no wallets, no blockchain RPC or smart-contract calls, no network calls, no
trading or order submission, and no investment / trading / token / venture
advice. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.tokenomics.models import (
    TokenomicsAnalysisRequest,
    TokenomicsAnalysisResponse,
    TokenomicsSampleResponse,
)
from app.tokenomics.sample import build_sample_response
from app.tokenomics.service import analyze_tokenomics

router = APIRouter(prefix="/tokenomics", tags=["tokenomics"])


@router.get(
    "/sample",
    response_model=TokenomicsSampleResponse,
    summary="Deterministic sample tokens",
    description=(
        "Return the static illustrative sample tokens (L1, DeFi governance, "
        "gaming unlock, stablecoin governance, low-float/high-FDV) with "
        "price/supply snapshots, unlock schedules, treasury balances, and "
        "holder-concentration snapshots. Educational only — not advice, not "
        "live data."
    ),
)
def get_sample() -> TokenomicsSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=TokenomicsAnalysisResponse,
    summary="Analyse a token's tokenomics",
    description=(
        "Compute market cap / FDV / float ratio, the unlock schedule and dilution "
        "pressure, emission inflation and a real staking-yield approximation, "
        "treasury value and runway, a holder-concentration score, a tokenomics "
        "risk-regime classification, and unlock/treasury stress scenarios. Static "
        "sample data; not investment, trading, token, or venture advice."
    ),
)
def analyze(request: TokenomicsAnalysisRequest) -> TokenomicsAnalysisResponse:
    return analyze_tokenomics(request)
