"""
Portfolio Construction / Risk Budgeting / Constraint Diagnostics Lab API
routes (Phase 56.0).

Local-first research diagnostics: explicit covariance assumptions with
validation and never-silent repair, deterministic solvers with independent
post-solve constraint checks, reconciled risk contributions, concentration
and diversification descriptions, cost-aware turnover via linked Phase 55
cost models, and regime-conditioned summaries via stored Phase 54
assignments.

Honest scope: the lab never applies weights anywhere, never recommends an
allocation, never identifies an optimal or safest portfolio, and never
guarantees diversification, risk reduction, or performance.  Validation
errors → 422, unknown ids → 404, conflicts → 409; execution is
deterministic and bounded (≤20 assets, ≤2000 observations, ≤60
rebalances, ≤40 sensitivity scenarios).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.portfolio_diagnostics import service
from app.portfolio_diagnostics import store as pd_store
from app.portfolio_diagnostics.constraints import ConstraintError
from app.portfolio_diagnostics.core import PortfolioInputError
from app.portfolio_diagnostics.covariance import CovarianceError
from app.portfolio_diagnostics.demo import seed_demo_portfolio_diagnostics
from app.portfolio_diagnostics.methods import MethodError
from app.portfolio_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/portfolio-diagnostics",
                   tags=["portfolio-diagnostics"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.PortfolioDiagnosticsError, PortfolioInputError,
            CovarianceError, ConstraintError, MethodError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List portfolio-diagnostic runs")
def list_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    solver_status: Optional[str] = None,
    method: Optional[str] = None,
    covariance_method: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    validation_run_id: Optional[int] = None,
    regime_run_id: Optional[int] = None,
    cost_diagnostic_run_id: Optional[int] = None,
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
                 "solver_status": solver_status, "method": method,
                 "covariance_method": covariance_method,
                 "dataset_version_id": dataset_version_id,
                 "validation_run_id": validation_run_id,
                 "regime_run_id": regime_run_id,
                 "cost_diagnostic_run_id": cost_diagnostic_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "universe_fingerprint": universe_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a portfolio-diagnostic run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["assets"] = [a.model_dump() for a in request.assets]
    return RunFull(**_guard(lambda: service.create_run(payload)))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + diagnostics as JSON")
def export_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    method: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status,
                           "integrity_status": integrity_status,
                           "method": method, "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_portfolio_diagnostics))


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


@router.get("/runs/{run_id}/assets", summary="Universe assets")
def assets(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": pd_store.list_assets(run_id)}


@router.get("/runs/{run_id}/weights", summary="Final weight results")
def weights(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": pd_store.list_weight_results(run_id)}


@router.get("/runs/{run_id}/risk-contributions",
            summary="Marginal / component / percentage risk contributions")
def risk_contributions(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": pd_store.list_risk_contributions(run_id)}


@router.get("/runs/{run_id}/rebalances",
            summary="Rebalance records with turnover and linked cost estimates")
def rebalances(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": pd_store.list_rebalances(run_id)}


@router.get("/runs/{run_id}/sensitivity",
            summary="Bounded one-at-a-time sensitivity scenarios")
def sensitivity(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": pd_store.list_sensitivity_results(run_id)}


@router.get("/runs/{run_id}/regimes",
            summary="Portfolio characteristics by stored regime assignment")
def regimes(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"regimes": run.get("regimes")}
