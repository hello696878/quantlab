"""Bounded, explicit input contract. Returns are outcomes, never signals."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Text = Annotated[str, Field(min_length=1, max_length=200)]
Fingerprint = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]
Basis = Literal["gross", "net_of_strategy_costs", "partially_costed", "unknown"]


def timestamp(value: str) -> str:
    """Naive ISO dates/times explicitly denote UTC; aware times normalize to UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(
        timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Definition(StrictModel):
    strategy_id: Id
    strategy_name: Text
    source_type: Literal["supplied"]
    source_run_id: Id | None = None
    source_fingerprint: Fingerprint
    configuration_fingerprint: Fingerprint
    dataset_identity: Text
    dataset_version_id: PositiveId | None = None
    return_convention: Literal["simple_arithmetic"]
    gross_or_net: Basis
    frequency: Literal["daily", "weekly", "monthly", "hourly", "irregular"]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3,8}$")]
    leverage_convention: Literal["already_in_returns", "unlevered", "unknown"]
    exposure_convention: Literal["strategy_return_weight"]
    availability_policy: Literal["outcome_at_or_after_period_end"]
    configuration_available_at: str
    observation_start: str
    observation_end: str
    metadata: dict[Id, Annotated[str, Field(max_length=200)]] = Field(
        default_factory=dict, max_length=20)

    _dates = field_validator("configuration_available_at", "observation_start",
                             "observation_end")(timestamp)

    @model_validator(mode="after")
    def window(self):
        if self.observation_end <= self.observation_start:
            raise ValueError("observation_end must follow observation_start")
        return self


class Observation(StrictModel):
    strategy_id: Id
    period_start: str
    period_end: str
    return_value: Annotated[Number, Field(gt=-1, le=100)]
    gross_or_net: Basis
    information_available_at: str
    turnover: Annotated[Number, Field(ge=0, le=1000)] | None = None
    cost_return: Annotated[Number, Field(ge=0, le=100)] | None = None
    gross_exposure: Annotated[Number, Field(ge=0, le=1000)] | None = None
    net_exposure: Annotated[Number, Field(ge=-1000, le=1000)] | None = None
    source_observation_id: Id | None = None

    _dates = field_validator("period_start", "period_end", "information_available_at")(timestamp)

    @model_validator(mode="after")
    def interval(self):
        if self.period_end <= self.period_start:
            raise ValueError("period_end must follow period_start")
        return self


class WeightPolicy(StrictModel):
    mode: Literal["equal_weight", "user_static"] = "equal_weight"
    weights: dict[Id, Annotated[Number, Field(ge=0, le=10)]] = Field(default_factory=dict, max_length=12)
    normalization: Literal["require_sum_to_one", "normalize_by_sum", "normalize_by_gross", "none"] = "require_sum_to_one"
    negative_weight_policy: Literal["reject"] = "reject"
    alignment: Literal["strict_intersection"] = "strict_intersection"
    rebalance_policy: Literal["static_return_reference"] = "static_return_reference"
    initial_build: Literal["unavailable", "zero_prior_weights"] = "unavailable"
    allocation_cost_policy: Literal["not_modeled"] = "not_modeled"

    @model_validator(mode="after")
    def mode_weights(self):
        if self.mode == "equal_weight" and self.weights:
            raise ValueError("equal_weight must not include user weights")
        if self.mode == "user_static" and not self.weights:
            raise ValueError("user_static requires one weight per strategy")
        return self


class Scenario(StrictModel):
    label: Text
    policy: WeightPolicy


class AnalysisPolicy(StrictModel):
    pairwise_alignment: Literal["strict_intersection", "pairwise_complete"] = "strict_intersection"
    matrix_method: Literal["pearson", "spearman"] = "pearson"
    minimum_samples: Annotated[int, Field(strict=True, ge=3, le=100)] = 4
    tail_quantile: Annotated[Number, Field(gt=0, lt=0.5)] = 0.1
    tail_minimum_samples: Annotated[int, Field(strict=True, ge=10, le=200)] = 20
    tail_ties: Literal["inclusive_linear_quantile"] = "inclusive_linear_quantile"
    severe_drawdown: Annotated[Number, Field(gt=-1, lt=0)] = -0.1
    rare_regime_minimum: Annotated[int, Field(strict=True, ge=10, le=200)] = 10
    correction: Literal["holm"] = "holm"
    alpha: Annotated[Number, Field(gt=0, lt=1)] = 0.05
    tolerance: Annotated[Number, Field(ge=1e-12, le=1e-8)] = 1e-10
    bootstrap: Literal["deferred"] = "deferred"


class RegimeLink(StrictModel):
    run_id: PositiveId
    definition_id: Id


class ValidationLink(StrictModel):
    run_id: PositiveId
    split_label: Text


class RunCreate(StrictModel):
    name: Text
    description: Annotated[str, Field(max_length=2000)] = ""
    definitions: list[Definition] = Field(min_length=2, max_length=12)
    observations: list[Observation] = Field(min_length=4, max_length=24000)
    policy: WeightPolicy = Field(default_factory=WeightPolicy)
    analysis: AnalysisPolicy = Field(default_factory=AnalysisPolicy)
    weights_available_at: str
    regime: RegimeLink | None = None
    validation: ValidationLink | None = None
    scenarios: list[Scenario] = Field(default_factory=list, max_length=12)

    _dates = field_validator("weights_available_at")(timestamp)

    @model_validator(mode="after")
    def streams(self):
        definitions = {d.strategy_id: d for d in self.definitions}
        if len(definitions) != len(self.definitions):
            raise ValueError("duplicate strategy IDs")
        if len({(d.frequency, d.currency) for d in self.definitions}) != 1:
            raise ValueError("frequency and currency must match; no automatic conversion")
        by_id: dict[str, list[Observation]] = {k: [] for k in definitions}
        for row in self.observations:
            if row.strategy_id not in definitions:
                raise ValueError("observation references an unknown strategy")
            d = definitions[row.strategy_id]
            if row.gross_or_net != d.gross_or_net:
                raise ValueError("observation cost basis differs from strategy definition")
            if row.period_start < d.observation_start or row.period_end > d.observation_end:
                raise ValueError("observation outside declared window")
            by_id[row.strategy_id].append(row)
        for rows in by_id.values():
            rows.sort(key=lambda r: (r.period_start, r.period_end))
            if not 2 <= len(rows) <= 2000:
                raise ValueError("each strategy requires 2-2000 observations")
            if any(b.period_start < a.period_end for a, b in zip(rows, rows[1:])):
                raise ValueError("duplicate or overlapping strategy periods")
        self.definitions.sort(key=lambda d: d.strategy_id)
        self.observations.sort(key=lambda r: (r.strategy_id, r.period_start, r.period_end))
        return self


class ExecuteRequest(StrictModel):
    create_experiment: bool = False


class InvalidateRequest(StrictModel):
    reason: Annotated[str, Field(min_length=1, max_length=500)]
