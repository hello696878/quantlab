"""
Portfolio Risk Lab API routes (Phase 21.0).

    GET  /portfolio-risk/sample    — deterministic 8-asset sample portfolio
    POST /portfolio-risk/analyze   — full risk analytics for a portfolio

Static illustrative sample data only — no live data, no network calls, no
trading, no investment advice. Validation errors return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.portfolio_risk.models import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    SamplePortfolioResponse,
)
from app.portfolio_risk.sample import build_sample_response
from app.portfolio_risk.service import analyze_portfolio

router = APIRouter(prefix="/portfolio-risk", tags=["portfolio-risk"])


@router.get(
    "/sample",
    response_model=SamplePortfolioResponse,
    summary="Deterministic sample portfolio",
    description=(
        "Return the static illustrative 8-asset sample portfolio (deterministic "
        "monthly return series, fixed seed). Educational only — not advice."
    ),
)
def get_sample() -> SamplePortfolioResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=PortfolioAnalysisResponse,
    summary="Analyse a portfolio's risk",
    description=(
        "Compute expected return, volatility, Sharpe, covariance/correlation, "
        "risk contributions, historical VaR/CVaR, optional stress P&L, a "
        "deterministic efficient frontier, the minimum-variance portfolio, and a "
        "basic risk-parity portfolio. Static sample data; not investment advice."
    ),
)
def analyze(request: PortfolioAnalysisRequest) -> PortfolioAnalysisResponse:
    return analyze_portfolio(request)
