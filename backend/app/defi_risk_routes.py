"""
DeFi Yield, Stablecoin Peg & Lending Risk Lab API routes (Phase 27.0).

    GET  /defi-risk/sample    — deterministic sample DeFi markets
    POST /defi-risk/analyze   — peg / utilization / collateral / net-APY analytics

Static illustrative sample data only — no live protocol data, no live crypto
prices, no wallets, no blockchain RPC or smart-contract calls, no network calls,
no trading or order submission, and no investment / trading / lending / borrowing
/ liquidation advice. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.defi_risk.models import (
    DeFiRiskAnalysisRequest,
    DeFiRiskAnalysisResponse,
    DeFiRiskSampleResponse,
)
from app.defi_risk.sample import build_sample_response
from app.defi_risk.service import analyze_defi_risk

router = APIRouter(prefix="/defi-risk", tags=["defi-risk"])


@router.get(
    "/sample",
    response_model=DeFiRiskSampleResponse,
    summary="Deterministic sample DeFi markets",
    description=(
        "Return the static illustrative sample DeFi markets (USDC lending, USDT "
        "peg stress, DAI collateralized debt, ETH collateral borrowing, WBTC "
        "collateral stress) with stablecoin peg snapshots, kinked rate-model "
        "markets, and collateralized positions. Educational only — not advice, "
        "not live data."
    ),
)
def get_sample() -> DeFiRiskSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=DeFiRiskAnalysisResponse,
    summary="Analyse a DeFi lending / peg / collateral sample",
    description=(
        "Compute stablecoin peg deviation, utilization and the kinked interest-"
        "rate model, collateral / debt / LTV / health factor and an approximate "
        "liquidation price, net APY, a risk-regime classification, and protocol "
        "stress scenarios. Static sample data; not investment, trading, lending, "
        "borrowing, or liquidation advice."
    ),
)
def analyze(request: DeFiRiskAnalysisRequest) -> DeFiRiskAnalysisResponse:
    return analyze_defi_risk(request)
