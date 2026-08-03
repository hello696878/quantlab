"""Pydantic v2 API models for the Signal Ensemble Lab (permissive
envelopes: the service layer owns validation and returns explicit 422s)."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    universe: Dict[str, Any]
    orientations: Optional[Dict[str, Any]] = None
    normalisation: Optional[Dict[str, Any]] = None
    combination: Optional[Dict[str, Any]] = None
    similarity: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    prices: Optional[List[Dict[str, Any]]] = None
    dataset_version_id: Optional[PositiveStrictInt] = None
    signal_decay_run_id: Optional[PositiveStrictInt] = None
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
    combination_mode: str
    alignment_policy: str
    frequency: str
    signal_count: int
    entity_count: int
    observation_count: int
    strict_intersection_count: int
    combined_available_count: Optional[int] = None
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    integrity_status: str
    completeness_status: str
    mean_absolute_correlation: Optional[float] = None
    effective_signal_count: Optional[float] = None
    universe_fingerprint: Optional[str] = None
    combination_fingerprint: Optional[str] = None
    similarity_fingerprint: Optional[str] = None
    analysis_fingerprint: Optional[str] = None
    configuration_fingerprint: Optional[str] = None
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False


class RunFull(RunSummary):
    model_config = ConfigDict(extra="allow")

    definitions: List[Dict[str, Any]] = Field(default_factory=list)
    missingness: Optional[Dict[str, Any]] = None
    matrix: Optional[Dict[str, Any]] = None
    distance: Optional[Dict[str, Any]] = None
    matrix_diagnostics: Optional[Dict[str, Any]] = None
    clustering: Optional[Dict[str, Any]] = None
    redundancy: Optional[Dict[str, Any]] = None
    reconciliation: Optional[Dict[str, Any]] = None
    combination_coverage: Optional[float] = None
    turnover_summary: Optional[Dict[str, Any]] = None
    holding_overlap: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    component_turnover: Optional[Dict[str, Any]] = None
    multiple_testing: Optional[Dict[str, Any]] = None
    held_out: Optional[Dict[str, Any]] = None
    factor_residual: Optional[Dict[str, Any]] = None
    leave_one_out: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    items: List[RunSummary]
    total: int
    page: int
    page_size: int


class LabSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    runs: int
    completed: int
    signals: int
    observations: int
    pairwise_rows: int
    baselines: int


class DemoSeedResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    created: bool
    created_count: int
    skipped_count: int
    run_ids: List[int]
    notes: List[str]
