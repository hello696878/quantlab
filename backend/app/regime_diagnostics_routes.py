"""
Market Regime Robustness / Conditional Performance Diagnostics Lab API routes
(Phase 54.0).

Local-first research diagnostics that condition candidate outcomes on
explicitly defined market regimes under a strict no-look-ahead policy:
trailing windows only, effective labels lagged by at least one period,
threshold-fitting subsets with distinct integrity states, and honest
unavailability for rare regimes.

Honest scope: regimes are descriptive research states — never predictions;
conditional statistics never prove causality, profitability, or safety; no
regime or candidate is ever selected, switched to, or recommended.
Validation errors → 422, unknown ids → 404, conflicts → 409; execution is
deterministic and bounded (≤16 candidates, ≤2000 periods, ≤6 definitions,
≤12 combined labels, ≤50 detailed transitions per definition).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.regime_diagnostics import service
from app.regime_diagnostics import store as rd_store
from app.regime_diagnostics.core import RegimeInputError
from app.regime_diagnostics.definitions import RegimeDefinitionError
from app.regime_diagnostics.demo import seed_demo_regime_diagnostics
from app.regime_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/regime-diagnostics", tags=["regime-diagnostics"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.RegimeError, RegimeInputError, RegimeDefinitionError,
            ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List regime-diagnostic runs")
def list_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    validation_run_id: Optional[int] = None,
    overfitting_run_id: Optional[int] = None,
    configuration_fingerprint: Optional[str] = None,
    universe_fingerprint: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    return RunListResponse(**service.list_runs(
        filters={"status": status, "integrity_status": integrity_status,
                 "dataset_version_id": dataset_version_id,
                 "validation_run_id": validation_run_id,
                 "overfitting_run_id": overfitting_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "universe_fingerprint": universe_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a regime-diagnostic run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["candidates"] = [c.model_dump() for c in request.candidates]
    payload["definitions"] = [d.model_dump() for d in request.definitions]
    return RunFull(**_guard(lambda: service.create_run(payload)))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + diagnostics as JSON")
def export_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status, "integrity_status": integrity_status,
                           "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_regime_diagnostics))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute (or re-execute) a run")
def execute_run(run_id: int, request: ExecuteRequest) -> RunFull:
    return RunFull(**_guard(
        lambda: service.execute_run(run_id, create_experiment=request.create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull,
             summary="Invalidate a run")
def invalidate_run(run_id: int, request: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id, request.reason)))


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull,
             summary="Mark a run as its scope's baseline (comparison reference only)")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.get("/runs/{run_id}/definitions",
            summary="Definitions with assignments, intervals and transitions")
def definitions(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": rd_store.list_definitions(run_id)}


@router.get("/runs/{run_id}/conditional-results",
            summary="Per candidate × definition × regime metrics")
def conditional_results(
    run_id: int,
    candidate_id: Optional[str] = None,
    definition_id: Optional[str] = None,
) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": rd_store.list_conditional_results(
        run_id, candidate_id=candidate_id, definition_id=definition_id)}
