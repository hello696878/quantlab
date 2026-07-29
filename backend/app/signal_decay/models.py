"""Pydantic v2 API models for the Signal Decay Lab (permissive envelopes:
the service layer owns validation and returns explicit 422s)."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    signal: Dict[str, Any]
    outcome: Dict[str, Any]
    observations: List[Dict[str, Any]] = Field(min_length=1)
    prices: Optional[List[Dict[str, Any]]] = None
    supplied_outcomes: Optional[List[Dict[str, Any]]] = None
    horizons: Optional[Dict[str, Any]] = None
    buckets: Optional[Dict[str, Any]] = None
    turnover: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    dataset_version_id: Optional[PositiveStrictInt] = None
    feature_run_id: Optional[PositiveStrictInt] = None
    meta_label_run_id: Optional[PositiveStrictInt] = None
    validation_run_id: Optional[PositiveStrictInt] = None
    validation_split_label: Optional[str] = None
    regime_run_id: Optional[PositiveStrictInt] = None
    regime_definition_id: Optional[str] = None
    cost_diagnostic_run_id: Optional[PositiveStrictInt] = None
    factor_run_id: Optional[PositiveStrictInt] = None
    notes: str = Field(default="", max_length=2000)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    create_experiment: bool = False


class InvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    created_at: str
    updated_at: str
    name: str
    description: str
    status: str
    signal_id: str
    signal_type: str
    outcome_id: str
    outcome_target_type: str
    frequency: str
    entity_count: int
    observation_count: int
    horizon_count: int
    lag_count: int
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    integrity_status: str
    completeness_status: str
    overlap_status: Optional[str] = None
    first_horizon_rank_ic: Optional[float] = None
    mean_one_way_turnover: Optional[float] = None
    signal_fingerprint: str
    outcome_fingerprint: str
    universe_fingerprint: str
    horizon_fingerprint: str
    analysis_fingerprint: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    error_message: Optional[str] = None


class RunFull(RunSummary):
    configuration: Dict[str, Any]
    signal: Optional[Dict[str, Any]] = None
    outcome: Optional[Dict[str, Any]] = None
    horizon_policy: Optional[Dict[str, Any]] = None
    bucket_policy: Optional[Dict[str, Any]] = None
    turnover_policy: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    decay: List[Dict[str, Any]] = Field(default_factory=list)
    overlap: List[Dict[str, Any]] = Field(default_factory=list)
    turnover_summary: Optional[Dict[str, Any]] = None
    holding_overlap: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    held_out: Optional[Dict[str, Any]] = None
    factor_residual: Optional[Dict[str, Any]] = None
    multiple_testing: Optional[Dict[str, Any]] = None
    signal_diagnostics: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    runs: int
    completed: int
    signals: int
    observations: int
    horizon_rows: int
    overlapping_runs: int
    baselines: int


class RunComparison(BaseModel):
    model_config = ConfigDict(extra="allow")

    a_id: int
    b_id: int
    comparability_warnings: List[str]
    fields: Dict[str, str]
    horizon_rows: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    baseline: Dict[str, bool]
    note: str


class DemoSeedResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    created: bool
    created_count: int
    skipped_count: int
    run_ids: List[int]
    notes: List[str] = Field(default_factory=list)


__all__ = [
    "RunCreate", "ExecuteRequest", "InvalidateRequest", "RunSummary",
    "RunFull", "RunListResponse", "LabSummary", "RunComparison",
    "DemoSeedResponse",
]
