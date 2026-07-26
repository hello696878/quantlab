"""
Factor Exposure, Return Decomposition and Macro Sensitivity Diagnostics Lab
API routes (Phase 59.0).

Local-first research diagnostics: measured sensitivities of ONE explicitly
declared return series to SUPPLIED factor and macro observations under a
stated timing rule, with strict timestamp alignment, honest rank and
availability states, exact contribution reconciliation, trailing rolling
estimates, stored-regime and stored-stress views, and held-out evaluation
that never refits on held-out data.

Honest scope: nothing here proves causality, proves alpha, proves manager
skill, predicts future returns, recommends a factor exposure, a macro trade
or a portfolio, executes trades, certifies a factor model, or constitutes
investment advice.  No market or macroeconomic data is ever fetched.
Validation errors → 422, unknown ids → 404, conflicts → 409, unexpected
execution failures → 500 with a sanitized message.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.factor_diagnostics import service
from app.factor_diagnostics import store as store_mod
from app.factor_diagnostics.decomposition import DecompositionError
from app.factor_diagnostics.definitions import DefinitionError
from app.factor_diagnostics.demo import seed_demo_factor_diagnostics
from app.factor_diagnostics.fingerprints import FingerprintError
from app.factor_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)
from app.factor_diagnostics.observations import ObservationError
from app.factor_diagnostics.regression import RegressionError
from app.factor_diagnostics.rolling import RollingError
from app.factor_diagnostics.sensitivity import SensitivityError
from app.factor_diagnostics.targets import TargetError

router = APIRouter(prefix="/factor-diagnostics", tags=["factor-diagnostics"])

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
    except (service.FactorError, DefinitionError, ObservationError,
            TargetError, RegressionError, DecompositionError, RollingError,
            SensitivityError, FingerprintError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List factor-diagnostic runs")
def list_runs(
    status: Optional[str] = None,
    analysis_mode: Optional[str] = None,
    regression_method: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    rank_status: Optional[str] = None,
    timing_policy: Optional[str] = None,
    target_type: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(store_mod.DEFAULT_PAGE_SIZE, ge=1,
                           le=store_mod.MAX_PAGE_SIZE),
) -> RunListResponse:
    filters = {"status": status, "analysis_mode": analysis_mode,
               "regression_method": regression_method,
               "integrity_status": integrity_status,
               "completeness_status": completeness_status,
               "rank_status": rank_status, "timing_policy": timing_policy,
               "target_type": target_type, "is_baseline": is_baseline,
               "query": query}
    return RunListResponse(**_guard(lambda: service.list_runs(
        filters=filters, sort_by=sort_by, sort_dir=sort_dir, page=page,
        page_size=page_size)))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a factor-diagnostic run")
def create_run(payload: RunCreate) -> RunFull:
    return RunFull(**_guard(lambda: service.create_run(
        payload.model_dump(exclude_none=False))))


@router.get("/compare", response_model=RunComparison,
            summary="Neutral comparison of two runs")
def compare(a: int = Query(..., gt=0), b: int = Query(..., gt=0)
            ) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs and factor results as JSON")
def export(status: Optional[str] = None,
           analysis_mode: Optional[str] = None,
           integrity_status: Optional[str] = None,
           query: Optional[str] = None) -> Dict[str, Any]:
    filters = {"status": status, "analysis_mode": analysis_mode,
               "integrity_status": integrity_status, "query": query}
    return _guard(lambda: service.export(filters))


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Seed the deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_factor_diagnostics))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute a factor-diagnostic run")
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


@router.get("/runs/{run_id}/coefficients",
            summary="Estimated or supplied factor exposures")
def get_coefficients(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_coefficients(run_id)}
    return _guard(_load)


@router.get("/runs/{run_id}/periods",
            summary="Per-period return decomposition and reconciliation")
def get_periods(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_periods(run_id)}
    return _guard(_load)


@router.get("/runs/{run_id}/observations",
            summary="Aligned factor observations with availability stamps")
def get_observations(run_id: int, factor_id: Optional[str] = None,
                     limit: int = Query(2000, ge=1, le=24000)
                     ) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_observations(run_id,
                                                     factor_id=factor_id,
                                                     limit=limit)}
    return _guard(_load)


@router.get("/runs/{run_id}/rolling",
            summary="Trailing rolling exposure estimates")
def get_rolling(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        run = service.get_run(run_id)
        return {"items": store_mod.list_rolling(run_id),
                "summary": run.get("rolling_summary")}
    return _guard(_load)


@router.get("/runs/{run_id}/stability",
            summary="Exposure stability across rolling windows")
def get_stability(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        run = service.get_run(run_id)
        return {"items": run.get("stability") or [],
                "summary": run.get("rolling_summary")}
    return _guard(_load)


@router.get("/runs/{run_id}/regimes",
            summary="Exposures by STORED regime assignment")
def get_regimes(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_regimes(run_id),
                "rare_threshold": service.RARE_REGIME_MIN_OBSERVATIONS}
    return _guard(_load)


@router.get("/runs/{run_id}/sensitivity",
            summary="Bounded deterministic sensitivity scenarios")
def get_sensitivity(run_id: int) -> Dict[str, Any]:
    def _load() -> Dict[str, Any]:
        service.get_run(run_id)
        return {"items": store_mod.list_sensitivity(run_id),
                "note": ("no scenario is labelled best, optimal or "
                         "recommended, and no hyper-parameter is selected "
                         "automatically")}
    return _guard(_load)


__all__ = ["router"]
