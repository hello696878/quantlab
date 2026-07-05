"""
Tokenomics, Unlock Schedule & Treasury Risk Lab (Phase 28.0).

A self-contained, **deterministic static-sample** crypto fundamental-risk
analytics lab: market cap / FDV / float ratio, an unlock schedule with dilution
pressure, emission inflation and a real staking-yield approximation, protocol
treasury runway, holder concentration, a tokenomics risk-regime classification,
and unlock / treasury stress scenarios.

It never fetches live token prices or on-chain data, connects to no wallets,
makes no blockchain RPC or smart-contract calls and no network calls at all, and
is educational only — not investment, trading, token, venture, legal, tax, or
risk-management advice, and not a production due-diligence engine.
"""

from app.tokenomics.models import (
    HolderConcentrationInput,
    TokenMarketInput,
    TokenomicsAnalysisRequest,
    TokenomicsAnalysisResponse,
    TokenomicsSampleResponse,
    TokenomicsScenarioInput,
    UnlockEventInput,
)
from app.tokenomics.sample import DISCLAIMER, build_sample_response, sample_requests
from app.tokenomics.service import analyze_tokenomics

__all__ = [
    "HolderConcentrationInput",
    "TokenMarketInput",
    "TokenomicsAnalysisRequest",
    "TokenomicsAnalysisResponse",
    "TokenomicsSampleResponse",
    "TokenomicsScenarioInput",
    "UnlockEventInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_tokenomics",
]
