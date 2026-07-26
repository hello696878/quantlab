"""Pydantic v2 request/response models for the Overfitting Diagnostics Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    candidate_group: Optional[str] = Field(default=None, max_length=100)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    configuration_fingerprint: Optional[str] = Field(default=None, max_length=128)
    result_fingerprint: Optional[str] = Field(default=None, max_length=128)
    returns: List[Any] = Field(min_length=1, max_length=2000)
    nominal_p_value: Optional[Any] = None
    p_value_provenance: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", "p_value_provenance")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    metric: str = "sharpe_like"
    block_count: int = 8
    timestamps: List[str] = Field(min_length=1, max_length=2000)
    candidates: List[CandidateInput] = Field(min_length=1, max_length=24)
    benchmark_sharpe: float = 0.0
    confidence: float = 0.95
    alpha: float = 0.05
    trial_count_policy: Optional[Dict[str, Any]] = None
    dependence: Optional[Dict[str, Any]] = None
    periods_per_year: Optional[float] = None
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    feature_diagnostics_run_id: Optional[int] = Field(default=None, ge=1)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("trial_count_policy", "dependence")
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
    metric: str
    block_count: int
    candidate_count: int
    observation_count: int
    combination_count: int
    valid_split_count: int
    invalid_split_count: int
    pbo_estimate: Optional[float] = None
    psr: Optional[float] = None
    dsr: Optional[float] = None
    benchmark_sharpe: Optional[float] = None
    effective_trial_count: Optional[float] = None
    universe_fingerprint: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    dataset_version_id: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version_label: Optional[str] = None
    dataset_invalidated: Optional[bool] = None
    validation_run_id: Optional[int] = None
    validation_method: Optional[str] = None
    experiment_id: Optional[int] = None
    feature_diagnostics_run_id: Optional[int] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    timestamps: List[str] = Field(default_factory=list)
    blocks: List[Dict[str, Any]] = Field(default_factory=list)
    pbo_aggregate: Dict[str, Any] = Field(default_factory=dict)
    sharpe_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    dependence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    baseline_scope: Optional[str] = None
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
    validation_valid_splits: Optional[int] = None
    validation_invalid_splits: Optional[int] = None
    feature_run_name: Optional[str] = None
    feature_run_integrity: Optional[str] = None


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    candidates: int
    valid_splits: int
    baselines: int
    adjusted_below_threshold: int
    metrics: Dict[str, int] = Field(default_factory=dict)


class CompareEntry(BaseModel):
    kind: str
    field: str
    a: Any = None
    b: Any = None
    note: str = ""


class RunComparison(BaseModel):
    a_id: int
    b_id: int
    comparability_warnings: List[str] = Field(default_factory=list)
    groups: Dict[str, List[CompareEntry]]
    selection: List[Dict[str, Any]] = Field(default_factory=list)
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)
    baseline: Dict[str, bool] = Field(default_factory=dict)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


__all__ = [
    "CandidateInput", "RunCreate", "ExecuteRequest", "InvalidateRequest",
    "RunSummary", "RunFull", "RunListResponse", "LabSummary", "CompareEntry",
    "RunComparison", "DemoSeedResponse",
]
