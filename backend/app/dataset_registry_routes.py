"""
Data Provenance & Dataset Lineage API routes (Phase 49.0).

Local-first dataset registry: identity, immutable versions, transformation
lineage, metadata-driven quality results, version comparison, and links to the
Experiment Registry.  All persistence is the project's existing SQLite
database; no login, no cloud, no telemetry, no live data, no provider calls.

Honest scope: provenance records are declared metadata plus deterministic
fingerprints over that metadata — integrity aids only, not a regulatory audit
trail, not tamper-proof, not proof of correctness, and not investment advice.
Storage locators are logical URIs; absolute local paths are rejected and never
returned.  Validation errors → 422, unknown ids → 404, conflicts → 409.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastapi import APIRouter, HTTPException, Query

from app.dataset_registry import service
from app.dataset_registry.demo import seed_demo_lineage
from app.dataset_registry.fingerprints import FingerprintError
from app.dataset_registry.lineage import DEFAULT_MAX_DEPTH, DEFAULT_NODE_LIMIT
from app.dataset_registry.locators import LocatorError
from app.dataset_registry.models import (
    DatasetCreate,
    DatasetFull,
    DatasetListResponse,
    DatasetUpdate,
    DemoSeedResponse,
    ExperimentLink,
    ExperimentLinkCreate,
    ExportResponse,
    InvalidateRequest,
    LineageCreate,
    LineageEdge,
    LineageGraph,
    QualityResult,
    QualityRunRequest,
    RegistrySummary,
    VersionComparison,
    VersionCreate,
    VersionFull,
    VersionSummary,
)

router = APIRouter(prefix="", tags=["dataset-registry"])

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (service.DatasetError, FingerprintError, LocatorError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _filters(
    *,
    source_type: Optional[str],
    domain: Optional[str],
    asset_class: Optional[str],
    format: Optional[str],
    frequency: Optional[str],
    demo: Optional[bool],
    active: Optional[bool],
    provenance_status: Optional[str],
    quality_status: Optional[str],
    tag: Optional[str],
    query: Optional[str],
) -> Dict[str, Any]:
    return {
        "source_type": source_type,
        "domain": domain,
        "asset_class": asset_class,
        "format": format,
        "frequency": frequency,
        "demo": demo,
        "active": active,
        "provenance_status": provenance_status,
        "quality_status": quality_status,
        "tag": tag,
        "query": query,
    }


# ---------------------------------------------------------------------------
# Summary / datasets
# ---------------------------------------------------------------------------


@router.get("/datasets/summary", response_model=RegistrySummary, summary="Registry summary + facets")
def get_summary() -> RegistrySummary:
    return RegistrySummary(**service.registry_summary())


@router.get("/datasets", response_model=DatasetListResponse, summary="List datasets (filtered, paginated)")
def list_datasets(
    source_type: Optional[str] = None,
    domain: Optional[str] = None,
    asset_class: Optional[str] = None,
    format: Optional[str] = None,
    frequency: Optional[str] = None,
    demo: Optional[bool] = None,
    active: Optional[bool] = None,
    provenance_status: Optional[str] = None,
    quality_status: Optional[str] = None,
    tag: Optional[str] = None,
    query: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> DatasetListResponse:
    filters = _filters(
        source_type=source_type,
        domain=domain,
        asset_class=asset_class,
        format=format,
        frequency=frequency,
        demo=demo,
        active=active,
        provenance_status=provenance_status,
        quality_status=quality_status,
        tag=tag,
        query=query,
    )
    result = service.list_datasets(
        filters=filters, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size
    )
    return DatasetListResponse(**result)


@router.post("/datasets", response_model=DatasetFull, status_code=201, summary="Register a dataset")
def create_dataset(request: DatasetCreate) -> DatasetFull:
    record = _guard(lambda: service.create_dataset(request.model_dump()))
    return DatasetFull(**service.get_dataset(record["id"]))


@router.get("/datasets/export", response_model=ExportResponse, summary="Export the registry as JSON")
def export_datasets(
    source_type: Optional[str] = None,
    domain: Optional[str] = None,
    asset_class: Optional[str] = None,
    format: Optional[str] = None,
    frequency: Optional[str] = None,
    demo: Optional[bool] = None,
    active: Optional[bool] = None,
    provenance_status: Optional[str] = None,
    quality_status: Optional[str] = None,
    tag: Optional[str] = None,
    query: Optional[str] = None,
) -> ExportResponse:
    filters = _filters(
        source_type=source_type,
        domain=domain,
        asset_class=asset_class,
        format=format,
        frequency=frequency,
        demo=demo,
        active=active,
        provenance_status=provenance_status,
        quality_status=quality_status,
        tag=tag,
        query=query,
    )
    return ExportResponse(**service.export(filters))


@router.post("/datasets/demo-seed", response_model=DemoSeedResponse, summary="Load deterministic demo lineage (idempotent)")
def demo_seed() -> DemoSeedResponse:
    return DemoSeedResponse(**_guard(seed_demo_lineage))


@router.get("/datasets/{dataset_id}", response_model=DatasetFull, summary="Get one dataset")
def get_dataset(dataset_id: int) -> DatasetFull:
    return DatasetFull(**_guard(lambda: service.get_dataset(dataset_id)))


@router.patch("/datasets/{dataset_id}", response_model=DatasetFull, summary="Update mutable dataset metadata")
def update_dataset(dataset_id: int, request: DatasetUpdate) -> DatasetFull:
    record = _guard(
        lambda: service.update_dataset(dataset_id, request.model_dump(exclude_unset=True))
    )
    return DatasetFull(**record)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/versions", response_model=List[VersionSummary], summary="List a dataset's versions")
def list_versions(dataset_id: int) -> List[VersionSummary]:
    return [VersionSummary(**v) for v in _guard(lambda: service.list_versions(dataset_id))]


@router.post("/datasets/{dataset_id}/versions", response_model=VersionFull, status_code=201, summary="Register an immutable version")
def create_version(dataset_id: int, request: VersionCreate) -> VersionFull:
    payload = request.model_dump()
    payload["schema_snapshot"] = request.schema_snapshot.model_dump()
    record = _guard(lambda: service.create_version(dataset_id, payload))
    return VersionFull(**service.get_version(record["id"]))


@router.get("/dataset-versions/compare", response_model=VersionComparison, summary="Compare two versions (neutral)")
def compare_versions(a: int = Query(..., ge=1), b: int = Query(..., ge=1)) -> VersionComparison:
    return VersionComparison(**_guard(lambda: service.compare_versions(a, b)))


@router.get("/dataset-versions/{version_id}", response_model=VersionFull, summary="Get one version")
def get_version(version_id: int) -> VersionFull:
    return VersionFull(**_guard(lambda: service.get_version(version_id)))


@router.post("/dataset-versions/{version_id}/invalidate", response_model=VersionFull, summary="Invalidate a version (record preserved)")
def invalidate_version(version_id: int, request: InvalidateRequest) -> VersionFull:
    return VersionFull(**_guard(lambda: service.invalidate_version(version_id, request.reason)))


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


@router.get("/dataset-versions/{version_id}/lineage", response_model=LineageGraph, summary="Bounded lineage neighborhood")
def get_lineage(
    version_id: int,
    max_depth: int = Query(default=DEFAULT_MAX_DEPTH, ge=1, le=12),
    node_limit: int = Query(default=DEFAULT_NODE_LIMIT, ge=1, le=200),
) -> LineageGraph:
    return LineageGraph(
        **_guard(lambda: service.lineage_graph(version_id, max_depth=max_depth, node_limit=node_limit))
    )


@router.post("/dataset-lineage", response_model=LineageEdge, status_code=201, summary="Add a lineage edge (idempotent on identical edges)")
def add_lineage(request: LineageCreate) -> LineageEdge:
    return LineageEdge(**_guard(lambda: service.add_lineage(request.model_dump())))


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------


@router.get("/dataset-versions/{version_id}/quality", response_model=List[QualityResult], summary="List quality results")
def list_quality(version_id: int) -> List[QualityResult]:
    return [QualityResult(**r) for r in _guard(lambda: service.list_quality(version_id))]


@router.post("/dataset-versions/{version_id}/quality-checks", response_model=List[QualityResult], summary="Run metadata quality checks")
def run_quality(version_id: int, request: QualityRunRequest) -> List[QualityResult]:
    return [
        QualityResult(**r)
        for r in _guard(lambda: service.run_quality_checks(version_id, request.model_dump()))
    ]


# ---------------------------------------------------------------------------
# Experiment links
# ---------------------------------------------------------------------------


@router.post("/dataset-links", response_model=ExperimentLink, status_code=201, summary="Link a version to an experiment")
def create_link(request: ExperimentLinkCreate) -> ExperimentLink:
    return ExperimentLink(**_guard(lambda: service.create_link(request.model_dump())))


@router.get("/dataset-versions/{version_id}/experiments", response_model=List[ExperimentLink], summary="Experiments linked to a version")
def version_links(version_id: int) -> List[ExperimentLink]:
    return [ExperimentLink(**l) for l in _guard(lambda: service.links_for_version(version_id))]


@router.get("/experiment-registry/experiments/{experiment_id}/datasets", response_model=List[ExperimentLink], summary="Dataset versions linked to an experiment")
def experiment_links(experiment_id: int) -> List[ExperimentLink]:
    return [ExperimentLink(**l) for l in _guard(lambda: service.links_for_experiment(experiment_id))]
