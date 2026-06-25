"""
Futures & Commodities Lab analytics (Phase 23.0) — pure, deterministic.

Cost-of-carry futures pricing, implied convenience yield, futures-curve shape
(contango / backwardation / mixed), roll yield, calendar spreads, contract
notional / margin / leverage P&L, and eight deterministic commodity scenarios.

All outputs are finite by construction (every division is guarded), so no
NaN/Infinity reaches the API. Educational only — not investment / trading advice.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.futures.models import (
    CalendarSpreadAnalysis,
    CommoditySummary,
    CurveAnalysis,
    CurveAnalysisPoint,
    FuturesAnalysisRequest,
    FuturesAnalysisResponse,
    FuturesScenarioResult,
    MarginAnalysis,
    PositionPnl,
    RollYieldRow,
    TheoreticalPricing,
)
from app.futures.sample import DISCLAIMER

_EPS = 1e-12

# id, name, description, spot_shock, parallel_shift, slope_shock, storage_shock,
# convenience_yield_shock, margin_multiplier
_SCENARIOS = [
    ("base", "Base case", "No shocks.", 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    ("spot_rally", "Spot rally", "Spot and curve up ~10%.", 0.10, 0.0, 0.0, 0.0, 0.0, 1.0),
    ("spot_selloff", "Spot selloff", "Spot and curve down ~12%.", -0.12, 0.0, 0.0, 0.0, 0.0, 1.0),
    ("contango_steepening", "Contango steepening", "Far contracts lifted (steeper upward slope).", 0.0, 0.0, 0.6, 0.0, 0.0, 1.0),
    ("backwardation_shock", "Backwardation shock", "Near up, far down (downward slope).", 0.0, 0.0, -0.9, 0.0, 0.0, 1.0),
    ("storage_cost_shock", "Storage cost shock", "Storage cost up ~3% (carry up, more contango).", 0.0, 0.0, 0.0, 0.03, 0.0, 1.0),
    ("convenience_yield_shock", "Convenience yield shock", "Convenience yield up ~5% (more backwardation).", 0.0, 0.0, 0.0, 0.0, 0.05, 1.0),
    ("margin_stress", "Margin stress", "Adverse 8% move with initial margin x1.5.", -0.08, 0.0, 0.0, 0.0, 0.0, 1.5),
]


# --------------------------------------------------------------------------- #
# Core formulas
# --------------------------------------------------------------------------- #
def cost_of_carry_price(spot: float, carry_rate: float, t_years: float) -> float:
    return float(spot * math.exp(carry_rate * t_years))


def implied_convenience_yield(
    spot: float, futures: float, r: float, u: float, t_years: float
) -> float:
    if t_years <= _EPS or spot <= _EPS or futures <= _EPS:
        return 0.0
    return float(r + u - math.log(futures / spot) / t_years)


def roll_yield(near: float, nxt: float) -> float:
    return float((near - nxt) / near) if abs(near) > _EPS else 0.0


def _curve_shape(prices: List[float]) -> str:
    ups = downs = 0
    for a, b in zip(prices, prices[1:]):
        tol = 1e-6 * max(abs(a), 1.0)
        if b - a > tol:
            ups += 1
        elif a - b > tol:
            downs += 1
    if ups > 0 and downs == 0:
        return "contango"
    if downs > 0 and ups == 0:
        return "backwardation"
    return "mixed"


def _position_pnl(position_type: str, entry: float, exit_: float, mult: float, contracts: float) -> float:
    if position_type == "short":
        return float((entry - exit_) * mult * contracts)
    return float((exit_ - entry) * mult * contracts)


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyze_futures(req: FuturesAnalysisRequest) -> FuturesAnalysisResponse:
    c = req.contract
    pos = req.position
    curve = sorted(req.curve, key=lambda p: p.maturity_months)
    spot = c.spot_price
    carry_rate = c.risk_free_rate + c.storage_cost_rate - c.convenience_yield

    # Curve analysis points.
    points: List[CurveAnalysisPoint] = []
    for i, pt in enumerate(curve):
        t = pt.maturity_months / 12.0
        model = cost_of_carry_price(spot, carry_rate, t)
        basis = pt.futures_price - spot
        ann_basis = (pt.futures_price / spot - 1.0) / t if t > _EPS and spot > _EPS else 0.0
        impl = implied_convenience_yield(spot, pt.futures_price, c.risk_free_rate, c.storage_cost_rate, t)
        ry = (
            roll_yield(pt.futures_price, curve[i + 1].futures_price)
            if i < len(curve) - 1
            else None
        )
        points.append(
            CurveAnalysisPoint(
                contract=pt.contract,
                maturity_months=pt.maturity_months,
                maturity_years=t,
                observed_futures=pt.futures_price,
                model_futures=model,
                basis=basis,
                annualized_basis=ann_basis,
                implied_convenience_yield=impl,
                pricing_deviation=pt.futures_price - model,
                roll_yield=ry,
            )
        )

    observed_prices = [pt.futures_price for pt in curve]
    near, far = curve[0], curve[-1]
    curve_analysis = CurveAnalysis(
        points=points,
        curve_slope=far.futures_price - near.futures_price,
        curve_shape=_curve_shape(observed_prices),
        near_contract=near.contract,
        far_contract=far.contract,
        near_basis=near.futures_price - spot,
    )

    roll_table = [
        RollYieldRow(
            from_contract=curve[i].contract,
            to_contract=curve[i + 1].contract,
            near_price=curve[i].futures_price,
            next_price=curve[i + 1].futures_price,
            roll_yield=roll_yield(curve[i].futures_price, curve[i + 1].futures_price),
        )
        for i in range(len(curve) - 1)
    ]

    spread = far.futures_price - near.futures_price
    calendar = CalendarSpreadAnalysis(
        near_contract=near.contract,
        deferred_contract=far.contract,
        near_price=near.futures_price,
        deferred_price=far.futures_price,
        spread=spread,
        spread_pct=spread / near.futures_price if near.futures_price > _EPS else 0.0,
    )

    # Position P&L + margin (on the position's entry price).
    pnl = _position_pnl(pos.position_type, pos.entry_price, pos.exit_price, pos.contract_multiplier, pos.contracts)
    notional = pos.entry_price * pos.contract_multiplier * pos.contracts
    initial_margin = notional * c.initial_margin_rate
    maintenance_margin = notional * c.maintenance_margin_rate
    position_pnl = PositionPnl(
        position_type=pos.position_type,
        contracts=pos.contracts,
        entry_price=pos.entry_price,
        exit_price=pos.exit_price,
        contract_multiplier=pos.contract_multiplier,
        pnl=pnl,
        notional=notional,
        initial_margin=initial_margin,
        return_on_margin=pnl / initial_margin if initial_margin > _EPS else 0.0,
    )
    margin_analysis = MarginAnalysis(
        notional=notional,
        initial_margin=initial_margin,
        maintenance_margin=maintenance_margin,
        leverage=notional / initial_margin if initial_margin > _EPS else 0.0,
        initial_margin_rate=c.initial_margin_rate,
        maintenance_margin_rate=c.maintenance_margin_rate,
    )

    theoretical = TheoreticalPricing(
        spot_price=spot,
        cost_of_carry_rate=carry_rate,
        model_futures_12m=cost_of_carry_price(spot, carry_rate, 1.0),
        model_near=cost_of_carry_price(spot, carry_rate, near.maturity_months / 12.0),
        model_far=cost_of_carry_price(spot, carry_rate, far.maturity_months / 12.0),
    )

    # Scenarios.
    base_near_p = near.futures_price
    base_next_p = curve[1].futures_price
    base_far_p = far.futures_price
    base_spread_nd = base_near_p - base_far_p
    mult, contracts = pos.contract_multiplier, pos.contracts

    def shock_price(price: float, t: float, spot_shock, parallel, slope, storage_shock, conv_shock) -> float:
        adj = (price * (1.0 + spot_shock) + parallel + slope * t)
        return max(adj * math.exp((storage_shock - conv_shock) * t), 1e-9)

    scenarios: List[FuturesScenarioResult] = []
    for sid, name, desc, sps, par, slp, stor, conv, mm in _SCENARIOS:
        t_near = near.maturity_months / 12.0
        t_next = curve[1].maturity_months / 12.0
        t_far = far.maturity_months / 12.0
        s_near = shock_price(base_near_p, t_near, sps, par, slp, stor, conv)
        s_next = shock_price(base_next_p, t_next, sps, par, slp, stor, conv)
        s_far = shock_price(base_far_p, t_far, sps, par, slp, stor, conv)
        shocked_spot = max(spot * (1.0 + sps), 1e-9)
        shocked_prices = [
            shock_price(pt.futures_price, pt.maturity_months / 12.0, sps, par, slp, stor, conv)
            for pt in curve
        ]
        near_pnl = _position_pnl(pos.position_type, pos.entry_price, s_near, mult, contracts)
        shocked_spread_nd = s_near - s_far
        cal_pnl = (shocked_spread_nd - base_spread_nd) * mult * contracts
        margin_req = s_near * mult * contracts * (c.initial_margin_rate * mm)
        scenarios.append(
            FuturesScenarioResult(
                id=sid,
                name=name,
                description=desc,
                spot_shock=sps,
                curve_parallel_shift=par,
                curve_slope_shock=slp,
                convenience_yield_shock=conv,
                shocked_spot=shocked_spot,
                curve_shape=_curve_shape(shocked_prices),
                near_pnl=near_pnl,
                calendar_spread_pnl=cal_pnl,
                roll_yield=roll_yield(s_near, s_next),
                margin_requirement=margin_req,
                return_on_margin=near_pnl / margin_req if margin_req > _EPS else 0.0,
                notes=["Illustrative deterministic scenario — not a forecast."],
            )
        )

    return FuturesAnalysisResponse(
        commodity_summary=CommoditySummary(
            commodity_name=c.commodity_name,
            symbol=c.symbol,
            spot_price=spot,
            risk_free_rate=c.risk_free_rate,
            storage_cost_rate=c.storage_cost_rate,
            convenience_yield=c.convenience_yield,
            contract_multiplier=c.contract_multiplier,
            initial_margin_rate=c.initial_margin_rate,
            maintenance_margin_rate=c.maintenance_margin_rate,
            cost_of_carry_rate=carry_rate,
        ),
        theoretical_pricing=theoretical,
        curve_analysis=curve_analysis,
        roll_yield_table=roll_table,
        calendar_spread_analysis=calendar,
        position_pnl=position_pnl,
        margin_analysis=margin_analysis,
        scenario_results=scenarios,
        notes=[
            "Cost-of-carry: F = S·exp((r + u − y)·T); implied convenience yield "
            "y = r + u − ln(F/S)/T.",
            "Curve shape is classified deterministically from consecutive observed "
            "futures (upward → contango, downward → backwardation, else mixed).",
            "Roll yield = (F_near − F_next)/F_near; calendar spread = F_deferred − "
            "F_near; P&L uses the contract multiplier and number of contracts.",
            "Scenario shocks are deterministic illustrative stresses, not forecasts.",
        ],
        disclaimer=DISCLAIMER,
    )
