"""Pydantic v2 request/response models for the Portfolio Diagnostics Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    asset_type: str = Field(default="other", max_length=20)
    group: Optional[str] = Field(default=None, max_length=64)
    currency: Optional[str] = Field(default=None, max_length=8)
    integer_lots: bool = False
    returns: List[Any] = Field(min_length=1, max_length=2000)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    method: str = Field(min_length=1, max_length=32)
    frequency: str = Field(min_length=1, max_length=40)
    timestamps: List[str] = Field(min_length=1, max_length=2000)
    assets: List[AssetInput] = Field(min_length=1, max_length=20)
    benchmark_returns: Optional[List[Any]] = Field(default=None, max_length=2000)
    prior_weights: Optional[Dict[str, Any]] = None
    sample_ids: Optional[List[str]] = Field(default=None, max_length=2000)
    weights: Optional[Dict[str, Any]] = None
    weight_provenance: Optional[Dict[str, Any]] = None
    normalization: Optional[str] = Field(default="sum_to_one", max_length=20)
    estimation: Optional[Dict[str, Any]] = None
    covariance: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None
    risk_budgets: Optional[Dict[str, Any]] = None
    rebalance: Optional[Dict[str, Any]] = None
    solver: Optional[Dict[str, Any]] = None
    sensitivity: Optional[Dict[str, Any]] = None
    volatility_floor: Optional[Any] = None
    cost_notional: Optional[Any] = None
    validation_split_label: Optional[str] = Field(default=None, max_length=100)
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    regime_run_id: Optional[int] = Field(default=None, ge=1)
    regime_definition_id: Optional[str] = Field(default=None, max_length=64)
    cost_diagnostic_run_id: Optional[int] = Field(default=None, ge=1)
    overfitting_run_id: Optional[int] = Field(default=None, ge=1)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("estimation", "covariance", "constraints", "risk_budgets",
                     "rebalance", "solver", "sensitivity", "prior_weights",
                     "weights", "weight_provenance")
    @classmethod
    def _structured_cfg(cls, v: Any) -> Any:
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
    covariance_method: str
    asset_count: int
    observation_count: int
    rebalance_count: int
    integrity_status: str
    solver_status: Optional[str] = None
    portfolio_volatility: Optional[float] = None
    effective_positions: Optional[float] = None
    max_budget_deviation: Optional[float] = None
    mean_turnover: Optional[float] = None
    constraint_violation_count: int = 0
    universe_fingerprint: str
    constraint_fingerprint: str
    configuration_fingerprint: str
    result_fingerprint: Optional[str] = None
    is_baseline: bool = False
    dataset_version_id: Optional[int] = None
    dataset_name: Optional[str] = None
    dataset_version_label: Optional[str] = None
    dataset_invalidated: Optional[bool] = None
    validation_run_id: Optional[int] = None
    validation_method: Optional[str] = None
    regime_run_id: Optional[int] = None
    regime_definition_id: Optional[str] = None
    cost_diagnostic_run_id: Optional[int] = None
    overfitting_run_id: Optional[int] = None
    experiment_id: Optional[int] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    universe: Dict[str, Any] = Field(default_factory=dict)
    risk: Optional[Dict[str, Any]] = None
    budget: Optional[Dict[str, Any]] = None
    concentration: Optional[Dict[str, Any]] = None
    covariance: Optional[Dict[str, Any]] = None
    regimes: Optional[Dict[str, Any]] = None
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
    regime_run_name: Optional[str] = None
    regime_run_integrity: Optional[str] = None
    cost_run_name: Optional[str] = None
    cost_model_fingerprint: Optional[str] = None
    overfitting_name: Optional[str] = None
    overfitting_pbo: Optional[float] = None
    overfitting_universe_fp: Optional[str] = None


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    assets: int
    constraint_violations: int
    solver_failures: int
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
    weights: List[Dict[str, Any]] = Field(default_factory=list)
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)
    baseline: Dict[str, bool] = Field(default_factory=dict)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


__all__ = [
    "AssetInput", "RunCreate", "ExecuteRequest", "InvalidateRequest",
    "RunSummary", "RunFull", "RunListResponse", "LabSummary", "CompareEntry",
    "RunComparison", "DemoSeedResponse",
]
