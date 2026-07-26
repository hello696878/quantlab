"""Pydantic v2 request/response models for the Regime Diagnostics Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    outcome_kind: str = "return"
    outcomes: List[Any] = Field(min_length=1, max_length=2000)
    experiment_id: Optional[int] = Field(default=None, ge=1)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return _validate_structured(v)


class RegimeDefinitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str = Field(min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    dimension: str
    source_feature: Optional[str] = Field(default=None, max_length=64)
    lookback: Optional[int] = None
    lag: Optional[int] = None
    threshold_mode: Optional[str] = None
    thresholds: Optional[List[Any]] = Field(default=None, max_length=4)
    quantiles: Optional[List[Any]] = Field(default=None, max_length=4)
    labels: Optional[List[str]] = Field(default=None, max_length=6)
    min_history: Optional[int] = None
    threshold_split_label: Optional[str] = Field(default=None, max_length=100)
    labels_supplied: Optional[List[Any]] = Field(default=None, max_length=2000)
    provenance: Optional[Dict[str, Any]] = None
    sources: Optional[List[str]] = Field(default=None, max_length=2)
    min_observations: Optional[int] = None
    centered: Optional[bool] = None
    window: Optional[str] = Field(default=None, max_length=20)

    @field_validator("provenance")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    frequency: str = Field(min_length=1, max_length=40)
    timestamps: List[str] = Field(min_length=1, max_length=2000)
    candidates: List[CandidateInput] = Field(min_length=1, max_length=16)
    market_features: Optional[Dict[str, List[Any]]] = None
    sample_ids: Optional[List[str]] = Field(default=None, max_length=2000)
    definitions: List[RegimeDefinitionInput] = Field(min_length=1, max_length=6)
    transition_window: Optional[int] = None
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    overfitting_run_id: Optional[int] = Field(default=None, ge=1)
    feature_diagnostics_run_id: Optional[int] = Field(default=None, ge=1)
    meta_label_run_id: Optional[int] = Field(default=None, ge=1)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s


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
    candidate_count: int
    observation_count: int
    period_count: int
    frequency: str
    regime_definition_count: int
    observed_regime_count: int
    invalid_definition_count: int
    low_coverage_warning_count: int
    integrity_status: str
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
    overfitting_run_id: Optional[int] = None
    feature_diagnostics_run_id: Optional[int] = None
    meta_label_run_id: Optional[int] = None
    experiment_id: Optional[int] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    timestamps: List[str] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    coverage: Dict[str, Any] = Field(default_factory=dict)
    robustness: List[Dict[str, Any]] = Field(default_factory=list)
    rank_stability: Dict[str, Any] = Field(default_factory=dict)
    concentration: List[Dict[str, Any]] = Field(default_factory=list)
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
    overfitting_name: Optional[str] = None
    overfitting_pbo: Optional[float] = None
    overfitting_psr: Optional[float] = None
    overfitting_dsr: Optional[float] = None
    overfitting_universe_fp: Optional[str] = None
    feature_run_name: Optional[str] = None
    feature_run_integrity: Optional[str] = None
    meta_label_run_name: Optional[str] = None
    meta_label_oof_status: Optional[str] = None


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
    observed_regimes: int
    verified_definitions: int
    low_coverage_warnings: int
    baselines: int


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
    robustness: List[Dict[str, Any]] = Field(default_factory=list)
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)
    baseline: Dict[str, bool] = Field(default_factory=dict)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


__all__ = [
    "CandidateInput", "RegimeDefinitionInput", "RunCreate", "ExecuteRequest",
    "InvalidateRequest", "RunSummary", "RunFull", "RunListResponse",
    "LabSummary", "CompareEntry", "RunComparison", "DemoSeedResponse",
]
