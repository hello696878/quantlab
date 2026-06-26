"""
Crypto Perpetual Futures Funding & Basis Lab API routes (Phase 26.0).

    GET  /crypto-derivatives/sample    — deterministic sample crypto markets
    POST /crypto-derivatives/analyze   — basis / funding / position / carry analytics

Static illustrative sample data only — no live exchange data, no live crypto
prices, no network calls, no broker/exchange integration, no order submission, no
trading, and no investment / trading / liquidation advice. Validation errors
return 422 automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.crypto_derivatives.models import (
    CryptoDerivativesAnalysisRequest,
    CryptoDerivativesAnalysisResponse,
    CryptoDerivativesSampleResponse,
)
from app.crypto_derivatives.sample import build_sample_response
from app.crypto_derivatives.service import analyze_crypto_derivatives

router = APIRouter(prefix="/crypto-derivatives", tags=["crypto-derivatives"])


@router.get(
    "/sample",
    response_model=CryptoDerivativesSampleResponse,
    summary="Deterministic sample crypto markets",
    description=(
        "Return the static illustrative sample crypto markets (BTCUSDT perp, "
        "ETHUSDT perp, SOLUSDT perp, BTC quarterly futures) with spot / index / "
        "perp-mark snapshots, dated futures curves, funding rates, and sample "
        "positions. Educational only — not advice, not live data."
    ),
)
def get_sample() -> CryptoDerivativesSampleResponse:
    return build_sample_response()


@router.post(
    "/analyze",
    response_model=CryptoDerivativesAnalysisResponse,
    summary="Analyse a crypto perp / futures market",
    description=(
        "Compute spot/perp/dated-futures basis, funding mechanics and annualized "
        "funding yield, long/short funding P&L, a cash-and-carry example, position "
        "margin / liquidation approximation, a funding-regime classification, and "
        "funding/basis stress scenarios. Static sample data; not investment, "
        "trading, or liquidation advice."
    ),
)
def analyze(request: CryptoDerivativesAnalysisRequest) -> CryptoDerivativesAnalysisResponse:
    return analyze_crypto_derivatives(request)
