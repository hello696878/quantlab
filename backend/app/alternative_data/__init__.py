"""
Alternative Data, News Sentiment & Signal Decay Lab (Phase 30.0).

A self-contained, **deterministic static-sample** alternative-data research lab:
sample news/social/earnings/macro/product/supply-chain events with sentiment,
intensity, novelty, reliability, and relevance scores; freshness decay and a
leakage guard; event-study horizons; information coefficient, hit rate, and a
signal-decay curve; a composite alpha score; a research risk-regime
classification; and scenario stresses.

It never fetches live news, social media, or market data, does no scraping,
calls no LLM or provider APIs, makes no network calls at all, and is educational
only — not investment, trading, legal, tax, or risk-management advice, and not a
production alpha engine.
"""

from app.alternative_data.models import (
    AlternativeDataAnalysisRequest,
    AlternativeDataAnalysisResponse,
    AlternativeDataEventInput,
    AlternativeDataSampleResponse,
    AlternativeDataScenarioInput,
    SignalDecayPointInput,
)
from app.alternative_data.sample import DISCLAIMER, build_sample_response, sample_requests
from app.alternative_data.service import analyze_alternative_data

__all__ = [
    "AlternativeDataAnalysisRequest",
    "AlternativeDataAnalysisResponse",
    "AlternativeDataEventInput",
    "AlternativeDataSampleResponse",
    "AlternativeDataScenarioInput",
    "SignalDecayPointInput",
    "DISCLAIMER",
    "build_sample_response",
    "sample_requests",
    "analyze_alternative_data",
]
