"""
Deterministic static-sample instruments for the Microstructure Lab (Phase 25.0).

Four illustrative instruments (BTCUSDT, SPY, CL futures, TSM equity), each with a
hand-parameterised limit-order book, a deterministic trade tape, a parent
execution order with sample child fills, and an intraday volume curve. Identical
every run and every test. Not live data, not advice.
"""

from __future__ import annotations

import math
from typing import List

from app.microstructure.models import (
    ExecutionFillInput,
    ExecutionOrderInput,
    MarketMicrostructureAnalysisRequest,
    MicrostructureSampleResponse,
    OrderBookLevelInput,
    OrderBookSnapshotInput,
    TradePrintInput,
)

DISCLAIMER = (
    "Static illustrative sample data. Market microstructure and execution analytics "
    "are educational and not investment, trading, order-routing, legal, tax, or "
    "risk-management advice."
)


def _build(
    symbol: str,
    mid: float,
    tick: float,
    levels: int,
    bid_base: float,
    ask_base: float,
    bid_growth: float,
    ask_growth: float,
    parent_side: str,
    parent_qty: float,
    adv: float,
    vol_bps: float,
    n_trades: int = 30,
) -> MarketMicrostructureAnalysisRequest:
    best_bid = mid - tick / 2.0
    best_ask = mid + tick / 2.0

    bids = [
        OrderBookLevelInput(
            price=round(best_bid - i * tick, 6),
            size=round(bid_base + i * bid_growth, 6),
        )
        for i in range(levels)
    ]
    asks = [
        OrderBookLevelInput(
            price=round(best_ask + i * tick, 6),
            size=round(ask_base + i * ask_growth, 6),
        )
        for i in range(levels)
    ]

    # Deterministic trade tape oscillating inside the spread, with a buy bias.
    trades: List[TradePrintInput] = []
    for i in range(n_trades):
        price = round(mid + (tick / 2.0) * math.sin(i * 0.7), 6)
        size = round(0.5 + 0.5 * ((i * 7) % 5), 6)
        side = "buy" if (i * 3) % 5 < 3 else "sell"  # ~60% buyer-initiated
        trades.append(
            TradePrintInput(timestamp=f"T+{i:02d}", price=max(price, tick), size=size, side=side)
        )

    # Parent buy order filled with a deterministic impact ramp off the touch.
    n_fills = 8
    fills: List[ExecutionFillInput] = []
    qty_each = parent_qty / n_fills
    for i in range(n_fills):
        if parent_side == "buy":
            price = round(best_ask + tick * i * 0.5, 6)  # walking up
        else:
            price = round(best_bid - tick * i * 0.5, 6)  # walking down
        fills.append(
            ExecutionFillInput(
                timestamp=f"F+{i:02d}",
                price=max(price, tick),
                quantity=round(qty_each, 6),
                liquidity_flag="taker" if i % 2 == 0 else "maker",
            )
        )

    # U-shaped intraday volume curve (10 buckets).
    volume_curve = [round(1.0 + 0.8 * (abs(b - 4.5) / 4.5), 4) for b in range(10)]

    return MarketMicrostructureAnalysisRequest(
        order_book=OrderBookSnapshotInput(symbol=symbol, timestamp="2025-01-02T15:30:00Z", bids=bids, asks=asks),
        trades=trades,
        execution_order=ExecutionOrderInput(
            symbol=symbol,
            side=parent_side,
            quantity=parent_qty,
            arrival_price=round(mid, 6),
            benchmark_price=round(mid, 6),
            participation_limit=0.10,
        ),
        fills=fills,
        volume_curve=volume_curve,
        average_daily_volume=adv,
        volatility_bps=vol_bps,
        impact_coefficient=0.1,
    )


def sample_requests() -> List[MarketMicrostructureAnalysisRequest]:
    return [
        # BTCUSDT — wide-ish tick, bid-heavy book.
        _build("BTCUSDT_SAMPLE", 65000.0, 1.0, 10, 1.2, 1.0, 0.3, 0.25, "buy", 10.0, 25000.0, 220.0),
        # SPY — penny tick, balanced book.
        _build("SPY_SAMPLE", 500.0, 0.01, 10, 1800.0, 1750.0, 250.0, 250.0, "buy", 50000.0, 70_000_000.0, 90.0),
        # CL futures — bigger tick, ask-heavy book.
        _build("CL_SAMPLE", 75.0, 0.01, 10, 40.0, 55.0, 8.0, 12.0, "sell", 2000.0, 300_000.0, 180.0),
        # TSM equity — penny tick, bid-heavy book.
        _build("TSM_SAMPLE", 180.0, 0.01, 10, 900.0, 800.0, 120.0, 110.0, "buy", 30000.0, 25_000_000.0, 130.0),
    ]


def build_sample_response() -> MicrostructureSampleResponse:
    return MicrostructureSampleResponse(
        instruments=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Four illustrative instruments (BTCUSDT, SPY, CL futures, TSM equity) with "
            "hand-parameterised order books, deterministic trade tapes, parent orders, "
            "sample fills, and intraday volume curves.",
            "Edit/select an instrument in the lab to explore the analytics.",
            "Not a live order book or trade feed, and not investment, trading, or "
            "order-routing advice.",
        ],
    )
