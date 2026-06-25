"""
Market Microstructure & Execution Lab analytics (Phase 25.0) — pure, deterministic.

Order-book summary (spread, depth, imbalance, microprice), trade-tape analytics
(VWAP / TWAP / trade imbalance), execution analytics (implementation shortfall,
slippage, participation, square-root market-impact approximation), a hypothetical
execution-schedule comparison, and eight liquidity stress scenarios.

All outputs are finite by construction (every division is guarded), so no
NaN/Infinity reaches the API. Educational only — not investment / trading /
order-routing advice, and not a production execution system.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.microstructure.models import (
    DepthLevel,
    ExecutionSummary,
    InstrumentSummary,
    LiquidityScenarioResult,
    MarketMicrostructureAnalysisRequest,
    MarketMicrostructureAnalysisResponse,
    OrderBookSummary,
    ScheduleComparisonResult,
    TradeTapeSummary,
)
from app.microstructure.sample import DISCLAIMER

_EPS = 1e-12

# id, name, description, spread_mult, depth_mult, vol_mult, volume_mult,
# impact_mult, imbalance_shift
_SCENARIOS = [
    ("base", "Base case", "No shocks.", 1.0, 1.0, 1.0, 1.0, 1.0, 0.0),
    ("spread_doubles", "Spread doubles", "Quoted spread ×2.", 2.0, 1.0, 1.0, 1.0, 1.0, 0.0),
    ("depth_halves", "Depth halves", "Book depth ×0.5 (thinner book).", 1.0, 0.5, 1.0, 1.0, 1.0, 0.0),
    ("volatility_spike", "Volatility spike", "Volatility ×2 (higher impact).", 1.0, 1.0, 2.0, 1.0, 1.0, 0.0),
    ("volume_drought", "Volume drought", "Volume ×0.4 (higher participation/impact).", 1.0, 1.0, 1.0, 0.4, 1.0, 0.0),
    ("liquidity_shock_combo", "Liquidity shock combo", "Spread ×2, depth ×0.5, vol ×1.8, volume ×0.5.", 2.0, 0.5, 1.8, 0.5, 1.0, 0.0),
    ("bid_side_pressure", "Bid-side pressure", "Bid sizes lifted (microprice up).", 1.0, 1.0, 1.0, 1.0, 1.0, 0.30),
    ("ask_side_pressure", "Ask-side pressure", "Ask sizes lifted (microprice down).", 1.0, 1.0, 1.0, 1.0, 1.0, -0.30),
]


def _walk_book(levels: List[Tuple[float, float]], qty: float) -> Tuple[float, float]:
    """Volume-weighted average price + filled qty walking sorted levels."""
    remaining = qty
    cost = 0.0
    filled = 0.0
    for price, size in levels:
        if remaining <= _EPS:
            break
        take = min(size, remaining)
        cost += take * price
        filled += take
        remaining -= take
    avg = cost / filled if filled > _EPS else (levels[0][0] if levels else 0.0)
    return avg, filled


def analyze_microstructure(
    req: MarketMicrostructureAnalysisRequest,
) -> MarketMicrostructureAnalysisResponse:
    book = req.order_book
    bids = sorted(book.bids, key=lambda x: x.price, reverse=True)
    asks = sorted(book.asks, key=lambda x: x.price)
    best_bid = bids[0].price
    best_ask = asks[0].price
    mid = (best_bid + best_ask) / 2.0
    spread = best_ask - best_bid
    spread_bps = spread / mid * 10000.0 if mid > _EPS else 0.0
    b1, a1 = bids[0].size, asks[0].size
    tob_imb = (b1 - a1) / (b1 + a1) if (b1 + a1) > _EPS else 0.0
    microprice = (best_ask * b1 + best_bid * a1) / (b1 + a1) if (b1 + a1) > _EPS else mid
    micro_vs_mid_bps = (microprice - mid) / mid * 10000.0 if mid > _EPS else 0.0

    n_levels = min(len(bids), len(asks))
    depth_table: List[DepthLevel] = []
    cum_bid = cum_ask = 0.0
    for i in range(n_levels):
        cum_bid += bids[i].size
        cum_ask += asks[i].size
        depth_table.append(
            DepthLevel(
                level=i + 1,
                bid_price=bids[i].price,
                bid_size=bids[i].size,
                cumulative_bid_size=cum_bid,
                ask_price=asks[i].price,
                ask_size=asks[i].size,
                cumulative_ask_size=cum_ask,
            )
        )
    k = min(5, n_levels)
    sum_bid_5 = sum(b.size for b in bids[:k])
    sum_ask_5 = sum(a.size for a in asks[:k])
    depth_imb_5 = (sum_bid_5 - sum_ask_5) / (sum_bid_5 + sum_ask_5) if (sum_bid_5 + sum_ask_5) > _EPS else 0.0
    total_depth = sum(b.size for b in bids) + sum(a.size for a in asks)

    order_book_summary = OrderBookSummary(
        best_bid=best_bid,
        best_ask=best_ask,
        mid_price=mid,
        spread=spread,
        spread_bps=spread_bps,
        top_of_book_imbalance=tob_imb,
        depth_imbalance_5=depth_imb_5,
        microprice=microprice,
        microprice_vs_mid_bps=micro_vs_mid_bps,
    )

    # ── Trade tape ─────────────────────────────────────────────────────────
    trades = req.trades
    total_volume = sum(t.size for t in trades)
    vwap = sum(t.price * t.size for t in trades) / total_volume if total_volume > _EPS else mid
    twap = sum(t.price for t in trades) / len(trades) if trades else mid
    buy_volume = sum(t.size for t in trades if t.side == "buy")
    sell_volume = sum(t.size for t in trades if t.side == "sell")
    signed = sum((t.size if t.side == "buy" else -t.size) for t in trades)
    trade_imbalance = signed / total_volume if total_volume > _EPS else 0.0
    tape = TradeTapeSummary(
        trade_count=len(trades),
        total_volume=total_volume,
        vwap=vwap,
        twap=twap,
        trade_imbalance=trade_imbalance,
        buy_volume=buy_volume,
        sell_volume=sell_volume,
    )

    # ── Execution analytics ────────────────────────────────────────────────
    order = req.execution_order
    side = order.side
    sign = 1.0 if side == "buy" else -1.0
    filled = sum(f.quantity for f in req.fills)
    avg_exec = sum(f.price * f.quantity for f in req.fills) / filled if filled > _EPS else order.arrival_price
    fill_ratio = filled / order.quantity if order.quantity > _EPS else 0.0
    arrival = order.arrival_price
    impl_shortfall = sign * (avg_exec - arrival) / arrival if arrival > _EPS else 0.0
    benchmark = order.benchmark_price if order.benchmark_price is not None else vwap
    slippage = sign * (avg_exec - benchmark) / benchmark if benchmark > _EPS else 0.0
    participation_rate = filled / total_volume if total_volume > _EPS else 0.0
    base_impact_bps = (
        req.impact_coefficient * math.sqrt(order.quantity / req.average_daily_volume) * req.volatility_bps
        if req.average_daily_volume > _EPS
        else 0.0
    )
    execution_summary = ExecutionSummary(
        side=side,
        parent_quantity=order.quantity,
        arrival_price=arrival,
        average_execution_price=avg_exec,
        filled_quantity=filled,
        fill_ratio=fill_ratio,
        implementation_shortfall=impl_shortfall,
        shortfall_bps=impl_shortfall * 10000.0,
        slippage_bps=slippage * 10000.0,
        participation_rate=participation_rate,
        market_impact_bps=base_impact_bps,
    )

    # ── Schedule comparison ────────────────────────────────────────────────
    half_spread_bps = spread_bps / 2.0
    pov = order.participation_limit or 0.10
    schedule_comparison = _schedules(
        order, bids, asks, mid, sign, half_spread_bps, base_impact_bps,
        total_depth, total_volume, req.volume_curve, pov,
    )

    # ── Liquidity scenarios ────────────────────────────────────────────────
    liquidity = _scenarios(
        order, mid, best_bid, best_ask, b1, a1, half_spread_bps, base_impact_bps, total_depth,
    )

    return MarketMicrostructureAnalysisResponse(
        instrument_summary=InstrumentSummary(
            symbol=book.symbol, timestamp=book.timestamp,
            best_bid=best_bid, best_ask=best_ask, mid_price=mid,
        ),
        order_book_summary=order_book_summary,
        depth_table=depth_table,
        trade_tape_summary=tape,
        execution_summary=execution_summary,
        schedule_comparison=schedule_comparison,
        liquidity_scenarios=liquidity,
        notes=[
            "Order-book metrics: mid = (bid+ask)/2, microprice weights the touch by "
            "the opposite size; imbalance uses level-1 and top-5 depth.",
            "Trade tape: VWAP = Σpq/Σq, TWAP = mean(price), trade imbalance from "
            "signed (buy +, sell −) volume.",
            "Execution: implementation shortfall and slippage are signed by side; "
            "market impact uses a square-root model with educational parameters.",
            "Schedule comparison and liquidity scenarios are hypothetical educational "
            "examples on deterministic sample data — no schedule is recommended and "
            "nothing here is order-routing advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _schedules(
    order, bids, asks, mid, sign, half_spread_bps, base_impact_bps,
    total_depth, total_volume, volume_curve, pov,
) -> List[ScheduleComparisonResult]:
    qty = order.quantity
    arrival = order.arrival_price
    same_side_levels = (
        [(a.price, a.size) for a in asks] if order.side == "buy" else [(b.price, b.size) for b in bids]
    )

    def result(name, child_orders, spread_cost_bps, impact_bps, participation, completion, notes):
        shortfall = spread_cost_bps + impact_bps
        avg = arrival * (1.0 + sign * shortfall / 10000.0)
        return ScheduleComparisonResult(
            schedule_name=name,
            child_orders=child_orders,
            expected_avg_price=avg,
            expected_shortfall_bps=shortfall,
            expected_spread_cost_bps=spread_cost_bps,
            expected_impact_bps=impact_bps,
            participation_rate=participation,
            completion_rate=completion,
            notes=notes,
        )

    # Immediate: walk the book now (depth-limited) → realised crossing cost.
    walk_avg, walk_filled = _walk_book(same_side_levels, qty)
    immediate_spread_cost = abs(walk_avg - mid) / mid * 10000.0 if mid > _EPS else half_spread_bps
    immediate_completion = walk_filled / qty if qty > _EPS else 0.0
    n_buckets = len(volume_curve)
    pov_completion = min(1.0, pov * total_volume / qty) if qty > _EPS else 1.0

    return [
        result(
            "Immediate", len(same_side_levels), immediate_spread_cost, base_impact_bps,
            qty / total_volume if total_volume > _EPS else 1.0, immediate_completion,
            ["Crosses the book now; pays the full crossing cost and front-loads impact."],
        ),
        result(
            "TWAP", n_buckets, half_spread_bps, base_impact_bps * 0.55,
            qty / total_volume if total_volume > _EPS else 1.0, 1.0,
            ["Equal child quantities across time buckets; spreads impact out."],
        ),
        result(
            "VWAP-style", n_buckets, half_spread_bps, base_impact_bps * 0.50,
            qty / total_volume if total_volume > _EPS else 1.0, 1.0,
            ["Child quantities follow the deterministic volume curve."],
        ),
        result(
            "Participation-of-volume", n_buckets, half_spread_bps, base_impact_bps * 0.45,
            pov, pov_completion,
            [f"Trades ~{pov:.0%} of each bucket's volume; completion depends on volume."],
        ),
    ]


def _scenarios(
    order, mid, best_bid, best_ask, b1, a1, half_spread_bps, base_impact_bps, total_depth,
) -> List[LiquidityScenarioResult]:
    base_spread_bps = half_spread_bps * 2.0
    results: List[LiquidityScenarioResult] = []
    for sid, name, desc, spread_m, depth_m, vol_m, volume_m, impact_m, imb_shift in _SCENARIOS:
        s_spread_bps = base_spread_bps * spread_m
        s_half_bps = s_spread_bps / 2.0
        s_total_depth = total_depth * depth_m
        # Stressed top sizes for imbalance/microprice.
        b1s = b1 * depth_m * (1.0 + imb_shift)
        a1s = a1 * depth_m * (1.0 - imb_shift)
        denom = b1s + a1s
        depth_imb = (b1s - a1s) / denom if denom > _EPS else 0.0
        microprice = (best_ask * b1s + best_bid * a1s) / denom if denom > _EPS else mid
        impact = base_impact_bps * vol_m * impact_m / math.sqrt(max(volume_m, _EPS))
        depth_penalty = 1.0 / max(depth_m, _EPS)
        results.append(
            LiquidityScenarioResult(
                id=sid,
                name=name,
                description=desc,
                spread_bps=s_spread_bps,
                total_depth=s_total_depth,
                depth_imbalance=depth_imb,
                microprice=microprice,
                immediate_shortfall_bps=s_half_bps * depth_penalty + impact,
                twap_shortfall_bps=s_half_bps + impact * 0.55,
                vwap_shortfall_bps=s_half_bps + impact * 0.50,
                pov_shortfall_bps=s_half_bps + impact * 0.45,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
