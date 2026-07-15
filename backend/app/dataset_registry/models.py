"""
Pydantic v2 request/response models for the Dataset Lineage registry.

Strict at the API boundary: bounded strings/tags, bounded JSON depth/size,
finite numbers only, SHA-256 validation, storage-locator policy enforcement,
credential-free URLs, and forbidden extra fields.  Rules that need database
state (immutability, cycles, link targets) live in :mod:`.service`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataset_registry.locators import LocatorError, validate_locator
from app.experiment_registry.fingerprints import is_valid_sha256
from app.experiment_registry.models import (
    _validate_iso_timestamp,
    _validate_structured,
    _validate_tags,
)

# --- vocabularies -----------------------------------------------------------

SOURCE_TYPES = (
    "deterministic_fixture",
    "local_file",
    "generated",
    "derived",
    "optional_provider",
    "manual",
    "unknown",
)
PROVENANCE_STATUSES = ("complete", "partial", "unknown", "invalidated")
QUALITY_STATUSES = ("passed", "warning", "failed", "skipped", "unknown")
SEVERITIES = ("info", "low", "medium", "high", "critical")
RELATIONSHIP_TYPES = (
    "derived_from",
    "filtered_from",
    "aggregated_from",
    "joined_with",
    "normalized_from",
    "resampled_from",
    "feature_generated_from",
    "labeled_from",
    "copied_from",
)
LINK_ROLES = ("input", "benchmark", "labels", "features", "reference", "output")
DRIFT_CLASSES = ("none", "compatible", "potentially_breaking", "breaking", "unknown")

MAX_NAME = 200
MAX_TEXT = 2000
MAX_SHORT = 100
MAX_TAGS = 25

_URL_CRED = re.compile(r"//[^/]*@")


def _validate_public_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if len(v) > 500:
        raise ValueError("URL exceeds 500 characters")
    if not (v.startswith("https://") or v.startswith("http://")):
        raise ValueError("URL must start with http(s)://")
    if _URL_CRED.search(v):
        raise ValueError("URL must not embed credentials")
    return v


def _validate_sha(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if not is_valid_sha256(v):
        raise ValueError("fingerprint must be a 64-char SHA-256 hex string")
    return v.lower()


def _validate_locator_field(value: str) -> str:
    try:
        validate_locator(value)
    except LocatorError as exc:
        raise ValueError(str(exc))
    return value.strip()


class SchemaField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_SHORT)
    type: str = Field(default="unknown", max_length=MAX_SHORT)
    nullable: bool = True


class SchemaSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: List[SchemaField] = Field(default_factory=list, max_length=200)
    ordering_significant: bool = False


# ---------------------------------------------------------------------------
# Dataset requests
# ---------------------------------------------------------------------------


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)
    description: str = Field(default="", max_length=MAX_TEXT)
    domain: str = Field(min_length=1, max_length=MAX_SHORT)
    dataset_type: str = Field(min_length=1, max_length=MAX_SHORT)
    source_type: str = Field(default="unknown")
    provider: Optional[str] = Field(default=None, max_length=MAX_SHORT)
    source_reference: Optional[str] = Field(default=None, max_length=300)
    license_name: Optional[str] = Field(default=None, max_length=MAX_SHORT)
    license_url: Optional[str] = None
    symbol_scope: Optional[str] = Field(default=None, max_length=200)
    asset_class: Optional[str] = Field(default=None, max_length=MAX_SHORT)
    frequency: Optional[str] = Field(default=None, max_length=50)
    timezone: Optional[str] = Field(default=None, max_length=64)
    format: str = Field(default="csv", max_length=50)
    schema_version: Optional[str] = Field(default=None, max_length=50)
    tags: List[str] = Field(default_factory=list, max_length=MAX_TAGS)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=MAX_TEXT)
    is_demo: bool = False

    @field_validator("name", "domain", "dataset_type")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("field must not be blank")
        return s

    @field_validator("source_type")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {SOURCE_TYPES}")
        return v

    @field_validator("license_url")
    @classmethod
    def _valid_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_public_url(v)

    @field_validator("source_reference")
    @classmethod
    def _sanitize_source_ref(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        # Reject anything that looks like an absolute local path or credential.
        if re.match(r"^[A-Za-z]:[\\/]", s) or s.startswith(("/", "\\\\")):
            raise ValueError("source_reference must not be an absolute path")
        if _URL_CRED.search(s):
            raise ValueError("source_reference must not embed credentials")
        return s

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: List[str]) -> List[str]:
        return _validate_tags(v)

    @field_validator("metadata")
    @classmethod
    def _meta(cls, v: Any) -> Any:
        return _validate_structured(v)


class DatasetUpdate(BaseModel):
    """PATCH — mutable descriptive metadata only (identity fields fixed)."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    notes: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    tags: Optional[List[str]] = Field(default=None, max_length=MAX_TAGS)
    license_name: Optional[str] = Field(default=None, max_length=MAX_SHORT)
    license_url: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("license_url")
    @classmethod
    def _valid_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_public_url(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        return None if v is None else _validate_tags(v)


# ---------------------------------------------------------------------------
# Version requests
# ---------------------------------------------------------------------------


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_label: str = Field(min_length=1, max_length=MAX_SHORT)
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    row_count: Optional[int] = Field(default=None, ge=0)
    column_count: Optional[int] = Field(default=None, ge=0)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    content_fingerprint: Optional[str] = None
    source_fingerprint: Optional[str] = None
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    format: str = Field(default="csv", max_length=50)
    compression: Optional[str] = Field(default=None, max_length=50)
    storage_locator: str = Field(min_length=1)
    ingestion_method: str = Field(default="manual", max_length=MAX_SHORT)
    deterministic: bool = False
    schema_snapshot: SchemaSnapshot = Field(default_factory=SchemaSnapshot)
    statistics_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("version_label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("version_label must not be blank")
        return s

    @field_validator("content_fingerprint", "source_fingerprint")
    @classmethod
    def _sha(cls, v: Optional[str]) -> Optional[str]:
        return _validate_sha(v)

    @field_validator("storage_locator")
    @classmethod
    def _locator(cls, v: str) -> str:
        return _validate_locator_field(v)

    @field_validator("effective_from", "effective_to", "start_time", "end_time")
    @classmethod
    def _ts(cls, v: Optional[str]) -> Optional[str]:
        return _validate_iso_timestamp(v)

    @field_validator("statistics_summary", "provenance")
    @classmethod
    def _meta(cls, v: Any) -> Any:
        return _validate_structured(v)

    @model_validator(mode="after")
    def _range_order(self) -> "VersionCreate":
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("start_time must not be after end_time")
        return self


class InvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=MAX_TEXT)

    @field_validator("reason")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("reason must not be blank")
        return s


# ---------------------------------------------------------------------------
# Lineage / quality / link requests
# ---------------------------------------------------------------------------


class LineageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_version_id: int = Field(ge=1)
    child_version_id: int = Field(ge=1)
    relationship_type: str
    transformation_name: str = Field(min_length=1, max_length=MAX_NAME)
    transformation_version: Optional[str] = Field(default=None, max_length=50)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    code_reference: Optional[str] = Field(default=None, max_length=300)
    notes: str = Field(default="", max_length=MAX_TEXT)

    @field_validator("relationship_type")
    @classmethod
    def _rel(cls, v: str) -> str:
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type must be one of {RELATIONSHIP_TYPES}")
        return v

    @field_validator("parameters")
    @classmethod
    def _params(cls, v: Any) -> Any:
        return _validate_structured(v)

    @field_validator("code_reference")
    @classmethod
    def _code_ref(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if re.match(r"^[A-Za-z]:[\\/]", s) or s.startswith(("/", "\\\\")):
            raise ValueError("code_reference must be repository-relative, not absolute")
        if ".." in re.split(r"[\\/]", s):
            raise ValueError("code_reference must not contain '..'")
        return s or None


class QualityRunRequest(BaseModel):
    """Run a subset of the built-in metadata checks against a version."""

    model_config = ConfigDict(extra="forbid")

    checks: List[str] = Field(default_factory=list, max_length=40)
    expectations: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("expectations")
    @classmethod
    def _exp(cls, v: Any) -> Any:
        return _validate_structured(v)


class ExperimentLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: int = Field(ge=1)
    dataset_version_id: int = Field(ge=1)
    role: str
    notes: str = Field(default="", max_length=MAX_TEXT)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in LINK_ROLES:
            raise ValueError(f"role must be one of {LINK_ROLES}")
        return v


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class DatasetSummary(BaseModel):
    id: int
    created_at: str
    updated_at: str
    name: str
    domain: str
    dataset_type: str
    source_type: str
    provider: Optional[str] = None
    format: str
    frequency: Optional[str] = None
    asset_class: Optional[str] = None
    schema_version: Optional[str] = None
    current_version_id: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    is_demo: bool = False
    is_active: bool = True
    provenance_status: str = "unknown"
    version_count: int = 0
    latest_quality_status: Optional[str] = None
    latest_row_count: Optional[int] = None
    latest_date_range: Optional[str] = None
    latest_manifest_fingerprint: Optional[str] = None
    linked_experiment_count: int = 0


class DatasetFull(DatasetSummary):
    description: str = ""
    source_reference: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    symbol_scope: Optional[str] = None
    timezone: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class VersionSummary(BaseModel):
    id: int
    dataset_id: int
    dataset_name: Optional[str] = None
    version_label: str
    created_at: str
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    format: str
    deterministic: bool = False
    quality_status: str = "unknown"
    validation_status: str = "unknown"
    manifest_fingerprint: str
    schema_fingerprint: Optional[str] = None
    content_fingerprint: Optional[str] = None
    storage_locator_type: str
    storage_locator: str
    invalidated_at: Optional[str] = None
    is_current: bool = False


class VersionFull(VersionSummary):
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    source_fingerprint: Optional[str] = None
    file_size_bytes: Optional[int] = None
    compression: Optional[str] = None
    ingestion_method: str = "manual"
    schema_snapshot: Dict[str, Any] = Field(default_factory=dict)
    statistics_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    invalidation_reason: Optional[str] = None


class LineageEdge(BaseModel):
    id: int
    parent_version_id: int
    child_version_id: int
    relationship_type: str
    transformation_name: str
    transformation_version: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    code_reference: Optional[str] = None
    git_commit: Optional[str] = None
    created_at: str
    notes: str = ""


class LineageNode(BaseModel):
    version_id: int
    dataset_id: int
    dataset_name: str
    version_label: str
    quality_status: str
    invalidated: bool = False
    is_demo: bool = False
    depth: int = 0
    direction: str = "self"


class LineageGraph(BaseModel):
    root_version_id: int
    nodes: List[LineageNode] = Field(default_factory=list)
    edges: List[LineageEdge] = Field(default_factory=list)
    truncated: bool = False
    max_depth: int
    node_limit: int


class QualityResult(BaseModel):
    id: int
    dataset_version_id: int
    check_name: str
    check_category: str
    status: str
    severity: str
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    message: str = ""
    checked_at: str
    checker_version: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ExperimentLink(BaseModel):
    id: int
    experiment_id: int
    experiment_name: Optional[str] = None
    dataset_version_id: int
    dataset_name: Optional[str] = None
    version_label: Optional[str] = None
    role: str
    created_at: str
    notes: str = ""
    fingerprint_match: Optional[bool] = None


class DatasetListResponse(BaseModel):
    items: List[DatasetSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class RegistrySummary(BaseModel):
    datasets: int
    versions: int
    derived_versions: int
    quality_failures: int
    unknown_provenance: int
    linked_experiments: int
    source_types: Dict[str, int] = Field(default_factory=dict)
    domains: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class DriftEntry(BaseModel):
    kind: str
    field: Optional[str] = None
    a: Any = None
    b: Any = None
    note: str = ""


class VersionComparison(BaseModel):
    a_id: int
    b_id: int
    identity: List[DriftEntry] = Field(default_factory=list)
    schema_drift: List[DriftEntry] = Field(default_factory=list)
    drift_class: str = "unknown"
    metrics: List[DriftEntry] = Field(default_factory=list)
    fingerprints: Dict[str, bool] = Field(default_factory=dict)
    quality: Dict[str, List[str]] = Field(default_factory=dict)
    provenance_changes: List[DriftEntry] = Field(default_factory=list)


class ExportResponse(BaseModel):
    schema_version: str
    exported_at: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    datasets: List[DatasetFull] = Field(default_factory=list)
    versions: List[VersionFull] = Field(default_factory=list)
    lineage: List[LineageEdge] = Field(default_factory=list)
    quality_results: List[QualityResult] = Field(default_factory=list)
    experiment_links: List[ExperimentLink] = Field(default_factory=list)


class DemoSeedResponse(BaseModel):
    created_datasets: int
    created_versions: int
    created_edges: int
    created_quality_results: int
    created_links: int
    skipped_existing: int


__all__ = [
    "SOURCE_TYPES",
    "PROVENANCE_STATUSES",
    "QUALITY_STATUSES",
    "SEVERITIES",
    "RELATIONSHIP_TYPES",
    "LINK_ROLES",
    "DRIFT_CLASSES",
    "SchemaField",
    "SchemaSnapshot",
    "DatasetCreate",
    "DatasetUpdate",
    "VersionCreate",
    "InvalidateRequest",
    "LineageCreate",
    "QualityRunRequest",
    "ExperimentLinkCreate",
    "DatasetSummary",
    "DatasetFull",
    "VersionSummary",
    "VersionFull",
    "LineageEdge",
    "LineageNode",
    "LineageGraph",
    "QualityResult",
    "ExperimentLink",
    "DatasetListResponse",
    "RegistrySummary",
    "DriftEntry",
    "VersionComparison",
    "ExportResponse",
    "DemoSeedResponse",
]
