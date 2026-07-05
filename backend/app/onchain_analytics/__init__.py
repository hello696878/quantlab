"""
On-Chain Flow, Exchange Reserve & Whale Concentration Lab (Phase 29.0).

A self-contained, **deterministic static-sample** crypto on-chain analytics lab:
exchange inflows/outflows and reserve ratios, 24h activity metrics (active
addresses, transfer volume, transaction count, token velocity), an NVT-style
valuation ratio, holder-cohort distribution with a Gini-style concentration
approximation, whale flow pressure, an on-chain risk-regime classification, and
on-chain stress scenarios.

It never fetches live on-chain data or token prices, connects to no wallets,
makes no blockchain RPC, smart-contract, explorer, or exchange API calls and no
network calls at all, and is educational only — not investment, trading, token,
legal, tax, or risk-management advice, and not a production due-diligence engine.
"""

from app.onchain_analytics.models import (
    HolderCohortInput,
    OnChainAnalysisRequest,
    OnChainAnalysisResponse,
    OnChainNetworkInput,
    OnChainSampleResponse,
    OnChainScenarioInput,
    WhaleFlowInput,
)
from app.onchain_analytics.sample import DISCLAIMER, build_sample_response, sample_requests
from app.onchain_analytics.service import analyze_onchain

__all__ = [
    "HolderCohortInput",
    "OnChainAnalysisRequest",
    "OnChainAnalysisResponse",
    "OnChainNetworkInput",
    "OnChainSampleResponse",
    "OnChainScenarioInput",
    "WhaleFlowInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_onchain",
]
