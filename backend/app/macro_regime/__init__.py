"""
Macro Regime & Cross-Asset Allocation Lab (Phase 31.0).

A self-contained, **deterministic static-sample** macro-regime analytics lab:
indicator z-scores and category scores (growth, inflation, policy, liquidity,
credit stress, USD pressure), a composite macro score and regime classification,
regime-adjusted cross-asset assumptions, a simplified correlation matrix,
inverse-volatility / risk-parity-style / regime-tilted educational allocations,
and macro stress scenarios.

It never fetches live macro or market data (no FRED, no yfinance, no scraping),
makes no network calls, and is educational only — not investment, trading,
asset-allocation, legal, tax, or risk-management advice, and not a production
allocation engine.
"""

from app.macro_regime.models import (
    AssetClassInput,
    MacroIndicatorInput,
    MacroRegimeAnalysisRequest,
    MacroRegimeAnalysisResponse,
    MacroRegimeSampleResponse,
    MacroScenarioInput,
)
from app.macro_regime.sample import DISCLAIMER, build_sample_response, sample_requests
from app.macro_regime.service import analyze_macro_regime

__all__ = [
    "AssetClassInput",
    "MacroIndicatorInput",
    "MacroRegimeAnalysisRequest",
    "MacroRegimeAnalysisResponse",
    "MacroRegimeSampleResponse",
    "MacroScenarioInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_macro_regime",
]
