"""
Crypto Perpetual Futures Funding & Basis Lab (Phase 26.0).

A self-contained, **deterministic static-sample** crypto-derivatives analytics
lab: spot / perpetual / dated-futures basis, funding-rate mechanics and annualized
funding yield, long/short funding P&L, a cash-and-carry example, position margin /
liquidation approximation, a funding-regime classification, and funding/basis
stress scenarios.

It never fetches live exchange data or live crypto prices, makes no network calls,
submits no orders, and is educational only — not investment, trading, liquidation,
legal, tax, or risk-management advice, and not a production risk engine.
"""

from app.crypto_derivatives.models import (
    CryptoDerivativesAnalysisRequest,
    CryptoDerivativesAnalysisResponse,
    CryptoDerivativesSampleResponse,
    CryptoMarketInput,
    DatedFutureInput,
    FundingScenarioInput,
    PositionInput,
)
from app.crypto_derivatives.sample import (
    DISCLAIMER,
    build_sample_response,
    sample_requests,
)
from app.crypto_derivatives.service import analyze_crypto_derivatives

__all__ = [
    "CryptoDerivativesAnalysisRequest",
    "CryptoDerivativesAnalysisResponse",
    "CryptoDerivativesSampleResponse",
    "CryptoMarketInput",
    "DatedFutureInput",
    "FundingScenarioInput",
    "PositionInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_crypto_derivatives",
]
