"""
Backtest Overfitting / PBO / Deflated Sharpe / Multiple Testing Diagnostics
Lab API routes (Phase 53.0).

Local-first research diagnostics for selection bias: CSCV/PBO with a fixed
documented rank convention, PSR/DSR with explicit trial-count assumptions,
Minimum Track Record Length, Bonferroni/Holm/Benjamini–Hochberg corrections
with p-value provenance, and bounded candidate-dependence diagnostics.

Honest scope: every value is a research statistic under stated assumptions —
never proof of profitability, robustness, or safety; no candidate is ever
selected, recommended, or allocated capital.  Validation errors → 422,
unknown ids → 404, conflicts → 409; execution is deterministic and bounded
(≤24 candidates, ≤2000 observations, ≤12 blocks, ≤924 CSCV combinations).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.overfitting_diagnostics import service
from app.overfitting_diagnostics import store as od_store
from app.overfitting_diagnostics.core import CandidateInputError
from app.overfitting_diagnostics.cscv import CSCVError
from app.overfitting_diagnostics.demo import seed_demo_overfitting
from app.overfitting_diagnostics.dependence import DependenceError
from app.overfitting_diagnostics.metrics import MetricError
from app.overfitting_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)
from app.overfitting_diagnostics.multiple_testing import MultipleTestingError
from app.overfitting_diagnostics.sharpe import SharpeError

router = APIRouter(prefix="/overfitting-diagnostics", tags=["overfitting-diagnostics"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.OverfittingError, CandidateInputError, CSCVError,
            SharpeError, MultipleTestingError, DependenceError, MetricError,
            ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse,
            summary="List overfitting-diagnostic runs")
def list_runs(
    status: Optional[str] = None,
    metric: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    validation_run_id: Optional[int] = None,
    configuration_fingerprint: Optional[str] = None,
    universe_fingerprint: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    min_pbo: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    max_pbo: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    return RunListResponse(**service.list_runs(
        filters={"status": status, "metric": metric,
                 "dataset_version_id": dataset_version_id,
                 "validation_run_id": validation_run_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "universe_fingerprint": universe_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "min_pbo": min_pbo, "max_pbo": max_pbo, "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a diagnostic run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["candidates"] = [c.model_dump() for c in request.candidates]
    return RunFull(**_guard(lambda: service.create_run(payload)))


@router.get("/compare", response_model=RunComparison,
            summary="Compare two runs (neutral, with comparability warnings)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + diagnostics as JSON")
def export_runs(
    status: Optional[str] = None,
    metric: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status, "metric": metric, "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_overfitting))


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


@router.get("/runs/{run_id}/candidates", summary="Candidate universe + statistics")
def candidates(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": od_store.list_candidates(run_id)}


@router.get("/runs/{run_id}/pbo-splits", summary="Paginated CSCV split results")
def pbo_splits(
    run_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return od_store.list_splits(run_id, page=page, page_size=page_size)


@router.get("/runs/{run_id}/sharpe-diagnostics", summary="PSR / DSR / MinTRL block")
def sharpe_diagnostics(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return run["sharpe_diagnostics"]


@router.get("/runs/{run_id}/multiple-testing", summary="Multiple-testing rows")
def multiple_testing(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"alpha": (run["configuration"] or {}).get("alpha"),
            "items": od_store.list_multiple_testing(run_id)}


@router.get("/runs/{run_id}/dependence", summary="Candidate dependence diagnostics")
def dependence(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return run["dependence"]
