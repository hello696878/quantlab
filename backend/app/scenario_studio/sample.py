"""
Deterministic static-sample scenario templates for the Unified Scenario Studio
(Phase 32.0).

Ten hand-written cross-asset stress templates. Every shock is a standardized
illustrative intensity (z-score-like units; multipliers neutral at 1.0) chosen
so the documented impact formulas land in distinct regimes — constructed
teaching examples, identical every run and every test. Not live macro, market,
crypto, or news data; not forecasts; not advice.
"""

from __future__ import annotations

from typing import List

from app.scenario_studio.models import (
    ModuleCatalogEntry,
    ScenarioStudioRequest,
    ScenarioStudioSampleResponse,
    ScenarioTemplateInput,
    SectionCatalogEntry,
)

DISCLAIMER = (
    "Static illustrative sample data. Unified scenario, cross-lab impact, and "
    "report-builder analytics are educational and not investment, trading, "
    "asset-allocation, legal, tax, or risk-management advice."
)

MODULE_LABELS = {
    "macro_regime": "Macro Regime",
    "portfolio_risk": "Portfolio Risk",
    "crypto_derivatives": "Crypto Derivatives",
    "defi_risk": "DeFi Risk",
    "tokenomics": "Tokenomics",
    "onchain_analytics": "On-Chain Analytics",
    "alternative_data": "Alternative Data",
    "market_microstructure": "Market Microstructure",
}

SECTION_TITLES = {
    "executive_summary": "Executive Summary",
    "macro": "Macro Regime",
    "portfolio": "Portfolio Risk",
    "crypto": "Crypto Derivatives",
    "defi": "DeFi Risk",
    "tokenomics": "Tokenomics",
    "onchain": "On-Chain Analytics",
    "alternative_data": "Alternative Data",
    "limitations": "Limitations",
}


def _t(
    scenario_id: str,
    name: str,
    description: str,
    *,
    growth: float = 0.0,
    inflation: float = 0.0,
    policy: float = 0.0,
    liquidity: float = 0.0,
    credit: float = 0.0,
    usd: float = 0.0,
    equity: float = 0.0,
    rate: float = 0.0,
    spread: float = 0.0,
    crypto: float = 0.0,
    funding: float = 0.0,
    defi_liq: float = 0.0,
    depeg: float = 0.0,
    whale: float = 0.0,
    sentiment: float = 0.0,
    vol_mult: float = 1.0,
    unlock_mult: float = 1.0,
    inflow_mult: float = 1.0,
    lag: float = 0.0,
) -> ScenarioTemplateInput:
    return ScenarioTemplateInput(
        scenario_id=scenario_id,
        scenario_name=name,
        description=description,
        growth_shock=growth,
        inflation_shock=inflation,
        policy_shock=policy,
        liquidity_shock=liquidity,
        credit_shock=credit,
        usd_shock=usd,
        equity_shock=equity,
        rate_shock=rate,
        credit_spread_shock=spread,
        crypto_price_shock=crypto,
        funding_rate_shock=funding,
        defi_liquidity_shock=defi_liq,
        stablecoin_depeg_shock=depeg,
        whale_concentration_shock=whale,
        sentiment_shock=sentiment,
        volatility_multiplier=vol_mult,
        token_unlock_multiplier=unlock_mult,
        exchange_inflow_multiplier=inflow_mult,
        publication_lag_shock=lag,
    )


