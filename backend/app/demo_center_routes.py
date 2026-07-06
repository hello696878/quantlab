"""
Product Demo Center, Guided Walkthroughs & Module Health Dashboard API routes
(Phase 34.0).

    GET  /demo-center/sample    — deterministic demo paths + module health catalog
    POST /demo-center/analyze   — path summary / readiness / capability / script analytics

Static illustrative demo metadata only — no live data, no telemetry, no
analytics tracking, no login, no cloud sync, no API keys, no trading, and no
investment / trading / asset-allocation / compliance advice. Validation errors
return 422 automatically; an unknown path id or an empty module match also
returns 422.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.demo_center.models import (
    DemoCenterAnalysisResponse,
    DemoCenterRequest,
    DemoCenterSampleResponse,
)
from app.demo_center.sample import build_sample_response
from app.demo_center.service import analyze_demo_center

router = APIRouter(prefix="/demo-center", tags=["demo-center"])


@router.get(
    "/sample",
    response_model=DemoCenterSampleResponse,
    summary="Deterministic demo paths and module health catalog",
    description=(
        "Return the eight static guided demo paths (founder/investor tour "
        "through full platform showcase) and the 21-module health/capability "
        "catalog, plus script-section and audience catalogs and a default "
        "request. Hand-written demo metadata — not telemetry, not live data, "
        "not advice."
    ),
)
def get_sample() -> DemoCenterSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=DemoCenterAnalysisResponse,
    summary="Analyse a demo-center request",
    description=(
        "Compute the path summary, category coverage, module readiness score, "
        "demo complexity score, script coverage, per-module capability "
        "scores, a completion checklist, and a deterministic audience-"
        "tailored Markdown demo script with a Markdown + JSON export payload. "
        "Static demo metadata; not investment, trading, or asset-allocation "
        "advice."
    ),
)
def analyze(request: DemoCenterRequest) -> DemoCenterAnalysisResponse:
    try:
        return analyze_demo_center(request)
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown demo path id: {request.selected_path_id!r}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
