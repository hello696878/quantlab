"""
Pydantic v2 request/response models for the Research Experiment Registry.

Validation is strict at the API boundary: bounded strings, bounded tag lists,
bounded JSON depth/size for free-form structured fields, rejection of non-finite
numbers (NaN / ±Infinity), and SHA-256 validation for supplied dataset
fingerprints.  Business-rule validation that needs database state (status
transitions, parent existence, baseline eligibility) lives in :mod:`.service`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.fingerprints import is_valid_sha256

# --- literals -------------------------------------------------------------

ExperimentStatus = ("pending", "running", "completed", "failed", "invalidated")
ReproducibilityStatus = (
    "unknown",
    "reproducible",
    "partially_reproducible",
    "not_reproducible",
)

# --- bounds ---------------------------------------------------------------

MAX_NAME = 200
MAX_MODULE = 100
MAX_TYPE = 100
MAX_DESCRIPTION = 2000
MAX_NOTES = 4000
MAX_ERROR = 2000
MAX_DATASET_NAME = 200
MAX_DATASET_VERSION = 100
MAX_TAGS = 25
MAX_TAG_LEN = 50
MAX_JSON_DEPTH = 8
MAX_JSON_NODES = 2000


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------


def _reject_non_finite(obj: Any, path: str = "") -> None:
    """Recursively reject NaN / ±Infinity anywhere in a structured value."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, float):
        # ``float('nan') != float('nan')`` and inf comparisons — use the math test.
        import math

        if not math.isfinite(obj):
            raise ValueError(f"non-finite number is not allowed{(' at ' + path) if path else ''}")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _reject_non_finite(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _reject_non_finite(v, f"{path}[{i}]")


def _bounded_json(obj: Any, *, depth: int = 0, counter: Optional[List[int]] = None) -> None:
    """Reject structured values that are too deep or have too many nodes."""
    if counter is None:
        counter = [0]
    if depth > MAX_JSON_DEPTH:
        raise ValueError(f"structured value nesting exceeds {MAX_JSON_DEPTH} levels")
    counter[0] += 1
    if counter[0] > MAX_JSON_NODES:
        raise ValueError(f"structured value has more than {MAX_JSON_NODES} nodes")
    if isinstance(obj, dict):
        for v in obj.values():
            _bounded_json(v, depth=depth + 1, counter=counter)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _bounded_json(v, depth=depth + 1, counter=counter)


def _validate_structured(value: Any) -> Any:
    _bounded_json(value)
    _reject_non_finite(value)
    return value


def _validate_tags(tags: List[str]) -> List[str]:
    cleaned: List[str] = []
    for t in tags:
        if not isinstance(t, str):
            raise ValueError("tags must be strings")
        stripped = t.strip()
        if not stripped:
            raise ValueError("tags must not be blank")
        if len(stripped) > MAX_TAG_LEN:
            raise ValueError(f"tag exceeds {MAX_TAG_LEN} characters")
        cleaned.append(stripped)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique = [t for t in cleaned if not (t in seen or seen.add(t))]
    return unique


def _validate_iso_timestamp(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    return text


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    """Request body for POST /experiment-registry/experiments."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)
    description: str = Field(default="", max_length=MAX_DESCRIPTION)
    module: str = Field(min_length=1, max_length=MAX_MODULE)
    experiment_type: str = Field(min_length=1, max_length=MAX_TYPE)
    status: str = Field(default="completed")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, max_length=MAX_TAGS)
    notes: str = Field(default="", max_length=MAX_NOTES)
    random_seed: Optional[int] = Field(default=None, ge=0)
    dataset_name: Optional[str] = Field(default=None, max_length=MAX_DATASET_NAME)
    dataset_version: Optional[str] = Field(default=None, max_length=MAX_DATASET_VERSION)
    dataset_fingerprint: Optional[str] = Field(default=None)
    dataset_identity: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional deterministic-fixture identity metadata used to "
        "derive a dataset fingerprint when one is not supplied.",
    )
    parent_experiment_id: Optional[int] = Field(default=None, ge=1)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = Field(default=None, max_length=MAX_ERROR)
    provenance_extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "module", "experiment_type")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("field must not be blank")
        return s

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ExperimentStatus:
            raise ValueError(f"status must be one of {ExperimentStatus}")
        return v

    @field_validator("parameters", "metrics", "provenance_extra", "dataset_identity")
    @classmethod
    def _valid_structured(cls, v: Any) -> Any:
        return _validate_structured(v)

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, v: List[str]) -> List[str]:
        return _validate_tags(v)

    @field_validator("dataset_fingerprint")
    @classmethod
    def _valid_dataset_fp(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if not is_valid_sha256(s):
            raise ValueError("dataset_fingerprint must be a 64-char SHA-256 hex string")
        return s.lower()

    @field_validator("started_at", "completed_at")
    @classmethod
    def _valid_ts(cls, v: Optional[str]) -> Optional[str]:
        return _validate_iso_timestamp(v)


class ExperimentUpdate(BaseModel):
    """Request body for PATCH — mutable descriptive fields only."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_NAME)
    description: Optional[str] = Field(default=None, max_length=MAX_DESCRIPTION)
    notes: Optional[str] = Field(default=None, max_length=MAX_NOTES)
    tags: Optional[List[str]] = Field(default=None, max_length=MAX_TAGS)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return _validate_tags(v)


class CompleteRequest(BaseModel):
    """Request body for POST /experiment-registry/experiments/{id}/complete."""

    model_config = ConfigDict(extra="forbid")

    metrics: Dict[str, Any] = Field(default_factory=dict)
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)

    @field_validator("metrics", "result_metadata")
    @classmethod
    def _valid_structured(cls, v: Any) -> Any:
        return _validate_structured(v)

    @field_validator("completed_at")
    @classmethod
    def _valid_ts(cls, v: Optional[str]) -> Optional[str]:
        return _validate_iso_timestamp(v)


class FailRequest(BaseModel):
    """Request body for POST /experiment-registry/experiments/{id}/fail."""

    model_config = ConfigDict(extra="forbid")

    error_message: str = Field(min_length=1, max_length=MAX_ERROR)
    completed_at: Optional[str] = None

    @field_validator("error_message")
    @classmethod
    def _strip_error(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("error_message must not be blank")
        return s

    @field_validator("completed_at")
    @classmethod
    def _valid_ts(cls, v: Optional[str]) -> Optional[str]:
        return _validate_iso_timestamp(v)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ExperimentSummary(BaseModel):
    """Lightweight list row."""

    id: int
    created_at: str
    updated_at: str
    name: str
    module: str
    experiment_type: str
    status: str
    reproducibility_status: str
    duration_ms: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version: Optional[str] = None
    dataset_fingerprint: Optional[str] = None
    random_seed: Optional[int] = None
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    git_commit: Optional[str] = None
    app_version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    parent_experiment_id: Optional[int] = None


class ExperimentFull(ExperimentSummary):
    """Full record."""

    description: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    error_message: Optional[str] = None


class ExperimentListResponse(BaseModel):
    items: List[ExperimentSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class RegistrySummaryResponse(BaseModel):
    total: int
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_reproducibility: Dict[str, int] = Field(default_factory=dict)
    baselines: int
    modules_represented: int
    modules: List[str] = Field(default_factory=list)
    experiment_types: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ReproducibilityCheck(BaseModel):
    name: str
    state: str


class ReproducibilityAssessment(BaseModel):
    status: str
    reference_id: Optional[int] = None
    summary: str
    checks: List[ReproducibilityCheck] = Field(default_factory=list)


class ComparisonEntry(BaseModel):
    key: str
    state: str
    a: Any = None
    b: Any = None
    abs_diff: Optional[float] = None
    pct_diff: Optional[float] = None


class ComparisonResponse(BaseModel):
    a_id: int
    b_id: int
    groups: Dict[str, List[ComparisonEntry]]
    summary: Dict[str, Dict[str, int]]
    fingerprint_match: Dict[str, bool]


class ExportResponse(BaseModel):
    schema_version: str
    exported_at: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    count: int
    experiments: List[ExperimentFull]


class DemoSeedResponse(BaseModel):
    created: int
    skipped: int
    total: int
    experiment_ids: List[int] = Field(default_factory=list)


class RegistryDeleteResponse(BaseModel):
    deleted: bool
    id: int


__all__ = [
    "ExperimentStatus",
    "ReproducibilityStatus",
    "ExperimentCreate",
    "ExperimentUpdate",
    "CompleteRequest",
    "FailRequest",
    "ExperimentSummary",
    "ExperimentFull",
    "ExperimentListResponse",
    "RegistrySummaryResponse",
    "ReproducibilityAssessment",
    "ComparisonResponse",
    "ComparisonEntry",
    "ExportResponse",
    "DemoSeedResponse",
    "RegistryDeleteResponse",
]
