"""
DeFi Yield, Stablecoin Peg & Lending Risk Lab (Phase 27.0).

A self-contained, **deterministic static-sample** DeFi analytics lab: stablecoin
peg deviation, lending/borrow APY with a kinked utilization interest-rate model,
collateral value / debt / LTV / health factor, liquidation threshold and
approximate liquidation price, net APY / carry, a risk-regime classification, and
protocol stress scenarios.

It never fetches live protocol data or crypto prices, connects to no wallets,
makes no blockchain RPC or smart-contract calls and no network calls at all, and
is educational only — not investment, trading, lending, borrowing, liquidation,
legal, tax, or risk-management advice, and not a production DeFi risk engine.
"""

from app.defi_risk.models import (
    CollateralPositionInput,
    DeFiMarketInput,
    DeFiRiskAnalysisRequest,
    DeFiRiskAnalysisResponse,
    DeFiRiskSampleResponse,
    DeFiScenarioInput,
    StablecoinInput,
)
from app.defi_risk.sample import DISCLAIMER, build_sample_response, sample_requests
from app.defi_risk.service import analyze_defi_risk, kinked_borrow_rate, supply_rate

__all__ = [
    "CollateralPositionInput",
    "DeFiMarketInput",
    "DeFiRiskAnalysisRequest",
    "DeFiRiskAnalysisResponse",
    "DeFiRiskSampleResponse",
    "DeFiScenarioInput",
    "StablecoinInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_defi_risk",
    "kinked_borrow_rate",
    "supply_rate",
]
