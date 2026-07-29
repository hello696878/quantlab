"""
Signal Decay, Forecast Horizon, Turnover and Implementation Lag Diagnostics
Lab API routes (Phase 60.0).

Local-first research diagnostics: descriptive associations between STORED
signal observations and later outcomes across explicit forecast horizons
and implementation delays, with signal-availability timing enforced,
overlap disclosed, ties/constants/small samples honestly unavailable, a
neutral equal-weight bucket reference whose gross and cost-adjusted results
stay separate, and every linked record read-only and fingerprint-pinned.

Honest scope: nothing here proves predictability or alpha, guarantees that
a relationship persists, recommends a horizon, lag, threshold, signal or
trade, selects a strategy, sizes a position, monitors or executes anything,
or constitutes investment advice.  Validation errors → 422, unknown ids →
404, conflicts → 409, unexpected failures → 500 with a sanitized message.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.signal_decay import service
from app.signal_decay import store as store_mod
from app.signal_decay.demo import seed_demo_signal_decay
from app.signal_decay.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/signal-decay", tags=["signal-decay"])

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
            summary="List signal-decay runs")
def list_runs(
    status: Optional[str] = None,
    signal_type: Optional[str] = None,
    outcome_target_type: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    overlap_status: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(store_mod.DEFAULT_PAGE_SIZE, ge=1,
                           le=store_mod.MAX_PAGE_SIZE),
) -> RunListResponse:
    filters = {"status": status, "signal_type": signal_type,
               "outcome_target_type": outcome_target_type,
               "integrity_status": integrity_status,
               "completeness_status": completeness_status,
               "overlap_status": overlap_status, "is_baseline": is_baseline,
               "query": query}
    return RunListResponse(**_guard(lambda: service.list_runs(
        filters=filters, sort_by=sort_by, sort_dir=sort_dir, page=page,
        page_size=page_size)))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a signal-decay run")
def create_run(payload: RunCreate) -> RunFull:
    return RunFull(**_guard(lambda: service.create_run(
        payload.model_dump(exclude_none=False))))


@router.get("/compare", response_model=RunComparison,
            summary="Neutral comparison of two runs")
def compare(a: int = Query(..., gt=0), b: int = Query(..., gt=0)
            ) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs and results as JSON")
def export(status: Optional[str] = None,
           signal_type: Optional[str] = None,
           integrity_status: Optional[str] = None,
           query: Optional[str] = None) -> Dict[str, Any]:
    filters = {"status": status, "signal_type": signal_type,
               "integrity_status": integrity_status, "query": query}
    return _guard(lambda: service.export(filters))


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Seed the deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_signal_decay))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute a signal-decay run")
def execute_run(run_id: int, payload: Optional[ExecuteRequest] = None
                ) -> RunFull:
    request = payload or ExecuteRequest()
    return RunFull(**_guard(lambda: service.execute_run(
        run_id, create_experiment=request.create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull,
             summary="Invalidate a run with an explicit reason")
def invalidate_run(run_id: int, payload: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id,
                                                           payload.reason)))


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull,
             summary="Mark an eligible run as the comparison baseline")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.get("/runs/{run_id}/horizons",
            summary="Per-horizon and per-lag diagnostics")
def get_horizons(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_horizons(run_id)}
    return _guard(_load)


@router.get("/runs/{run_id}/buckets", summary="Bucket outcome diagnostics")
def get_buckets(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_buckets(run_id)}
    return _guard(_load)


@router.get("/runs/{run_id}/turnover",
            summary="Reference turnover and membership timeline")
def get_turnover(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        run = service.get_run(run_id)
        return {"items": store_mod.list_turnover(run_id),
                "summary": run.get("turnover_summary"),
                "holding_overlap": run.get("holding_overlap")}
    return _guard(_load)


@router.get("/runs/{run_id}/observations",
            summary="Stored signal observations")
def get_observations(run_id: int,
                     limit: int = Query(2000, ge=1, le=20000)
                     ) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_observations(run_id, limit=limit)}
    return _guard(_load)


@router.get("/runs/{run_id}/regimes",
            summary="Diagnostics by STORED regime assignment")
def get_regimes(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_regimes(run_id),
                "rare_threshold": service.RARE_REGIME_MIN_OBSERVATIONS}
    return _guard(_load)


@router.get("/runs/{run_id}/bootstrap",
            summary="Seeded bootstrap quantiles")
def get_bootstrap(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_bootstrap(run_id)}
    return _guard(_load)


__all__ = ["router"]
