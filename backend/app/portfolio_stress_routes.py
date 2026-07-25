"""
Portfolio Stress Testing / Scenario Shock / Drawdown Attribution Lab API
routes (Phase 57.0).

Local-first research diagnostics: explicit deterministic scenarios applied
to STORED Phase 56 portfolio weights — direct shock attribution with
reconciliation, volatility/correlation stress with validated covariance
rebuilds, baseline-vs-stressed risk contributions, liquidity/cost stress
over linked Phase 55 models (copies with new fingerprints, never
mutations), trailing-only drawdown episodes and interval attribution, and
bounded one-at-a-time sensitivity probes.

Honest scope: scenarios are explicit assumptions, not predictions; no
scenario is a worst case; the lab never hedges, rebalances, trades, or
recommends an action, and results are never proof of safety or
robustness.  Validation errors → 422, unknown ids → 404, conflicts → 409,
unexpected execution failures → 500 with a sanitized message.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.portfolio_stress import service
from app.portfolio_stress import store as ps_store
from app.portfolio_stress.demo import seed_demo_portfolio_stress
from app.portfolio_stress.drawdown import DrawdownError
from app.portfolio_stress.fingerprints import FingerprintError
from app.portfolio_stress.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)
from app.portfolio_stress.scenario import ScenarioError

router = APIRouter(prefix="/portfolio-stress", tags=["portfolio-stress"])

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
    except (service.PortfolioStressError, ScenarioError, DrawdownError,
            FingerprintError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List portfolio-stress runs")
def list_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    scenario_type: Optional[str] = None,
    portfolio_run_id: Optional[int] = None,
    dataset_version_id: Optional[int] = None,
    regime_run_id: Optional[int] = None,
    cost_diagnostic_run_id: Optional[int] = None,
    configuration_fingerprint: Optional[str] = None,
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
                 "scenario_type": scenario_type,
                 "portfolio_run_id": portfolio_run_id,
                 "dataset_version_id": dataset_version_id,
                 "regime_run_id": regime_run_id,
                 "cost_diagnostic_run_id": cost_diagnostic_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a portfolio-stress run")
def create_run(request: RunCreate) -> RunFull:
    return RunFull(**_guard(lambda: service.create_run(request.model_dump())))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + stress diagnostics as JSON")
def export_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    scenario_type: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status,
                           "integrity_status": integrity_status,
                           "scenario_type": scenario_type, "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_portfolio_stress))


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


@router.get("/runs/{run_id}/scenario",
            summary="The stored scenario definition")
def scenario(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"scenario": ps_store.get_scenario(run_id)}


@router.get("/runs/{run_id}/asset-results",
            summary="Per-asset shocks, contributions and drifted weights")
def asset_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_asset_results(run_id)}


@router.get("/runs/{run_id}/risk-results",
            summary="Baseline vs stressed MCR/CCR/PCR per asset")
def risk_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_risk_results(run_id)}


@router.get("/runs/{run_id}/constraint-results",
            summary="Constraint checks on original and drifted books")
def constraint_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_constraint_results(run_id)}


@router.get("/runs/{run_id}/episodes",
            summary="Drawdown episodes (trailing-only peaks)")
def episodes(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_episodes(run_id)}


@router.get("/runs/{run_id}/attribution",
            summary="Per-asset attribution of the deepest episode")
def attribution(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_attribution(run_id)}


@router.get("/runs/{run_id}/sensitivity",
            summary="Bounded one-at-a-time sensitivity probes")
def sensitivity(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": ps_store.list_sensitivity_results(run_id)}
