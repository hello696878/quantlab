"""
On-Chain Flow, Exchange Reserve & Whale Concentration Lab API routes (Phase 29.0).

    GET  /onchain-analytics/sample    — deterministic sample networks/tokens
    POST /onchain-analytics/analyze   — flow / activity / whale / regime analytics

Static illustrative sample data only — no live on-chain data, no live token
prices, no wallets, no blockchain RPC, smart-contract, explorer, or exchange API
calls, no network calls, no trading or order submission, and no investment /
trading / token advice. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.onchain_analytics.models import (
    OnChainAnalysisRequest,
    OnChainAnalysisResponse,
    OnChainSampleResponse,
)
from app.onchain_analytics.sample import build_sample_response
from app.onchain_analytics.service import analyze_onchain

router = APIRouter(prefix="/onchain-analytics", tags=["onchain-analytics"])


@router.get(
    "/sample",
    response_model=OnChainSampleResponse,
    summary="Deterministic sample on-chain networks",
    description=(
        "Return the static illustrative sample networks/tokens (BTC-like, "
        "ETH-like, L1 exchange reserve, DeFi governance whale, exchange-inflow "
        "stress) with exchange-flow snapshots, activity metrics, holder cohorts, "
        "and whale flows. Educational only — not advice, not live data."
    ),
)
def get_sample() -> OnChainSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=OnChainAnalysisResponse,
    summary="Analyse an on-chain sample",
    description=(
        "Compute exchange inflow/outflow and reserve analytics, activity metrics "
        "and token velocity, an NVT-style valuation ratio, holder distribution "
        "with a Gini-style concentration approximation, whale flow pressure, an "
        "on-chain risk-regime classification, and on-chain stress scenarios. "
        "Static sample data; not investment, trading, or token advice."
    ),
)
def analyze(request: OnChainAnalysisRequest) -> OnChainAnalysisResponse:
    return analyze_onchain(request)
