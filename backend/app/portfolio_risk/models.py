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
    # Optional extra factor-shock scenarios appended to the sample library.
    custom_scenarios: List["ScenarioDefinition"] = Field(default_factory=list)
    # Optimization & Black-Litterman inputs (Phase 21.2).
    optimization_constraints: Optional["OptimizationConstraints"] = None
    black_litterman_views: Optional[List["BlackLittermanView"]] = None
    risk_aversion: Annotated[FiniteFloat, Field(gt=0.0, le=100.0)] = 2.5
    tau: Annotated[FiniteFloat, Field(gt=0.0, le=1.0)] = 0.05
    # Monte Carlo simulation config (Phase 21.3).
    simulation_config: Optional["PortfolioSimulationConfig"] = None

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


# --------------------------------------------------------------------------- #
# Factor model & scenario stress (Phase 21.1)
# --------------------------------------------------------------------------- #
class FactorDefinition(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    category: NonEmptyStr
    description: NonEmptyStr
    volatility: PositiveFloat
    is_sample: bool = True


class PortfolioFactorExposure(PortfolioModel):
    factor_id: NonEmptyStr
    name: NonEmptyStr
    exposure: FiniteFloat  # portfolio beta to the factor (Bᵀw)
    contribution_to_variance: FiniteFloat
    contribution_to_volatility: FiniteFloat
    percent_risk_contribution: FiniteFloat  # variance-share convention


class SpecificRiskContribution(PortfolioModel):
    variance: FiniteFloat
    contribution_to_volatility: FiniteFloat
    percent_risk_contribution: FiniteFloat


class FactorModelSummary(PortfolioModel):
    factor_variance: FiniteFloat
    specific_variance: FiniteFloat
    model_variance: FiniteFloat
    model_volatility: FiniteFloat


class ScenarioDefinition(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    factor_shocks: Dict[str, FiniteFloat]
    asset_shocks: Optional[Dict[str, FiniteFloat]] = None
    is_sample: bool = True


class ScenarioFactorImpact(PortfolioModel):
    factor_id: NonEmptyStr
    name: NonEmptyStr
    shock: FiniteFloat
    impact: FiniteFloat  # portfolio_beta_factor * shock_factor


class ScenarioAssetImpact(PortfolioModel):
    asset_id: NonEmptyStr
    name: NonEmptyStr
    weight: FiniteFloat
    impact: FiniteFloat  # asset return impact
    contribution: FiniteFloat  # weight * impact


class ScenarioResult(PortfolioModel):
    scenario_id: NonEmptyStr
    name: NonEmptyStr
    portfolio_return_impact: FiniteFloat
    factor_impact: List[ScenarioFactorImpact]
    asset_impact: List[ScenarioAssetImpact]
    worst_asset: NonEmptyStr
    best_asset: NonEmptyStr
    notes: List[NonEmptyStr]


# --------------------------------------------------------------------------- #
# Optimization & Black-Litterman (Phase 21.2)
# --------------------------------------------------------------------------- #
class OptimizationConstraints(PortfolioModel):
    min_weight: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] = 0.0
    max_weight: Annotated[FiniteFloat, Field(gt=0.0, le=1.0)] = 0.40
    target_return: Optional[FiniteFloat] = None
    target_volatility: Optional[PositiveFloat] = None
    turnover_penalty: Optional[Annotated[FiniteFloat, Field(ge=0.0)]] = None
    previous_weights: Optional[Dict[str, FiniteFloat]] = None

    @model_validator(mode="after")
    def _check(self) -> "OptimizationConstraints":
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight must be <= max_weight")
        return self


class OptimizedPortfolio(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    objective: NonEmptyStr
    weights: Dict[str, FiniteFloat]
    expected_return: FiniteFloat
    volatility: FiniteFloat
    sharpe_ratio: FiniteFloat
    turnover: FiniteFloat
    notes: List[NonEmptyStr]
    feasible: bool


class EffectiveConstraints(PortfolioModel):
    min_weight: FiniteFloat
    max_weight: FiniteFloat
    target_return: Optional[FiniteFloat] = None
    target_volatility: Optional[FiniteFloat] = None
    turnover_penalty: Optional[FiniteFloat] = None


class OptimizationResults(PortfolioModel):
    current_portfolio: OptimizedPortfolio
    equal_weight_portfolio: OptimizedPortfolio
    max_sharpe_portfolio: OptimizedPortfolio
    min_variance_portfolio: OptimizedPortfolio
    risk_parity_portfolio: OptimizedPortfolio
    target_return_portfolio: Optional[OptimizedPortfolio] = None
    target_volatility_portfolio: Optional[OptimizedPortfolio] = None
    candidate_count: int
    constraints: EffectiveConstraints
    notes: List[NonEmptyStr]


class BlackLittermanView(PortfolioModel):
    id: NonEmptyStr
    description: NonEmptyStr
    asset_weights: Dict[str, FiniteFloat]  # P-matrix row
    view_return: FiniteFloat  # q
    confidence: Annotated[FiniteFloat, Field(gt=0.0, le=1.0)]
    is_sample: bool = True


class AssetReturnView(PortfolioModel):
    asset_id: NonEmptyStr
    name: NonEmptyStr
    implied_return: FiniteFloat
    posterior_return: FiniteFloat
    prior_return: FiniteFloat


class BlackLittermanResult(PortfolioModel):
    risk_aversion: FiniteFloat
    tau: FiniteFloat
    returns: List[AssetReturnView]
    views: List[BlackLittermanView]
    bl_optimized_portfolio: OptimizedPortfolio
    notes: List[NonEmptyStr]


class RebalanceAssetDelta(PortfolioModel):
    asset_id: NonEmptyStr
    name: NonEmptyStr
    current_weight: FiniteFloat
    target_weight: FiniteFloat
    delta: FiniteFloat


class RebalanceAnalysis(PortfolioModel):
    target_portfolio_id: NonEmptyStr
    asset_deltas: List[RebalanceAssetDelta]
    absolute_turnover: FiniteFloat
    largest_increase: NonEmptyStr
    largest_decrease: NonEmptyStr
    note: NonEmptyStr


# --------------------------------------------------------------------------- #
# Monte Carlo & robustness (Phase 21.3)
# --------------------------------------------------------------------------- #
SimulationMethod = Literal["parametric_gaussian", "historical_bootstrap"]


class PortfolioSimulationConfig(PortfolioModel):
    horizon_days: Annotated[int, Field(gt=0, le=2520)] = 252
    num_paths: Annotated[int, Field(gt=0, le=5000)] = 500
    initial_value: PositiveFloat = 100000.0
    seed: int = 42
    drawdown_threshold: Annotated[FiniteFloat, Field(gt=-1.0, lt=0.0)] = -0.20
    method: SimulationMethod = "parametric_gaussian"


class MonteCarloFanPoint(PortfolioModel):
    day: int
    p05: FiniteFloat
    p25: FiniteFloat
    median: FiniteFloat
    p75: FiniteFloat
    p95: FiniteFloat


class MonteCarloPathPoint(PortfolioModel):
    day: int
    value: FiniteFloat


class MonteCarloSamplePath(PortfolioModel):
    path_id: int
    points: List[MonteCarloPathPoint]


class MonteCarloSummary(PortfolioModel):
    method: SimulationMethod
    seed: int
    horizon_days: int
    num_paths: int
    initial_value: FiniteFloat
    terminal_wealth_mean: FiniteFloat
    terminal_wealth_median: FiniteFloat
    terminal_wealth_p05: FiniteFloat
    terminal_wealth_p95: FiniteFloat
    probability_of_loss: FiniteFloat
    probability_drawdown_breach: FiniteFloat
    drawdown_threshold: FiniteFloat
    max_drawdown_mean: FiniteFloat
    max_drawdown_p05: FiniteFloat
    max_drawdown_p95: FiniteFloat
    simulated_var_95: FiniteFloat
    simulated_cvar_95: FiniteFloat
    fan_chart_points: List[MonteCarloFanPoint]
    sample_paths: List[MonteCarloSamplePath]
    notes: List[NonEmptyStr]


class SensitivityResult(PortfolioModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    expected_return: FiniteFloat
    volatility: FiniteFloat
    sharpe_ratio: FiniteFloat
    historical_var: FiniteFloat
    historical_cvar: FiniteFloat
    notes: List[NonEmptyStr]


class OptimizationRobustnessResult(PortfolioModel):
    portfolio_id: NonEmptyStr
    name: NonEmptyStr
    base_sharpe: FiniteFloat
    worst_case_sharpe: FiniteFloat
    sharpe_range: FiniteFloat
    rank_stability: FiniteFloat
    notes: List[NonEmptyStr]


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
    # Factor model & scenario stress (Phase 21.1).
    factors: List[FactorDefinition]
    factor_order: List[NonEmptyStr]
    factor_exposures: List[List[FiniteFloat]]  # assets × factors beta matrix
    factor_covariance_matrix: List[List[FiniteFloat]]
    factor_correlation_matrix: List[List[FiniteFloat]]
    portfolio_factor_exposure: List[PortfolioFactorExposure]
    specific_risk_contribution: SpecificRiskContribution
    factor_model: FactorModelSummary
    scenario_library: List[ScenarioDefinition]
    scenario_results: List[ScenarioResult]
    # Optimization & Black-Litterman (Phase 21.2).
    optimization_results: OptimizationResults
    black_litterman: BlackLittermanResult
    rebalance_analysis: RebalanceAnalysis
    # Monte Carlo & robustness (Phase 21.3).
    monte_carlo: MonteCarloSummary
    bootstrap_robustness: MonteCarloSummary
    assumption_sensitivity: List[SensitivityResult]
    optimization_robustness: List[OptimizationRobustnessResult]
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


# ``PortfolioAnalysisRequest.custom_scenarios`` forward-references
# ``ScenarioDefinition`` (defined below it), so resolve it now.
PortfolioAnalysisRequest.model_rebuild()
