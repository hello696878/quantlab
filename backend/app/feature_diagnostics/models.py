"""Pydantic v2 request/response models for the Feature Diagnostics Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class FeatureDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_name: str = Field(min_length=1, max_length=64)
    display_name: Optional[str] = Field(default=None, max_length=200)
    data_type: str = "numeric"
    source_column: Optional[str] = Field(default=None, max_length=200)
    feature_group: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=200)
    dataset_schema_reference: Optional[str] = Field(default=None, max_length=200)


class FeatureSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1, max_length=64)
    timestamp: str
    features: Dict[str, Any]
    target: Any


class DeclaredSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    split_id: str = Field(min_length=1, max_length=64)
    train_sample_ids: List[str] = Field(min_length=1, max_length=2000)
    test_sample_ids: List[str] = Field(min_length=1, max_length=2000)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    method: str = "permutation"
    model_type: str = "logistic_regression"
    target_type: str = "binary_classification"
    metric: str = "log_loss"
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    features: List[FeatureDefinition] = Field(min_length=1, max_length=32)
    samples: List[FeatureSample] = Field(min_length=1, max_length=2000)
    permutation_repeats: Optional[int] = None
    seed: Optional[int] = None
    correlation: Optional[Dict[str, Any]] = None
    drift: Optional[Dict[str, Any]] = None
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    declared_splits: Optional[List[DeclaredSplit]] = Field(default=None, max_length=12)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    meta_label_run_id: Optional[int] = Field(default=None, ge=1)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("hyperparameters", "correlation", "drift")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    create_experiment: bool = False


class InvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class RunSummary(BaseModel):
    id: int
    created_at: str
    updated_at: str
    name: str
    status: str
    method: str
    model_type: str
    target_type: str
    metric: str
    metric_direction: str
    split_source: str
    integrity_status: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    sample_count: int
    feature_count: int
    split_count: int
    valid_split_count: int
    invalid_split_count: int
    is_baseline: bool = False
    validation_run_id: Optional[int] = None
    validation_method: Optional[str] = None
    dataset_version_id: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version_label: Optional[str] = None
    dataset_invalidated: Optional[bool] = None
    experiment_id: Optional[int] = None
    meta_label_run_id: Optional[int] = None
    top_feature: Optional[str] = None
    top_feature_importance: Optional[float] = None
    stable_feature_count: int = 0
    unstable_feature_count: int = 0
    drift_flag_count: int = 0
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    baseline_fingerprint: Optional[str] = None
    baseline_scope: Optional[str] = None
    splits: List[Dict[str, Any]] = Field(default_factory=list)
    stability_summary: Dict[str, Any] = Field(default_factory=dict)
    importance_drift: Dict[str, Any] = Field(default_factory=dict)
    references: Dict[str, Any] = Field(default_factory=dict)
    drift_context: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    app_version: Optional[str] = None
    git_commit: Optional[str] = None
    notes: str = ""
    experiment_name: Optional[str] = None
    dataset_manifest_fingerprint: Optional[str] = None
    dataset_provenance_status: Optional[str] = None
    dataset_quality_status: Optional[str] = None
    validation_leakage_clean: Optional[bool] = None
    validation_config_fp: Optional[str] = None
    validation_result_fp: Optional[str] = None
    meta_label_run_name: Optional[str] = None
    meta_label_oof_status: Optional[str] = None
    meta_label_calibration_method: Optional[str] = None
    meta_label_result_fp: Optional[str] = None


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    held_out_verified: int
    stable_features: int
    drift_flags: int
    baselines: int
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
    features: List[Dict[str, Any]] = Field(default_factory=list)
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)
    baseline: Dict[str, bool] = Field(default_factory=dict)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


__all__ = [
    "FeatureDefinition", "FeatureSample", "DeclaredSplit", "RunCreate",
    "ExecuteRequest", "InvalidateRequest", "RunSummary", "RunFull",
    "RunListResponse", "LabSummary", "CompareEntry", "RunComparison",
    "DemoSeedResponse",
]
