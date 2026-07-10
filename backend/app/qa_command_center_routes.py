"""
Release Readiness, Smoke Test Matrix & QA Command Center API routes
(Phase 36.0).

    GET  /qa-command-center/sample    — static QA registry + catalogs
    POST /qa-command-center/analyze   — coverage rates / score / decision / report

Static QA metadata only — this layer lists verification commands but never
runs them, never claims tests or builds were executed, fetches no data, adds
no telemetry, and is not a compliance system. Validation errors return 422
automatically; an empty filter match also returns 422. Educational only —
not investment, trading, or compliance advice.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.qa_command_center.models import (
    QACommandCenterAnalysisResponse,
    QACommandCenterRequest,
    QACommandCenterSampleResponse,
)
from app.qa_command_center.sample import build_sample_response
from app.qa_command_center.service import analyze_qa_command_center

router = APIRouter(prefix="/qa-command-center", tags=["qa-command-center"])


@router.get(
    "/sample",
    response_model=QACommandCenterSampleResponse,
    summary="Static QA registry and catalogs",
    description=(
        "Return the hand-maintained 21-module QA registry (capability flags, "
        "smoke-test and regression steps, release-status and priority labels, "
        "known limitations) plus section/category/status/priority catalogs "
        "and a default request. Static metadata — commands are listed, never "
        "run; not advice."
    ),
)
def get_sample() -> QACommandCenterSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=QACommandCenterAnalysisResponse,
    summary="Analyse release readiness for a module scope",
    description=(
        "Compute ready-rate / smoke / test-proxy / interactivity / chart "
        "coverage and the release score Q = 100·(0.30R + 0.20S + 0.20T + "
        "0.15I + 0.15C) with a rule-based decision label, the smoke-test "
        "matrix, a grouped regression checklist, the exact local verification "
        "commands (listed, never executed), a limitations tracker, draft "
        "release notes, and a deterministic Markdown report with a Markdown + "
        "JSON export payload. Static registry metadata; the score does not "
        "prove tests were run; not advice."
    ),
)
def analyze(request: QACommandCenterRequest) -> QACommandCenterAnalysisResponse:
    try:
        return analyze_qa_command_center(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
