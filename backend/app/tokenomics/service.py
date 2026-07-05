"""
Tokenomics, Unlock Schedule & Treasury Risk Lab analytics (Phase 28.0) — pure,
deterministic.

Valuation (market cap, FDV, FDV ratio, float ratio), an unlock schedule with
cumulative dilution, unlock-pressure buckets, emission inflation and a real-yield
approximation, treasury value and runway, a documented holder-concentration
score, a deterministic tokenomics risk-regime classification, and ten unlock /
treasury stress scenarios.

All outputs are finite by construction (every division is guarded; runway months
are capped when the burn is ~zero), so no NaN/Infinity reaches the API.
Educational only — not investment, trading, token, venture, legal, tax, or
risk-management advice; not a production due-diligence engine; never live token
prices, on-chain data, wallets, RPC, or smart-contract calls.
"""

from __future__ import annotations

from typing import List, Tuple

from app.tokenomics.models import (
    EmissionAnalysis,
    HolderConcentration,
    RiskRegime,
    StakingAnalysis,
    TokenSummary,
    TokenomicsAnalysisRequest,
    TokenomicsAnalysisResponse,
    TokenomicsScenarioResult,
    TreasuryAnalysis,
    UnlockPressure,
    UnlockScheduleRow,
    ValuationMetrics,
)
from app.tokenomics.sample import DISCLAIMER

_EPS = 1e-12
_RUNWAY_CAP = 9999.0  # displayed months when the (net) burn is ~zero

# Regime thresholds (deterministic, educational).
_FDV_RATIO_HIGH = 5.0
_FLOAT_LOW = 0.25
_UNLOCK_180_HIGH = 0.15
_EMISSION_HIGH = 0.10
_RUNWAY_SHORT = 12.0
_TOP1_HIGH = 0.20
_TOP10_HIGH = 0.60
_SEVERE_TRIGGERS = 3

# id, name, description, price_shock, unlock_mult, emission_mult, burn_mult,
# treasury_shock, concentration_shock, revenue_mult
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample token as provided.", 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0),
    ("price_drawdown", "Price drawdown", "Token price falls 40%.", -0.40, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0),
    ("unlock_acceleration", "Unlock acceleration", "Scheduled unlocks double.", 0.0, 2.0, 1.0, 1.0, 0.0, 0.0, 1.0),
    ("emission_increase", "Emission increase", "Emission rate doubles.", 0.0, 1.0, 2.0, 1.0, 0.0, 0.0, 1.0),
    ("treasury_asset_drawdown", "Treasury asset drawdown", "Treasury assets fall 50%.", 0.0, 1.0, 1.0, 1.0, -0.50, 0.0, 1.0),
    ("burn_increase", "Monthly burn increase", "Monthly burn rises 80%.", 0.0, 1.0, 1.0, 1.8, 0.0, 0.0, 1.0),
    ("concentration_shock", "Concentration shock", "Top-holder shares rise 15 points.", 0.0, 1.0, 1.0, 1.0, 0.0, 0.15, 1.0),
    ("revenue_decline", "Revenue decline", "Protocol revenue falls 70% (revenue-adjusted runway shortens; gross-burn runway unchanged).", 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.3),
    ("low_float_repricing", "Low-float repricing", "Price falls 30% while unlocks run 50% hotter.", -0.30, 1.5, 1.0, 1.0, 0.0, 0.0, 1.0),
    ("severe_combo", "Severe tokenomics stress combo", "Price −50%, unlocks ×2, emissions ×1.5, burn ×1.5, treasury −40%, concentration +10 pts.", -0.50, 2.0, 1.5, 1.5, -0.40, 0.10, 0.7),
]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _runway(treasury_value: float, monthly_burn: float) -> float:
    if monthly_burn <= _EPS:
        return _RUNWAY_CAP
    return min(treasury_value / monthly_burn, _RUNWAY_CAP)


def _concentration_score(top1: float, top5: float, top10: float) -> float:
    """Documented deterministic weighted-share score: 0.5·top1 + 0.3·top5 + 0.2·top10."""
    return max(0.0, min(0.5 * top1 + 0.3 * top5 + 0.2 * top10, 1.0))


def _pressure_score(next_180d_pct: float) -> float:
    """Documented deterministic scale: 30% of circulating unlocking in 180d → 1.0."""
    return max(0.0, min(next_180d_pct / 0.30, 1.0))


