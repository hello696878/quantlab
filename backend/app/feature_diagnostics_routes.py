"""
Feature Importance / Stability / Drift Diagnostics Lab API routes (Phase 52.0).

Local-first research lab: held-out permutation importance (deterministic
seeds, bounded repeats) as the primary method, model-native impurity and
coefficient magnitudes as clearly-caveated training-data references, rank
stability across Model Validation splits, bounded correlated-feature groups,
and feature distribution / importance drift diagnostics.

Honest scope: importance is a measured sensitivity under one method and one
metric — never causality, profitability, feature selection, model selection,
or a recommendation.  Validation errors → 422, unknown ids → 404, conflicts
→ 409; execution is deterministic and bounded (≤2000 samples, ≤32 features,
≤20 permutation repeats).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.feature_diagnostics import service
from app.feature_diagnostics import store as fd_store
from app.feature_diagnostics.core import FeatureInputError
from app.feature_diagnostics.correlation import CorrelationError
from app.feature_diagnostics.demo import seed_demo_feature_diagnostics
from app.feature_diagnostics.drift import DriftError
from app.feature_diagnostics.estimators import EstimatorError
from app.feature_diagnostics.metrics import MetricUnavailable
from app.feature_diagnostics.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    RunComparison, RunCreate, RunFull, RunListResponse,
)

router = APIRouter(prefix="/feature-diagnostics", tags=["feature-diagnostics"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.FeatureDiagnosticsError, FeatureInputError, EstimatorError,
            MetricUnavailable, CorrelationError, DriftError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse, summary="List feature-diagnostics runs")
def list_runs(
    status: Optional[str] = None,
    method: Optional[str] = None,
    metric: Optional[str] = None,
    integrity_status: Optional[str] = None,
    validation_run_id: Optional[int] = None,
    dataset_version_id: Optional[int] = None,
    configuration_fingerprint: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    return RunListResponse(**service.list_runs(
        filters={"status": status, "method": method, "metric": metric,
                 "integrity_status": integrity_status,
                 "validation_run_id": validation_run_id,
                 "dataset_version_id": dataset_version_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "is_baseline": (None if is_baseline is None else int(is_baseline)),
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201,
             summary="Create a feature-diagnostics run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    return RunFull(**_guard(lambda: service.create_run(payload)))


@router.get("/compare", response_model=RunComparison, summary="Compare two runs (neutral)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + diagnostics as JSON (no raw samples)")
def export_runs(
    status: Optional[str] = None,
    method: Optional[str] = None,
    metric: Optional[str] = None,
    integrity_status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status, "method": method, "metric": metric,
                           "integrity_status": integrity_status, "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse,
             summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_feature_diagnostics))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull,
             summary="Execute (or re-execute) a run")
def execute_run(run_id: int, request: ExecuteRequest) -> RunFull:
    return RunFull(**_guard(
        lambda: service.execute_run(run_id, create_experiment=request.create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull, summary="Invalidate a run")
def invalidate_run(run_id: int, request: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id, request.reason)))


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull,
             summary="Mark a run as its scope's baseline (comparison reference only)")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.get("/runs/{run_id}/features", summary="Aggregate per-feature results")
def feature_results(run_id: int) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    return {"items": fd_store.list_results(run_id)}


@router.get("/runs/{run_id}/splits", summary="Split-level importance results")
def split_results(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"splits": run["splits"], "items": fd_store.list_split_results(run_id)}


@router.get("/runs/{run_id}/correlations", summary="Correlated-feature groups")
def correlations(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"configuration": (run["configuration"] or {}).get("correlation"),
            "groups": fd_store.list_correlation_groups(run_id)}


@router.get("/runs/{run_id}/drift", summary="Distribution + importance drift rows")
def drift(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return {"context": run["drift_context"],
            "importance_drift": run["importance_drift"],
            "items": fd_store.list_drift_results(run_id)}
