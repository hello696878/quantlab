"""
Crypto Perpetual Futures Funding & Basis Lab analytics (Phase 26.0) — pure, deterministic.

Spot / perp / dated-futures basis, funding-rate mechanics and annualized funding
yield, long/short funding P&L, a cash-and-carry example, position margin /
liquidation approximation, a funding-regime classification, and ten funding/basis
stress scenarios.

All outputs are finite by construction (every division is guarded; the compound
annualized-funding exponent is clamped), so no NaN/Infinity reaches the API.
Educational only — not investment, trading, or liquidation advice; not a
production risk engine; never live exchange data or live crypto prices.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.crypto_derivatives.models import (
    BasisAnalysis,
    CarryAnalysis,
    CryptoDerivativesAnalysisRequest,
    CryptoDerivativesAnalysisResponse,
    CryptoScenarioResult,
    FundingAnalysis,
    FundingRegime,
    FuturesCurvePoint,
    MarketSummary,
    PositionRisk,
)
from app.crypto_derivatives.sample import DISCLAIMER

_EPS = 1e-12

# id, name, description, spot_shock, perp_basis_shock_bps, futures_premium_mult,
# funding_rate_shock, margin_mult
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample market as provided.", 0.0, 0.0, 1.0, 0.0, 1.0),
    ("funding_spike_positive", "Funding spike (positive)", "Funding jumps positive; longs pay more.", 0.0, 40.0, 1.0, 0.0008, 1.0),
    ("funding_turns_negative", "Funding turns negative", "Funding flips negative; shorts pay longs.", 0.0, -40.0, 1.0, -0.0010, 1.0),
    ("perp_premium_blowout", "Perp premium blowout", "Perp trades at a large premium to spot.", 0.0, 120.0, 1.0, 0.0, 1.0),
    ("perp_discount_shock", "Perp discount shock", "Perp trades at a discount to spot.", 0.0, -120.0, 1.0, 0.0, 1.0),
    ("spot_selloff", "Spot selloff", "Spot falls 15%.", -0.15, 0.0, 1.0, 0.0, 1.0),
    ("spot_rally", "Spot rally", "Spot rises 15%.", 0.15, 0.0, 1.0, 0.0, 1.0),
    ("basis_convergence", "Basis convergence", "Dated futures basis collapses toward spot.", 0.0, 0.0, 0.1, 0.0, 1.0),
    ("margin_stress", "Margin stress", "Maintenance margin doubles; liquidation buffer shrinks.", 0.0, 0.0, 1.0, 0.0, 2.0),
    ("volatility_shock", "Volatility shock", "Vol spike widens perp premium and tightens margin.", 0.0, 25.0, 1.0, 0.0, 1.3),
]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _compound_annualized(f8h: float) -> float:
    """(1 + f_8h)^(3*365) − 1, with the exponent clamped so it stays finite."""
    base = 1.0 + f8h
    if base <= 0.0:
        return -1.0
    exponent = 3.0 * 365.0 * math.log(base)
    exponent = max(min(exponent, 50.0), -50.0)
    return math.expm1(exponent)


def _annualized_basis(futures_price: float, spot: float, maturity_days: float) -> float:
    if spot <= _EPS or maturity_days <= _EPS:
        return 0.0
    return (futures_price / spot - 1.0) * 365.0 / maturity_days


def _position_pnl(side: str, notional: float, mark: float, entry: float) -> float:
    if entry <= _EPS:
        return 0.0
    ratio = mark / entry
    return notional * (ratio - 1.0) if side == "long" else notional * (1.0 - ratio)


def _liq_price(side: str, entry: float, leverage: float, m_maint: float) -> float:
    inv_l = 1.0 / leverage if leverage > _EPS else 0.0
    if side == "long":
        return max(entry * (1.0 - inv_l + m_maint), 0.0)
    return entry * (1.0 + inv_l - m_maint)


def _curve_shape(ann_bases: List[float]) -> str:
    if not ann_bases:
        return "flat"
    thr = 0.01
    if all(a > thr for a in ann_bases):
        return "contango"
    if all(a < -thr for a in ann_bases):
        return "backwardation"
    if all(abs(a) <= thr for a in ann_bases):
        return "flat"
    return "mixed"


def _classify_regime(f8h: float, perp_basis_bps: float, max_ann_basis: float) -> Tuple[str, str, List[str], str]:
    small_f = 5e-5
    f_hi, f_lo = 3e-4, -3e-4
    pb_hi, pb_lo = 30.0, 10.0
    ab_rich = 0.10
    drivers: List[str] = []

    if f8h >= f_hi and perp_basis_bps >= pb_hi:
        drivers = [f"funding {f8h * 1e4:.1f} bp/8h ≥ {f_hi * 1e4:.0f}", f"perp basis {perp_basis_bps:.1f} bps ≥ {pb_hi:.0f}"]
        return ("overheated_long_perp", "Overheated long perp", drivers,
                "High positive funding and a rich perp premium — crowded long-perp positioning in this sample.")
    if f8h <= f_lo and perp_basis_bps < 0.0:
        drivers = [f"funding {f8h * 1e4:.1f} bp/8h ≤ {f_lo * 1e4:.0f}", f"perp basis {perp_basis_bps:.1f} bps < 0"]
        return ("short_squeeze_risk", "Short-squeeze risk", drivers,
                "Deeply negative funding with a perp discount — crowded shorts that can squeeze in this sample.")
    if max_ann_basis >= ab_rich:
        drivers = [f"max annualized basis {max_ann_basis * 100:.1f}% ≥ {ab_rich * 100:.0f}%"]
        return ("basis_carry_rich", "Basis carry rich", drivers,
                "Dated futures carry a high annualized basis — cash-and-carry looks rich in this sample.")
    if f8h > small_f and perp_basis_bps > 0.0:
        drivers = [f"funding {f8h * 1e4:.1f} bp/8h > 0", f"perp basis {perp_basis_bps:.1f} bps > 0"]
        return ("positive_funding", "Positive funding", drivers,
                "Positive funding with a perp premium — longs pay shorts in this sample.")
    if f8h < -small_f and perp_basis_bps < 0.0:
        drivers = [f"funding {f8h * 1e4:.1f} bp/8h < 0", f"perp basis {perp_basis_bps:.1f} bps < 0"]
        return ("negative_funding", "Negative funding", drivers,
                "Negative funding with a perp discount — shorts pay longs in this sample.")
    if abs(f8h) < small_f and abs(perp_basis_bps) < pb_lo and abs(max_ann_basis) < 0.03:
        drivers = [f"|funding| {abs(f8h) * 1e4:.1f} bp/8h small", f"|perp basis| {abs(perp_basis_bps):.1f} bps small", "low annualized basis"]
        return ("basis_compressed", "Basis compressed", drivers,
                "Funding and basis are all compressed — little carry on offer in this sample.")
    drivers = [f"funding {f8h * 1e4:.1f} bp/8h", f"perp basis {perp_basis_bps:.1f} bps"]
    return ("neutral", "Neutral", drivers,
            "Funding and basis are near neutral in this sample.")


def _regime_score(f8h: float, perp_basis_bps: float, max_ann_basis: float) -> float:
    simple_ann = abs(f8h) * 3.0 * 365.0
    score = 0.4 * min(simple_ann / 0.5, 1.0) + 0.3 * min(abs(perp_basis_bps) / 50.0, 1.0) + 0.3 * min(abs(max_ann_basis) / 0.2, 1.0)
    return max(0.0, min(1.0, score))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_crypto_derivatives(
    req: CryptoDerivativesAnalysisRequest,
) -> CryptoDerivativesAnalysisResponse:
    mkt = req.market
    pos = req.position
    spot = mkt.spot_price
    perp_mark = mkt.perp_mark_price
    f8h = mkt.funding_rate_8h
    intervals = req.funding_intervals_per_day

    # ── Basis ───────────────────────────────────────────────────────────────
    perp_basis = perp_mark - spot
    perp_basis_bps = perp_basis / spot * 10000.0 if spot > _EPS else 0.0

    curve: List[FuturesCurvePoint] = []
    ann_bases: List[float] = []
    basis_bps_list: List[float] = []
    for f in req.dated_futures:
        basis = f.futures_price - spot
        basis_bps = basis / spot * 10000.0 if spot > _EPS else 0.0
        ann = _annualized_basis(f.futures_price, spot, f.maturity_days)
        ann_bases.append(ann)
        basis_bps_list.append(basis_bps)
        curve.append(
            FuturesCurvePoint(
                contract=f.contract,
                maturity_days=f.maturity_days,
                futures_price=f.futures_price,
                basis=basis,
                basis_bps=basis_bps,
                annualized_basis=ann,
            )
        )
    avg_futures_basis_bps = sum(basis_bps_list) / len(basis_bps_list) if basis_bps_list else 0.0
    max_ann_basis = max(ann_bases) if ann_bases else 0.0

    basis_analysis = BasisAnalysis(
        perp_basis=perp_basis,
        perp_basis_bps=perp_basis_bps,
        average_futures_basis_bps=avg_futures_basis_bps,
        max_annualized_basis=max_ann_basis,
        curve_shape=_curve_shape(ann_bases),
    )

    # ── Funding ───────────────────────────────────────────────────────────────
    funding_simple = f8h * intervals * 365.0
    funding_compound = _compound_annualized(f8h)
    long_funding_daily = -pos.notional * f8h * intervals
    short_funding_daily = pos.notional * f8h * intervals
    funding_analysis = FundingAnalysis(
        funding_rate_8h=f8h,
        funding_annualized_compound=funding_compound,
        funding_annualized_simple=funding_simple,
        long_funding_pnl_daily=long_funding_daily,
        short_funding_pnl_daily=short_funding_daily,
        next_funding_hours=mkt.next_funding_hours,
    )

    # ── Position risk ─────────────────────────────────────────────────────────
    initial_margin = pos.notional / pos.leverage if pos.leverage > _EPS else pos.notional
    maintenance_margin = pos.notional * pos.maintenance_margin_rate
    unrealized = _position_pnl(pos.side, pos.notional, pos.mark_price, pos.entry_price)
    margin_ratio = (initial_margin + unrealized) / maintenance_margin if maintenance_margin > _EPS else 0.0
    liq_price = _liq_price(pos.side, pos.entry_price, pos.leverage, pos.maintenance_margin_rate)
    liq_distance_bps = abs(pos.mark_price - liq_price) / pos.mark_price * 10000.0 if pos.mark_price > _EPS else 0.0
    position_risk = PositionRisk(
        side=pos.side,
        notional=pos.notional,
        leverage=pos.leverage,
        initial_margin=initial_margin,
        maintenance_margin=maintenance_margin,
        unrealized_pnl=unrealized,
        margin_ratio=margin_ratio,
        liquidation_price_approx=liq_price,
        liquidation_distance_bps=liq_distance_bps,
    )

    # ── Carry ─────────────────────────────────────────────────────────────────
    best_idx = max(range(len(curve)), key=lambda i: ann_bases[i]) if curve else 0
    best = curve[best_idx]
    round_trip_fees = 2.0 * (pos.taker_fee_rate or 0.0)
    period_years = best.maturity_days / 365.0
    estimated_costs = (mkt.risk_free_rate or 0.0) * period_years + round_trip_fees
    raw_basis_return = (best.futures_price / spot - 1.0) if spot > _EPS else 0.0
    expected_gross_carry = raw_basis_return - estimated_costs
    carry_analysis = CarryAnalysis(
        best_carry_contract=best.contract,
        annualized_basis=best.annualized_basis,
        estimated_costs=estimated_costs,
        expected_gross_carry=expected_gross_carry,
        notes=[
            "Cash-and-carry: buy spot, sell the dated future; the basis converges to "
            "zero at expiry. Gross carry = (F/S − 1) − costs (period, not annualized).",
            "Costs are an illustrative estimate (risk-free funding over the horizon + "
            "round-trip taker fees) — not exchange fees, borrow, or slippage.",
        ],
    )

    # ── Funding regime ────────────────────────────────────────────────────────
    regime_id, regime_label, drivers, explanation = _classify_regime(f8h, perp_basis_bps, max_ann_basis)
    funding_regime = FundingRegime(
        regime_id=regime_id,
        regime_label=regime_label,
        score=_regime_score(f8h, perp_basis_bps, max_ann_basis),
        drivers=drivers,
        explanation=explanation,
        notes=["Deterministic educational classification — not a trading signal or recommendation."],
    )

    # ── Scenarios ───────────────────────────────────────────────────────────
    futures_premia = [(f.futures_price / spot - 1.0) if spot > _EPS else 0.0 for f in req.dated_futures]
    maturities = [f.maturity_days for f in req.dated_futures]
    scenarios = _scenarios(
        spot, perp_basis_bps, futures_premia, maturities, f8h, pos, intervals,
    )

    return CryptoDerivativesAnalysisResponse(
        market_summary=MarketSummary(
            symbol=mkt.symbol,
            spot_price=spot,
            index_price=mkt.index_price,
            perp_mark_price=perp_mark,
            funding_rate_8h=f8h,
            next_funding_hours=mkt.next_funding_hours,
        ),
        basis_analysis=basis_analysis,
        funding_analysis=funding_analysis,
        futures_curve=curve,
        position_risk=position_risk,
        carry_analysis=carry_analysis,
        funding_regime=funding_regime,
        scenario_results=scenarios,
        notes=[
            "Perp basis = perp mark − spot; annualized basis = (F/S − 1)·365/T_days.",
            "Funding P&L: longs pay funding when it is positive (long P&L = −notional·Σf), "
            "shorts receive it; signs reverse when funding is negative.",
            "Liquidation price and margin ratio are simplified approximations on a single "
            "position — not an exchange's actual liquidation engine.",
            "Scenarios are hypothetical deterministic shocks on static sample data — not "
            "forecasts and not advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(
    spot: float,
    base_perp_basis_bps: float,
    futures_premia: List[float],
    maturities: List[float],
    f8h: float,
    pos,
    intervals: int,
) -> List[CryptoScenarioResult]:
    results: List[CryptoScenarioResult] = []
    for sid, name, desc, spot_shock, pb_shock_bps, fut_mult, fund_shock, margin_mult in _SCENARIOS:
        s_spot = spot * (1.0 + spot_shock)
        s_perp_basis_bps = base_perp_basis_bps + pb_shock_bps
        s_perp_mark = s_spot * (1.0 + s_perp_basis_bps / 10000.0)

        # Shocked dated-futures annualized basis (rebased to shocked spot, premium scaled).
        s_ann_bases = []
        for prem, mat in zip(futures_premia, maturities):
            s_future = s_spot * (1.0 + prem * fut_mult)
            s_ann_bases.append(_annualized_basis(s_future, s_spot, mat))
        s_max_ann = max(s_ann_bases) if s_ann_bases else 0.0

        f_prime = f8h + fund_shock
        funding_annualized = _compound_annualized(f_prime)
        long_funding = -pos.notional * f_prime * intervals
        short_funding = pos.notional * f_prime * intervals

        position_pnl = _position_pnl(pos.side, pos.notional, s_perp_mark, pos.entry_price)
        m_maint = min(pos.maintenance_margin_rate * margin_mult, 0.99)
        initial_margin = pos.notional / pos.leverage if pos.leverage > _EPS else pos.notional
        maintenance_margin = pos.notional * m_maint
        margin_ratio = (initial_margin + position_pnl) / maintenance_margin if maintenance_margin > _EPS else 0.0
        liq_price = _liq_price(pos.side, pos.entry_price, pos.leverage, m_maint)
        liq_distance_bps = abs(s_perp_mark - liq_price) / s_perp_mark * 10000.0 if s_perp_mark > _EPS else 0.0

        _, regime_label, _, _ = _classify_regime(f_prime, s_perp_basis_bps, s_max_ann)

        results.append(
            CryptoScenarioResult(
                id=sid,
                name=name,
                description=desc,
                shocked_spot=s_spot,
                shocked_perp_mark=s_perp_mark,
                perp_basis_bps=s_perp_basis_bps,
                annualized_basis=s_max_ann,
                funding_annualized=funding_annualized,
                long_funding_pnl=long_funding,
                short_funding_pnl=short_funding,
                position_pnl=position_pnl,
                margin_ratio=margin_ratio,
                liquidation_distance_bps=liq_distance_bps,
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
