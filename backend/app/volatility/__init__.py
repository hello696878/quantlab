"""
Volatility Surface & Variance Swap Lab (Phase 24.0).

A self-contained, **deterministic static-sample** derivatives-volatility lab:
implied-volatility inversion (reusing the Options Lab Black-Scholes), volatility
smile / skew / term structure, a 2-D volatility surface, realized-vol comparison,
a simplified educational variance-swap fair-strike approximation, vega exposure,
and volatility scenario stress.

It never fetches live option chains or market data, makes no network calls, and is
educational only — not investment, trading, legal, tax, or risk-management advice,
and not official VIX / exchange methodology.
"""

from app.volatility.models import (
    OptionQuoteInput,
    UnderlyingInput,
    VolatilityAnalysisRequest,
    VolatilityAnalysisResponse,
    VolatilitySampleResponse,
)
from app.volatility.sample import build_sample_response, sample_request
from app.volatility.service import DISCLAIMER, analyze_volatility

__all__ = [
    "OptionQuoteInput",
    "UnderlyingInput",
    "VolatilityAnalysisRequest",
    "VolatilityAnalysisResponse",
    "VolatilitySampleResponse",
    "build_sample_response",
    "sample_request",
    "DISCLAIMER",
    "analyze_volatility",
]
