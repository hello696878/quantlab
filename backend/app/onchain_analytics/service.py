"""
On-Chain Flow, Exchange Reserve & Whale Concentration Lab analytics (Phase 29.0)
— pure, deterministic.

Exchange inflow/outflow and reserve analytics, 24h activity metrics (active
addresses, transfer volume, transaction count, token velocity), an NVT-style
valuation ratio, holder-cohort distribution with a Gini-style concentration
approximation, whale flow pressure, a deterministic on-chain risk-regime
classification, and ten on-chain stress scenarios.

All outputs are finite by construction (every division is guarded; the NVT ratio
is capped when 24h transfer value is ~zero), so no NaN/Infinity reaches the API.
Educational only — not investment, trading, token, legal, tax, or risk-management
advice; not a production due-diligence engine; never live on-chain data, token
prices, wallets, RPC, smart-contract, explorer, or exchange API calls.
"""

from __future__ import annotations

from typing import List, Tuple

from app.onchain_analytics.models import (
    ActivityMetrics,
    ConcentrationAnalysis,
    ExchangeFlowAnalysis,
    HolderCohortInput,
    HolderDistributionRow,
    NetworkSummary,
    OnChainAnalysisRequest,
    OnChainAnalysisResponse,
    OnChainScenarioResult,
    OnChainValuationMetrics,
    RiskRegime,
    WhaleAnalysis,
)
from app.onchain_analytics.sample import DISCLAIMER

_EPS = 1e-12
_NVT_CAP = 99_999.0  # displayed NVT when 24h transfer value is ~zero

# Concentration-score weights (documented deterministic heuristic).
_W10, _W50, _W100 = 0.5, 0.3, 0.2

# Regime thresholds (deterministic, educational).
_NETFLOW_PCT_HIGH = 0.01      # |24h net exchange flow| ≥ 1% of circulating
_TOP10_HIGH = 0.30
_CONC_HIGH = 0.30
_NVT_HIGH = 50.0
_VELOCITY_LOW = 0.03
_VELOCITY_HIGH = 0.15
_NVT_LOW = 20.0
_SEVERE_TRIGGERS = 3

# id, name, description, price_shock, inflow_mult, outflow_mult, addr_shock,
# transfer_mult, whale_in_mult, whale_out_mult, concentration_shock
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample network as provided.", 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0),
    ("exchange_inflow_spike", "Exchange inflow spike", "24h exchange deposits triple.", 0.0, 3.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0),
    ("exchange_outflow_wave", "Exchange outflow wave", "24h exchange withdrawals triple.", 0.0, 1.0, 3.0, 0.0, 1.0, 1.0, 1.0, 0.0),
    ("whale_deposit_pressure", "Whale deposit pressure", "Whale deposits to exchanges surge.", 0.0, 1.5, 1.0, 0.0, 1.0, 2.5, 1.0, 0.0),
    ("whale_accumulation", "Whale accumulation", "Whales withdraw from exchanges to cold wallets.", 0.0, 1.0, 1.5, 0.0, 1.0, 1.0, 2.5, 0.0),
    ("active_address_slowdown", "Active address slowdown", "Active addresses fall 60%; activity cools.", 0.0, 1.0, 1.0, -0.60, 0.7, 1.0, 1.0, 0.0),
    ("transfer_volume_collapse", "Transfer volume collapse", "24h transfer volume falls 85%; NVT jumps.", 0.0, 1.0, 1.0, -0.20, 0.15, 1.0, 1.0, 0.0),
    ("high_velocity_burst", "High velocity activity burst", "Transfer volume triples on rising addresses.", 0.0, 1.0, 1.0, 0.40, 3.0, 1.0, 1.0, 0.0),
    ("holder_concentration_shock", "Holder concentration shock", "Top-holder shares rise 12 points.", 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.12),
    ("severe_combo", "Severe on-chain stress combo", "Price −40%, inflows ×3, addresses −50%, transfers ×0.4, whale deposits ×2, concentration +10 pts.", -0.40, 3.0, 1.0, -0.50, 0.4, 2.0, 1.0, 0.10),
]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _nvt(market_cap: float, transfer_value: float) -> float:
    if transfer_value <= _EPS:
        return _NVT_CAP
    return min(market_cap / transfer_value, _NVT_CAP)


def _nvt_status(nvt: float) -> str:
    if nvt < 15.0:
        return "low"
    if nvt < 50.0:
        return "moderate"
    if nvt < 100.0:
        return "elevated"
    return "high"


def _concentration_score(top10: float, top50: float, top100: float) -> float:
    """Documented deterministic weighted-share score: 0.5·top10 + 0.3·top50 + 0.2·top100."""
    return max(0.0, min(_W10 * top10 + _W50 * top50 + _W100 * top100, 1.0))


