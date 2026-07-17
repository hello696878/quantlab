"""Pydantic v2 request/response models for the Meta-Labeling Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class RawObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1, max_length=100)
    prediction_time: str
    evaluation_time: str
    primary_side: int
    primary_score: Optional[float] = None
    raw_probability: Optional[float] = None
    realized_outcome: Optional[float] = None
    sample_weight: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _meta(cls, v: Any) -> Any:
        return _validate_structured(v)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    outcome_threshold: float = 0.0
    calibration_method: str = "none"
    n_bins: int = 10
    binning: str = "equal_width"
    threshold_grid: Dict[str, Any] = Field(default_factory=dict)
    abstention: Optional[Dict[str, Any]] = None
    declared_out_of_fold: bool = False
    observations: List[RawObservation] = Field(min_length=1, max_length=2000)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    random_seed: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("threshold_grid", "abstention")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    create_experiment: bool = False


class InvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, max_length=200)
    threshold: float
    abstention: Optional[Dict[str, Any]] = None
    notes: str = Field(default="", max_length=2000)

    @field_validator("abstention")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class RunSummary(BaseModel):
    id: int
    created_at: str
    updated_at: str
    name: str
    status: str
    calibration_method: str
    oof_status: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    observation_count: int
    labeled_count: int
    positive_count: int
    abstained_count: int
    validation_run_id: Optional[int] = None
    validation_method: Optional[str] = None
    dataset_version_id: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version_label: Optional[str] = None
    dataset_invalidated: Optional[bool] = None
    experiment_id: Optional[int] = None
    positive_prevalence: Optional[float] = None
    brier_preview: Optional[float] = None
    ece_preview: Optional[float] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    label_policy: Dict[str, Any] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)
    calibrated_metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration_params: Dict[str, Any] = Field(default_factory=dict)
    threshold_analysis: Dict[str, Any] = Field(default_factory=dict)
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


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    oof_verified: int
    calibrated: int
    threshold_policies: int
    baselines: int
    methods: Dict[str, int] = Field(default_factory=dict)


class ThresholdPolicy(BaseModel):
    id: int
    created_at: str
    updated_at: str
    run_id: int
    name: str
    threshold: float
    abstention: Optional[Dict[str, Any]] = None
    configuration_fingerprint: str
    observed_coverage: Optional[float] = None
    observed_precision: Optional[float] = None
    observed_recall: Optional[float] = None
    observed_f1: Optional[float] = None
    is_baseline: bool = False
    notes: str = ""


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


class DemoSeedResponse(BaseModel):
    created_runs: int
    created_policies: int
    skipped_existing: int


__all__ = [
    "RawObservation", "RunCreate", "ExecuteRequest", "InvalidateRequest",
    "PolicyCreate", "RunSummary", "RunFull", "RunListResponse", "LabSummary",
    "ThresholdPolicy", "CompareEntry", "RunComparison", "DemoSeedResponse",
]
