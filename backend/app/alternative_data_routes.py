"""
Alternative Data, News Sentiment & Signal Decay Lab API routes (Phase 30.0).

    GET  /alternative-data/sample    — deterministic sample event sets
    POST /alternative-data/analyze   — sentiment / freshness / leakage / decay analytics

Static illustrative sample data only — no live news, social media, or market
data, no scraping, no LLM or provider APIs, no API keys, no network calls, no
trading or order submission, and no investment / trading / signal advice.
Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.alternative_data.models import (
    AlternativeDataAnalysisRequest,
    AlternativeDataAnalysisResponse,
    AlternativeDataSampleResponse,
)
from app.alternative_data.sample import build_sample_response
from app.alternative_data.service import analyze_alternative_data

router = APIRouter(prefix="/alternative-data", tags=["alternative-data"])


@router.get(
    "/sample",
    response_model=AlternativeDataSampleResponse,
    summary="Deterministic sample alternative-data event sets",
    description=(
        "Return the static illustrative sample event sets (mega-cap equity news, "
        "crypto sentiment stress, earnings surprise, macro shock news, supply-"
        "chain alternative data) with hand-written sentiment/novelty/reliability "
        "scores and observed return paths. Educational only — not advice, not "
        "live data."
    ),
)
def get_sample() -> AlternativeDataSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=AlternativeDataAnalysisResponse,
    summary="Analyse an alternative-data event set",
    description=(
        "Compute weighted sentiment, novelty adjustment, freshness decay, a "
        "leakage guard, event-study horizons, information coefficient / hit rate, "
        "a signal-decay curve, a composite alpha score, a research risk-regime "
        "classification, and scenario stresses. Static sample data; not "
        "investment, trading, or signal advice."
    ),
)
def analyze(request: AlternativeDataAnalysisRequest) -> AlternativeDataAnalysisResponse:
    return analyze_alternative_data(request)
