"""
Deterministic static-sample research presets for the Research Workspace
(Phase 33.0).

Six hand-written "research packs", each bundling illustrative experiment runs
(metric baselines/stresses, severity scores, confidence labels, notes) on
fixed sample timestamps. Every number is invented for teaching — the runs
mirror the kinds of outputs the other labs produce but are NOT recorded lab
outputs, not research records, and not live or current data. Identical every
run and every test. Not advice.
"""

from __future__ import annotations

from typing import List

from app.research_workspace.models import (
    ExperimentRunInput,
    ModuleCatalogEntry,
    ResearchWorkspacePresetInput,
    ResearchWorkspaceSampleResponse,
    SectionCatalogEntry,
    WorkspaceAnalysisRequest,
)

DISCLAIMER = (
    "Static illustrative sample data. Research workspace, saved preset, "
    "experiment journal, and report export features are educational and not "
    "investment, trading, asset-allocation, legal, tax, compliance, or "
    "risk-management advice."
)

MODULE_LABELS = {
    "macro_regime": "Macro Regime",
    "portfolio_risk": "Portfolio Risk",
    "scenario_studio": "Scenario Studio",
    "crypto_derivatives": "Crypto Derivatives",
    "defi_risk": "DeFi Risk",
    "tokenomics": "Tokenomics",
    "onchain_analytics": "On-Chain Analytics",
    "alternative_data": "Alternative Data",
    "market_microstructure": "Market Microstructure",
}

SECTION_TITLES = {
    "overview": "Overview",
    "assumptions": "Assumptions",
    "experiment_summary": "Experiment Summary",
    "run_comparison": "Run Comparison",
    "methodology": "Methodology",
    "limitations": "Limitations",
    "next_steps": "Next Steps",
}


def _run(
    run_id: str,
    run_name: str,
    module_id: str,
    scenario_name: str,
    created_at: str,
    key_metric_name: str,
    baseline_value: float,
    stressed_value: float,
    severity_score: float,
    confidence_label: str,
    notes: str,
) -> ExperimentRunInput:
    return ExperimentRunInput(
        run_id=run_id,
        run_name=run_name,
        module_id=module_id,  # type: ignore[arg-type]
        scenario_name=scenario_name,
        created_at=created_at,
        key_metric_name=key_metric_name,
        baseline_value=baseline_value,
        stressed_value=stressed_value,
        severity_score=severity_score,
        confidence_label=confidence_label,  # type: ignore[arg-type]
        notes=notes,
    )


