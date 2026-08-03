"""
Signal Ensemble Lab API (Phase 61, v1) — descriptive multi-signal
similarity, redundancy and explicit combination diagnostics: strict
(entity, timestamp) alignment with missingness disclosed, real scipy
p-values, matrix concentration described as such, deterministic
combinations whose contributions reconcile, and read-only fingerprint-
pinned links.  Nothing selects signals or weights, and nothing here is
investment advice.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.signal_ensemble import service
from app.signal_ensemble import store as store_mod
from app.signal_ensemble.demo import seed_demo_signal_ensemble
from app.signal_ensemble.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/signal-ensembles", tags=["signal-ensembles"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except service.InternalExecutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except (*service.ENGINE_ERRORS, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List signal-ensemble runs")
def list_runs(
    status: Optional[str] = None,
    combination_mode: Optional[str] = None,
    alignment_policy: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(store_mod.DEFAULT_PAGE_SIZE, ge=1,
                           le=store_mod.MAX_PAGE_SIZE),
) -> RunListResponse:
    filters = {"status": status, "combination_mode": combination_mode,
               "alignment_policy": alignment_policy,
               "integrity_status": integrity_status,
               "completeness_status": completeness_status,
               "is_baseline": is_baseline, "query": query}
    return RunListResponse(**_guard(lambda: service.list_runs(
        filters=filters, sort=sort_by,
        descending=(sort_dir != "asc"), page=page, page_size=page_size)))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a signal-ensemble run")
def create_run(payload: RunCreate) -> RunFull:
    created = _guard(lambda: service.create_run(
        payload.model_dump(exclude_none=False)))
    return RunFull(**_guard(lambda: service.get_run(created["id"])))


@router.get("/compare", summary="Neutral comparison of two runs")
def compare(a: int = Query(..., gt=0),
            b: int = Query(..., gt=0)) -> Dict[str, Any]:
    return _guard(lambda: service.compare_runs(a, b))


@router.get("/export", summary="Export runs and results as JSON")
def export(status: Optional[str] = None,
           combination_mode: Optional[str] = None,
           integrity_status: Optional[str] = None,
           query: Optional[str] = None) -> Dict[str, Any]:
    filters = {"status": status, "combination_mode": combination_mode,
               "integrity_status": integrity_status, "query": query}
    return _guard(lambda: service.export(filters))


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Seed the deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_signal_ensemble))


@router.get("/runs/{run_id}", response_model=RunFull,
            summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute a run (pins links, replaces results)")
def execute_run(run_id: int,
                payload: Optional[ExecuteRequest] = None) -> RunFull:
    create_experiment = bool(payload and payload.create_experiment)
    return RunFull(**_guard(lambda: service.execute_run(
        run_id, create_experiment=create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull,
             summary="Invalidate a run (append-only audit)")
def invalidate_run(run_id: int, payload: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(
        run_id, payload.reason)))


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull,
             summary="Mark an eligible run as the comparison baseline")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.get("/runs/{run_id}/pairwise", summary="Pairwise similarity rows")
def get_pairwise(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_pairwise(run_id)}


@router.get("/runs/{run_id}/matrix",
            summary="Correlation + distance matrices and diagnostics")
def get_matrix(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id,
                                         include_configuration=False))
    return {"matrix": run.get("matrix"), "distance": run.get("distance"),
            "diagnostics": run.get("matrix_diagnostics"),
            "clustering": run.get("clustering"),
            "redundancy": run.get("redundancy")}


@router.get("/runs/{run_id}/components",
            summary="Combined observations + component contributions")
def get_components(run_id: int,
                   limit: int = Query(500, ge=1, le=2000)) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id,
                                         include_configuration=False))
    return {"observations": store_mod.list_observations(run_id,
                                                        limit=limit),
            "components": store_mod.list_components(run_id, limit=limit),
            "reconciliation": run.get("reconciliation"),
            "contribution_rows_total":
                run.get("contribution_rows_total"),
            "contribution_rows_stored":
                run.get("contribution_rows_stored")}


@router.get("/runs/{run_id}/horizons", summary="Horizon x lag rows")
def get_horizons(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_horizons(run_id)}


@router.get("/runs/{run_id}/leave-one-out",
            summary="Leave-one-signal-out rows")
def get_leave_one_out(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_leave_one_out(run_id)}


@router.get("/runs/{run_id}/regimes", summary="Regime-conditioned rows")
def get_regimes(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_regimes(run_id)}


@router.get("/runs/{run_id}/bootstrap", summary="Bootstrap quantile rows")
def get_bootstrap(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_bootstrap(run_id)}


@router.get("/runs/{run_id}/sensitivity",
            summary="Sensitivity scenario rows")
def get_sensitivity(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id, include_configuration=False))
    return {"items": store_mod.list_sensitivity(run_id)}
