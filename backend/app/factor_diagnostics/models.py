"""Pydantic v2 API models for the Factor Diagnostics Lab (permissive
envelopes: the service layer owns validation and returns explicit 422s)."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    analysis_mode: str = "time_series_regression"
    target: Dict[str, Any]
    factors: List[Dict[str, Any]] = Field(min_length=1, max_length=12)
    policy: Optional[Dict[str, Any]] = None
    asset_exposures: Optional[Dict[str, Any]] = None
    benchmark_comparison: bool = False
    stress_factor_shocks: Optional[Dict[str, Any]] = None
    sensitivity: Optional[List[Dict[str, Any]]] = None
    dataset_version_id: Optional[PositiveStrictInt] = None
    portfolio_run_id: Optional[PositiveStrictInt] = None
    validation_run_id: Optional[PositiveStrictInt] = None
    validation_split_label: Optional[str] = None
    regime_run_id: Optional[PositiveStrictInt] = None
    regime_definition_id: Optional[str] = None
    stress_run_id: Optional[PositiveStrictInt] = None
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
    analysis_mode: str
    regression_method: str
    intercept_policy: str
    rank_policy: str
    timing_policy: str
    vintage_policy: str
    target_id: str
    target_type: str
    target_source: str
    return_convention: str
    return_frequency: str
    currency: str
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    factor_count: int
    observation_count: int
    excluded_period_count: int
    integrity_status: str
    completeness_status: str
    rank_status: Optional[str] = None
    reconciliation_status: Optional[str] = None
    r_squared: Optional[float] = None
    adjusted_r_squared: Optional[float] = None
    root_mean_squared_error: Optional[float] = None
    residual_std: Optional[float] = None
    intercept: Optional[float] = None
    condition_number: Optional[float] = None
    degrees_of_freedom: Optional[int] = None
    held_out_r_squared: Optional[float] = None
    target_fingerprint: str
    observation_fingerprint: str
    model_policy_fingerprint: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    error_message: Optional[str] = None


class RunFull(RunSummary):
    configuration: Dict[str, Any]
    factors: List[Dict[str, Any]] = Field(default_factory=list)
    target: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    fit: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    multicollinearity: Optional[Dict[str, Any]] = None
    residual_diagnostics: Optional[Dict[str, Any]] = None
    stability: List[Dict[str, Any]] = Field(default_factory=list)
    rolling_summary: Optional[Dict[str, Any]] = None
    exposure_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    held_out: Optional[Dict[str, Any]] = None
    stress_linkage: Optional[Dict[str, Any]] = None
    attribution_linkage: Optional[Dict[str, Any]] = None
    multiple_testing: Optional[Dict[str, Any]] = None
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
    factors: int
    observations: int
    verified_runs: int
    rank_deficient_runs: int
    baselines: int


class RunComparison(BaseModel):
    model_config = ConfigDict(extra="allow")

    a_id: int
    b_id: int
    comparability_warnings: List[str]
    coefficients: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    fingerprint_match: Dict[str, bool]
    baseline: Dict[str, bool]


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
