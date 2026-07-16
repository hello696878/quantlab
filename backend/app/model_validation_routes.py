"""
Purged CV / Embargo / CPCV Model Validation Lab API routes (Phase 50.0).

Local-first validation lab: temporal-event samples, standard K-fold
(reference), walk-forward, purged K-fold, and CPCV splits with interval
purging, configurable embargo, a from-scratch leakage audit, neutral fold
metrics, deterministic fingerprints, and links to the Experiment Registry and
Dataset Lineage registries.

Honest scope: methodology and audit only — no profitability claims, no model
recommendations, no certification, no live data, and nothing here is
investment, trading, or risk advice.  Validation errors → 422, unknown ids →
404, state conflicts → 409; execution is bounded (≤2000 samples, ≤100 CPCV
combinations) and deterministic.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.model_validation import service
from app.model_validation.demo import seed_demo_validation
from app.model_validation.engine import SplitConfigError
from app.model_validation.events import EventError
from app.model_validation.models import (
    DemoSeedResponse,
    ExecuteRequest,
    ExportResponse,
    InvalidateRequest,
    LabSummary,
    RunComparison,
    RunCreate,
    RunFull,
    RunListResponse,
    SplitRecord,
)

router = APIRouter(prefix="/model-validation", tags=["model-validation"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.ValidationError, SplitConfigError, EventError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _filters(
    *,
    method: Optional[str],
    status: Optional[str],
    dataset_version_id: Optional[int],
    experiment_id: Optional[int],
    baseline: Optional[bool],
    leakage_clean: Optional[bool],
    query: Optional[str],
    created_from: Optional[str],
    created_to: Optional[str],
    configuration_fingerprint: Optional[str],
) -> Dict[str, Any]:
    return {
        "method": method,
        "status": status,
        "dataset_version_id": dataset_version_id,
        "experiment_id": experiment_id,
        "baseline": baseline,
        "leakage_clean": leakage_clean,
        "query": query,
        "created_from": created_from,
        "created_to": created_to,
        "configuration_fingerprint": configuration_fingerprint,
    }


@router.get("/summary", response_model=LabSummary, summary="Lab summary")
def get_summary() -> LabSummary:
    return LabSummary(**service.lab_summary())


@router.get("/runs", response_model=RunListResponse, summary="List validation runs")
def list_runs(
    method: Optional[str] = None,
    status: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    baseline: Optional[bool] = None,
    leakage_clean: Optional[bool] = None,
    query: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    configuration_fingerprint: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    result = service.list_runs(
        filters=_filters(
            method=method, status=status, dataset_version_id=dataset_version_id,
            experiment_id=experiment_id, baseline=baseline, leakage_clean=leakage_clean,
            query=query, created_from=created_from, created_to=created_to,
            configuration_fingerprint=configuration_fingerprint,
        ),
        sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size,
    )
    return RunListResponse(**result)


@router.post("/runs", response_model=RunFull, status_code=201, summary="Create a validation run")
def create_run(request: RunCreate) -> RunFull:
    payload = request.model_dump()
    payload["samples"] = [s.model_dump() for s in request.samples]
    record = _guard(lambda: service.create_run(payload))
    return RunFull(**service.get_run(record["id"]))


@router.get("/compare", response_model=RunComparison, summary="Compare two validation runs (neutral)")
def compare_runs(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> RunComparison:
    return RunComparison(**_guard(lambda: service.compare_runs(a, b)))


@router.get("/export", response_model=ExportResponse, summary="Export runs + splits as JSON")
def export_runs(
    method: Optional[str] = None,
    status: Optional[str] = None,
    dataset_version_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    baseline: Optional[bool] = None,
    leakage_clean: Optional[bool] = None,
    query: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    configuration_fingerprint: Optional[str] = None,
) -> ExportResponse:
    return ExportResponse(
        **service.export(
            _filters(
                method=method, status=status, dataset_version_id=dataset_version_id,
                experiment_id=experiment_id, baseline=baseline, leakage_clean=leakage_clean,
                query=query, created_from=created_from, created_to=created_to,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    )


@router.post("/demo-seed", response_model=DemoSeedResponse, summary="Load deterministic demo validation (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_validation))


@router.get("/runs/{run_id}", response_model=RunFull, summary="Get one run")
def get_run(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.get_run(run_id)))


@router.post("/runs/{run_id}/execute", response_model=RunFull, summary="Execute (or re-execute) a run")
def execute_run(run_id: int, request: ExecuteRequest) -> RunFull:
    return RunFull(
        **_guard(lambda: service.execute_run(run_id, create_experiment=request.create_experiment))
    )


@router.post("/runs/{run_id}/mark-baseline", response_model=RunFull, summary="Mark a leakage-clean run as baseline")
def mark_baseline(run_id: int) -> RunFull:
    return RunFull(**_guard(lambda: service.mark_baseline(run_id)))


@router.post("/runs/{run_id}/invalidate", response_model=RunFull, summary="Invalidate a run (record preserved)")
def invalidate_run(run_id: int, request: InvalidateRequest) -> RunFull:
    return RunFull(**_guard(lambda: service.invalidate_run(run_id, request.reason)))


@router.get("/runs/{run_id}/splits", response_model=List[SplitRecord], summary="List a run's splits")
def list_splits(run_id: int) -> List[SplitRecord]:
    return [SplitRecord(**s) for s in _guard(lambda: service.list_splits(run_id))]


@router.get("/runs/{run_id}/leakage-audit", summary="Leakage audit for a run")
def leakage_audit(run_id: int) -> Dict[str, Any]:
    return _guard(lambda: service.leakage_audit(run_id))


@router.get("/runs/{run_id}/samples", summary="Run samples (for the split timeline)")
def run_samples(run_id: int) -> List[Dict[str, Any]]:
    run = _guard(lambda: service.get_run(run_id))
    return run.get("samples", [])
