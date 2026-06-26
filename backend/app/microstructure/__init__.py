"""
Market Microstructure & Execution Lab (Phase 25.0).

A self-contained, **deterministic static-sample** microstructure / execution
analytics lab: limit-order-book summary (spread, depth, imbalance, microprice),
trade-tape analytics (VWAP / TWAP / trade imbalance), execution analytics
(implementation shortfall, slippage, participation, market-impact approximation),
a hypothetical execution-schedule comparison, and liquidity stress scenarios.

It never fetches live order books or trades, makes no network calls, submits no
orders, and is educational only — not investment, trading, order-routing, legal,
tax, or risk-management advice, and not a production execution system.
"""

from app.microstructure.models import (
    ExecutionOrderInput,
    MarketMicrostructureAnalysisRequest,
    MarketMicrostructureAnalysisResponse,
    OrderBookLevelInput,
    OrderBookSnapshotInput,
    OrderFlowToxicityResult,
    QuoteUpdateInput,
    SignedTradeInput,
    TCAAttributionRow,
    TCAResult,
    ToxicityConfig,
    TradePrintInput,
)
from app.microstructure.sample import build_sample_response, sample_requests
from app.microstructure.service import DISCLAIMER, analyze_microstructure
from app.microstructure.toxicity import analyze_order_flow_toxicity

__all__ = [
    "ExecutionOrderInput",
    "MarketMicrostructureAnalysisRequest",
    "MarketMicrostructureAnalysisResponse",
    "OrderBookLevelInput",
    "OrderBookSnapshotInput",
    "OrderFlowToxicityResult",
    "QuoteUpdateInput",
    "SignedTradeInput",
    "TCAAttributionRow",
    "TCAResult",
    "ToxicityConfig",
    "TradePrintInput",
    "build_sample_response",
    "sample_requests",
    "DISCLAIMER",
    "analyze_microstructure",
    "analyze_order_flow_toxicity",
]
