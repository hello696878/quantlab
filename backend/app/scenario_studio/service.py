"""
Unified Scenario Studio & Cross-Lab Report Builder analytics (Phase 32.0) —
pure, deterministic.

A lightweight educational cross-lab impact layer: the selected scenario
template (plus optional overrides) is mapped through documented linear weight
tables into per-module impact scores I_m = clip_0_100(Σ_k w_{m,k}·|s_k|)
(multipliers contribute max(mult − 1, 0)), a composite severity (mean of the
included module impacts), a deterministic scenario-regime classification, a
module × shock-group heatmap, illustrative baseline-vs-stress metric rows, and
a deterministic Markdown report builder.

It intentionally does NOT call the other labs' engines — the scores are a
transparent teaching approximation of cross-module sensitivity, not risk
measurements. All outputs are finite by construction (inputs are FiniteFloat,
every score is clipped), so no NaN/Infinity reaches the API. Educational only —
not investment, trading, or asset-allocation advice; not a production risk
report; never live data.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.scenario_studio.models import (
    BaselineStressRow,
    GeneratedReport,
    GlobalShockRow,
    HeatmapCell,
    ModuleImpactRow,
    ReportBuilderSummary,
    ReportSection,
    ScenarioRegime,
    ScenarioStudioAnalysisResponse,
    ScenarioStudioRequest,
    ScenarioTemplateInput,
)
from app.scenario_studio.sample import (
    DISCLAIMER,
    MODULE_LABELS,
    SECTION_TITLES,
    template_by_id,
)

_MODULE_IDS = list(MODULE_LABELS.keys())
_SECTION_IDS = list(SECTION_TITLES.keys())

# Shock metadata: id -> (label, neutral value, contribution kind).
# "abs" contributes |value|; "excess" contributes max(value - 1, 0).
_SHOCKS: Dict[str, Tuple[str, float, str]] = {
    "growth_shock": ("Growth shock", 0.0, "abs"),
    "inflation_shock": ("Inflation shock", 0.0, "abs"),
    "policy_shock": ("Policy shock", 0.0, "abs"),
    "liquidity_shock": ("Liquidity shock", 0.0, "abs"),
    "credit_shock": ("Credit shock", 0.0, "abs"),
    "usd_shock": ("USD shock", 0.0, "abs"),
    "equity_shock": ("Equity shock", 0.0, "abs"),
    "rate_shock": ("Rate shock", 0.0, "abs"),
    "credit_spread_shock": ("Credit spread shock", 0.0, "abs"),
    "crypto_price_shock": ("Crypto price shock", 0.0, "abs"),
    "funding_rate_shock": ("Funding rate shock", 0.0, "abs"),
    "defi_liquidity_shock": ("DeFi liquidity shock", 0.0, "abs"),
    "stablecoin_depeg_shock": ("Stablecoin depeg shock", 0.0, "abs"),
    "whale_concentration_shock": ("Whale concentration shock", 0.0, "abs"),
    "sentiment_shock": ("Sentiment shock", 0.0, "abs"),
    "volatility_multiplier": ("Volatility multiplier", 1.0, "excess"),
    "token_unlock_multiplier": ("Token unlock multiplier", 1.0, "excess"),
    "exchange_inflow_multiplier": ("Exchange inflow multiplier", 1.0, "excess"),
    "publication_lag_shock": ("Publication lag shock", 0.0, "abs"),
}

# Documented per-module weight tables (spec formulas): module -> [(shock, w)].
_MODULE_TERMS: Dict[str, List[Tuple[str, float]]] = {
    "macro_regime": [
        ("growth_shock", 20.0), ("inflation_shock", 20.0), ("policy_shock", 15.0),
        ("liquidity_shock", 15.0), ("credit_shock", 20.0), ("usd_shock", 10.0),
    ],
    "portfolio_risk": [
        ("equity_shock", 30.0), ("rate_shock", 20.0),
        ("credit_spread_shock", 25.0), ("volatility_multiplier", 25.0),
    ],
    "crypto_derivatives": [
        ("crypto_price_shock", 35.0), ("funding_rate_shock", 25.0),
        ("volatility_multiplier", 25.0), ("exchange_inflow_multiplier", 15.0),
    ],
    "defi_risk": [
        ("crypto_price_shock", 35.0), ("defi_liquidity_shock", 30.0),
        ("stablecoin_depeg_shock", 25.0), ("volatility_multiplier", 10.0),
    ],
    "tokenomics": [
        ("crypto_price_shock", 30.0), ("token_unlock_multiplier", 35.0),
        ("whale_concentration_shock", 20.0), ("volatility_multiplier", 15.0),
    ],
    "onchain_analytics": [
        ("exchange_inflow_multiplier", 30.0), ("crypto_price_shock", 25.0),
        ("whale_concentration_shock", 25.0), ("volatility_multiplier", 20.0),
    ],
    "alternative_data": [
        ("sentiment_shock", 35.0), ("publication_lag_shock", 25.0),
        ("volatility_multiplier", 20.0), ("equity_shock", 20.0),
    ],
    "market_microstructure": [
        ("volatility_multiplier", 35.0), ("equity_shock", 25.0),
        ("crypto_price_shock", 20.0), ("liquidity_shock", 20.0),
    ],
}

# Illustrative calm-state baseline readings (documented sample constants).
_MODULE_BASELINES: Dict[str, float] = {
    "macro_regime": 12.0,
    "portfolio_risk": 15.0,
    "crypto_derivatives": 18.0,
    "defi_risk": 16.0,
    "tokenomics": 14.0,
    "onchain_analytics": 13.0,
    "alternative_data": 11.0,
    "market_microstructure": 15.0,
}

# Heatmap columns: shock-group label -> member shocks.
_HEATMAP_GROUPS: List[Tuple[str, List[str]]] = [
    ("Macro & policy", ["growth_shock", "inflation_shock", "policy_shock", "usd_shock"]),
    ("Credit & liquidity", ["liquidity_shock", "credit_shock", "credit_spread_shock"]),
    ("Market & vol", ["equity_shock", "rate_shock", "volatility_multiplier"]),
    ("Crypto market", ["crypto_price_shock", "funding_rate_shock"]),
    ("DeFi & on-chain", [
        "defi_liquidity_shock", "stablecoin_depeg_shock", "token_unlock_multiplier",
        "exchange_inflow_multiplier", "whale_concentration_shock",
    ]),
    ("Data quality", ["sentiment_shock", "publication_lag_shock"]),
]

_REGIME_LABELS = {
    "benign_cross_asset": "Benign cross-asset",
    "macro_policy_stress": "Macro / policy stress",
    "credit_liquidity_stress": "Credit & liquidity stress",
    "crypto_specific_stress": "Crypto-specific stress",
    "data_quality_stress": "Data-quality stress",
    "broad_risk_off": "Broad risk-off",
    "severe_systemic_stress": "Severe systemic stress",
}

_LIMITATIONS = [
    "Static illustrative sample data — not live macro, market, crypto, or news data, and not current.",
    "Module impact scores are documented linear teaching weights on standardized shock units — not calibrated risk measurements and not outputs of the underlying lab engines.",
    "Baseline-vs-stress rows use illustrative sample metrics with simplified linear transforms — not portfolio, position, or protocol measurements.",
    "The scenario regime uses fixed deterministic thresholds — a constructed classification, not a market regime detector.",
    "The generated report is a deterministic educational summary — not a production risk report, not investment research, and not investment, trading, asset-allocation, legal, tax, or risk-management advice.",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _clip_0_100(x: float) -> float:
    return min(max(x, 0.0), 100.0)


def _bucket(x: float) -> str:
    if x < 15.0:
        return "low"
    if x < 35.0:
        return "moderate"
    if x < 55.0:
        return "elevated"
    if x < 75.0:
        return "high"
    return "severe"


def _shock_value(shocks: Dict[str, float], shock_id: str) -> float:
    """Contribution magnitude for one shock (abs, or excess above 1.0)."""
    _, _, kind = _SHOCKS[shock_id]
    v = shocks[shock_id]
    return max(v - 1.0, 0.0) if kind == "excess" else abs(v)


def _resolve_shocks(
    template: ScenarioTemplateInput, request: ScenarioStudioRequest
) -> Tuple[Dict[str, float], Dict[str, bool]]:
    """Template values with any custom overrides applied on top."""
    shocks: Dict[str, float] = {}
    overridden: Dict[str, bool] = {}
    ov = request.custom_overrides
    for shock_id in _SHOCKS:
        base = getattr(template, shock_id)
        over = getattr(ov, shock_id) if ov is not None else None
        shocks[shock_id] = float(base if over is None else over)
        overridden[shock_id] = over is not None
    return shocks, overridden


def _term_contributions(module_id: str, shocks: Dict[str, float]) -> List[Tuple[str, float]]:
    """(shock_id, weighted contribution) for one module, largest first."""
    contribs = [
        (shock_id, w * _shock_value(shocks, shock_id))
        for shock_id, w in _MODULE_TERMS[module_id]
    ]
    return sorted(contribs, key=lambda t: (-t[1], t[0]))


def _impact_score(module_id: str, shocks: Dict[str, float]) -> float:
    return _clip_0_100(sum(c for _, c in _term_contributions(module_id, shocks)))


# --------------------------------------------------------------------------- #
# Module impacts + heatmap
# --------------------------------------------------------------------------- #
def _module_rows(
    included: List[str], impacts: Dict[str, float], shocks: Dict[str, float]
) -> List[ModuleImpactRow]:
    rows: List[ModuleImpactRow] = []
    for mid in _MODULE_IDS:
        if mid not in included:
            continue
        impact = impacts[mid]
        baseline = _MODULE_BASELINES[mid]
        drivers = [
            f"{_SHOCKS[sid][0]} (+{c:.1f} pts)"
            for sid, c in _term_contributions(mid, shocks)[:3]
            if c > 0.0
        ] or ["No active shocks for this module"]
        rows.append(
            ModuleImpactRow(
                module_id=mid,  # type: ignore[arg-type]
                module_label=MODULE_LABELS[mid],
                baseline_score=baseline,
                stressed_score=_clip_0_100(baseline + impact),
                impact_score=impact,
                impact_bucket=_bucket(impact),  # type: ignore[arg-type]
                drivers=drivers,
                notes=[
                    "Documented linear teaching weights on standardized shock "
                    "units — illustrative sensitivity, not a risk measurement."
                ],
            )
        )
    return rows


def _heatmap(included: List[str], shocks: Dict[str, float]) -> List[HeatmapCell]:
    cells: List[HeatmapCell] = []
    for mid in _MODULE_IDS:
        if mid not in included:
            continue
        contribs = dict(_term_contributions(mid, shocks))
        for group_label, members in _HEATMAP_GROUPS:
            value = _clip_0_100(sum(contribs.get(sid, 0.0) for sid in members))
            cells.append(
                HeatmapCell(
                    row_label=MODULE_LABELS[mid],
                    column_label=group_label,
                    value=value,
                    bucket=_bucket(value),  # type: ignore[arg-type]
                )
            )
    return cells


# --------------------------------------------------------------------------- #
# Baseline vs stress metric rows (illustrative sample metrics)
# --------------------------------------------------------------------------- #
def _baseline_stress_rows(
    included: List[str], shocks: Dict[str, float]
) -> List[BaselineStressRow]:
    s = shocks
    metric_defs: Dict[str, Tuple[str, float, float]] = {
        "macro_regime": (
            "Composite macro score (sample)",
            0.40,
            0.40 + 0.30 * s["growth_shock"] - 0.20 * s["inflation_shock"]
            - 0.15 * s["policy_shock"] + 0.20 * s["liquidity_shock"]
            - 0.15 * s["credit_shock"],
        ),
        "portfolio_risk": (
            "Portfolio volatility (ann., sample)",
            0.12,
            0.12 * s["volatility_multiplier"],
        ),
        "crypto_derivatives": (
            "Annualized perp funding (sample)",
            0.10,
            0.10 + 0.10 * s["funding_rate_shock"],
        ),
        "defi_risk": (
            "Lending health factor (sample)",
            1.85,
            max(
                1.85
                * (1.0 + 0.15 * s["crypto_price_shock"])
                * (1.0 - 0.10 * abs(s["stablecoin_depeg_shock"])),
                0.0,
            ),
        ),
        "tokenomics": (
            "Next-180d unlock, % of circulating (sample)",
            0.06,
            0.06 * s["token_unlock_multiplier"],
        ),
        "onchain_analytics": (
            "Net exchange flow, % of circulating (sample)",
            0.001,
            0.005 * s["exchange_inflow_multiplier"] - 0.004,
        ),
        "alternative_data": (
            "Average event sentiment (sample)",
            0.15,
            min(max(0.15 + 0.5 * s["sentiment_shock"], -1.0), 1.0),
        ),
        "market_microstructure": (
            "Quoted spread, bps (sample)",
            4.0,
            4.0 * s["volatility_multiplier"] * (1.0 + 0.25 * abs(s["liquidity_shock"])),
        ),
    }
    rows: List[BaselineStressRow] = []
    for mid in _MODULE_IDS:
        if mid not in included:
            continue
        name, base, stressed = metric_defs[mid]
        rows.append(
            BaselineStressRow(
                metric_name=name,
                baseline_value=base,
                stressed_value=stressed,
                change=stressed - base,
                module_id=mid,  # type: ignore[arg-type]
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Regime classification
# --------------------------------------------------------------------------- #
def _classify_regime(impacts: Dict[str, float], shocks: Dict[str, float]) -> ScenarioRegime:
    avg_all = sum(impacts.values()) / len(impacts)
    very_high = [mid for mid in _MODULE_IDS if impacts[mid] >= 70.0]
    crypto_cluster = sum(
        impacts[m] for m in ("crypto_derivatives", "defi_risk", "tokenomics", "onchain_analytics")
    ) / 4.0
    clusters: List[Tuple[str, float]] = [
        ("macro_policy_stress", _clip_0_100(
            25.0 * abs(shocks["inflation_shock"]) + 20.0 * abs(shocks["policy_shock"])
            + 15.0 * abs(shocks["growth_shock"]))),
        ("credit_liquidity_stress", _clip_0_100(
            30.0 * abs(shocks["credit_shock"]) + 25.0 * abs(shocks["liquidity_shock"])
            + 25.0 * abs(shocks["credit_spread_shock"]))),
        ("crypto_specific_stress", crypto_cluster),
        ("data_quality_stress", _clip_0_100(
            45.0 * abs(shocks["sentiment_shock"]) + 35.0 * shocks["publication_lag_shock"])),
        ("broad_risk_off", (
            impacts["portfolio_risk"] + impacts["macro_regime"]
            + impacts["market_microstructure"]) / 3.0),
    ]

    if len(very_high) >= 5:
        regime_id = "severe_systemic_stress"
        explanation = (
            f"{len(very_high)} of {len(_MODULE_IDS)} modules score at or above "
            "70/100 simultaneously — the documented threshold for severe "
            "systemic stress in this teaching classification."
        )
    elif avg_all < 15.0:
        regime_id = "benign_cross_asset"
        explanation = (
            f"Average module impact is {avg_all:.1f}/100, below the documented "
            "15-point benign threshold — small shocks across every module."
        )
    else:
        regime_id, best = max(clusters, key=lambda c: c[1])
        # Deterministic tie-break: first cluster in the documented order wins.
        for cid, val in clusters:
            if val == best:
                regime_id = cid
                break
        explanation = (
            f"The {_REGIME_LABELS[regime_id]} cluster scores highest "
            f"({best:.1f}) among the documented deterministic cluster scores, "
            f"with average module impact {avg_all:.1f}/100."
        )

    # Top scenario-level drivers: largest weighted contributions across modules.
    totals: Dict[str, float] = {}
    for mid in _MODULE_IDS:
        for sid, c in _term_contributions(mid, shocks):
            totals[sid] = totals.get(sid, 0.0) + c
    top = sorted(totals.items(), key=lambda t: (-t[1], t[0]))[:3]
    drivers = [
        f"{_SHOCKS[sid][0]} (+{c:.1f} pts across modules)" for sid, c in top if c > 0.0
    ] or ["No active shocks"]

    return ScenarioRegime(
        regime_id=regime_id,  # type: ignore[arg-type]
        regime_label=_REGIME_LABELS[regime_id],
        severity_score=_clip_0_100(avg_all),
        drivers=drivers,
        explanation=explanation,
        notes=[
            "Fixed deterministic thresholds on documented teaching scores — a "
            "constructed classification, not a market regime detector."
        ],
    )


# --------------------------------------------------------------------------- #
# Report builder
# --------------------------------------------------------------------------- #
def _fmt_shock(shocks: Dict[str, float], sid: str) -> str:
    label, neutral, _ = _SHOCKS[sid]
    v = shocks[sid]
    if neutral == 1.0:
        return f"{label} ×{v:.2f}"
    return f"{label} {v:+.2f}"


def _section_markdown(
    sid: str,
    scenario: ScenarioTemplateInput,
    shocks: Dict[str, float],
    impacts: Dict[str, float],
    regime: ScenarioRegime,
    composite: float,
    included_modules: List[str],
) -> str:
    def module_line(mid: str, shock_ids: List[str]) -> str:
        status = "included" if mid in included_modules else "not selected in this run"
        shock_txt = "; ".join(_fmt_shock(shocks, s) for s in shock_ids)
        return (
            f"Impact score **{impacts[mid]:.1f}/100** ({_bucket(impacts[mid])}; "
            f"module {status}). Key applied shocks: {shock_txt}. The score is a "
            "documented linear teaching weight on standardized shock units — "
            "an illustrative sensitivity, not a risk measurement."
        )

    if sid == "executive_summary":
        return (
            f"Scenario **{scenario.scenario_name}** — {scenario.description} "
            f"Composite severity is **{composite:.1f}/100** across "
            f"{len(included_modules)} included module(s); the scenario "
            f"classifies as **{regime.regime_label}** "
            f"(severity {regime.severity_score:.1f}/100 over all modules). "
            f"Top drivers: {', '.join(regime.drivers)}. All figures are "
            "deterministic educational scores on static sample shocks."
        )
    if sid == "macro":
        return module_line(
            "macro_regime",
            ["growth_shock", "inflation_shock", "policy_shock", "liquidity_shock", "credit_shock", "usd_shock"],
        )
    if sid == "portfolio":
        return module_line(
            "portfolio_risk",
            ["equity_shock", "rate_shock", "credit_spread_shock", "volatility_multiplier"],
        )
    if sid == "crypto":
        return module_line(
            "crypto_derivatives",
            ["crypto_price_shock", "funding_rate_shock", "volatility_multiplier", "exchange_inflow_multiplier"],
        )
    if sid == "defi":
        return module_line(
            "defi_risk",
            ["crypto_price_shock", "defi_liquidity_shock", "stablecoin_depeg_shock"],
        )
    if sid == "tokenomics":
        return module_line(
            "tokenomics",
            ["crypto_price_shock", "token_unlock_multiplier", "whale_concentration_shock"],
        )
    if sid == "onchain":
        return module_line(
            "onchain_analytics",
            ["exchange_inflow_multiplier", "crypto_price_shock", "whale_concentration_shock"],
        )
    if sid == "alternative_data":
        return module_line(
            "alternative_data",
            ["sentiment_shock", "publication_lag_shock", "volatility_multiplier"],
        )
    # limitations
    return "\n".join(f"- {line}" for line in _LIMITATIONS)


def _build_report(
    request: ScenarioStudioRequest,
    scenario: ScenarioTemplateInput,
    shocks: Dict[str, float],
    impacts: Dict[str, float],
    regime: ScenarioRegime,
    composite: float,
) -> Tuple[ReportBuilderSummary, GeneratedReport]:
    # Limitations is always included, whatever was requested.
    requested = set(request.report_sections) | {"limitations"}
    included_ids = [sid for sid in _SECTION_IDS if sid in requested]
    coverage = len(included_ids) / len(_SECTION_IDS)

    sections: List[ReportSection] = []
    for sid in _SECTION_IDS:
        sections.append(
            ReportSection(
                section_id=sid,  # type: ignore[arg-type]
                section_title=SECTION_TITLES[sid],
                included=sid in requested,
                markdown=_section_markdown(
                    sid, scenario, shocks, impacts, regime, composite,
                    list(request.included_modules),
                ),
            )
        )

    title = f"Unified Scenario Studio Report — {scenario.scenario_name}"
    subtitle = (
        "Deterministic educational cross-lab stress summary on static "
        "illustrative sample data — not investment research."
    )
    parts = [f"# {title}", f"_{subtitle}_", ""]
    for sec in sections:
        if not sec.included:
            continue
        parts.append(f"## {sec.section_title}")
        parts.append(sec.markdown)
        parts.append("")
    parts.append(f"> {DISCLAIMER}")
    markdown = "\n".join(parts)

    summary = ReportBuilderSummary(
        available_sections=_SECTION_IDS,  # type: ignore[arg-type]
        included_sections=included_ids,  # type: ignore[arg-type]
        section_coverage=coverage,
        notes=[
            "Section coverage C = N_included / N_available.",
            "The Limitations section is always included in the generated report.",
        ],
    )
    report = GeneratedReport(
        title=title,
        subtitle=subtitle,
        sections=sections,
        markdown=markdown,
        limitations=list(_LIMITATIONS),
    )
    return summary, report


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def analyze_scenario_studio(request: ScenarioStudioRequest) -> ScenarioStudioAnalysisResponse:
    """Deterministic cross-lab impact + report analytics for one request.

    Raises ``KeyError`` for an unknown ``selected_scenario_id`` (the route
    maps this to a 422).
    """
    scenario = template_by_id(request.selected_scenario_id)
    shocks, overridden = _resolve_shocks(scenario, request)

    # Impacts for ALL modules (regime reflects the full scenario); the
    # response rows/composite honour the request's included_modules.
    impacts = {mid: _impact_score(mid, shocks) for mid in _MODULE_IDS}
    included = list(dict.fromkeys(request.included_modules))  # de-dup, keep order
    composite = sum(impacts[mid] for mid in included) / len(included)

    regime = _classify_regime(impacts, shocks)
    builder, report = _build_report(request, scenario, shocks, impacts, regime, composite)

    global_shocks = [
        GlobalShockRow(
            shock_id=sid,
            shock_label=_SHOCKS[sid][0],
            value=shocks[sid],
            neutral_value=_SHOCKS[sid][1],
            overridden=overridden[sid],
        )
        for sid in _SHOCKS
    ]

    return ScenarioStudioAnalysisResponse(
        selected_scenario=scenario,
        global_shocks=global_shocks,
        module_impacts=_module_rows(included, impacts, shocks),
        composite_severity=_clip_0_100(composite),
        scenario_regime=regime,
        baseline_vs_stress=_baseline_stress_rows(included, shocks),
        heatmap=_heatmap(included, shocks),
        report_builder=builder,
        generated_report=report,
        notes=[
            "Cross-lab impact scores are a documented deterministic teaching "
            "layer — they do not call the underlying lab engines.",
            "Shocks are standardized illustrative intensities (z-score-like "
            "units; multipliers neutral at 1.0), not market returns.",
            "Baseline-vs-stress rows use illustrative sample metrics with "
            "simplified linear transforms.",
            "Educational only — not investment, trading, or asset-allocation "
            "advice, and not a production risk report.",
        ],
        disclaimer=DISCLAIMER,
    )
