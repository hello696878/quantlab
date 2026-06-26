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
    QuoteUpdateInput,
    SignedTradeInput,
    ToxicityConfig,
    TradePrintInput,
)

DISCLAIMER = (
    "Static illustrative sample data. Market microstructure and execution analytics "
    "are educational and not investment, trading, order-routing, legal, tax, or "
    "risk-management advice."
)


def _toxicity_inputs(
    symbol: str,
    mid: float,
    tick: float,
    bid_base: float,
    ask_base: float,
    parent_side: str,
    eff_spread_bps: float,
    adverse_frac: float,
    n_signed: int = 60,
    n_quotes: int = 30,
):
    """Deterministic signed trade tape + quote sequence + config (Phase 25.2).

    Buys execute above the prevailing mid and sells below it (positive effective
    spread); the post-trade mid drifts in the trade direction by ``adverse_frac``
    of the half-spread (positive adverse selection). Identical every run.
    """
    half_spread = mid * eff_spread_bps / 2.0 / 10000.0  # price units
    adverse = adverse_frac * half_spread
    buy_heavy = parent_side == "buy"

    signed_trades = []
    for i in range(n_signed):
        m_before = mid + tick * 0.5 * math.sin(i * 0.25) + tick * 0.02 * i
        is_buy_slot = (i * 7) % 12 < 7  # ~58% of slots
        is_buy = is_buy_slot if buy_heavy else not is_buy_slot
        eps = 1.0 if is_buy else -1.0
        price = m_before + eps * half_spread
        m_after_30 = m_before + eps * adverse
        m_after_5 = m_before + eps * adverse * 0.6
        size = round(0.8 + 0.5 * ((i * 3) % 4) + 0.3 * ((i * 5) % 3), 4)
        signed_trades.append(
            SignedTradeInput(
                timestamp=f"S+{i:03d}",
                price=round(max(price, tick), 6),
                size=size,
                side="buy" if is_buy else "sell",
                mid_before=round(max(m_before, tick), 6),
                mid_after_5s=round(max(m_after_5, tick), 6),
                mid_after_30s=round(max(m_after_30, tick), 6),
            )
        )

    quotes = []
    for j in range(n_quotes):
        mq = mid + tick * 0.5 * math.sin(j * 0.3) + tick * 0.03 * j
        bid = mq - tick / 2.0
        ask = mq + tick / 2.0
        bid_size = round(bid_base * (1.0 + 0.3 * math.sin(j * 0.4)), 4)
        ask_size = round(ask_base * (1.0 + 0.3 * math.cos(j * 0.4)), 4)
        quotes.append(
            QuoteUpdateInput(
                timestamp=f"Q+{j:03d}",
                bid=round(max(bid, tick), 6),
                ask=round(max(ask, bid + tick), 6),
                bid_size=max(bid_size, 0.01),
                ask_size=max(ask_size, 0.01),
                mid_price=round(max(mq, tick), 6),
            )
        )

    total_size = sum(t.size for t in signed_trades)
    config = ToxicityConfig(
        bucket_volume=round(max(total_size / 12.0, 0.01), 6),
        realized_spread_horizon_seconds=30.0,
        vpin_window_buckets=10,
        lambda_window_trades=50,
        regime_threshold_low=0.2,
        regime_threshold_high=0.4,
    )
    return signed_trades, quotes, config


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
    eff_spread_bps: float = 4.0,
    adverse_frac: float = 0.4,
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

    # Deterministic per-unit commission (~0.5 bps of mid) for TCA fee attribution.
    commission_per_unit = round(mid * 0.00005, 6)

    # Deterministic order-flow toxicity inputs (Phase 25.2).
    signed_trades, quotes, toxicity_config = _toxicity_inputs(
        symbol, mid, tick, bid_base, ask_base, parent_side, eff_spread_bps, adverse_frac,
    )

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
        commission_per_unit=commission_per_unit,
        signed_trades=signed_trades,
        quotes=quotes,
        toxicity_config=toxicity_config,
    )


def sample_requests() -> List[MarketMicrostructureAnalysisRequest]:
    return [
        # BTCUSDT — wide-ish tick, bid-heavy book, buy-heavy toxic-ish flow.
        _build("BTCUSDT_SAMPLE", 65000.0, 1.0, 10, 1.2, 1.0, 0.3, 0.25, "buy", 10.0, 25000.0, 220.0,
               eff_spread_bps=4.0, adverse_frac=0.45),
        # SPY — penny tick, balanced book, tight spreads.
        _build("SPY_SAMPLE", 500.0, 0.01, 10, 1800.0, 1750.0, 250.0, 250.0, "buy", 50000.0, 70_000_000.0, 90.0,
               eff_spread_bps=1.5, adverse_frac=0.35),
        # CL futures — bigger tick, ask-heavy book, sell-heavy flow.
        _build("CL_SAMPLE", 75.0, 0.01, 10, 40.0, 55.0, 8.0, 12.0, "sell", 2000.0, 300_000.0, 180.0,
               eff_spread_bps=6.0, adverse_frac=0.5),
        # TSM equity — penny tick, bid-heavy book.
        _build("TSM_SAMPLE", 180.0, 0.01, 10, 900.0, 800.0, 120.0, 110.0, "buy", 30000.0, 25_000_000.0, 130.0,
               eff_spread_bps=2.5, adverse_frac=0.4),
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
