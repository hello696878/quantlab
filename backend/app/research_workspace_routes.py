"""
Research Workspace, Saved Presets & Experiment Journal API routes (Phase 33.0).

    GET  /research-workspace/sample    — deterministic research presets + catalogs
    POST /research-workspace/analyze   — run comparison / severity / report analytics

Static illustrative sample data only — no live data of any kind, no login, no
database, no cloud sync, no API keys, no trading or order submission, and no
investment / trading / asset-allocation / compliance advice. Validation errors
return 422 automatically; an unknown preset id or an empty staged-run match
also returns 422.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.research_workspace.models import (
    ResearchWorkspaceAnalysisResponse,
    ResearchWorkspaceSampleResponse,
    WorkspaceAnalysisRequest,
)
from app.research_workspace.sample import build_sample_response
from app.research_workspace.service import analyze_research_workspace

router = APIRouter(prefix="/research-workspace", tags=["research-workspace"])


@router.get(
    "/sample",
    response_model=ResearchWorkspaceSampleResponse,
    summary="Deterministic research presets",
    description=(
        "Return the six static illustrative research packs (macro stress, "
        "crypto risk-off, DeFi liquidity stress, tokenomics unlock review, "
        "alternative-data signal quality, cross-asset scenario report) with "
        "their sample experiment runs, plus module and report-section catalogs "
        "and a default request. Educational only — not advice, not live data."
    ),
)
def get_sample() -> ResearchWorkspaceSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=ResearchWorkspaceAnalysisResponse,
    summary="Analyse a research workspace preset",
    description=(
        "Compute per-run change and guarded percentage change, a "
        "severity-ranked run comparison, average/max severity, module "
        "coverage, a documented reproducibility checklist and score, a "
        "workspace-regime classification, a workflow timeline, a deterministic "
        "Markdown report preview, and a Markdown + JSON export payload. Static "
        "sample data; not investment, trading, or asset-allocation advice."
    ),
)
def analyze(request: WorkspaceAnalysisRequest) -> ResearchWorkspaceAnalysisResponse:
    try:
        return analyze_research_workspace(request)
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown preset id: {request.selected_preset_id!r}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