def sample_templates() -> List[ScenarioTemplateInput]:
    """The ten deterministic scenario templates (fresh copies each call)."""
    return [
        _t(
            "soft_landing",
            "Soft Landing",
            "Growth cools gently while inflation drifts down; small, mostly "
            "benign shocks across every module.",
            growth=0.2, inflation=-0.25, policy=-0.1, liquidity=0.2, credit=-0.1,
            usd=-0.1, equity=0.2, rate=-0.2, spread=-0.15, crypto=0.2,
            funding=0.1, defi_liq=0.1, depeg=0.05, whale=0.05, sentiment=0.2,
            vol_mult=0.95, unlock_mult=1.0, inflow_mult=0.9, lag=0.1,
        ),
        _t(
            "inflation_reacceleration",
            "Inflation Reacceleration",
            "Inflation re-heats and policy re-tightens; rates and the USD "
            "rise while risk assets wobble.",
            growth=0.3, inflation=1.8, policy=1.4, liquidity=-0.6, credit=0.3,
            usd=0.8, equity=-0.8, rate=1.5, spread=0.5, crypto=-0.6,
            funding=-0.2, defi_liq=-0.3, depeg=0.05, whale=0.05, sentiment=-0.5,
            vol_mult=1.25, unlock_mult=1.0, inflow_mult=1.2, lag=0.2,
        ),
        _t(
            "growth_shock",
            "Growth Shock",
            "Growth rolls over hard; policy eases but risk assets, credit, "
            "and crypto all de-rate together.",
            growth=-2.0, inflation=-0.5, policy=-0.8, liquidity=-0.4, credit=0.8,
            usd=0.4, equity=-1.2, rate=-1.0, spread=0.8, crypto=-1.0,
            funding=-0.5, defi_liq=-0.5, depeg=0.1, whale=0.1, sentiment=-0.8,
            vol_mult=1.4, unlock_mult=1.0, inflow_mult=1.4, lag=0.3,
        ),
        _t(
            "liquidity_crunch",
            "Liquidity Crunch",
            "Funding liquidity drains sharply; spreads widen, DeFi liquidity "
            "thins, and volatility jumps.",
            growth=-0.5, inflation=0.2, policy=0.6, liquidity=-2.0, credit=0.9,
            usd=0.6, equity=-0.9, rate=0.4, spread=0.9, crypto=-0.8,
            funding=-0.4, defi_liq=-1.2, depeg=0.2, whale=0.15, sentiment=-0.6,
            vol_mult=1.5, unlock_mult=1.0, inflow_mult=1.5, lag=0.3,
        ),
        _t(
            "credit_stress",
            "Credit Stress",
            "Credit conditions deteriorate; spreads gap wider, downgrades "
            "accelerate, and equity and crypto reprice lower.",
            growth=-0.8, inflation=0.3, policy=0.2, liquidity=-1.0, credit=2.0,
            usd=0.5, equity=-1.1, rate=-0.3, spread=1.8, crypto=-0.9,
            funding=-0.5, defi_liq=-0.8, depeg=0.15, whale=0.1, sentiment=-0.7,
            vol_mult=1.5, unlock_mult=1.0, inflow_mult=1.3, lag=0.2,
        ),
        _t(
            "crypto_risk_off",
            "Crypto Risk-Off",
            "A crypto-specific de-risking: prices drop, funding flips "
            "negative, and coins move onto exchanges.",
            growth=-0.2, inflation=0.0, policy=0.2, liquidity=-0.5, credit=0.3,
            usd=0.4, equity=-0.4, rate=0.0, spread=0.3, crypto=-1.6,
            funding=-1.2, defi_liq=-0.9, depeg=0.25, whale=0.35, sentiment=-0.9,
            vol_mult=1.4, unlock_mult=1.15, inflow_mult=1.8, lag=0.2,
        ),
        _t(
            "stablecoin_depeg_stress",
            "Stablecoin Depeg Stress",
            "A major sample stablecoin trades away from its peg; DeFi "
            "lending and collateral channels feel it first.",
            growth=0.0, inflation=0.0, policy=0.0, liquidity=-0.6, credit=0.4,
            usd=0.2, equity=-0.2, rate=0.0, spread=0.3, crypto=-0.8,
            funding=-0.6, defi_liq=-1.5, depeg=2.0, whale=0.2, sentiment=-0.6,
            vol_mult=1.3, unlock_mult=1.0, inflow_mult=1.6, lag=0.2,
        ),
        _t(
            "exchange_inflow_panic",
            "Exchange Inflow Panic",
            "Tokens flood onto exchanges as holders de-risk; whale wallets "
            "concentrate and reserves swell.",
            growth=0.0, inflation=0.0, policy=0.0, liquidity=-0.4, credit=0.2,
            usd=0.1, equity=-0.2, rate=0.0, spread=0.2, crypto=-1.0,
            funding=-0.8, defi_liq=-0.6, depeg=0.1, whale=0.6, sentiment=-0.5,
            vol_mult=1.4, unlock_mult=1.0, inflow_mult=3.0, lag=0.1,
        ),
        _t(
            "alternative_data_noise_shock",
            "Alternative Data Noise Shock",
            "News/sentiment feeds turn noisy and stale; signal quality "
            "degrades while markets stay orderly.",
            growth=0.0, inflation=0.0, policy=0.0, liquidity=-0.2, credit=0.1,
            usd=0.0, equity=-0.3, rate=0.0, spread=0.1, crypto=-0.2,
            funding=-0.1, defi_liq=-0.2, depeg=0.05, whale=0.05, sentiment=-1.8,
            vol_mult=1.3, unlock_mult=1.0, inflow_mult=1.1, lag=1.5,
        ),
        _t(
            "severe_cross_asset_stress_combo",
            "Severe Cross-Asset Stress Combo",
            "Everything at once: growth collapse, sticky inflation, credit "
            "and liquidity stress, a crypto crash, a depeg, unlock and "
            "inflow waves, and degraded data quality.",
            growth=-2.2, inflation=1.5, policy=1.0, liquidity=-2.2, credit=2.2,
            usd=1.2, equity=-2.0, rate=1.2, spread=2.0, crypto=-2.2,
            funding=-1.8, defi_liq=-1.8, depeg=1.5, whale=0.8, sentiment=-1.5,
            vol_mult=2.0, unlock_mult=2.0, inflow_mult=2.5, lag=1.0,
        ),
    ]


def template_by_id(scenario_id: str) -> ScenarioTemplateInput:
    """Look up one template; raises KeyError for unknown ids."""
    for t in sample_templates():
        if t.scenario_id == scenario_id:
            return t
    raise KeyError(scenario_id)


def default_request() -> ScenarioStudioRequest:
    return ScenarioStudioRequest(
        selected_scenario_id="soft_landing",
        custom_overrides=None,
        included_modules=list(MODULE_LABELS.keys()),  # type: ignore[arg-type]
        report_sections=list(SECTION_TITLES.keys()),  # type: ignore[arg-type]
    )


def build_sample_response() -> ScenarioStudioSampleResponse:
    return ScenarioStudioSampleResponse(
        templates=sample_templates(),
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
            "Ten hand-written scenario templates with standardized illustrative "
            "shock intensities (z-score-like units; multipliers neutral at 1.0).",
            "Deterministic and identical every run — not live macro, market, "
            "crypto, or news data, and not forecasts.",
            "Educational workflow illustration only — not investment, trading, "
            "or asset-allocation advice.",
        ],
    )
