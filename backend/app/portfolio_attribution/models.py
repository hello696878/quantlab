"""Pydantic v2 API models for the Portfolio Attribution Lab (permissive
envelopes: the service layer owns validation and returns explicit 422s)."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    portfolio_run_id: PositiveStrictInt
    attribution_method: str = "brinson"
    brinson_variant: str = "brinson_fachler"
    linking_method: str = "arithmetic"
    cost_policy: str = "stored_rebalance_costs"
    policy: Optional[Dict[str, Any]] = None
    benchmark: Optional[Dict[str, Any]] = None
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    dataset_version_id: Optional[PositiveStrictInt] = None
    cost_diagnostic_run_id: Optional[PositiveStrictInt] = None
    regime_run_id: Optional[PositiveStrictInt] = None
    regime_definition_id: Optional[str] = None
    stress_run_id: Optional[PositiveStrictInt] = None
    validation_run_id: Optional[PositiveStrictInt] = None
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
    attribution_method: str
    brinson_variant: Optional[str] = None
    linking_method: str
    return_convention: str
    return_frequency: str
    weight_timing_policy: str
    benchmark_timing_policy: str
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    asset_count: int
    group_count: int
    period_count: int
    integrity_status: str
    completeness_status: str
    reconciliation_status: str
    portfolio_market_return: Optional[float] = None
    portfolio_net_return: Optional[float] = None
    benchmark_return: Optional[float] = None
    active_return: Optional[float] = None
    total_cost_return: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    observation_fingerprint: str
    policy_fingerprint: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    portfolio_run_id: int
    error_message: Optional[str] = None


class RunFull(RunSummary):
    configuration: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None
    linking: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    active_risk: Optional[Dict[str, Any]] = None
    concentration: Optional[Dict[str, Any]] = None
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
    periods: int
    benchmarked_runs: int
    reconciled_runs: int
    baselines: int


class RunComparison(BaseModel):
    model_config = ConfigDict(extra="allow")

    a_id: int
    b_id: int
    comparability_warnings: List[str]
    groups: Dict[str, Any]
    brinson: List[Dict[str, Any]]
    contributions: List[Dict[str, Any]]
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