def sample_presets() -> List[ResearchWorkspacePresetInput]:
    """The six deterministic research packs (fresh copies each call)."""
    return [
        ResearchWorkspacePresetInput(
            preset_id="macro_stress_research_pack",
            preset_name="Macro Stress Research Pack",
            description=(
                "An illustrative macro-first research pack: inflation and growth "
                "shock reads from the Macro Regime Lab staged against a portfolio "
                "volatility read and a cross-lab broad risk-off scenario."
            ),
            primary_module="macro_regime",
            linked_modules=["macro_regime", "portfolio_risk", "scenario_studio"],
            created_at="2026-05-04T09:00:00Z",
            tags=["macro", "stress", "cross-asset"],
            assumptions=[
                "Sample macro indicators are placed at hand-chosen z-scores.",
                "Portfolio volatility uses the illustrative 12% annualized sample baseline.",
                "Scenario Studio shocks are standardized illustrative intensities.",
            ],
            limitations=[
                "All runs are hand-written sample numbers, not recorded lab outputs.",
                "Severity scores are documented teaching heuristics, not risk measurements.",
            ],
            experiment_runs=[
                _run(
                    "run_macro_inflation", "Inflation reacceleration sweep", "macro_regime",
                    "Inflation Reacceleration", "2026-05-04T09:10:00Z",
                    "Composite macro score (sample)", 0.40, -0.45, 62.0, "medium",
                    "Composite flips negative as inflation and policy scores tighten.",
                ),
                _run(
                    "run_macro_growth", "Growth shock read", "macro_regime",
                    "Growth Shock", "2026-05-04T09:25:00Z",
                    "Composite macro score (sample)", 0.40, -0.85, 71.0, "medium",
                    "Growth-led drawdown in the composite; credit stress score rises.",
                ),
                _run(
                    "run_portfolio_vol", "Portfolio vol under combo stress", "portfolio_risk",
                    "Severe Cross-Asset Stress Combo", "2026-05-04T10:05:00Z",
                    "Portfolio volatility (ann., sample)", 0.12, 0.24, 78.0, "low",
                    "Volatility doubles under the ×2 multiplier; first-order approximation only.",
                ),
                _run(
                    "run_studio_broad", "Cross-lab broad risk-off", "scenario_studio",
                    "Growth Shock", "2026-05-04T10:30:00Z",
                    "Composite severity (sample)", 11.5, 62.4, 62.0, "medium",
                    "Scenario Studio classifies the template as broad risk-off.",
                ),
            ],
        ),
        ResearchWorkspacePresetInput(
            preset_id="crypto_risk_off_research_pack",
            preset_name="Crypto Risk-Off Research Pack",
            description=(
                "An illustrative crypto de-risking pack: funding and liquidation "
                "reads from the Crypto Derivatives Lab plus exchange-flow and "
                "cross-lab scenario reads."
            ),
            primary_module="crypto_derivatives",
            linked_modules=["crypto_derivatives", "onchain_analytics", "scenario_studio"],
            created_at="2026-05-11T14:00:00Z",
            tags=["crypto", "funding", "exchange-flow"],
            assumptions=[
                "Sample perp markets use the static BTC/ETH/SOL snapshots.",
                "Exchange-flow figures are single-24h sample snapshots without history.",
            ],
            limitations=[
                "Liquidation distances use the coarse closed-form educational estimate.",
                "No live exchange, funding, or on-chain data — hand-written sample numbers only.",
            ],
            experiment_runs=[
                _run(
                    "run_funding_flip", "Funding flip stress", "crypto_derivatives",
                    "Crypto Risk-Off", "2026-05-11T14:10:00Z",
                    "Annualized perp funding (sample)", 0.10, -0.02, 64.0, "medium",
                    "Funding flips negative; long carry becomes a short-side tailwind.",
                ),
                _run(
                    "run_liq_distance", "Liquidation distance check", "crypto_derivatives",
                    "Spot selloff", "2026-05-11T14:30:00Z",
                    "Liquidation distance (sample)", 0.18, 0.07, 68.0, "low",
                    "Distance to the approximate liquidation price compresses sharply.",
                ),
                _run(
                    "run_inflow_wave", "Exchange inflow wave", "onchain_analytics",
                    "Exchange Inflow Panic", "2026-05-11T15:00:00Z",
                    "Net exchange flow, % of circulating (sample)", 0.001, 0.011, 69.0, "medium",
                    "Net flow turns strongly positive as sample tokens move onto exchanges.",
                ),
                _run(
                    "run_studio_crypto", "Cross-lab crypto stress", "scenario_studio",
                    "Crypto Risk-Off", "2026-05-11T15:20:00Z",
                    "Composite severity (sample)", 11.5, 71.9, 72.0, "medium",
                    "Scenario Studio reads the template as crypto-specific stress.",
                ),
            ],
        ),
        ResearchWorkspacePresetInput(
            preset_id="defi_liquidity_stress_research_pack",
            preset_name="DeFi Liquidity Stress Research Pack",
            description=(
                "An illustrative DeFi lending pack: health-factor, depeg, and "
                "rate-model reads from the DeFi Risk Lab plus the cross-lab depeg "
                "scenario."
            ),
            primary_module="defi_risk",
            linked_modules=["defi_risk", "scenario_studio"],
            created_at="2026-05-18T11:00:00Z",
            tags=["defi", "stablecoin", "lending"],
            assumptions=[
                "Single-collateral / single-debt sample positions; only collateral price moves.",
                "The kinked rate model uses generic educational parameters.",
            ],
            limitations=[
                "Health factors and liquidation prices are simplified educational approximations.",
                "No wallets, RPC, or protocol data — hand-written sample numbers only.",
            ],
            experiment_runs=[
                _run(
                    "run_health_factor", "Health factor drawdown", "defi_risk",
                    "Collateral drawdown", "2026-05-18T11:10:00Z",
                    "Lending health factor (sample)", 1.85, 1.12, 66.0, "medium",
                    "HF compresses toward the liquidation threshold under a collateral slide.",
                ),
                _run(
                    "run_depeg_read", "Severe depeg read", "defi_risk",
                    "Severe depeg", "2026-05-18T11:35:00Z",
                    "Peg deviation, bps (sample)", 8.0, 320.0, 84.0, "low",
                    "Peg deviation jumps past the depegged threshold in the sample.",
                ),
                _run(
                    "run_rate_spike", "Borrow rate past the kink", "defi_risk",
                    "Liquidity drought", "2026-05-18T12:00:00Z",
                    "Borrow APY (sample)", 0.052, 0.19, 58.0, "medium",
                    "Utilization pushes past the kink onto the steep slope of the rate curve.",
                ),
                _run(
                    "run_studio_depeg", "Cross-lab depeg stress", "scenario_studio",
                    "Stablecoin Depeg Stress", "2026-05-18T12:20:00Z",
                    "Composite severity (sample)", 11.5, 58.6, 59.0, "medium",
                    "Scenario Studio reads the depeg template as crypto-specific stress.",
                ),
            ],
        ),
        ResearchWorkspacePresetInput(
            preset_id="tokenomics_unlock_review_pack",
            preset_name="Tokenomics Unlock Review Pack",
            description=(
                "An illustrative token supply review: unlock, runway, and "
                "concentration reads from the Tokenomics Lab plus a whale-flow "
                "read from the On-Chain Lab."
            ),
            primary_module="tokenomics",
            linked_modules=["tokenomics", "onchain_analytics"],
            created_at="2026-05-25T16:00:00Z",
            tags=["tokenomics", "unlock", "treasury"],
            assumptions=[
                "Unlock events sit on deterministic day offsets — no real vesting contracts.",
                "Treasury tokens are valued at the same sample price as the float.",
            ],
            limitations=[
                "Unlocks are treated as potential new float, not a prediction of selling.",
                "Holder shares are illustrative sample numbers without address disaggregation.",
            ],
            experiment_runs=[
                _run(
                    "run_unlock_double", "Unlock acceleration sweep", "tokenomics",
                    "Unlock acceleration", "2026-05-25T16:10:00Z",
                    "Next-180d unlock, % of circulating (sample)", 0.06, 0.12, 55.0, "medium",
                    "Doubling scheduled unlocks doubles the 180-day dilution bucket.",
                ),
                _run(
                    "run_runway_cut", "Treasury runway compression", "tokenomics",
                    "Treasury drawdown", "2026-05-25T16:30:00Z",
                    "Treasury runway, months (sample)", 38.0, 19.0, 61.0, "medium",
                    "A 50% treasury asset shock halves the gross-burn runway.",
                ),
                _run(
                    "run_concentration", "Concentration shift check", "tokenomics",
                    "Concentration shock", "2026-05-25T16:50:00Z",
                    "Top-10 holder share (sample)", 0.42, 0.55, 26.0, "high",
                    "A modest shift in the sample top-holder shares; score stays moderate.",
                ),
                _run(
                    "run_whale_deposits", "Whale deposit pressure", "onchain_analytics",
                    "Whale deposit pressure", "2026-05-25T17:15:00Z",
                    "Whale net flow, tokens (sample)", -12000.0, 45000.0, 52.0, "low",
                    "",
                ),
            ],
        ),
        ResearchWorkspacePresetInput(
            preset_id="alternative_data_signal_quality_pack",
            preset_name="Alternative Data Signal Quality Pack",
            description=(
                "An illustrative single-module signal-quality review: decay, "
                "noise, and leakage reads from the Alternative Data Lab."
            ),
            primary_module="alternative_data",
            linked_modules=["alternative_data"],
            created_at="2026-06-01T10:00:00Z",
            tags=["alternative-data", "signal-decay", "leakage"],
            assumptions=[
                "Event scores and return paths are hand-assigned sample numbers (no NLP, no LLM).",
                "IC and hit-rate figures illustrate the workflow, not evidence of alpha.",
            ],
            limitations=[
                "The leakage run uses the synthetic leakage-violation scenario for teaching.",
                "Half-life estimates interpolate over only three sample horizons.",
            ],
            experiment_runs=[
                _run(
                    "run_ic_decay", "Lag-driven IC decay", "alternative_data",
                    "Lag increase", "2026-06-01T10:10:00Z",
                    "IC(5d) (sample)", 0.31, 0.12, 44.0, "low",
                    "Stale signals lose most of their sample information coefficient.",
                ),
                _run(
                    "run_noise_spike", "Social noise spike", "alternative_data",
                    "Social noise spike", "2026-06-01T10:30:00Z",
                    "Signal-to-noise (sample)", 1.9, 0.8, 57.0, "low",
                    "Deterministic alternating noise halves the sample signal-to-noise read.",
                ),
                _run(
                    "run_leakage_flags", "Synthetic leakage violation", "alternative_data",
                    "Leakage violation", "2026-06-01T11:00:00Z",
                    "Leakage flags (sample)", 0.0, 3.0, 66.0, "medium",
                    "The synthetic violation trips the leakage guard on three sample events.",
                ),
            ],
        ),
        ResearchWorkspacePresetInput(
            preset_id="cross_asset_scenario_report_pack",
            preset_name="Cross-Asset Scenario Report Pack",
            description=(
                "An illustrative everything-at-once report pack: the severe "
                "cross-asset combo staged across macro, portfolio, "
                "microstructure, and alternative-data reads."
            ),
            primary_module="scenario_studio",
            linked_modules=[
                "scenario_studio", "macro_regime", "portfolio_risk",
                "crypto_derivatives", "defi_risk", "tokenomics",
                "onchain_analytics", "alternative_data", "market_microstructure",
            ],
            created_at="2026-06-08T13:00:00Z",
            tags=["cross-asset", "severe-combo", "report"],
            assumptions=[
                "All runs stage the Severe Cross-Asset Stress Combo family of scenarios.",
                "Module scores use the Scenario Studio teaching weight tables.",
            ],
            limitations=[
                "Severity 90+ readings reflect the deliberately extreme sample combo, not markets.",
                "The pack demonstrates report assembly — not a risk process.",
            ],
            experiment_runs=[
                _run(
                    "run_severe_combo", "Severe combo read", "scenario_studio",
                    "Severe Cross-Asset Stress Combo", "2026-06-08T13:10:00Z",
                    "Composite severity (sample)", 11.5, 100.0, 96.0, "low",
                    "Every module pins at the 100-point clip in the teaching layer.",
                ),
                _run(
                    "run_micro_spread", "Spread widening read", "market_microstructure",
                    "Volatility shock", "2026-06-08T13:30:00Z",
                    "Quoted spread, bps (sample)", 4.0, 9.6, 77.0, "medium",
                    "Spreads widen with the vol multiplier and liquidity drain.",
                ),
                _run(
                    "run_macro_combo", "Macro composite collapse", "macro_regime",
                    "Severe macro stress combo", "2026-06-08T13:50:00Z",
                    "Composite macro score (sample)", 0.40, -1.90, 88.0, "medium",
                    "The combo flips every sample macro state to severe stress.",
                ),
                _run(
                    "run_portfolio_dd", "Portfolio drawdown read", "portfolio_risk",
                    "Credit spread shock", "2026-06-08T14:10:00Z",
                    "Portfolio drawdown (sample)", -0.08, -0.26, 74.0, "low",
                    "Sample drawdown deepens as spreads gap wider.",
                ),
                _run(
                    "run_alpha_fade", "Alpha composite fade", "alternative_data",
                    "Crowded cluster", "2026-06-08T14:30:00Z",
                    "Alpha score (sample)", 0.21, 0.05, 49.0, "low",
                    "Crowding erodes the sample alpha composite toward zero.",
                ),
            ],
        ),
    ]


