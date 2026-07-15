"""
Research Experiment Registry & Reproducibility Dashboard API routes (Phase 48.0).

A local-first, single-user registry of reproducibility metadata for QuantLab
research runs.  All persistence is the project's existing SQLite database; there
is no login, no cloud sync, no telemetry, and no external data of any kind.

Honest scope: fingerprints and the reproducibility assessment are integrity and
reproducibility *aids*, not a regulatory audit trail, tamper-proof security, or
proof of scientific reproducibility.  Nothing here is investment, trading, or
risk-management advice.  Validation errors return 422; unknown ids 404; disallowed
state transitions 409.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.experiment_registry import service
from app.experiment_registry.demo import seed_demo_registry
from app.experiment_registry.fingerprints import FingerprintError
from app.experiment_registry.models import (
    CompleteRequest,
    ComparisonResponse,
    DemoSeedResponse,
    ExperimentCreate,
    ExperimentFull,
    ExperimentListResponse,
    ExperimentUpdate,
    ExportResponse,
    FailRequest,
    RegistryDeleteResponse,
    RegistrySummaryResponse,
    ReproducibilityAssessment,
)

router = APIRouter(prefix="/experiment-registry", tags=["experiment-registry"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    """Run *fn*, mapping registry errors to clean HTTP status codes."""
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.RegistryError, FingerprintError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _filters(
    *,
    module: Optional[str],
    experiment_type: Optional[str],
    status: Optional[str],
    reproducibility_status: Optional[str],
    baseline: Optional[bool],
    tag: Optional[str],
    query: Optional[str],
    created_from: Optional[str],
    created_to: Optional[str],
    configuration_fingerprint: Optional[str],
    dataset_fingerprint: Optional[str],
) -> Dict[str, Any]:
    return {
        "module": module,
        "experiment_type": experiment_type,
        "status": status,
        "reproducibility_status": reproducibility_status,
        "baseline": baseline,
        "tag": tag,
        "query": query,
        "created_from": created_from,
        "created_to": created_to,
        "configuration_fingerprint": configuration_fingerprint,
        "dataset_fingerprint": dataset_fingerprint,
    }


# ---------------------------------------------------------------------------
# Summary + list + create
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=RegistrySummaryResponse, summary="Registry summary + filter facets")
def get_summary() -> RegistrySummaryResponse:
    return RegistrySummaryResponse(**service.registry_summary())


@router.get("/experiments", response_model=ExperimentListResponse, summary="List experiments (filtered, paginated)")
def list_experiments(
    module: Optional[str] = None,
    experiment_type: Optional[str] = None,
    status: Optional[str] = None,
    reproducibility_status: Optional[str] = None,
    baseline: Optional[bool] = None,
    tag: Optional[str] = None,
    query: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    configuration_fingerprint: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> ExperimentListResponse:
    filters = _filters(
        module=module,
        experiment_type=experiment_type,
        status=status,
        reproducibility_status=reproducibility_status,
        baseline=baseline,
        tag=tag,
        query=query,
        created_from=created_from,
        created_to=created_to,
        configuration_fingerprint=configuration_fingerprint,
        dataset_fingerprint=dataset_fingerprint,
    )
    result = service.list_experiments(
        filters=filters, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size
    )
    return ExperimentListResponse(**result)


@router.post("/experiments", response_model=ExperimentFull, status_code=201, summary="Record an experiment")
def create_experiment(request: ExperimentCreate) -> ExperimentFull:
    record = _guard(lambda: service.create_experiment(request.model_dump(), source="api"))
    return ExperimentFull(**record)


# ---------------------------------------------------------------------------
# Compare + export + demo (declared before /{id} paths for clarity)
# ---------------------------------------------------------------------------


@router.get("/compare", response_model=ComparisonResponse, summary="Compare exactly two experiments")
def compare_experiments(
    a: int = Query(..., ge=1), b: int = Query(..., ge=1)
) -> ComparisonResponse:
    result = _guard(lambda: service.compare(a, b))
    return ComparisonResponse(**result)


@router.get("/export", response_model=ExportResponse, summary="Export experiments as JSON")
def export_experiments(
    module: Optional[str] = None,
    experiment_type: Optional[str] = None,
    status: Optional[str] = None,
    reproducibility_status: Optional[str] = None,
    baseline: Optional[bool] = None,
    tag: Optional[str] = None,
    query: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    configuration_fingerprint: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
) -> ExportResponse:
    filters = _filters(
        module=module,
        experiment_type=experiment_type,
        status=status,
        reproducibility_status=reproducibility_status,
        baseline=baseline,
        tag=tag,
        query=query,
        created_from=created_from,
        created_to=created_to,
        configuration_fingerprint=configuration_fingerprint,
        dataset_fingerprint=dataset_fingerprint,
    )
    return ExportResponse(**service.export(filters))


@router.post("/demo-seed", response_model=DemoSeedResponse, summary="Load deterministic demo records (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**seed_demo_registry())


# ---------------------------------------------------------------------------
# Single-experiment read / update / lifecycle
# ---------------------------------------------------------------------------


@router.get("/experiments/{experiment_id}", response_model=ExperimentFull, summary="Get one experiment")
def get_experiment(experiment_id: int) -> ExperimentFull:
    record = _guard(lambda: service.get_experiment(experiment_id))
    return ExperimentFull(**record)


@router.patch("/experiments/{experiment_id}", response_model=ExperimentFull, summary="Update mutable fields")
def update_experiment(experiment_id: int, request: ExperimentUpdate) -> ExperimentFull:
    record = _guard(lambda: service.update_experiment(experiment_id, request.model_dump(exclude_unset=True)))
    return ExperimentFull(**record)


@router.delete("/experiments/{experiment_id}", response_model=RegistryDeleteResponse, summary="Delete one experiment")
def delete_experiment(experiment_id: int) -> RegistryDeleteResponse:
    _guard(lambda: service.delete_experiment(experiment_id))
    return RegistryDeleteResponse(deleted=True, id=experiment_id)


@router.post("/experiments/{experiment_id}/complete", response_model=ExperimentFull, summary="Complete a run")
def complete_experiment(experiment_id: int, request: CompleteRequest) -> ExperimentFull:
    record = _guard(lambda: service.complete_experiment(experiment_id, request.model_dump()))
    return ExperimentFull(**record)


@router.post("/experiments/{experiment_id}/fail", response_model=ExperimentFull, summary="Fail a run")
def fail_experiment(experiment_id: int, request: FailRequest) -> ExperimentFull:
    record = _guard(lambda: service.fail_experiment(experiment_id, request.model_dump()))
    return ExperimentFull(**record)


@router.post("/experiments/{experiment_id}/mark-baseline", response_model=ExperimentFull, summary="Mark as baseline")
def mark_baseline(experiment_id: int) -> ExperimentFull:
    record = _guard(lambda: service.mark_baseline(experiment_id))
    return ExperimentFull(**record)


@router.post("/experiments/{experiment_id}/invalidate", response_model=ExperimentFull, summary="Invalidate a run")
def invalidate_experiment(experiment_id: int) -> ExperimentFull:
    record = _guard(lambda: service.invalidate_experiment(experiment_id))
    return ExperimentFull(**record)


@router.get(
    "/experiments/{experiment_id}/reproducibility",
    response_model=ReproducibilityAssessment,
    summary="Assess reproducibility vs the reference run",
)
def reproducibility(experiment_id: int) -> ReproducibilityAssessment:
    result = _guard(lambda: service.assess_experiment(experiment_id))
    return ReproducibilityAssessment(**result)