def _triggers(
    fdv_ratio: float, float_ratio: float, next180_pct: float, inflation: float,
    real_yield: float, runway_months: float, top1: float, top10: float,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if fdv_ratio >= _FDV_RATIO_HIGH and float_ratio <= _FLOAT_LOW:
        out.append(("low_float_high_fdv", f"FDV/MC {fdv_ratio:.1f}× ≥ {_FDV_RATIO_HIGH:.0f}× with float {float_ratio * 100:.0f}% ≤ {_FLOAT_LOW * 100:.0f}%"))
    if next180_pct >= _UNLOCK_180_HIGH:
        out.append(("unlock_pressure", f"next-180d unlocks {next180_pct * 100:.0f}% of circulating ≥ {_UNLOCK_180_HIGH * 100:.0f}%"))
    if runway_months < _RUNWAY_SHORT:
        out.append(("treasury_runway_risk", f"runway {runway_months:.1f} months < {_RUNWAY_SHORT:.0f}"))
    if inflation >= _EMISSION_HIGH and real_yield < 0.0:
        out.append(("emission_pressure", f"emission inflation {inflation * 100:.0f}% ≥ {_EMISSION_HIGH * 100:.0f}% with negative real yield"))
    if top1 >= _TOP1_HIGH or top10 >= _TOP10_HIGH:
        out.append(("concentration_risk", f"top-1 {top1 * 100:.0f}% / top-10 {top10 * 100:.0f}% holder share elevated"))
    return out


_REGIME_LABELS = {
    "balanced": "Balanced",
    "low_float_high_fdv": "Low float / high FDV",
    "unlock_pressure": "Unlock pressure",
    "emission_pressure": "Emission pressure",
    "treasury_runway_risk": "Treasury runway risk",
    "concentration_risk": "Concentration risk",
    "severe_tokenomics_stress": "Severe tokenomics stress",
}

_REGIME_EXPLANATIONS = {
    "balanced": "No single tokenomics dimension is stressed in this sample.",
    "low_float_high_fdv": "A small circulating float against a large fully diluted valuation — future supply dominates in this sample.",
    "unlock_pressure": "A large share of the float unlocks within 180 days in this sample.",
    "emission_pressure": "Emission inflation exceeds the staking yield — the real yield is negative in this sample.",
    "treasury_runway_risk": "The treasury covers less than a year of burn at the current rate in this sample.",
    "concentration_risk": "Token holdings are concentrated in a few top holders in this sample.",
    "severe_tokenomics_stress": "Several tokenomics dimensions are stressed at once in this sample.",
}


def _classify(
    fdv_ratio: float, float_ratio: float, next180_pct: float, inflation: float,
    real_yield: float, runway_months: float, top1: float, top10: float,
) -> Tuple[str, str, List[str], str]:
    trig = _triggers(fdv_ratio, float_ratio, next180_pct, inflation, real_yield, runway_months, top1, top10)
    if len(trig) >= _SEVERE_TRIGGERS:
        rid = "severe_tokenomics_stress"
        return rid, _REGIME_LABELS[rid], [d for _, d in trig], _REGIME_EXPLANATIONS[rid]
    if trig:
        rid, driver = trig[0]  # priority = trigger order above
        return rid, _REGIME_LABELS[rid], [driver], _REGIME_EXPLANATIONS[rid]
    rid = "balanced"
    drivers = [
        f"FDV/MC {fdv_ratio:.1f}×", f"float {float_ratio * 100:.0f}%",
        f"next-180d unlocks {next180_pct * 100:.1f}%", f"runway {runway_months:.0f} months",
    ]
    return rid, _REGIME_LABELS[rid], drivers, _REGIME_EXPLANATIONS[rid]


def _regime_score(
    fdv_ratio: float, next180_pct: float, inflation: float, runway_months: float, conc_score: float,
) -> float:
    fdv_comp = min(max(fdv_ratio - 1.0, 0.0) / 9.0, 1.0)
    unlock_comp = min(next180_pct / 0.30, 1.0)
    emission_comp = min(max(inflation, 0.0) / 0.20, 1.0)
    runway_comp = (24.0 - min(runway_months, 24.0)) / 24.0
    score = 0.20 * fdv_comp + 0.25 * unlock_comp + 0.20 * emission_comp + 0.20 * runway_comp + 0.15 * conc_score
    return max(0.0, min(score, 1.0))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_tokenomics(req: TokenomicsAnalysisRequest) -> TokenomicsAnalysisResponse:
    mkt = req.market
    hold = req.holder_concentration
    price = mkt.price
    circ = mkt.circulating_supply
    total = mkt.total_supply

    # ── Valuation ───────────────────────────────────────────────────────────
    market_cap = price * circ
    fdv = price * total
    fdv_ratio = fdv / market_cap if market_cap > _EPS else 0.0
    float_ratio = circ / total if total > _EPS else 0.0
    valuation = ValuationMetrics(
        market_cap=market_cap,
        fully_diluted_valuation=fdv,
        fdv_to_market_cap=fdv_ratio,
        float_ratio=float_ratio,
        circulating_supply=circ,
        total_supply=total,
        max_supply=mkt.max_supply,
    )

    # ── Unlock schedule ─────────────────────────────────────────────────────
    events = sorted(req.unlock_events, key=lambda e: e.days_until)
    schedule: List[UnlockScheduleRow] = []
    cum_tokens = 0.0
    for e in events:
        cum_tokens += e.tokens
        schedule.append(
            UnlockScheduleRow(
                date=e.date,
                days_until=e.days_until,
                category=e.category,
                tokens=e.tokens,
                unlock_value=price * e.tokens,
                unlock_pct_circulating=e.tokens / circ if circ > _EPS else 0.0,
                cumulative_unlock_tokens=cum_tokens,
                cumulative_unlock_pct_circulating=cum_tokens / circ if circ > _EPS else 0.0,
                description=e.description,
            )
        )

    def bucket(days: float) -> float:
        return sum(e.tokens for e in events if e.days_until <= days)

    n30, n90, n180, n365 = bucket(30.0), bucket(90.0), bucket(180.0), bucket(365.0)
    next180_pct = n180 / circ if circ > _EPS else 0.0
    unlock_pressure = UnlockPressure(
        next_30d_tokens=n30,
        next_90d_tokens=n90,
        next_180d_tokens=n180,
        next_365d_tokens=n365,
        next_180d_pct_circulating=next180_pct,
        pressure_score=_pressure_score(next180_pct),
        notes=[
            "Pressure score scales the next-180-day unlocks against 30% of the "
            "circulating supply (documented deterministic scale).",
            "Unlocks are potential new float — not a forecast of selling.",
        ],
    )

    # ── Emissions & staking ─────────────────────────────────────────────────
    annual_emission_tokens = circ * mkt.emission_rate_annual
    emission_inflation = annual_emission_tokens / circ if circ > _EPS else 0.0
    emission = EmissionAnalysis(
        emission_rate_annual=mkt.emission_rate_annual,
        annual_emission_tokens=annual_emission_tokens,
        annual_emission_value=price * annual_emission_tokens,
        emission_inflation=emission_inflation,
        notes=[
            "Annual emission = circulating supply × emission rate; with this v1 "
            "definition the emission inflation equals the emission rate.",
        ],
    )
    real_yield = mkt.staking_yield - emission_inflation
    revenue_yield = (
        (mkt.protocol_revenue_annual / market_cap)
        if (mkt.protocol_revenue_annual is not None and market_cap > _EPS)
        else None
    )
    staking = StakingAnalysis(
        staking_yield=mkt.staking_yield,
        real_yield_approx=real_yield,
        protocol_revenue_yield=revenue_yield,
        notes=[
            "Real yield ≈ staking yield − emission inflation: a dilution-adjusted "
            "approximation, not a return estimate or forecast.",
        ],
    )

    # ── Treasury ────────────────────────────────────────────────────────────
    treasury_tokens = mkt.treasury_tokens or 0.0
    treasury_stables = mkt.treasury_stables or 0.0
    treasury_token_value = price * treasury_tokens
    treasury_total = treasury_token_value + treasury_stables
    monthly_revenue = (mkt.protocol_revenue_annual or 0.0) / 12.0
    runway = _runway(treasury_total, mkt.monthly_burn_usd)
    runway_adj = _runway(treasury_total, max(mkt.monthly_burn_usd - monthly_revenue, _EPS))
    treasury = TreasuryAnalysis(
        treasury_token_value=treasury_token_value,
        treasury_stables=treasury_stables,
        treasury_total_value=treasury_total,
        monthly_burn_usd=mkt.monthly_burn_usd,
        monthly_revenue_usd=monthly_revenue,
        runway_months=runway,
        revenue_adjusted_runway_months=runway_adj,
        notes=[
            f"Runway months are capped at {_RUNWAY_CAP:.0f} when the (net) burn is ~zero.",
            "Treasury tokens are valued at the same sample price as the float — a "
            "simplification; selling treasury tokens would itself move the price.",
        ],
    )

    # ── Holder concentration ────────────────────────────────────────────────
    conc_score = _concentration_score(
        hold.top_1_holder_share, hold.top_5_holder_share, hold.top_10_holder_share,
    )
    concentration = HolderConcentration(
        top_1_holder_share=hold.top_1_holder_share,
        top_5_holder_share=hold.top_5_holder_share,
        top_10_holder_share=hold.top_10_holder_share,
        insider_share=hold.insider_share,
        foundation_share=hold.foundation_share,
        community_share=hold.community_share,
        concentration_score=conc_score,
        notes=[
            "Concentration score = 0.5·top-1 + 0.3·top-5 + 0.2·top-10 shares "
            "(documented deterministic weighting on illustrative sample shares).",
        ],
    )

    # ── Risk regime ─────────────────────────────────────────────────────────
    rid, label, drivers, explanation = _classify(
        fdv_ratio, float_ratio, next180_pct, emission_inflation, real_yield,
        runway, hold.top_1_holder_share, hold.top_10_holder_share,
    )
    regime = RiskRegime(
        regime_id=rid,
        regime_label=label,
        score=_regime_score(fdv_ratio, next180_pct, emission_inflation, runway, conc_score),
        drivers=drivers,
        explanation=explanation,
    )

    # ── Scenarios ───────────────────────────────────────────────────────────
    scenarios = _scenarios(req, n180, treasury_tokens, treasury_stables)

    return TokenomicsAnalysisResponse(
        token_summary=TokenSummary(symbol=mkt.symbol, token_name=mkt.token_name, price=price),
        valuation_metrics=valuation,
        unlock_schedule=schedule,
        unlock_pressure=unlock_pressure,
        emission_analysis=emission,
        staking_analysis=staking,
        treasury_analysis=treasury,
        holder_concentration=concentration,
        risk_regime=regime,
        scenario_results=scenarios,
        notes=[
            "Market cap = price × circulating supply; FDV = price × total supply; "
            "float ratio = circulating ÷ total.",
            "Unlock pressure sums scheduled unlocks inside each horizon as a share "
            "of the circulating supply.",
            "Real yield ≈ staking yield − emission inflation; treasury runway = "
            "treasury value ÷ monthly burn (revenue-adjusted variant nets revenue).",
            "Regime classification and stress scenarios are deterministic educational "
            "examples on static sample data — not forecasts, ratings, or advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(
    req: TokenomicsAnalysisRequest, base_n180: float, treasury_tokens: float, treasury_stables: float,
) -> List[TokenomicsScenarioResult]:
    mkt = req.market
    hold = req.holder_concentration
    circ = mkt.circulating_supply
    total = mkt.total_supply
    results: List[TokenomicsScenarioResult] = []

    for sid, name, desc, p_shock, u_mult, e_mult, b_mult, t_shock, c_shock, _rev_mult in _SCENARIOS:
        price = max(mkt.price * (1.0 + p_shock), _EPS)
        market_cap = price * circ
        fdv = price * total
        fdv_ratio = fdv / market_cap if market_cap > _EPS else 0.0

        next180_pct = (base_n180 * u_mult) / circ if circ > _EPS else 0.0
        inflation = mkt.emission_rate_annual * e_mult
        real_yield = mkt.staking_yield - inflation

        treasury_value = max((price * treasury_tokens + treasury_stables) * (1.0 + t_shock), 0.0)
        runway = _runway(treasury_value, mkt.monthly_burn_usd * b_mult)

        top1 = min(hold.top_1_holder_share + c_shock, 1.0)
        top5 = min(hold.top_5_holder_share + c_shock, 1.0)
        top10 = min(hold.top_10_holder_share + c_shock, 1.0)
        conc_score = _concentration_score(top1, top5, top10)

        float_ratio = circ / total if total > _EPS else 0.0
        _, regime_label, _, _ = _classify(
            fdv_ratio, float_ratio, next180_pct, inflation, real_yield, runway, top1, top10,
        )

        results.append(
            TokenomicsScenarioResult(
                id=sid,
                name=name,
                description=desc,
                price=price,
                market_cap=market_cap,
                fully_diluted_valuation=fdv,
                fdv_to_market_cap=fdv_ratio,
                next_180d_unlock_pressure=next180_pct,
                emission_inflation=inflation,
                real_yield_approx=real_yield,
                treasury_value=treasury_value,
                runway_months=runway,
                concentration_score=conc_score,
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