def _gini_style(cohorts: List[HolderCohortInput]) -> float:
    """Cohort-level Gini approximation from the Lorenz curve over holders.

    Cohorts are sorted by average balance; the discrete Lorenz curve accumulates
    holder share (x) vs balance share (y); Gini = 1 − Σ(xᵢ−xᵢ₋₁)(yᵢ+yᵢ₋₁).
    Bounded [0, 1); a cohort-level approximation that understates wallet-level
    inequality. Returns 0 when holders or balances are ~zero.
    """
    total_holders = sum(c.holder_count for c in cohorts)
    total_balance = sum(c.token_balance for c in cohorts)
    if total_holders <= _EPS or total_balance <= _EPS:
        return 0.0
    ordered = sorted(
        cohorts,
        key=lambda c: (c.token_balance / c.holder_count) if c.holder_count > _EPS else 0.0,
    )
    x_prev = y_prev = 0.0
    area2 = 0.0  # twice the area under the Lorenz curve
    for c in ordered:
        x = x_prev + c.holder_count / total_holders
        y = y_prev + c.token_balance / total_balance
        area2 += (x - x_prev) * (y + y_prev)
        x_prev, y_prev = x, y
    return max(0.0, min(1.0 - area2, 1.0))


_REGIME_LABELS = {
    "balanced_activity": "Balanced activity",
    "exchange_inflow_pressure": "Exchange inflow pressure",
    "exchange_outflow_accumulation": "Exchange outflow / accumulation",
    "whale_concentration_risk": "Whale concentration risk",
    "low_activity_high_valuation": "Low activity / high valuation",
    "high_velocity_activity": "High-velocity activity",
    "severe_onchain_stress": "Severe on-chain stress",
}

_REGIME_EXPLANATIONS = {
    "balanced_activity": "Flows, activity, and concentration are all moderate in this sample.",
    "exchange_inflow_pressure": "A large net token flow onto exchanges — potential sell-side supply in this sample.",
    "exchange_outflow_accumulation": "A large net token flow off exchanges — accumulation-style behaviour in this sample.",
    "whale_concentration_risk": "Top holders control a large share of the supply in this sample.",
    "low_activity_high_valuation": "The NVT-style ratio is high while transfer activity is weak in this sample.",
    "high_velocity_activity": "Transfer velocity is high against a modest NVT-style ratio in this sample.",
    "severe_onchain_stress": "Several on-chain dimensions are stressed at once in this sample.",
}


