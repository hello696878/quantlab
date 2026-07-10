"""
Data Mode Registry, Offline Fixtures & API Reliability Center API routes
(Phase 35.0).

    GET  /data-reliability/sample    — static module/provider/fixture registries
    POST /data-reliability/analyze   — rates / score / matrices / report analytics

Static reliability metadata only — this layer never calls the providers it
describes (no yfinance, no FRED, no network), holds no API keys, adds no
telemetry, and never guarantees external availability. Validation errors
return 422 automatically; an empty category/module match also returns 422.
Educational only — not investment, trading, or compliance advice.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data_reliability.models import (
    DataReliabilityAnalysisResponse,
    DataReliabilityRequest,
    DataReliabilitySampleResponse,
)
from app.data_reliability.sample import build_sample_response
from app.data_reliability.service import analyze_data_reliability

router = APIRouter(prefix="/data-reliability", tags=["data-reliability"])


@router.get(
    "/sample",
    response_model=DataReliabilitySampleResponse,
    summary="Static data-mode, provider, and fixture registries",
    description=(
        "Return the hand-maintained 20-module data-mode registry, the "
        "7-provider registry (internal fixtures/local/user-input plus the "
        "optional yfinance/FRED/delayed-quote providers, disabled by default), "
        "and the 11-fixture offline registry, plus section/category catalogs "
        "and a default request. Static metadata — never a provider call, not "
        "advice."
    ),
)
def get_sample() -> DataReliabilitySampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=DataReliabilityAnalysisResponse,
    summary="Analyse data reliability for a module scope",
    description=(
        "Compute demo-safe / test-safe / fallback-coverage / external-exposure "
        "rates and the reliability score R = 100·(0.35D + 0.25T + 0.25F + "
        "0.15(1−E)) over the scoped modules, plus test-safety and fallback "
        "matrices and a deterministic Markdown reliability report with a "
        "Markdown + JSON export payload. Static registry metadata; not an SLA, "
        "audit, or advice."
    ),
)
def analyze(request: DataReliabilityRequest) -> DataReliabilityAnalysisResponse:
    try:
        return analyze_data_reliability(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