def preset_by_id(preset_id: str) -> ResearchWorkspacePresetInput:
    """Look up one preset; raises KeyError for unknown ids."""
    for p in sample_presets():
        if p.preset_id == preset_id:
            return p
    raise KeyError(preset_id)


def default_request() -> WorkspaceAnalysisRequest:
    return WorkspaceAnalysisRequest(
        selected_preset_id="macro_stress_research_pack",
        included_run_ids=None,
        user_note=None,
        report_sections=list(SECTION_TITLES.keys()),  # type: ignore[arg-type]
    )


def build_sample_response() -> ResearchWorkspaceSampleResponse:
    return ResearchWorkspaceSampleResponse(
        presets=sample_presets(),
        modules=[
            ModuleCatalogEntry(module_id=mid, module_label=label)  # type: ignore[arg-type]
            for mid, label in MODULE_LABELS.items()
        ],
        sections=[
            SectionCatalogEntry(section_id=sid, section_title=title)  # type: ignore[arg-type]
            for sid, title in SECTION_TITLES.items()
        ],
        default_request=default_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "Six hand-written research packs on fixed sample timestamps — the "
            "runs mirror the kinds of outputs the labs produce but are invented "
            "sample numbers, not recorded lab outputs.",
            "Deterministic and identical every run — not live or current data, "
            "not research records, not compliance records.",
            "Educational workflow illustration only — not investment, trading, "
            "or asset-allocation advice.",
        ],
    )
