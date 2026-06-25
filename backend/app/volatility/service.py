"""
Volatility Lab analytics (Phase 24.0) — pure, deterministic computation.

Reuses the Options Lab Black-Scholes (price / greeks / bisection IV solver) to
invert implied vols from sample quotes, then builds the smile / skew / term
structure / surface, a realized-vol comparison, a simplified educational
variance-swap fair-strike approximation, vega exposure, and volatility scenarios.

All outputs are finite by construction (divisions guarded, IV failures returned
as ``None`` with a note), so no NaN/Infinity reaches the API. Educational only —
not investment / trading advice, and not official VIX / exchange methodology.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.options import black_scholes_greeks, implied_volatility
from app.volatility.models import (
    ImpliedRealizedSpread,
    OptionAnalysis,
    RealizedVolatility,
    SkewMetric,
    SmilePoint,
    SurfaceSummary,
    TermStructurePoint,
    UnderlyingSummary,
    VarianceStripPoint,
    VarianceSwap,
    VegaExposure,
    VegaGroup,
    VolatilityAnalysisRequest,
    VolatilityAnalysisResponse,
    VolatilityScenarioResult,
)
from app.volatility.sample import DISCLAIMER

_EPS = 1e-12
_TRADING_DAYS = 252

# id, name, description, parallel, skew, term_slope, spot_shock
_SCENARIOS = [
    ("base", "Base case", "No shifts.", 0.0, 0.0, 0.0, 0.0),
    ("parallel_vol_up", "Parallel vol up", "Whole surface +5 vol points.", 0.05, 0.0, 0.0, 0.0),
    ("parallel_vol_down", "Parallel vol down", "Whole surface −5 vol points.", -0.05, 0.0, 0.0, 0.0),
    ("skew_steepening", "Skew steepening", "Downside vols richer (steeper skew).", 0.0, 0.10, 0.0, 0.0),
    ("skew_flattening", "Skew flattening", "Skew compresses toward flat.", 0.0, -0.10, 0.0, 0.0),
    ("short_dated_vol_spike", "Short-dated vol spike", "Front-end vol jumps, back-end softer.", 0.06, 0.0, -0.10, 0.0),
    ("long_dated_vol_repricing", "Long-dated vol repricing", "Back-end vol re-rates higher.", 0.02, 0.0, 0.06, 0.0),
    ("spot_selloff_vol_up", "Spot selloff with vol up", "Spot −7% with vol up and steeper skew.", 0.06, 0.05, 0.0, -0.07),
]


def _iv_shift(parallel: float, skew: float, term_slope: float, moneyness: float, t_years: float) -> float:
    return parallel + skew * (1.0 - moneyness) + term_slope * (t_years - 0.25)


def _stdev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return math.sqrt(max(var, 0.0))


def analyze_volatility(req: VolatilityAnalysisRequest) -> VolatilityAnalysisResponse:
    u = req.underlying
    S, r, q = u.spot_price, u.risk_free_rate, u.dividend_yield

    # ── Per-option implied vol + greeks ────────────────────────────────────
    analyses: List[OptionAnalysis] = []
    iv_by_id: Dict[str, Optional[float]] = {}
    vega_by_id: Dict[str, float] = {}
    for quote in req.option_quotes:
        t = quote.maturity_days / 365.0
        forward = S * math.exp((r - q) * t)
        moneyness = quote.strike / S
        log_m = math.log(quote.strike / forward) if forward > _EPS else 0.0
        iv, _conv, _it, warning = implied_volatility(
            quote.option_type, quote.mid_price, S, quote.strike, t, r, q
        )
        sigma = iv if iv is not None else 0.0
        greeks = black_scholes_greeks(quote.option_type, S, quote.strike, t, r, max(sigma, 1e-6), q)
        vega = float(greeks["vega"])
        delta = float(greeks["delta"])
        if quote.option_type == "call":
            intrinsic = max(S - quote.strike, 0.0)
        else:
            intrinsic = max(quote.strike - S, 0.0)
        iv_by_id[quote.option_id] = iv
        vega_by_id[quote.option_id] = vega
        analyses.append(
            OptionAnalysis(
                option_id=quote.option_id,
                option_type=quote.option_type,
                strike=quote.strike,
                maturity_days=quote.maturity_days,
                maturity_years=t,
                moneyness=moneyness,
                log_moneyness=log_m,
                mid_price=quote.mid_price,
                implied_volatility=iv,
                iv_note=warning,
                vega=vega,
                delta=delta,
                intrinsic_value=intrinsic,
                time_value=quote.mid_price - intrinsic,
            )
        )

    solved = [a for a in analyses if a.implied_volatility is not None]
    maturities = sorted({a.maturity_days for a in analyses})

    # ── Smile points ───────────────────────────────────────────────────────
    smile_points = [
        SmilePoint(
            maturity_days=a.maturity_days,
            strike=a.strike,
            moneyness=a.moneyness,
            implied_volatility=a.implied_volatility,  # type: ignore[arg-type]
            option_type=a.option_type,
            vega=a.vega,
        )
        for a in solved
    ]

    def _closest(maturity: int, target_m: float) -> Optional[OptionAnalysis]:
        pool = [a for a in solved if a.maturity_days == maturity]
        if not pool:
            return None
        return min(pool, key=lambda a: abs(a.moneyness - target_m))

    # ── Term structure (ATM IV per maturity) ───────────────────────────────
    term_structure: List[TermStructurePoint] = []
    atm_by_maturity: Dict[int, float] = {}
    for mat in maturities:
        atm = _closest(mat, 1.0)
        if atm and atm.implied_volatility is not None:
            atm_by_maturity[mat] = atm.implied_volatility
            term_structure.append(
                TermStructurePoint(maturity_days=mat, atm_implied_volatility=atm.implied_volatility)
            )

    # ── Skew metrics per maturity ──────────────────────────────────────────
    skew_metrics: List[SkewMetric] = []
    for mat in maturities:
        atm = atm_by_maturity.get(mat)
        p90 = _closest(mat, 0.90)
        c110 = _closest(mat, 1.10)
        if atm is None or p90 is None or c110 is None:
            continue
        put_90 = p90.implied_volatility or 0.0
        call_110 = c110.implied_volatility or 0.0
        skew_metrics.append(
            SkewMetric(
                maturity_days=mat,
                put_90_iv=put_90,
                atm_iv=atm,
                call_110_iv=call_110,
                put_spread=put_90 - atm,
                call_spread=call_110 - atm,
                skew_slope=(call_110 - put_90) / (1.10 - 0.90),
            )
        )

    # ── Surface summary ────────────────────────────────────────────────────
    ivs = [a.implied_volatility for a in solved if a.implied_volatility is not None]

    def _atm_at(days: int) -> float:
        if atm_by_maturity:
            return atm_by_maturity.get(days, min(atm_by_maturity.items(), key=lambda kv: abs(kv[0] - days))[1])
        return 0.0

    steepest = max(skew_metrics, key=lambda s: abs(s.skew_slope)).maturity_days if skew_metrics else (maturities[0] if maturities else 0)
    atm_30 = _atm_at(30)
    atm_1y = _atm_at(365)
    surface_summary = SurfaceSummary(
        atm_iv_30d=atm_30,
        atm_iv_90d=_atm_at(90),
        atm_iv_1y=atm_1y,
        min_iv=min(ivs) if ivs else 0.0,
        max_iv=max(ivs) if ivs else 0.0,
        average_iv=sum(ivs) / len(ivs) if ivs else 0.0,
        steepest_skew_maturity=steepest,
        term_structure_slope=atm_1y - atm_30,
    )

    # ── Realized volatility ────────────────────────────────────────────────
    returns = u.realized_returns or []
    realized = _stdev(returns) * math.sqrt(_TRADING_DAYS)

    def _window(n: int) -> Optional[float]:
        if len(returns) >= n:
            return _stdev(returns[-n:]) * math.sqrt(_TRADING_DAYS)
        return None

    realized_volatility = RealizedVolatility(
        num_returns=len(returns),
        realized_vol_annual=realized,
        realized_vol_20d=_window(20),
        realized_vol_60d=_window(60),
        realized_vol_120d=_window(120),
    )
    implied_realized = ImpliedRealizedSpread(
        implied_atm_30d=atm_30, realized_vol=realized, spread=atm_30 - realized
    )

    # ── Variance swap fair strike (option-strip approximation) ─────────────
    variance_swap = _variance_swap(req, S, r, q, analyses)

    # ── Vega exposure ──────────────────────────────────────────────────────
    vega_exposure = _vega_exposure(req, analyses, vega_by_id)

    # ── Scenarios ──────────────────────────────────────────────────────────
    pos_vega: Dict[str, float] = {}
    pos_delta: Dict[str, float] = {}
    positions = req.positions or []
    a_by_id = {a.option_id: a for a in analyses}
    for p in positions:
        a = a_by_id.get(p.option_id)
        if a:
            pos_vega[p.option_id] = a.vega * p.quantity * p.contract_multiplier
            pos_delta[p.option_id] = a.delta * p.quantity * p.contract_multiplier
    total_vega = sum(pos_vega.values())
    base_skew = skew_metrics[0].skew_slope if skew_metrics else 0.0

    scenarios: List[VolatilityScenarioResult] = []
    for sid, name, desc, par, skew, term, spot in _SCENARIOS:
        value_change = 0.0
        for a in analyses:
            d_sigma = _iv_shift(par, skew, term, a.moneyness, a.maturity_years)
            value_change += pos_vega.get(a.option_id, 0.0) * d_sigma
            value_change += pos_delta.get(a.option_id, 0.0) * (S * spot)
        shifted_atm_30 = atm_30 + _iv_shift(par, skew, term, 1.0, 30 / 365.0)
        shifted_atm_1y = atm_1y + _iv_shift(par, skew, term, 1.0, 1.0)
        scenarios.append(
            VolatilityScenarioResult(
                id=sid,
                name=name,
                description=desc,
                parallel_iv_shift=par,
                skew_shift=skew,
                term_structure_shift=term,
                spot_shock=spot,
                shifted_atm_iv_30d=shifted_atm_30,
                shifted_atm_iv_1y=shifted_atm_1y,
                term_structure_slope=shifted_atm_1y - shifted_atm_30,
                atm_iv_change=shifted_atm_30 - atm_30,
                skew_change=skew,
                portfolio_value_change=value_change,
                total_vega=total_vega,
                notes=["Illustrative deterministic scenario — not a forecast."],
            )
        )

    return VolatilityAnalysisResponse(
        underlying=UnderlyingSummary(symbol=u.symbol, spot_price=S, risk_free_rate=r, dividend_yield=q),
        option_quotes=analyses,
        smile_points=smile_points,
        term_structure=term_structure,
        skew_metrics=skew_metrics,
        surface_summary=surface_summary,
        realized_volatility=realized_volatility,
        implied_realized_spread=implied_realized,
        variance_swap=variance_swap,
        vega_exposure=vega_exposure,
        scenario_results=scenarios,
        notes=[
            "Implied vols are recovered with a bisection Black-Scholes solver "
            "(reused from the Options Lab); failures return null with a note.",
            "Smile/skew/term structure and the surface are built from the recovered "
            "implied vols; ATM IV uses the strike closest to spot.",
            "The variance-swap fair strike is a simplified educational option-strip "
            "approximation — NOT official VIX / exchange methodology.",
            "Vega exposure and scenario value changes are first-order (vega/delta) "
            "approximations on illustrative sample positions, not trading advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _variance_swap(req, S, r, q, analyses: List[OptionAnalysis]) -> VarianceSwap:
    maturities = sorted({a.maturity_days for a in analyses})
    target = req.variance_swap_maturity_days or (maturities[0] if maturities else 30)
    mat = min(maturities, key=lambda d: abs(d - target)) if maturities else target
    t = mat / 365.0
    forward = S * math.exp((r - q) * t)

    pool = sorted(
        [a for a in analyses if a.maturity_days == mat and a.mid_price > 0],
        key=lambda a: a.strike,
    )
    strip: List[VarianceStripPoint] = []
    total = 0.0
    for i, a in enumerate(pool):
        # OTM leg: put below the forward, call above.
        otm_type = "put" if a.strike < forward else "call"
        if a.option_type != otm_type:
            continue
        if i == 0:
            dk = pool[1].strike - a.strike if len(pool) > 1 else a.strike * 0.05
        elif i == len(pool) - 1:
            dk = a.strike - pool[i - 1].strike
        else:
            dk = (pool[i + 1].strike - pool[i - 1].strike) / 2.0
        dk = max(dk, _EPS)
        weight = dk / (a.strike ** 2)
        contribution = weight * a.mid_price
        total += contribution
        strip.append(
            VarianceStripPoint(
                strike=a.strike,
                otm_type=otm_type,
                otm_price=a.mid_price,
                delta_k=dk,
                weight=weight,
                contribution=contribution,
            )
        )

    variance_strike = (2.0 * math.exp(r * t) / t) * total if t > _EPS else 0.0
    variance_strike = max(variance_strike, 0.0)
    return VarianceSwap(
        maturity_days=mat,
        maturity_years=t,
        forward=forward,
        variance_strike=variance_strike,
        volatility_strike=math.sqrt(variance_strike),
        strip_points=strip,
        notes=[
            "Educational option-strip approximation: K_var² ≈ (2·e^{rT}/T)·Σ ΔK/K²·Q(K). "
            "NOT official VIX / exchange methodology; coarse strike grid.",
        ],
    )


def _vega_exposure(req, analyses: List[OptionAnalysis], vega_by_id: Dict[str, float]) -> VegaExposure:
    a_by_id = {a.option_id: a for a in analyses}
    if req.positions:
        positions = [(p.option_id, p.quantity, p.contract_multiplier) for p in req.positions]
    else:
        positions = [(a.option_id, 1.0, 100.0) for a in analyses]

    total = 0.0
    by_mat: Dict[int, float] = {}
    by_money: Dict[str, float] = {}
    for oid, qty, mult in positions:
        a = a_by_id.get(oid)
        if not a:
            continue
        pv = a.vega * qty * mult
        total += pv
        by_mat[a.maturity_days] = by_mat.get(a.maturity_days, 0.0) + pv
        bucket = "<0.95" if a.moneyness < 0.95 else (">1.05" if a.moneyness > 1.05 else "0.95–1.05")
        by_money[bucket] = by_money.get(bucket, 0.0) + pv

    return VegaExposure(
        total_vega=total,
        positions_used=len(positions),
        vega_by_maturity=[VegaGroup(key=f"{d}d", vega=v) for d, v in sorted(by_mat.items())],
        vega_by_moneyness=[VegaGroup(key=k, vega=by_money[k]) for k in ("<0.95", "0.95–1.05", ">1.05") if k in by_money],
    )
