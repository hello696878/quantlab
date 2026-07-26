"""
Portfolio Performance Attribution, Benchmark and Active Risk Lab API routes
(Phase 58.0).

Local-first research diagnostics: measured contributions of STORED Phase 56
portfolio weights, decomposed against an EXPLICIT benchmark definition
(never auto-selected) under a stated return convention and a
beginning-of-period weight-timing contract, with exact single-period
reconciliation, honest residuals, separated transaction costs, active-risk
diagnostics, regime views and stored drawdown-episode views.

Honest scope: nothing here proves alpha or manager skill, recommends a
benchmark or a portfolio, guarantees future performance, produces
GIPS-compliant reporting, performs tax accounting, executes trades, or
constitutes investment advice.  Validation errors → 422, unknown ids → 404,
conflicts → 409, unexpected execution failures → 500 with a sanitized
message.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.portfolio_attribution import service
from app.portfolio_attribution import store as store_mod
from app.portfolio_attribution.benchmarks import BenchmarkError
from app.portfolio_attribution.brinson import BrinsonError
from app.portfolio_attribution.contribution import ContributionError
from app.portfolio_attribution.demo import seed_demo_portfolio_attribution
from app.portfolio_attribution.fingerprints import FingerprintError
from app.portfolio_attribution.linking import LinkingError
from app.portfolio_attribution.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)
from app.portfolio_attribution.observations import ObservationError

router = APIRouter(prefix="/portfolio-attribution",
                   tags=["portfolio-attribution"])

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
    except (service.AttributionError, ObservationError, BenchmarkError,
            BrinsonError, ContributionError, LinkingError, FingerprintError,
            ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List portfolio-attribution runs")
def list_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    completeness_status: Optional[str] = None,
    reconciliation_status: Optional[str] = None,
    attribution_method: Optional[str] = None,
    linking_method: Optional[str] = None,
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
                 "reconciliation_status": reconciliation_status,
                 "attribution_method": attribution_method,
                 "linking_method": linking_method,
                 "portfolio_run_id": portfolio_run_id,
                 "dataset_version_id": dataset_version_id,
                 "regime_run_id": regime_run_id,
                 "cost_diagnostic_run_id": cost_diagnostic_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "is_baseline": (None if is_baseline is None
                                 else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a portfolio-attribution run")
def create_run(request: RunCreate) -> RunFull:
    return RunFull(**_guard(lambda: service.create_run(request.model_dump())))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1),
                 b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + attribution results as JSON")
def export_runs(
    status: Optional[str] = None,
    integrity_status: Optional[str] = None,
    attribution_method: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status,
                           "integrity_status": integrity_status,
                           "attribution_method": attribution_method,
                           "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_portfolio_attribution))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute (or re-execute) a run")
def execute_run(run_id: int, request: ExecuteRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.execute_run(
        run_id, create_experiment=request.create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull,
             summary="Invalidate a run")
def invalidate_run(run_id: int, request: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id,
                                                           request.reason)))


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull,
             summary="Mark a run as its scope's baseline (comparison reference)")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.get("/runs/{run_id}/benchmark", summary="The stored benchmark definition")
def benchmark(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"benchmark": store_mod.get_benchmark(run_id)}


@router.get("/runs/{run_id}/periods",
            summary="Per-period reconciliation and Brinson effects")
def periods(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_periods(run_id)}


@router.get("/runs/{run_id}/assets", summary="Per-asset contributions")
def assets(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_assets(run_id)}


@router.get("/runs/{run_id}/groups", summary="Per-group contributions")
def groups(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_groups(run_id)}


@router.get("/runs/{run_id}/brinson",
            summary="Allocation / selection / interaction effects by group")
def brinson(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_brinson(run_id)}


@router.get("/runs/{run_id}/active-risk",
            summary="Tracking error, information ratio and active drawdown")
def active_risk(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"active_risk": run.get("active_risk"),
            "active_drawdown": (run.get("summary") or {}).get("active_drawdown"),
            "concentration": run.get("concentration")}


@router.get("/runs/{run_id}/regimes",
            summary="Attribution by stored regime assignment")
def regimes(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_regimes(run_id),
            "note": (run.get("summary") or {}).get("regime_note")}


@router.get("/runs/{run_id}/drawdowns",
            summary="Attribution over stored Phase 57 drawdown episodes")
def drawdowns(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": store_mod.list_drawdowns(run_id)}
