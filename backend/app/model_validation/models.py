"""
Pydantic v2 request/response models for the Model Validation Lab.

Strict at the boundary: bounded strings/JSON, finite numbers only, method and
embargo vocabularies enforced, forbidden extra fields.  Engine-level rules
(fold counts vs samples, CPCV limits, interval validity) raise in the engine
and map to 422 via the router guard.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured

METHODS = ("standard_kfold", "walk_forward", "purged_kfold", "cpcv")
RUN_STATUSES = ("pending", "completed", "failed", "invalidated")

MAX_NAME = 200
MAX_TEXT = 2000


class RawSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1, max_length=100)
    prediction_time: str
    evaluation_time: Optional[str] = None
    group: Optional[str] = Field(default=None, max_length=100)
    label: Optional[float] = None
    prediction: Optional[float] = None
    score: Optional[float] = None
    ret: Optional[float] = None
    weight: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _meta(cls, v: Any) -> Any:
        return _validate_structured(v)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)
    description: str = Field(default="", max_length=MAX_TEXT)
    method: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    samples: List[RawSample] = Field(min_length=1, max_length=2000)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    random_seed: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=MAX_TEXT)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("method")
    @classmethod
    def _method(cls, v: str) -> str:
        if v not in METHODS:
            raise ValueError(f"method must be one of {METHODS}")
        return v

    @field_validator("configuration")
    @classmethod
    def _config(cls, v: Any) -> Any:
        return _validate_structured(v)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    create_experiment: bool = False


class InvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=MAX_TEXT)


class RunSummary(BaseModel):
    id: int
    created_at: str
    updated_at: str
    name: str
    method: str
    status: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    sample_count: int
    split_count: int
    valid_split_count: int
    invalid_split_count: int
    leakage_clean: Optional[bool] = None
    duration_ms: Optional[int] = None
    experiment_id: Optional[int] = None
    dataset_version_id: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version_label: Optional[str] = None
    dataset_invalidated: Optional[bool] = None
    random_seed: Optional[int] = None
    is_baseline: bool = False
    key_metric_preview: Optional[str] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    aggregate_metrics: Dict[str, Any] = Field(default_factory=dict)
    leakage_summary: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    app_version: Optional[str] = None
    git_commit: Optional[str] = None
    notes: str = ""
    experiment_name: Optional[str] = None
    dataset_manifest_fingerprint: Optional[str] = None
    dataset_provenance_status: Optional[str] = None
    dataset_quality_status: Optional[str] = None


class SplitRecord(BaseModel):
    id: int
    validation_run_id: int
    split_index: int
    split_label: str
    split_fingerprint: str
    status: str
    train_ids: List[str] = Field(default_factory=list)
    test_ids: List[str] = Field(default_factory=list)
    purged_ids: List[str] = Field(default_factory=list)
    embargoed_ids: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    leakage_clean: int
    invalid_splits: int
    baselines: int
    linked_datasets: int
    methods: Dict[str, int] = Field(default_factory=dict)


class CompareEntry(BaseModel):
    kind: str
    field: str
    a: Any = None
    b: Any = None
    note: str = ""


class RunComparison(BaseModel):
    a_id: int
    b_id: int
    groups: Dict[str, List[CompareEntry]]
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    schema_version: str
    exported_at: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    runs: List[RunFull] = Field(default_factory=list)
    splits: List[SplitRecord] = Field(default_factory=list)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


class SamplePoint(BaseModel):
    """Timeline point for the split visualization."""

    sample_id: str
    prediction_time: str
    evaluation_time: str
    category: str  # train | test | purged | embargoed | unused


__all__ = [
    "METHODS",
    "RUN_STATUSES",
    "RawSample",
    "RunCreate",
    "ExecuteRequest",
    "InvalidateRequest",
    "RunSummary",
    "RunFull",
    "SplitRecord",
    "RunListResponse",
    "LabSummary",
    "CompareEntry",
    "RunComparison",
    "ExportResponse",
    "DemoSeedResponse",
    "SamplePoint",
]
