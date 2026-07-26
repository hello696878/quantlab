"""
Transaction Cost / Slippage / Market Impact / Capacity Diagnostics Lab API
routes (Phase 55.0).

Local-first research diagnostics that apply explicitly configured
execution-cost assumptions to supplied historical observations: unit-safe
cost normalization, commission / spread / slippage / square-root-impact
components, no-look-ahead liquidity inputs, gross-to-net reconciliation,
break-even diagnostics, a bounded sensitivity grid and capacity scaling
with participation warnings.

Honest scope: the lab is not an order execution system or broker simulator;
it does not predict real fills, guarantee market capacity, recommend trade
sizes or brokers, prove profitability, or provide investment or execution
advice.  Missing cost inputs stay unavailable — never zero.  Validation
errors → 422, unknown ids → 404, conflicts → 409; execution is
deterministic and bounded (≤16 candidates, ≤2000 observations, ≤60
sensitivity scenarios, ≤8 capacity scales).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.cost_diagnostics import service
from app.cost_diagnostics import store as cd_store
from app.cost_diagnostics.core import CostInputError
from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
from app.cost_diagnostics.liquidity import LiquidityInputError
from app.cost_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/cost-diagnostics", tags=["cost-diagnostics"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.CostDiagnosticsError, CostInputError, LiquidityInputError,
            ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List cost-diagnostic runs")
def list_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    observation_type: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    validation_run_id: Optional[int] = None,
    overfitting_run_id: Optional[int] = None,
    regime_run_id: Optional[int] = None,
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
                 "completeness_status": completeness_status,
                 "observation_type": observation_type,
                 "dataset_version_id": dataset_version_id,
                 "validation_run_id": validation_run_id,
                 "overfitting_run_id": overfitting_run_id,
                 "regime_run_id": regime_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "universe_fingerprint": universe_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a cost-diagnostic run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["observations"] = [o.model_dump(exclude_none=True)
                               for o in request.observations]
    return RunFull(**_guard(lambda: service.create_run(payload)))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + diagnostics as JSON")
def export_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status,
                           "integrity_status": integrity_status,
                           "completeness_status": completeness_status,
                           "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_cost_diagnostics))


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


@router.get("/runs/{run_id}/observations",
            summary="Per-observation gross-to-net reconciliation rows")
def observation_results(
    run_id: int,
    candidate_id: Optional[str] = None,
    completeness: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return cd_store.list_observation_results(
        run_id, candidate_id=candidate_id, completeness=completeness,
        page=page, page_size=page_size)


@router.get("/runs/{run_id}/sensitivity",
            summary="Bounded cost-sensitivity scenario grid")
def sensitivity_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": cd_store.list_sensitivity_results(run_id)}


@router.get("/runs/{run_id}/capacity",
            summary="Capacity scaling diagnostics (estimates under "
                    "configured assumptions)")
def capacity_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": cd_store.list_capacity_results(run_id)}


@router.get("/runs/{run_id}/regimes",
            summary="Costs conditioned on stored regime assignments")
def regime_results(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"regimes": run.get("regimes")}
