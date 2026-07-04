"""
DeFi Yield, Stablecoin Peg & Lending Risk Lab analytics (Phase 27.0) — pure,
deterministic.

Stablecoin peg deviation, utilization + kinked interest-rate model, collateral /
debt / LTV / health-factor / liquidation approximation, net APY, a deterministic
risk-regime classification, and ten protocol stress scenarios.

All outputs are finite by construction (every division is guarded; the health
factor is capped when there is no debt), so no NaN/Infinity reaches the API.
Educational only — not investment, trading, lending, borrowing, or liquidation
advice; not a production DeFi risk engine; never live protocol data, live crypto
prices, wallets, RPC, or smart-contract calls.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.defi_risk.models import (
    CollateralRisk,
    DeFiRiskAnalysisRequest,
    DeFiRiskAnalysisResponse,
    DeFiScenarioResult,
    InterestRateModelResult,
    NetAPYAnalysis,
    ProtocolSummary,
    RiskRegime,
    StablecoinPegAnalysis,
    UtilizationAnalysis,
)
from app.defi_risk.sample import DISCLAIMER

_EPS = 1e-12
_HF_CAP = 999.0  # displayed health factor when there is (almost) no debt

# Regime thresholds (deterministic, educational).
_PEG_MINOR_BPS = 20.0
_PEG_STRESS_BPS = 100.0
_PEG_SEVERE_BPS = 500.0
_HF_WATCH = 1.15
_HF_HEALTHY = 1.5
_LIQUIDITY_THIN_FRAC = 0.10

# id, name, description, collateral_shock, debt_price_shock, depeg_shock,
# utilization_shock, liquidity_mult, borrow_rate_shock, threshold_shock
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample market as provided.", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    ("stable_mild_depeg", "Stablecoin mild depeg", "Stablecoin slips ~1% below peg.", 0.0, 0.0, -0.01, 0.0, 1.0, 0.0, 0.0),
    ("stable_severe_depeg", "Stablecoin severe depeg", "Stablecoin breaks ~6% below peg.", 0.0, 0.0, -0.06, 0.0, 1.0, 0.0, 0.0),
    ("collateral_drawdown", "Collateral drawdown", "Collateral price falls 30%.", -0.30, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    ("borrow_asset_rally", "Borrow asset rally", "Debt asset price rises 20%.", 0.0, 0.20, 0.0, 0.0, 1.0, 0.0, 0.0),
    ("utilization_spike", "Utilization spike", "Utilization jumps 25 points.", 0.0, 0.0, 0.0, 0.25, 1.0, 0.0, 0.0),
    ("liquidity_drought", "Liquidity drought", "Available liquidity falls 90%; utilization rises.", 0.0, 0.0, 0.0, 0.15, 0.1, 0.0, 0.0),
    ("borrow_rate_shock", "Borrow rate shock", "Borrow APY jumps 5 points.", 0.0, 0.0, 0.0, 0.0, 1.0, 0.05, 0.0),
    ("liquidation_threshold_cut", "Liquidation threshold cut", "Protocol cuts the liquidation threshold by 10 points.", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -0.10),
    ("protocol_stress_combo", "Protocol stress combo", "Collateral −25%, depeg −2%, utilization +20 pts, liquidity −80%.", -0.25, 0.0, -0.02, 0.20, 0.2, 0.02, -0.05),
]


# --------------------------------------------------------------------------- #
# Core building blocks
# --------------------------------------------------------------------------- #
def kinked_borrow_rate(u: float, r0: float, s1: float, s2: float, kink: float) -> float:
    """Kinked (Aave/Compound-style) borrow rate as a function of utilization."""
    u = max(0.0, min(u, 1.0))
    if u <= kink:
        return r0 + (u / kink) * s1 if kink > _EPS else r0
    return r0 + s1 + ((u - kink) / max(1.0 - kink, _EPS)) * s2


def supply_rate(borrow_rate: float, u: float, reserve_factor: float) -> float:
    return borrow_rate * max(0.0, min(u, 1.0)) * (1.0 - reserve_factor)


def _health_factor(coll_value: float, debt_value: float, threshold: float) -> float:
    if debt_value <= _EPS:
        return _HF_CAP
    return min(coll_value * threshold / debt_value, _HF_CAP)


def _liq_price(debt_value: float, coll_amount: float, threshold: float) -> float:
    denom = coll_amount * threshold
    return debt_value / denom if denom > _EPS else 0.0


def _peg_status(dev_bps: float) -> str:
    a = abs(dev_bps)
    if a < _PEG_MINOR_BPS:
        return "on_peg"
    if a < _PEG_STRESS_BPS:
        return "minor_deviation"
    return "depegged"


def _utilization_regime(u: float, kink: float) -> str:
    if u < 0.4:
        return "low"
    if u <= kink:
        return "moderate"
    if u < 0.95:
        return "high"
    return "extreme"


def _classify_regime(
    hf: float, peg_dev_bps: float, u: float, kink: float, liquidity_frac: float,
) -> Tuple[str, str, List[str], str]:
    apeg = abs(peg_dev_bps)
    if hf < 1.0 or apeg >= _PEG_SEVERE_BPS:
        drivers = ([f"health factor {hf:.2f} < 1.00"] if hf < 1.0 else []) + (
            [f"|peg deviation| {apeg:.0f} bps ≥ {_PEG_SEVERE_BPS:.0f}"] if apeg >= _PEG_SEVERE_BPS else []
        )
        return ("severe_stress", "Severe stress", drivers,
                "Liquidation-level health factor and/or an extreme depeg — severe stress in this sample.")
    if hf < _HF_WATCH:
        return ("liquidation_watch", "Liquidation watch", [f"health factor {hf:.2f} < {_HF_WATCH:.2f}"],
                "The health factor is close to 1.0 — a modest collateral move could reach the liquidation level in this sample.")
    if apeg >= _PEG_STRESS_BPS:
        return ("peg_stress", "Peg stress", [f"|peg deviation| {apeg:.0f} bps ≥ {_PEG_STRESS_BPS:.0f}"],
                "The stablecoin is trading meaningfully away from its peg in this sample.")
    if liquidity_frac < _LIQUIDITY_THIN_FRAC and u >= kink:
        return ("protocol_stress", "Protocol stress",
                [f"liquidity {liquidity_frac * 100:.0f}% of supply < {_LIQUIDITY_THIN_FRAC * 100:.0f}%", f"utilization {u * 100:.0f}% ≥ kink"],
                "Thin available liquidity with utilization at/above the kink — withdrawal/borrow stress in this sample.")
    if u > kink:
        return ("elevated_utilization", "Elevated utilization", [f"utilization {u * 100:.0f}% > kink {kink * 100:.0f}%"],
                "Utilization is past the kink, pushing borrow rates up the steep slope in this sample.")
    drivers = [f"health factor {hf:.2f}" + (" (no debt)" if hf >= _HF_CAP else ""), f"|peg deviation| {apeg:.0f} bps", f"utilization {u * 100:.0f}%"]
    return ("healthy", "Healthy", drivers,
            "Comfortable health factor, tight peg, and moderate utilization in this sample.")


def _regime_score(hf: float, peg_dev_bps: float, u: float) -> float:
    hf_comp = max(0.0, min((_HF_HEALTHY - min(hf, _HF_HEALTHY)) / (_HF_HEALTHY - 0.5), 1.0))
    peg_comp = min(abs(peg_dev_bps) / _PEG_SEVERE_BPS, 1.0)
    u_comp = min(max(u, 0.0) / 0.95, 1.0)
    return max(0.0, min(0.4 * hf_comp + 0.3 * peg_comp + 0.3 * u_comp, 1.0))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_defi_risk(req: DeFiRiskAnalysisRequest) -> DeFiRiskAnalysisResponse:
    stable = req.stablecoin
    mkt = req.market
    pos = req.position

    # ── Stablecoin peg ──────────────────────────────────────────────────────
    peg_dev = (stable.market_price - stable.target_peg) / stable.target_peg
    peg_dev_bps = peg_dev * 10000.0
    stablecoin_peg = StablecoinPegAnalysis(
        symbol=stable.symbol,
        target_peg=stable.target_peg,
        market_price=stable.market_price,
        peg_deviation=peg_dev,
        peg_deviation_bps=peg_dev_bps,
        reserve_quality_score=stable.reserve_quality_score,
        status=_peg_status(peg_dev_bps),
    )

    # ── Utilization + rate model ────────────────────────────────────────────
    utilization = mkt.total_borrowed / mkt.total_supplied if mkt.total_supplied > _EPS else 0.0
    borrow_model = kinked_borrow_rate(utilization, mkt.base_rate, mkt.slope_1, mkt.slope_2, mkt.kink_utilization)
    supply_model = supply_rate(borrow_model, utilization, mkt.reserve_factor)
    utilization_analysis = UtilizationAnalysis(
        total_supplied=mkt.total_supplied,
        total_borrowed=mkt.total_borrowed,
        liquidity=mkt.liquidity,
        utilization=utilization,
        kink_utilization=mkt.kink_utilization,
        utilization_regime=_utilization_regime(utilization, mkt.kink_utilization),
    )
    interest_rate_model = InterestRateModelResult(
        borrow_apy_model=borrow_model,
        supply_apy_model=supply_model,
        reserve_factor=mkt.reserve_factor,
        base_rate=mkt.base_rate,
        slope_1=mkt.slope_1,
        slope_2=mkt.slope_2,
        kink_utilization=mkt.kink_utilization,
    )

    # ── Collateral risk ─────────────────────────────────────────────────────
    coll_value = pos.collateral_amount * pos.collateral_price
    debt_value = pos.debt_amount * pos.debt_price
    ltv = debt_value / coll_value if coll_value > _EPS else 0.0
    hf = _health_factor(coll_value, debt_value, pos.liquidation_threshold)
    liq_price = _liq_price(debt_value, pos.collateral_amount, pos.liquidation_threshold)
    liq_distance_bps = (
        (pos.collateral_price - liq_price) / pos.collateral_price * 10000.0
        if pos.collateral_price > _EPS
        else 0.0
    )
    collateral_risk = CollateralRisk(
        collateral_value=coll_value,
        debt_value=debt_value,
        loan_to_value=ltv,
        collateral_factor=pos.collateral_factor,
        liquidation_threshold=pos.liquidation_threshold,
        health_factor=hf,
        liquidation_price_approx=liq_price,
        liquidation_distance_bps=liq_distance_bps,
        liquidation_penalty=pos.liquidation_penalty,
    )

    # ── Net APY ─────────────────────────────────────────────────────────────
    net_apy = pos.supply_apy - pos.borrow_apy - req.fees_apy
    net_apy_analysis = NetAPYAnalysis(
        supply_apy=pos.supply_apy,
        borrow_apy=pos.borrow_apy,
        fees_apy=req.fees_apy,
        net_apy=net_apy,
        notes=[
            "Net APY = supply APY − borrow APY − fees on the sample position — a "
            "simple carry read, not a levered-loop or reward-token model.",
            "A negative net APY means the borrow cost exceeds the supply yield here.",
        ],
    )

    # ── Risk regime ─────────────────────────────────────────────────────────
    liquidity_frac = mkt.liquidity / mkt.total_supplied if mkt.total_supplied > _EPS else 0.0
    regime_id, regime_label, drivers, explanation = _classify_regime(
        hf, peg_dev_bps, utilization, mkt.kink_utilization, liquidity_frac,
    )
    risk_regime = RiskRegime(
        regime_id=regime_id,
        regime_label=regime_label,
        score=_regime_score(hf, peg_dev_bps, utilization),
        drivers=drivers,
        explanation=explanation,
    )

    # ── Scenarios ───────────────────────────────────────────────────────────
    scenarios = _scenarios(req, utilization, liquidity_frac)

    return DeFiRiskAnalysisResponse(
        protocol_summary=ProtocolSummary(
            sample_id=req.sample_id,
            protocol_name=mkt.protocol_name,
            chain=mkt.chain,
            asset_symbol=mkt.asset_symbol,
            collateral_asset=pos.collateral_asset,
            debt_asset=pos.debt_asset,
        ),
        stablecoin_peg=stablecoin_peg,
        utilization_analysis=utilization_analysis,
        interest_rate_model=interest_rate_model,
        collateral_risk=collateral_risk,
        net_apy_analysis=net_apy_analysis,
        risk_regime=risk_regime,
        scenario_results=scenarios,
        notes=[
            "Peg deviation = (price − peg)/peg; utilization U = borrowed/supplied.",
            "Borrow rate uses a kinked model (base + slope₁ up to the kink, then "
            "slope₂); supply rate = borrow rate × U × (1 − reserve factor).",
            "Health factor = collateral value × liquidation threshold ÷ debt value; "
            "the approximate liquidation price assumes only the collateral price moves.",
            "Regime classification and stress scenarios are deterministic educational "
            "examples on static sample data — not forecasts, signals, or advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(
    req: DeFiRiskAnalysisRequest, base_u: float, base_liquidity_frac: float,
) -> List[DeFiScenarioResult]:
    stable = req.stablecoin
    mkt = req.market
    pos = req.position
    results: List[DeFiScenarioResult] = []

    for sid, name, desc, coll_shock, debt_shock, depeg, u_shock, liq_mult, rate_shock, thr_shock in _SCENARIOS:
        s_stable_price = max(stable.market_price * (1.0 + depeg), _EPS)
        s_peg_dev_bps = (s_stable_price - stable.target_peg) / stable.target_peg * 10000.0

        s_u = max(0.0, min(base_u + u_shock, 0.99))
        s_borrow = kinked_borrow_rate(s_u, mkt.base_rate, mkt.slope_1, mkt.slope_2, mkt.kink_utilization) + rate_shock
        s_supply = supply_rate(s_borrow, s_u, mkt.reserve_factor)

        s_coll_price = max(pos.collateral_price * (1.0 + coll_shock), _EPS)
        s_debt_price = max(pos.debt_price * (1.0 + debt_shock), _EPS)
        s_coll_value = pos.collateral_amount * s_coll_price
        s_debt_value = pos.debt_amount * s_debt_price
        s_thr = max(0.01, min(pos.liquidation_threshold + thr_shock, 1.0))

        s_ltv = s_debt_value / s_coll_value if s_coll_value > _EPS else 0.0
        s_hf = _health_factor(s_coll_value, s_debt_value, s_thr)
        s_liq_price = _liq_price(s_debt_value, pos.collateral_amount, s_thr)
        s_liq_dist_bps = (s_coll_price - s_liq_price) / s_coll_price * 10000.0 if s_coll_price > _EPS else 0.0

        s_net_apy = s_supply - s_borrow - req.fees_apy
        s_liquidity_frac = base_liquidity_frac * liq_mult
        _, regime_label, _, _ = _classify_regime(s_hf, s_peg_dev_bps, s_u, mkt.kink_utilization, s_liquidity_frac)

        results.append(
            DeFiScenarioResult(
                id=sid,
                name=name,
                description=desc,
                peg_deviation_bps=s_peg_dev_bps,
                utilization=s_u,
                borrow_apy=s_borrow,
                supply_apy=s_supply,
                collateral_value=s_coll_value,
                debt_value=s_debt_value,
                loan_to_value=s_ltv,
                health_factor=s_hf,
                liquidation_price=s_liq_price,
                liquidation_distance_bps=s_liq_dist_bps,
                net_apy=s_net_apy,
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
