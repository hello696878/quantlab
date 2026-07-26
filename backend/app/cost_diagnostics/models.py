"""Pydantic v2 request/response models for the Cost Diagnostics Lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.experiment_registry.models import _validate_structured


class ObservationInput(BaseModel):
    """One trade-level or period-level observation (validated in core)."""
    model_config = ConfigDict(extra="forbid")

    # shared
    candidate_id: str = Field(min_length=1, max_length=64)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cost_inputs: Optional[Dict[str, Any]] = None
    # trade-level
    trade_id: Optional[str] = Field(default=None, max_length=64)
    instrument: Optional[str] = Field(default=None, max_length=32)
    side: Optional[str] = Field(default=None, max_length=8)
    entry_timestamp: Optional[str] = Field(default=None, max_length=40)
    exit_timestamp: Optional[str] = Field(default=None, max_length=40)
    entry_price: Optional[Any] = None
    exit_price: Optional[Any] = None
    quantity: Optional[Any] = None
    contract_multiplier: Optional[Any] = None
    currency: Optional[str] = Field(default=None, max_length=8)
    gross_pnl: Optional[Any] = None
    # period-level
    observation_id: Optional[str] = Field(default=None, max_length=64)
    timestamp: Optional[str] = Field(default=None, max_length=40)
    gross_return: Optional[Any] = None
    turnover: Optional[Any] = None
    traded_notional: Optional[Any] = None

    @field_validator("metadata")
    @classmethod
    def _structured(cls, v: Any) -> Any:
        return _validate_structured(v)

    @field_validator("cost_inputs")
    @classmethod
    def _structured_inputs(cls, v: Any) -> Any:
        return None if v is None else _validate_structured(v)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    observation_type: str = Field(min_length=1, max_length=10)
    observations: List[ObservationInput] = Field(min_length=1, max_length=2000)
    tick_size: Optional[Any] = None
    commission: Optional[Dict[str, Any]] = None
    spread: Optional[Dict[str, Any]] = None
    slippage: Optional[Dict[str, Any]] = None
    impact: Optional[Dict[str, Any]] = None
    participation_threshold: Optional[Any] = None
    sensitivity_grid: Optional[Dict[str, Any]] = None
    capacity_scales: Optional[List[Any]] = Field(default=None, max_length=16)
    integer_contracts: bool = False
    liquidity: Optional[Dict[str, Any]] = None
    dataset_version_id: Optional[int] = Field(default=None, ge=1)
    validation_run_id: Optional[int] = Field(default=None, ge=1)
    overfitting_run_id: Optional[int] = Field(default=None, ge=1)
    regime_run_id: Optional[int] = Field(default=None, ge=1)
    regime_definition_id: Optional[str] = Field(default=None, max_length=64)
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

    @field_validator("commission", "spread", "slippage", "impact", "liquidity")
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
    observation_type: str
    candidate_count: int
    observation_count: int
    currency: Optional[str] = None
    integrity_status: str
    completeness_status: str
    gross_total: Optional[float] = None
    net_total: Optional[float] = None
    total_cost: Optional[float] = None
    participation_warning_count: int = 0
    unavailable_input_count: int = 0
    universe_fingerprint: str
    cost_model_fingerprint: str
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
    regime_run_id: Optional[int] = None
    regime_definition_id: Optional[str] = None
    feature_diagnostics_run_id: Optional[int] = None
    meta_label_run_id: Optional[int] = None
    experiment_id: Optional[int] = None
    error_message: Optional[str] = None


class RunFull(RunSummary):
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    aggregates: Optional[Dict[str, Any]] = None
    breakeven: Optional[Dict[str, Any]] = None
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
    overfitting_name: Optional[str] = None
    overfitting_pbo: Optional[float] = None
    overfitting_psr: Optional[float] = None
    overfitting_dsr: Optional[float] = None
    overfitting_universe_fp: Optional[str] = None
    regime_run_name: Optional[str] = None
    regime_run_integrity: Optional[str] = None
    feature_run_name: Optional[str] = None
    feature_run_integrity: Optional[str] = None
    meta_label_run_name: Optional[str] = None


class RunListResponse(BaseModel):
    items: List[RunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabSummary(BaseModel):
    runs: int
    completed: int
    observations: int
    participation_warnings: int
    incomplete_input_observations: int
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
    fingerprint_match: Dict[str, bool] = Field(default_factory=dict)
    baseline: Dict[str, bool] = Field(default_factory=dict)


class DemoSeedResponse(BaseModel):
    created_runs: int
    skipped_existing: int


__all__ = [
    "ObservationInput", "RunCreate", "ExecuteRequest", "InvalidateRequest",
    "RunSummary", "RunFull", "RunListResponse", "LabSummary", "CompareEntry",
    "RunComparison", "DemoSeedResponse",
]
