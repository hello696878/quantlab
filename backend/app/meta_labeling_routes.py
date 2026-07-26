"""
Meta-Labeling / Probability Calibration / Decision Threshold Lab API routes
(Phase 51.0).

Local-first research lab: meta-labels a primary signal under a documented
outcome rule, calibrates probabilities (Platt sigmoid / isotonic PAV —
dependency-light, no model files, no pickle), audits out-of-fold integrity via
Model Validation split memberships, and reports neutral threshold trade-offs.

Honest scope: meta-label 1 means the documented research condition was met —
not that a trade is profitable.  No best-model or best-threshold selection, no
position sizing, no execution, not certification, not investment advice.
Validation errors → 422, unknown ids → 404, conflicts → 409; execution is
deterministic and bounded (≤2000 observations, ≤101 thresholds, ≤30 bins).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.meta_labeling import service
from app.meta_labeling.calibration import CalibrationError
from app.meta_labeling.core import ObservationError
from app.meta_labeling.demo import seed_demo_meta_labeling
from app.meta_labeling.models import (
    DemoSeedResponse, ExecuteRequest, InvalidateRequest, LabSummary,
    PolicyCreate, RunComparison, RunCreate, RunFull, RunListResponse,
    ThresholdPolicy,
)
from app.meta_labeling.thresholds import ThresholdError

router = APIRouter(prefix="/meta-labeling", tags=["meta-labeling"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.MetaLabelError, ObservationError, CalibrationError,
            ThresholdError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse, summary="List meta-label runs")
def list_runs(
    status: Optional[str] = None,
    calibration_method: Optional[str] = None,
    oof_status: Optional[str] = None,
    validation_run_id: Optional[int] = None,
    dataset_version_id: Optional[int] = None,
    configuration_fingerprint: Optional[str] = None,
    query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    return RunListResponse(**service.list_runs(
        filters={"status": status, "calibration_method": calibration_method,
                 "oof_status": oof_status, "validation_run_id": validation_run_id,
                 "dataset_version_id": dataset_version_id,
                 "configuration_fingerprint": configuration_fingerprint,
                 "query": query},
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size))


@router.post("/runs", response_model=RunFull, status_code=201, summary="Create a meta-label run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["observations"] = [o.model_dump() for o in request.observations]
    record = _guard(lambda: service.create_run(payload))
    return RunFull(**record)


@router.get("/compare", response_model=RunComparison, summary="Compare two runs (neutral)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", summary="Export runs + bins + policies as JSON")
def export_runs(
    status: Optional[str] = None,
    calibration_method: Optional[str] = None,
    oof_status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    return service.export({"status": status, "calibration_method": calibration_method,
                           "oof_status": oof_status, "query": query})


@router.post("/demo-seed", response_model=DemoSeedResponse, summary="Load deterministic demo (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_meta_labeling))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull, summary="Execute (or re-execute) a run")
def execute_run(run_id: int, request: ExecuteRequest) -> RunFull:
    return RunFull(**_guard(
        lambda: service.execute_run(run_id, create_experiment=request.create_experiment)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull, summary="Invalidate a run")
def invalidate_run(run_id: int, request: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id, request.reason)))


@router.get("/runs/{run_id}/observations", summary="Paginated observations")
def observations(
    run_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    _guard(lambda: service.get_run(run_id))
    from app.meta_labeling import store
    return store.list_observations(run_id, page=page, page_size=page_size)


@router.get("/runs/{run_id}/calibration", summary="Reliability bins (raw + calibrated)")
def calibration_bins(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    from app.meta_labeling import store
    return {"bins": store.list_bins(run_id),
            "raw_metrics": run["raw_metrics"],
            "calibrated_metrics": run["calibrated_metrics"]}


@router.get("/runs/{run_id}/thresholds", summary="Threshold analysis table")
def thresholds(run_id: int) -> Dict[str, Any]:
    run = _guard(lambda: service.get_run(run_id))
    return run["threshold_analysis"]


@router.get("/runs/{run_id}/threshold-policies", response_model=List[ThresholdPolicy], summary="List policies")
def list_policies(run_id: int) -> List[ThresholdPolicy]:
    _guard(lambda: service.get_run(run_id))
    from app.meta_labeling import store
    return [ThresholdPolicy(**p) for p in store.list_policies(run_id)]


@router.post("/runs/{run_id}/threshold-policies", response_model=ThresholdPolicy, status_code=201,
             summary="Save a research threshold policy")
def create_policy(run_id: int, request: PolicyCreate) -> ThresholdPolicy:
    return ThresholdPolicy(**_guard(lambda: service.create_policy(run_id, request.model_dump())))


@router.post("/threshold-policies/{policy_id}/mark-baseline", response_model=ThresholdPolicy,
             summary="Mark a policy as the run's baseline")
def mark_baseline(policy_id: int) -> ThresholdPolicy:
    return ThresholdPolicy(**_guard(lambda: service.mark_policy_baseline(policy_id)))
