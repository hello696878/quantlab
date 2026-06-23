"""
Typed Pydantic models for the Portfolio Risk Lab (Phase 21.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. Long-only by default; ``allow_short``
opts into negative weights. All data is static illustrative sample data.
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

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


class PortfolioModel(BaseModel):
    """Strict base model for stable, JSON-safe portfolio payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class PortfolioAsset(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    ticker: NonEmptyStr
    asset_class: NonEmptyStr
    region: NonEmptyStr
    weight: FiniteFloat
    expected_return: FiniteFloat  # annual, decimal (0.08 == 8%)
    volatility: PositiveFloat  # annual, decimal (must be > 0)
    sample_return_series: List[FiniteFloat] = Field(min_length=12)


class StressScenario(PortfolioModel):
    name: NonEmptyStr
    description: Optional[NonEmptyStr] = None
    # asset id -> shock return (decimal, e.g. -0.12 for a -12% move)
    shocks: Dict[str, FiniteFloat]


class PortfolioAnalysisRequest(PortfolioModel):
    assets: List[PortfolioAsset] = Field(min_length=1)
    risk_free_rate: FiniteFloat = 0.02
    confidence_level: Annotated[FiniteFloat, Field(ge=0.5, le=0.999)] = 0.95
    stress_scenario: Optional[StressScenario] = None
    allow_short: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "PortfolioAnalysisRequest":
        ids = [a.id for a in self.assets]
        if len(set(ids)) != len(ids):
            raise ValueError("asset ids must be unique")
        series_len = len(self.assets[0].sample_return_series)
        for a in self.assets:
            if len(a.sample_return_series) != series_len:
                raise ValueError(
                    "all assets must share the same sample_return_series length"
                )
            if not self.allow_short and a.weight < 0:
                raise ValueError(
                    "negative weights are not allowed in long-only mode "
                    "(set allow_short=true to permit them)"
                )
        if sum(a.weight for a in self.assets) <= 0:
            raise ValueError("portfolio weights must sum to a positive number")
        if self.stress_scenario:
            unknown = sorted(set(self.stress_scenario.shocks) - set(ids))
            if unknown:
                raise ValueError(
                    f"stress scenario references unknown asset ids: {unknown}"
                )
        return self


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class FrontierPoint(PortfolioModel):
    expected_return: FiniteFloat
    volatility: FiniteFloat
    sharpe: FiniteFloat
    weights: Dict[str, FiniteFloat]


class NamedPortfolio(PortfolioModel):
    label: NonEmptyStr
    weights: Dict[str, FiniteFloat]
    expected_return: FiniteFloat
    volatility: FiniteFloat
    sharpe: FiniteFloat


class AssetRiskContribution(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    weight: FiniteFloat
    marginal_contribution: FiniteFloat
    component_contribution: FiniteFloat
    percent_contribution: FiniteFloat


class StressResult(PortfolioModel):
    name: NonEmptyStr
    asset_pnl: Dict[str, FiniteFloat]
    portfolio_pnl: FiniteFloat


class PortfolioAnalysisResponse(PortfolioModel):
    asset_order: List[NonEmptyStr]
    asset_names: Dict[str, NonEmptyStr]
    normalized_weights: Dict[str, FiniteFloat]
    expected_return: FiniteFloat
    volatility: FiniteFloat
    sharpe_ratio: FiniteFloat
    covariance_matrix: List[List[FiniteFloat]]
    correlation_matrix: List[List[FiniteFloat]]
    asset_risk_contributions: List[AssetRiskContribution]
    historical_var: FiniteFloat
    historical_cvar: FiniteFloat
    var_horizon: NonEmptyStr
    confidence_level: FiniteFloat
    risk_free_rate: FiniteFloat
    stress_result: Optional[StressResult] = None
    efficient_frontier: List[FrontierPoint]
    min_variance_portfolio: NamedPortfolio
    risk_parity_portfolio: NamedPortfolio
    notes: List[NonEmptyStr]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr


class SamplePortfolioResponse(PortfolioModel):
    assets: List[PortfolioAsset]
    risk_free_rate: FiniteFloat
    confidence_level: FiniteFloat
    stress_scenario: Optional[StressScenario] = None
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
