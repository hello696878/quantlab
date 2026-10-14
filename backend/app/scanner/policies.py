"""Versioned, opt-in scanner declarations. No provider or executable formulas."""
from datetime import date, datetime, timezone
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
AssetId = Annotated[str, Field(strict=True, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")]


class Declaration(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VolatilityReference(Declaration):
    target: Finite = Field(gt=0, le=2)
    window: StrictInt = Field(default=60, ge=2, le=252)
    min_observations: StrictInt = Field(default=20, ge=2, le=252)
    periods_per_year: Literal[252] = 252

    @model_validator(mode="after")
    def minimum(self):
        if self.min_observations > self.window:
            raise ValueError("min_observations must not exceed window")
        return self


class NeutralisationPolicy(Declaration):
    schema_version: Literal["scanner_neutralisation_v1"] = "scanner_neutralisation_v1"
    mode: Literal["dollar", "sector", "beta"] = "dollar"
    missing: Literal["exclude", "refuse"] = "exclude"
    failed_rebalance: Literal["cash"] = "cash"
    gross_cap: Finite = Field(default=2.0, gt=0, le=10)
    beta_window: StrictInt = Field(default=60, ge=5, le=252)
    beta_min_observations: StrictInt = Field(default=20, ge=5, le=252)
    volatility: VolatilityReference | None = None

    @model_validator(mode="after")
    def minimum(self):
        if self.beta_min_observations > self.beta_window:
            raise ValueError("beta_min_observations must not exceed beta_window")
        return self


class AvailableObservation(Declaration):
    period: str = Field(min_length=10, max_length=10)
    available_at: str = Field(min_length=20, max_length=40)

    @field_validator("period")
    @classmethod
    def period_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("period must be a canonical YYYY-MM-DD session")
        return value

    @field_validator("available_at")
    @classmethod
    def aware(cls, value):
        if re.search(r"[.,]\d{7,}", value):
            raise ValueError("available_at supports at most six fractional digits")
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("available_at requires a UTC offset")
        try:
            return instant.astimezone(timezone.utc).isoformat()
        except OverflowError as exc:
            raise ValueError("available_at is outside the supported UTC range") from exc


class ExposureObservation(AvailableObservation):
    asset_id: AssetId
    sector: Annotated[str, Field(strict=True, min_length=1, max_length=40)] | None = None
    beta: Finite | None = Field(default=None, ge=-20, le=20)
    eligible: StrictBool
    liquidity: Finite = Field(ge=0, le=1)

    @field_validator("sector")
    @classmethod
    def label(cls, value):
        if value is not None and (value != value.strip() or not value.isprintable()):
            raise ValueError("sector must be an explicit printable nonblank label")
        return value


class FactorObservation(AvailableObservation):
    value: Finite = Field(ge=-1, le=10)


class ScannerInputs(Declaration):
    schema_version: Literal["scanner_declarations_v1"] = "scanner_declarations_v1"
    source: Literal["time_varying_declared"] = "time_varying_declared"
    exposures: list[ExposureObservation] | None = Field(default=None, max_length=10000)
    factor_returns: list[FactorObservation] | None = Field(default=None, max_length=1000)


class ExposureReport(Declaration):
    net: float
    gross: float
    sectors: dict[str, float]
    beta: float | None


class RebalanceDiagnostic(Declaration):
    date: str
    status: str
    reason: str | None
    eligible_count: int
    excluded: list[dict[str, str]]
    rank: int | None = None
    columns: int | None = None
    condition_number: float | None = None
    reconstruction_error: float | None = None
    support_rank: int | None = None
    raw: ExposureReport
    transformed: ExposureReport
    neutral: ExposureReport
    final: ExposureReport
    volatility_estimate: float | None = None
    volatility_target: float | None = None
    volatility_scale: float | None = None
    achieved_ex_ante: float | None = None
    cap_binding: bool = False
    constraint_error: float = 0.0
    outcome_date: str | None = None
    turnover: float = 0.0
    cost: float = 0.0
    gross_return: float = 0.0
    net_return: float = 0.0


class AdvancedResult(Declaration):
    policy: NeutralisationPolicy
    input_fingerprint: str
    exposure_provenance: str
    factor_provenance: str
    timing: str
    support_policy: str
    failed_rebalance: str
    diagnostics: list[RebalanceDiagnostic]
    total_rebalances: int
    diagnostics_truncated: bool
    latest_scores: list[dict[str, str | float | None]]
    realized_net_volatility: float
    caveats: list[str]
