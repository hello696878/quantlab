"""
Unified Scenario Studio & Cross-Lab Report Builder API routes (Phase 32.0).

    GET  /scenario-studio/sample    — deterministic scenario templates + catalogs
    POST /scenario-studio/analyze   — cross-lab impact / regime / report analytics

Static illustrative sample data only — no live macro, market, crypto, or news
data, no scraping, no LLM or provider APIs, no API keys, no trading or order
submission, and no investment / trading / asset-allocation advice. Validation
errors return 422 automatically; an unknown scenario id also returns 422.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.scenario_studio.models import (
    ScenarioStudioAnalysisResponse,
    ScenarioStudioRequest,
    ScenarioStudioSampleResponse,
)
from app.scenario_studio.sample import build_sample_response
from app.scenario_studio.service import analyze_scenario_studio

router = APIRouter(prefix="/scenario-studio", tags=["scenario-studio"])


@router.get(
    "/sample",
    response_model=ScenarioStudioSampleResponse,
    summary="Deterministic scenario templates",
    description=(
        "Return the ten static illustrative scenario templates (soft landing "
        "through severe cross-asset stress combo) plus the module and "
        "report-section catalogs and a default request. Educational only — "
        "not advice, not live data."
    ),
)
def get_sample() -> ScenarioStudioSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=ScenarioStudioAnalysisResponse,
    summary="Analyse a cross-lab scenario",
    description=(
        "Map the selected scenario template (plus optional shock overrides) "
        "through documented deterministic teaching weights into module impact "
        "scores, a composite severity, a scenario-regime classification, a "
        "module × shock-group heatmap, baseline-vs-stress metric rows, and a "
        "deterministic Markdown report. Static sample data; not investment, "
        "trading, or asset-allocation advice."
    ),
)
def analyze(request: ScenarioStudioRequest) -> ScenarioStudioAnalysisResponse:
    try:
        return analyze_scenario_studio(request)
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario id: {request.selected_scenario_id!r}",
        )
