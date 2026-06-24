"""
Portfolio Risk Lab (Phase 21.0).

A self-contained, **deterministic static-sample** portfolio analytics lab:
expected return, volatility, Sharpe, covariance/correlation, marginal &
component risk contributions, historical VaR/CVaR, stress P&L, a deterministic
efficient frontier, a minimum-variance portfolio, and a basic risk-parity
portfolio.

This is separate from ``app.portfolio`` (the price-based multi-asset backtest).
It never fetches live data, makes no network calls, and is educational only —
not investment advice and not a production risk engine.
"""

from app.portfolio_risk.factors import (
    FACTOR_IDS,
    compute_factor_block,
    compute_scenarios,
    factor_definitions,
    scenario_library,
)
from app.portfolio_risk.models import (
    AssetRiskContribution,
    BlackLittermanResult,
    BlackLittermanView,
    FactorDefinition,
    FactorModelSummary,
    FrontierPoint,
    NamedPortfolio,
    OptimizationConstraints,
    OptimizationResults,
    OptimizedPortfolio,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioAsset,
    PortfolioFactorExposure,
    RebalanceAnalysis,
    SamplePortfolioResponse,
    ScenarioDefinition,
    ScenarioResult,
    SpecificRiskContribution,
    StressResult,
    StressScenario,
)
from app.portfolio_risk.models import (
    MonteCarloSummary,
    OptimizationRobustnessResult,
    PortfolioSimulationConfig,
    SensitivityResult,
)
from app.portfolio_risk.optimize import (
    build_black_litterman,
    build_optimization,
    build_rebalance,
    sample_bl_views,
)
from app.portfolio_risk.simulate import (
    build_optimization_robustness,
    build_sensitivity,
    build_simulations,
)
from app.portfolio_risk.sample import build_sample_response, sample_assets
from app.portfolio_risk.service import DISCLAIMER, analyze_portfolio

__all__ = [
    "AssetRiskContribution",
    "FactorDefinition",
    "FactorModelSummary",
    "FrontierPoint",
    "NamedPortfolio",
    "PortfolioAnalysisRequest",
    "PortfolioAnalysisResponse",
    "PortfolioAsset",
    "PortfolioFactorExposure",
    "SamplePortfolioResponse",
    "ScenarioDefinition",
    "ScenarioResult",
    "SpecificRiskContribution",
    "StressResult",
    "StressScenario",
    "FACTOR_IDS",
    "compute_factor_block",
    "compute_scenarios",
    "factor_definitions",
    "scenario_library",
    "build_sample_response",
    "sample_assets",
    "DISCLAIMER",
    "analyze_portfolio",
]
