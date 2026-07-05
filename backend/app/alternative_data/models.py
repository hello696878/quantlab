"""
Typed Pydantic models for the Alternative Data, News Sentiment & Signal Decay
Lab (30.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment, trading, legal, tax, or risk-management
advice; never live news, social media, market data, scraping, LLM APIs, or paid
data providers.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegFloat = Annotated[FiniteFloat, Field(ge=0)]
UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
SignedUnitFloat = Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]
SourceType = Literal["news", "social", "earnings", "macro", "product", "regulatory", "supply_chain"]


class AdModel(BaseModel):
    """Strict base model for stable, JSON-safe alternative-data payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class AlternativeDataEventInput(AdModel):
    event_id: NonEmptyStr
    timestamp: NonEmptyStr
    symbol: NonEmptyStr
    source_type: SourceType
    headline: NonEmptyStr
    sentiment_score: SignedUnitFloat
    event_intensity: UnitFloat
    novelty_score: UnitFloat
    source_reliability: UnitFloat
    relevance_score: UnitFloat
    observed_return_1d: FiniteFloat
    observed_return_5d: FiniteFloat
    observed_return_20d: FiniteFloat
    publication_lag_minutes: NonNegFloat
    feature_available_timestamp: NonEmptyStr

    @model_validator(mode="after")
    def _check(self) -> "AlternativeDataEventInput":
        # Timestamps are ISO-8601 strings on a static sample timeline, so a
        # lexicographic comparison is a deterministic ordering check.
        if self.feature_available_timestamp < self.timestamp:
            raise ValueError(
                "feature_available_timestamp must be >= timestamp "
                f"({self.feature_available_timestamp} < {self.timestamp})"
            )
        return self


class SignalDecayPointInput(AdModel):
    horizon_days: PositiveFloat
    signal_value: FiniteFloat
    realized_return: FiniteFloat


class AlternativeDataScenarioInput(AdModel):
    name: NonEmptyStr
    sentiment_shock: FiniteFloat = 0.0
    intensity_shock: FiniteFloat = 0.0
    novelty_shock: FiniteFloat = 0.0
    reliability_shock: FiniteFloat = 0.0
    publication_lag_shock: NonNegFloat = 1.0
    noise_multiplier: NonNegFloat = 1.0
    event_count_multiplier: NonNegFloat = 1.0


class AlternativeDataAnalysisRequest(AdModel):
    sample_id: NonEmptyStr
    sample_name: NonEmptyStr
    events: List[AlternativeDataEventInput] = Field(min_length=2)
    # Documented model constants (editable assumptions, not fitted parameters).
    lambda_novelty: NonNegFloat = 0.5
    gamma_freshness_per_hour: NonNegFloat = 0.1
    custom_decay_points: Optional[List[SignalDecayPointInput]] = None
    custom_scenarios: Optional[List[AlternativeDataScenarioInput]] = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class SampleSummary(AdModel):
    sample_id: NonEmptyStr
    sample_name: NonEmptyStr
    event_count: int
    symbols: List[NonEmptyStr]
    source_types: List[NonEmptyStr]


class AlternativeDataEventRow(AdModel):
    event_id: NonEmptyStr
    timestamp: NonEmptyStr
    symbol: NonEmptyStr
    source_type: SourceType
    headline: NonEmptyStr
    sentiment_score: FiniteFloat
    event_intensity: FiniteFloat
    novelty_score: FiniteFloat
    source_reliability: FiniteFloat
    relevance_score: FiniteFloat
    weighted_sentiment: FiniteFloat
    novelty_adjusted_signal: FiniteFloat
    freshness: FiniteFloat
    lag_adjusted_signal: FiniteFloat
    observed_return_1d: FiniteFloat
    observed_return_5d: FiniteFloat
    observed_return_20d: FiniteFloat
    leakage_flag: bool


class SentimentAnalysis(AdModel):
    average_sentiment: FiniteFloat
    weighted_sentiment_average: FiniteFloat
    positive_event_count: int
    negative_event_count: int
    neutral_event_count: int
    alpha_score: FiniteFloat


class FreshnessAnalysis(AdModel):
    average_publication_lag_minutes: FiniteFloat
    average_freshness: FiniteFloat
    stale_event_count: int
    notes: List[NonEmptyStr]


class LeakageGuard(AdModel):
    leakage_count: int
    leakage_rate: FiniteFloat
    has_leakage: bool
    notes: List[NonEmptyStr]


class SignalQuality(AdModel):
    information_coefficient_1d: Optional[FiniteFloat] = None
    information_coefficient_5d: Optional[FiniteFloat] = None
    information_coefficient_20d: Optional[FiniteFloat] = None
    hit_rate_1d: FiniteFloat
    hit_rate_5d: FiniteFloat
    hit_rate_20d: FiniteFloat
    signal_to_noise_score: FiniteFloat
    reliability_weighted_quality: FiniteFloat
    notes: List[NonEmptyStr]


class EventStudyPoint(AdModel):
    horizon_days: FiniteFloat
    average_forward_return: FiniteFloat
    average_signal: FiniteFloat
    ic_at_horizon: Optional[FiniteFloat] = None


class SignalDecayPoint(AdModel):
    horizon_days: FiniteFloat
    decay_correlation: Optional[FiniteFloat] = None
    signal_half_life_estimate: Optional[FiniteFloat] = None


class RiskRegime(AdModel):
    regime_id: NonEmptyStr
    regime_label: NonEmptyStr
    score: FiniteFloat
    drivers: List[NonEmptyStr]
    explanation: NonEmptyStr


class AltDataScenarioResult(AdModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    average_sentiment: FiniteFloat
    average_intensity: FiniteFloat
    average_novelty: FiniteFloat
    average_reliability: FiniteFloat
    average_freshness: FiniteFloat
    alpha_score: FiniteFloat
    information_coefficient_5d: Optional[FiniteFloat] = None
    hit_rate_5d: FiniteFloat
    leakage_count: int
    decay_5d: Optional[FiniteFloat] = None
    decay_20d: Optional[FiniteFloat] = None
    regime_label: NonEmptyStr
    notes: List[NonEmptyStr]


class AlternativeDataAnalysisResponse(AdModel):
    data_status: Literal["static_sample"] = "static_sample"
    sample_summary: SampleSummary
    event_table: List[AlternativeDataEventRow]
    sentiment_analysis: SentimentAnalysis
    freshness_analysis: FreshnessAnalysis
    leakage_guard: LeakageGuard
    signal_quality: SignalQuality
    event_study: List[EventStudyPoint]
    signal_decay: List[SignalDecayPoint]
    risk_regime: RiskRegime
    scenario_results: List[AltDataScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class AlternativeDataSampleResponse(AdModel):
    samples: List[AlternativeDataAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