def _triggers(
    net_flow_pct: float, top10: float, conc_score: float, nvt: float, velocity: float,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if net_flow_pct >= _NETFLOW_PCT_HIGH:
        out.append(("exchange_inflow_pressure", f"net exchange inflow {net_flow_pct * 100:.2f}% of circulating ≥ {_NETFLOW_PCT_HIGH * 100:.0f}%"))
    if net_flow_pct <= -_NETFLOW_PCT_HIGH:
        out.append(("exchange_outflow_accumulation", f"net exchange outflow {abs(net_flow_pct) * 100:.2f}% of circulating ≥ {_NETFLOW_PCT_HIGH * 100:.0f}%"))
    if top10 >= _TOP10_HIGH or conc_score >= _CONC_HIGH:
        out.append(("whale_concentration_risk", f"top-10 share {top10 * 100:.0f}% / concentration score {conc_score:.2f} elevated"))
    if nvt >= _NVT_HIGH and velocity <= _VELOCITY_LOW:
        out.append(("low_activity_high_valuation", f"NVT {nvt:.0f} ≥ {_NVT_HIGH:.0f} with velocity {velocity:.3f} ≤ {_VELOCITY_LOW:.2f}"))
    if velocity >= _VELOCITY_HIGH and nvt <= _NVT_LOW:
        out.append(("high_velocity_activity", f"velocity {velocity:.2f} ≥ {_VELOCITY_HIGH:.2f} with NVT {nvt:.0f} ≤ {_NVT_LOW:.0f}"))
    return out


def _classify(
    net_flow_pct: float, top10: float, conc_score: float, nvt: float, velocity: float,
) -> Tuple[str, str, List[str], str]:
    trig = _triggers(net_flow_pct, top10, conc_score, nvt, velocity)
    if len(trig) >= _SEVERE_TRIGGERS:
        rid = "severe_onchain_stress"
        return rid, _REGIME_LABELS[rid], [d for _, d in trig], _REGIME_EXPLANATIONS[rid]
    if trig:
        rid, driver = trig[0]  # priority = trigger order above
        return rid, _REGIME_LABELS[rid], [driver], _REGIME_EXPLANATIONS[rid]
    rid = "balanced_activity"
    drivers = [
        f"net flow {net_flow_pct * 100:+.2f}% of circulating",
        f"top-10 share {top10 * 100:.0f}%",
        f"NVT {nvt:.0f}", f"velocity {velocity:.3f}",
    ]
    return rid, _REGIME_LABELS[rid], drivers, _REGIME_EXPLANATIONS[rid]


def _regime_score(net_flow_pct: float, conc_score: float, nvt: float, velocity: float) -> float:
    flow_comp = min(abs(net_flow_pct) / 0.02, 1.0)
    nvt_comp = min(nvt / 100.0, 1.0)
    activity_comp = min(max(_VELOCITY_LOW - velocity, 0.0) / _VELOCITY_LOW, 1.0)
    score = 0.35 * flow_comp + 0.25 * conc_score + 0.25 * nvt_comp + 0.15 * activity_comp
    return max(0.0, min(score, 1.0))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_onchain(req: OnChainAnalysisRequest) -> OnChainAnalysisResponse:
    net = req.network
    whale = req.whale_flow
    price = net.token_price
    circ = net.circulating_supply

    # ── Exchange flow ───────────────────────────────────────────────────────
    market_cap = price * circ
    net_flow = net.exchange_inflow_tokens_24h - net.exchange_outflow_tokens_24h
    net_flow_pct = net_flow / circ if circ > _EPS else 0.0
    reserve_ratio = net.exchange_reserve_tokens / circ if circ > _EPS else 0.0
    exchange_flow = ExchangeFlowAnalysis(
        exchange_reserve_tokens=net.exchange_reserve_tokens,
        exchange_reserve_value=price * net.exchange_reserve_tokens,
        exchange_reserve_ratio=reserve_ratio,
        exchange_inflow_tokens_24h=net.exchange_inflow_tokens_24h,
        exchange_outflow_tokens_24h=net.exchange_outflow_tokens_24h,
        net_exchange_flow_tokens=net_flow,
        net_exchange_flow_value=price * net_flow,
        net_exchange_flow_pct_circulating=net_flow_pct,
        reserve_change_tokens=net_flow,
    )

    # ── Activity ────────────────────────────────────────────────────────────
    velocity = net.transfer_volume_tokens_24h / circ if circ > _EPS else 0.0
    avg_tx = (
        net.average_transaction_value_tokens
        if net.average_transaction_value_tokens is not None
        else (
            net.transfer_volume_tokens_24h / net.transaction_count_24h
            if net.transaction_count_24h > _EPS
            else 0.0
        )
    )
    transfer_value = price * net.transfer_volume_tokens_24h
    activity = ActivityMetrics(
        active_addresses_24h=net.active_addresses_24h,
        transfer_volume_tokens_24h=net.transfer_volume_tokens_24h,
        transfer_volume_value_24h=transfer_value,
        transaction_count_24h=net.transaction_count_24h,
        average_transaction_value_tokens=avg_tx,
        token_velocity=velocity,
    )

    # ── Valuation ───────────────────────────────────────────────────────────
    nvt = _nvt(market_cap, transfer_value)
    valuation = OnChainValuationMetrics(
        token_price=price,
        market_cap=market_cap,
        nvt_ratio=nvt,
        nvt_status=_nvt_status(nvt),
    )

    # ── Holder distribution ─────────────────────────────────────────────────
    distribution = [
        HolderDistributionRow(
            cohort_name=c.cohort_name,
            holder_count=c.holder_count,
            token_balance=c.token_balance,
            balance_share=c.token_balance / circ if circ > _EPS else 0.0,
            average_balance=c.token_balance / c.holder_count if c.holder_count > _EPS else 0.0,
            description=c.description,
        )
        for c in req.holder_cohorts
    ]
    largest_share = max((r.balance_share for r in distribution), default=0.0)

    # ── Whale flow ──────────────────────────────────────────────────────────
    whale_net = whale.whale_inflow_tokens_24h - whale.whale_outflow_tokens_24h
    whale_analysis = WhaleAnalysis(
        whale_inflow_tokens_24h=whale.whale_inflow_tokens_24h,
        whale_outflow_tokens_24h=whale.whale_outflow_tokens_24h,
        whale_net_flow_tokens=whale_net,
        whale_net_flow_pct_circulating=whale_net / circ if circ > _EPS else 0.0,
        top_10_holder_share=whale.top_10_holder_share,
        top_50_holder_share=whale.top_50_holder_share,
        top_100_holder_share=whale.top_100_holder_share,
    )

    # ── Concentration ───────────────────────────────────────────────────────
    conc_score = _concentration_score(
        whale.top_10_holder_share, whale.top_50_holder_share, whale.top_100_holder_share,
    )
    gini = _gini_style(req.holder_cohorts)
    concentration = ConcentrationAnalysis(
        concentration_score=conc_score,
        gini_style_score=gini,
        largest_cohort_share=largest_share,
        notes=[
            "Concentration score = 0.5·top-10 + 0.3·top-50 + 0.2·top-100 shares "
            "(documented deterministic weighting on illustrative sample shares).",
            "Gini-style score is a cohort-level Lorenz-curve approximation — it "
            "understates wallet-level inequality and is not a formal Gini index.",
        ],
    )

    # ── Risk regime ─────────────────────────────────────────────────────────
    rid, label, drivers, explanation = _classify(
        net_flow_pct, whale.top_10_holder_share, conc_score, nvt, velocity,
    )
    regime = RiskRegime(
        regime_id=rid,
        regime_label=label,
        score=_regime_score(net_flow_pct, conc_score, nvt, velocity),
        drivers=drivers,
        explanation=explanation,
    )

    # ── Scenarios ───────────────────────────────────────────────────────────
    scenarios = _scenarios(req)

    return OnChainAnalysisResponse(
        network_summary=NetworkSummary(
            symbol=net.symbol,
            token_name=net.token_name,
            network_name=net.network_name,
            token_price=price,
            circulating_supply=circ,
        ),
        exchange_flow=exchange_flow,
        activity_metrics=activity,
        valuation_metrics=valuation,
        holder_distribution=distribution,
        whale_analysis=whale_analysis,
        concentration_analysis=concentration,
        risk_regime=regime,
        scenario_results=scenarios,
        notes=[
            "Net exchange flow = 24h inflow − outflow (positive = tokens moving onto "
            "exchanges); the reserve change uses the same 24h approximation.",
            "Velocity = 24h transfer volume ÷ circulating supply; NVT-style ratio = "
            "market cap ÷ 24h transfer value (capped when transfer value is ~zero).",
            "Whale inflow means whale deposits onto exchanges (potential sell-side "
            "pressure); whale outflow means withdrawals to whale wallets.",
            "Regime classification and stress scenarios are deterministic educational "
            "examples on static sample data — not forecasts, signals, or advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(req: OnChainAnalysisRequest) -> List[OnChainScenarioResult]:
    net = req.network
    whale = req.whale_flow
    circ = net.circulating_supply
    results: List[OnChainScenarioResult] = []

    for sid, name, desc, p_shock, in_m, out_m, addr_shock, tv_m, w_in_m, w_out_m, c_shock in _SCENARIOS:
        price = max(net.token_price * (1.0 + p_shock), _EPS)
        market_cap = price * circ

        inflow = net.exchange_inflow_tokens_24h * in_m
        outflow = net.exchange_outflow_tokens_24h * out_m
        net_flow = inflow - outflow
        net_flow_pct = net_flow / circ if circ > _EPS else 0.0
        # Reserve after applying the scenario's 24h net flow (floored at zero).
        reserve = max(net.exchange_reserve_tokens + net_flow, 0.0)
        reserve_ratio = reserve / circ if circ > _EPS else 0.0

        addresses = max(net.active_addresses_24h * (1.0 + addr_shock), 0.0)
        transfer_volume = net.transfer_volume_tokens_24h * tv_m
        velocity = transfer_volume / circ if circ > _EPS else 0.0
        nvt = _nvt(market_cap, price * transfer_volume)

        whale_net = whale.whale_inflow_tokens_24h * w_in_m - whale.whale_outflow_tokens_24h * w_out_m

        top10 = min(whale.top_10_holder_share + c_shock, 1.0)
        top50 = min(whale.top_50_holder_share + c_shock, 1.0)
        top100 = min(whale.top_100_holder_share + c_shock, 1.0)
        conc_score = _concentration_score(top10, top50, top100)

        _, regime_label, _, _ = _classify(net_flow_pct, top10, conc_score, nvt, velocity)

        results.append(
            OnChainScenarioResult(
                id=sid,
                name=name,
                description=desc,
                token_price=price,
                market_cap=market_cap,
                net_exchange_flow_tokens=net_flow,
                net_exchange_flow_pct_circulating=net_flow_pct,
                exchange_reserve_ratio=reserve_ratio,
                active_addresses_24h=addresses,
                transfer_volume_tokens_24h=transfer_volume,
                token_velocity=velocity,
                nvt_ratio=nvt,
                whale_net_flow_tokens=whale_net,
                concentration_score=conc_score,
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
