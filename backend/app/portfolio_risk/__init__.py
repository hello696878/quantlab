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

from app.portfolio_risk.models import (
    AssetRiskContribution,
    FrontierPoint,
    NamedPortfolio,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioAsset,
    SamplePortfolioResponse,
    StressResult,
    StressScenario,
)
from app.portfolio_risk.sample import build_sample_response, sample_assets
from app.portfolio_risk.service import DISCLAIMER, analyze_portfolio

__all__ = [
    "AssetRiskContribution",
    "FrontierPoint",
    "NamedPortfolio",
    "PortfolioAnalysisRequest",
    "PortfolioAnalysisResponse",
    "PortfolioAsset",
    "SamplePortfolioResponse",
    "StressResult",
    "StressScenario",
    "build_sample_response",
    "sample_assets",
    "DISCLAIMER",
    "analyze_portfolio",
]
