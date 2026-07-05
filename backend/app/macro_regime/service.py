"""
Macro Regime & Cross-Asset Allocation Lab analytics (Phase 31.0) — pure,
deterministic.

Indicator z-scores and direction-adjusted category scores (growth, inflation,
policy, liquidity, credit stress, USD pressure), a composite macro score, a
deterministic regime classification, regime-adjusted cross-asset return
assumptions, a simplified category-based correlation matrix, inverse-volatility /
risk-parity-style / regime-tilted educational allocations with risk
contributions, and ten macro stress scenarios.

All outputs are finite by construction (every division is guarded; the tilted
weights fall back to inverse-vol with a note when all scores are non-positive),
so no NaN/Infinity reaches the API. Educational only — not investment, trading,
or asset-allocation advice; not a production allocation engine; never live macro
or market data.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from app.macro_regime.models import (
    AllocationResult,
    AssetAssumptionRow,
    CategoryScores,
    IndicatorRow,
    MacroRegime,
    MacroRegimeAnalysisRequest,
    MacroRegimeAnalysisResponse,
    MacroScenarioResult,
    SampleSummary,
)
from app.macro_regime.sample import DISCLAIMER

_EPS = 1e-12
_CATEGORIES = ("growth", "inflation", "policy", "liquidity", "credit", "fx")

# Composite macro-score weights (documented; per the spec formula the credit
# term is subtracted).
_W_COMPOSITE = {"growth": 0.30, "inflation": 0.20, "policy": 0.15, "liquidity": 0.20, "credit": 0.15}

# Simplified correlation matrix (documented): same category 0.75, cash pairs
# 0.0, everything else 0.25; correlation stress blends off-diagonals toward 1.
_RHO_SAME = 0.75
_RHO_CROSS = 0.25

_RISK_PARITY_ITERS = 40

# id, name, description, growth, inflation, policy, liquidity, credit, usd,
# vol_mult, corr_stress  (shocks are additive shifts to the category scores)
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample macro state as provided.", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    ("growth_upside", "Growth upside", "Growth score shifts +1.0.", 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    ("growth_slowdown", "Growth slowdown", "Growth score shifts −1.0.", -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    ("inflation_spike", "Inflation spike", "Inflation +1.25 with tighter policy.", 0.0, 1.25, 0.6, 0.0, 0.0, 0.0, 1.1, 0.1),
    ("disinflation", "Disinflation", "Inflation score shifts −1.0.", 0.0, -1.0, -0.25, 0.0, 0.0, 0.0, 1.0, 0.0),
    ("policy_tightening", "Policy tightening", "Policy +1.0 as liquidity drains.", 0.0, 0.0, 1.0, -0.5, 0.0, 0.0, 1.1, 0.1),
    ("liquidity_easing", "Liquidity easing", "Liquidity +1.0 as policy eases.", 0.0, 0.0, -0.5, 1.0, 0.0, 0.0, 0.9, 0.0),
    ("credit_spread_shock", "Credit spread shock", "Credit stress +1.25 as growth wobbles.", -0.25, 0.0, 0.0, -0.25, 1.25, 0.0, 1.25, 0.25),
    ("strong_usd_shock", "Strong USD shock", "USD pressure +1.25 with tighter policy.", 0.0, 0.0, 0.25, 0.0, 0.0, 1.25, 1.1, 0.1),
    ("severe_combo", "Severe macro stress combo", "Growth −2, inflation +1.5, credit +1.8, liquidity −1.8, USD +1.2; vol ×1.5.", -2.0, 1.5, 0.0, -1.8, 1.8, 1.2, 1.5, 0.5),
]


# --------------------------------------------------------------------------- #
# Macro scoring
# --------------------------------------------------------------------------- #
def _indicator_rows(req: MacroRegimeAnalysisRequest) -> List[IndicatorRow]:
    rows: List[IndicatorRow] = []
    for i in req.indicators:
        z = (i.value - i.long_run_mean) / i.long_run_std
        d = 1.0 if i.direction == "higher_is_expansionary" else -1.0
        rows.append(
            IndicatorRow(
                name=i.name,
                category=i.category,
                value=i.value,
                long_run_mean=i.long_run_mean,
                long_run_std=i.long_run_std,
                z_score=z,
                direction_adjusted_score=d * z,
                weight=i.weight,
            )
        )
    return rows


def _category_scores(rows: List[IndicatorRow]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for cat in _CATEGORIES:
        cat_rows = [r for r in rows if r.category == cat]
        wsum = sum(r.weight for r in cat_rows)
        out[cat] = (
            sum(r.weight * r.direction_adjusted_score for r in cat_rows) / wsum
            if wsum > _EPS
            else 0.0
        )
    return out


def _composite(scores: Dict[str, float]) -> float:
    return (
        _W_COMPOSITE["growth"] * scores["growth"]
        + _W_COMPOSITE["inflation"] * scores["inflation"]
        + _W_COMPOSITE["policy"] * scores["policy"]
        + _W_COMPOSITE["liquidity"] * scores["liquidity"]
        - _W_COMPOSITE["credit"] * scores["credit"]
    )


# --------------------------------------------------------------------------- #
# Regime classification
# --------------------------------------------------------------------------- #
_REGIME_LABELS = {
    "goldilocks_growth": "Goldilocks growth",
    "inflation_shock": "Inflation shock",
    "recession_credit_stress": "Recession / credit stress",
    "stagflation": "Stagflation",
    "liquidity_easing": "Liquidity easing",
    "policy_tightening": "Policy tightening",
    "strong_usd_pressure": "Strong USD pressure",
    "severe_macro_stress": "Severe macro stress",
}

_REGIME_EXPLANATIONS = {
    "goldilocks_growth": "Solid growth with contained inflation and easy liquidity in this sample.",
    "inflation_shock": "Hot inflation with tightening policy pressure in this sample.",
    "recession_credit_stress": "Weak growth with elevated credit stress in this sample.",
    "stagflation": "Weak growth combined with hot inflation in this sample.",
    "liquidity_easing": "Easy liquidity with light policy pressure in this sample.",
    "policy_tightening": "Tight policy draining liquidity in this sample.",
    "strong_usd_pressure": "Strong USD pressure alongside tight policy in this sample.",
    "severe_macro_stress": "Several macro dimensions are stressed at once in this sample.",
}

# Prototype category vectors used only as a deterministic nearest-match
# fallback when no threshold rule fires (documented).
_PROTOTYPES = {
    "goldilocks_growth": (1.0, -0.5, 0.0, 0.5, -0.5, 0.0),
    "inflation_shock": (0.0, 1.0, 0.75, -0.25, 0.0, 0.0),
    "recession_credit_stress": (-1.0, 0.0, -0.25, -0.25, 1.0, 0.0),
    "stagflation": (-1.0, 1.0, 0.0, 0.0, 0.5, 0.0),
    "liquidity_easing": (0.25, 0.0, -0.5, 1.0, -0.25, 0.0),
    "policy_tightening": (0.0, 0.25, 1.0, -0.75, 0.25, 0.25),
    "strong_usd_pressure": (0.0, 0.0, 0.5, -0.25, 0.0, 1.0),
}


def _severe_extremes(s: Dict[str, float]) -> List[str]:
    out = []
    if s["growth"] <= -1.0:
        out.append(f"growth score {s['growth']:+.2f} ≤ −1")
    if s["inflation"] >= 1.0:
        out.append(f"inflation score {s['inflation']:+.2f} ≥ +1")
    if s["policy"] >= 1.0:
        out.append(f"policy score {s['policy']:+.2f} ≥ +1")
    if s["liquidity"] <= -1.0:
        out.append(f"liquidity score {s['liquidity']:+.2f} ≤ −1")
    if s["credit"] >= 1.0:
        out.append(f"credit stress score {s['credit']:+.2f} ≥ +1")
    if s["fx"] >= 1.0:
        out.append(f"USD pressure score {s['fx']:+.2f} ≥ +1")
    return out


def _classify(s: Dict[str, float]) -> Tuple[str, str, List[str], str]:
    extremes = _severe_extremes(s)
    if len(extremes) >= 3:
        rid = "severe_macro_stress"
        return rid, _REGIME_LABELS[rid], extremes, _REGIME_EXPLANATIONS[rid]

    def done(rid: str, drivers: List[str]):
        return rid, _REGIME_LABELS[rid], drivers, _REGIME_EXPLANATIONS[rid]

    if s["growth"] <= -0.5 and s["credit"] >= 0.5:
        return done("recession_credit_stress", [f"growth {s['growth']:+.2f} ≤ −0.5", f"credit stress {s['credit']:+.2f} ≥ +0.5"])
    if s["growth"] <= -0.5 and s["inflation"] >= 0.5:
        return done("stagflation", [f"growth {s['growth']:+.2f} ≤ −0.5", f"inflation {s['inflation']:+.2f} ≥ +0.5"])
    if s["inflation"] >= 0.5 and s["policy"] >= 0.25:
        return done("inflation_shock", [f"inflation {s['inflation']:+.2f} ≥ +0.5", f"policy {s['policy']:+.2f} ≥ +0.25"])
    if s["fx"] >= 0.5 and s["policy"] >= 0.25:
        return done("strong_usd_pressure", [f"USD pressure {s['fx']:+.2f} ≥ +0.5", f"policy {s['policy']:+.2f} ≥ +0.25"])
    if s["policy"] >= 0.5 and s["liquidity"] <= 0.0:
        return done("policy_tightening", [f"policy {s['policy']:+.2f} ≥ +0.5", f"liquidity {s['liquidity']:+.2f} ≤ 0"])
    if s["growth"] >= 0.3 and s["inflation"] <= 0.3 and s["liquidity"] >= -0.2:
        return done("goldilocks_growth", [f"growth {s['growth']:+.2f} ≥ +0.3", f"inflation {s['inflation']:+.2f} contained", f"liquidity {s['liquidity']:+.2f} supportive"])
    if s["liquidity"] >= 0.5 and s["policy"] <= 0.25:
        return done("liquidity_easing", [f"liquidity {s['liquidity']:+.2f} ≥ +0.5", f"policy {s['policy']:+.2f} light"])

    # Nearest-prototype fallback (deterministic dot product).
    vec = (s["growth"], s["inflation"], s["policy"], s["liquidity"], s["credit"], s["fx"])
    best_id = max(
        sorted(_PROTOTYPES),
        key=lambda rid: sum(a * b for a, b in zip(_PROTOTYPES[rid], vec)),
    )
    return done(best_id, [f"nearest prototype match on category scores ({best_id})"])


def _regime_score(s: Dict[str, float]) -> float:
    stress = (
        max(-s["growth"], 0.0) + max(s["inflation"], 0.0) + max(s["policy"], 0.0)
        + max(-s["liquidity"], 0.0) + max(s["credit"], 0.0) + max(s["fx"], 0.0)
    )
    return max(0.0, min(stress / 6.0, 1.0))


# --------------------------------------------------------------------------- #
# Assets, correlation, allocations
# --------------------------------------------------------------------------- #
def _adjusted_returns(assets, s: Dict[str, float]) -> List[float]:
    return [
        a.expected_return
        + a.growth_beta * s["growth"]
        + a.inflation_beta * s["inflation"]
        + a.rate_beta * s["policy"]
        + a.usd_beta * s["fx"]
        - a.credit_beta * s["credit"]
        for a in assets
    ]


def _correlation(assets, stress: float) -> List[List[float]]:
    n = len(assets)
    rho = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if assets[i].category == "cash" or assets[j].category == "cash":
                base = 0.0
            elif assets[i].category == assets[j].category:
                base = _RHO_SAME
            else:
                base = _RHO_CROSS
            rho[i][j] = base + stress * (1.0 - base)
    return rho


def _portfolio_stats(weights: List[float], mus: List[float], vols: List[float], rho: List[List[float]]) -> Tuple[float, float]:
    mu_p = sum(w * m for w, m in zip(weights, mus))
    var = 0.0
    n = len(weights)
    for i in range(n):
        for j in range(n):
            var += weights[i] * weights[j] * vols[i] * vols[j] * rho[i][j]
    return mu_p, math.sqrt(max(var, 0.0))


def _simple_risk_contributions(weights: List[float], vols: List[float]) -> List[float]:
    total = sum(w * v for w, v in zip(weights, vols))
    if total <= _EPS:
        return [0.0] * len(weights)
    return [w * v / total for w, v in zip(weights, vols)]


def _inverse_vol_weights(vols: List[float]) -> List[float]:
    inv = [1.0 / v if v > _EPS else 0.0 for v in vols]
    total = sum(inv)
    return [x / total for x in inv] if total > _EPS else [1.0 / len(vols)] * len(vols)


def _risk_parity_weights(vols: List[float], rho: List[List[float]]) -> List[float]:
    """Fixed-point equal-risk-contribution approximation on the simplified Σ."""
    n = len(vols)
    w = _inverse_vol_weights(vols)
    for _ in range(_RISK_PARITY_ITERS):
        # Marginal contributions (Σw)_i and total variance.
        sigma_w = [sum(vols[i] * vols[j] * rho[i][j] * w[j] for j in range(n)) for i in range(n)]
        var = sum(w[i] * sigma_w[i] for i in range(n))
        if var <= _EPS:
            break
        target = var / n
        new_w = []
        for i in range(n):
            rc = w[i] * sigma_w[i]
            factor = math.sqrt(target / rc) if rc > _EPS else 1.0
            new_w.append(max(w[i] * factor, _EPS))
        total = sum(new_w)
        w = [x / total for x in new_w]
    return w


def _tilted_weights(
    mus: List[float], vols: List[float], liq: List[float], lam: float, eta: float,
) -> Tuple[List[float], bool]:
    scores = [m - lam * v + eta * l for m, v, l in zip(mus, vols, liq)]
    positive = [max(t, 0.0) for t in scores]
    total = sum(positive)
    if total <= _EPS:
        return _inverse_vol_weights(vols), True
    return [p / total for p in positive], False


def _allocations(assets, mus, vols, rho, lam, eta) -> List[AllocationResult]:
    ids = [a.asset_id for a in assets]

    def result(method: str, weights: List[float], notes: List[str]) -> AllocationResult:
        mu_p, sigma_p = _portfolio_stats(weights, mus, vols, rho)
        rcs = _simple_risk_contributions(weights, vols)
        return AllocationResult(
            method=method,
            weights=dict(zip(ids, weights)),
            portfolio_expected_return=mu_p,
            portfolio_volatility_approx=sigma_p,
            risk_contributions=dict(zip(ids, rcs)),
            notes=notes,
        )

    inv = _inverse_vol_weights(vols)
    rp = _risk_parity_weights(vols, rho)
    tilted, fell_back = _tilted_weights(mus, vols, [a.liquidity_score for a in assets], lam, eta)

    tilt_notes = [
        "Tilted score T = μ_regime − λσ + ηL, normalised over positive scores — an "
        "educational construction, not an allocation recommendation.",
    ]
    if fell_back:
        tilt_notes.append("All tilted scores were non-positive — fell back to inverse-volatility weights.")

    return [
        result("inverse_volatility", inv, ["Weights ∝ 1/σ on the sample volatilities."]),
        result("risk_parity_style", rp, [
            f"Equal-risk-contribution fixed-point approximation ({_RISK_PARITY_ITERS} iterations) "
            "on the simplified category-based correlation matrix.",
        ]),
        result("regime_tilted", tilted, tilt_notes),
    ]


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_macro_regime(req: MacroRegimeAnalysisRequest) -> MacroRegimeAnalysisResponse:
    rows = _indicator_rows(req)
    scores = _category_scores(rows)
    composite = _composite(scores)

    category_scores = CategoryScores(
        growth_score=scores["growth"],
        inflation_score=scores["inflation"],
        policy_score=scores["policy"],
        liquidity_score=scores["liquidity"],
        credit_stress_score=scores["credit"],
        usd_pressure_score=scores["fx"],
        composite_macro_score=composite,
    )

    rid, label, drivers, explanation = _classify(scores)
    regime = MacroRegime(
        regime_id=rid,
        regime_label=label,
        score=_regime_score(scores),
        drivers=drivers,
        explanation=explanation,
    )

    assets = req.assets
    mus = _adjusted_returns(assets, scores)
    vols = [a.volatility for a in assets]
    rho = _correlation(assets, 0.0)

    asset_assumptions = [
        AssetAssumptionRow(
            asset_id=a.asset_id,
            asset_name=a.asset_name,
            category=a.category,
            expected_return=a.expected_return,
            regime_adjusted_expected_return=mu,
            volatility=a.volatility,
            liquidity_score=a.liquidity_score,
            growth_beta=a.growth_beta,
            inflation_beta=a.inflation_beta,
            rate_beta=a.rate_beta,
            usd_beta=a.usd_beta,
            credit_beta=a.credit_beta,
        )
        for a, mu in zip(assets, mus)
    ]

    allocations = _allocations(assets, mus, vols, rho, req.risk_aversion_lambda, req.liquidity_preference_eta)
    scenarios = _scenarios(req, scores)

    return MacroRegimeAnalysisResponse(
        sample_summary=SampleSummary(
            sample_id=req.sample_id,
            sample_name=req.sample_name,
            indicator_count=len(req.indicators),
            asset_count=len(assets),
        ),
        indicator_table=rows,
        category_scores=category_scores,
        macro_regime=regime,
        asset_assumptions=asset_assumptions,
        allocation_results=allocations,
        scenario_results=scenarios,
        notes=[
            "Category scores are weighted direction-adjusted z-scores; a higher score "
            "means stronger growth / hotter inflation / tighter policy / easier "
            "liquidity / more credit stress / stronger USD pressure.",
            "Regime-adjusted returns shift the sample assumptions by illustrative "
            "betas times category scores — assumptions, not forecasts.",
            "The correlation matrix is a simplified category-based construction "
            "(same category 0.75, cross 0.25, cash 0.0); allocations are educational "
            "constructions, not recommendations.",
            "Regime classification and stress scenarios are deterministic educational "
            "examples on static sample data — not forecasts, signals, or advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(req: MacroRegimeAnalysisRequest, base_scores: Dict[str, float]) -> List[MacroScenarioResult]:
    assets = req.assets
    ids = [a.asset_id for a in assets]
    results: List[MacroScenarioResult] = []

    for sid, name, desc, g, pi, p, l, c, u, vol_mult, corr_stress in _SCENARIOS:
        s = {
            "growth": base_scores["growth"] + g,
            "inflation": base_scores["inflation"] + pi,
            "policy": base_scores["policy"] + p,
            "liquidity": base_scores["liquidity"] + l,
            "credit": base_scores["credit"] + c,
            "fx": base_scores["fx"] + u,
        }
        _, regime_label, _, _ = _classify(s)

        mus = _adjusted_returns(assets, s)
        vols = [a.volatility * vol_mult for a in assets]
        rho = _correlation(assets, corr_stress)
        tilted, _ = _tilted_weights(
            mus, vols, [a.liquidity_score for a in assets],
            req.risk_aversion_lambda, req.liquidity_preference_eta,
        )
        mu_p, sigma_p = _portfolio_stats(tilted, mus, vols, rho)
        largest = ids[max(range(len(ids)), key=lambda i: tilted[i])]

        results.append(
            MacroScenarioResult(
                id=sid,
                name=name,
                description=desc,
                growth_score=s["growth"],
                inflation_score=s["inflation"],
                policy_score=s["policy"],
                liquidity_score=s["liquidity"],
                credit_stress_score=s["credit"],
                usd_pressure_score=s["fx"],
                regime_label=regime_label,
                portfolio_expected_return=mu_p,
                portfolio_volatility_approx=sigma_p,
                largest_weight_asset=largest,
                notes=["Illustrative deterministic scenario (regime-tilted weights) — not a forecast or advice."],
            )
        )
    return results
