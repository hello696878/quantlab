"""
Deterministic static reliability metadata for the Data Mode Registry, Offline
Fixtures & API Reliability Center (Phase 35.0).

A hand-maintained catalog of how QuantLab's modules source data (static
sample / user input / local calculation / optional external provider), which
providers exist (and that the optional yfinance/FRED paths are disabled by
default, fail closed, and are never relied on in tests), and which
deterministic offline fixtures back the default demos — including the KO/PEP
pairs-trading demo fixture that keeps the built-in pairs demo network-free.

Every record is a static annotation fact-checked against the code when
written — not telemetry, not runtime introspection, and never a guarantee
that an external provider is available. Identical every run. Not advice.
"""

from __future__ import annotations

from typing import List

from app.data_reliability.models import (
    CategoryCatalogEntry,
    DataReliabilityRequest,
    DataReliabilitySampleResponse,
    ModuleDataModeRow,
    OfflineFixtureRow,
    ProviderRow,
    SectionCatalogEntry,
)

DISCLAIMER = (
    "Static illustrative reliability metadata. Data-mode registry, offline "
    "fixtures, and API reliability diagnostics are educational and not "
    "investment, trading, legal, tax, compliance, or risk-management advice."
)

SECTION_TITLES = {
    "overview": "Overview",
    "module_modes": "Module Data Modes",
    "providers": "Providers",
    "offline_fixtures": "Offline Fixtures",
    "test_safety": "Test Safety",
    "limitations": "Limitations",
    "recommendations": "Suggested Handling",
}

CATEGORY_LABELS = {
    "platform": "Platform",
    "backtesting": "Backtesting",
    "portfolio_risk": "Portfolio Risk",
    "macro_cross_asset": "Macro & Cross-Asset",
    "research_workflow": "Research Workflow",
    "crypto": "Crypto",
    "alternative_data": "Alternative Data",
    "microstructure": "Microstructure",
    "derivatives_volatility": "Derivatives & Volatility",
    "real_assets_credit": "Real Assets & Credit",
}

_STATIC_FAILURE = (
    "No network path exists — the module serves its deterministic static "
    "sample and validation errors return friendly 422 messages."
)
_LOCAL_FAILURE = (
    "No network path exists — everything is computed locally from user "
    "inputs; invalid inputs produce friendly validation messages."
)

_STATIC_HANDLING = (
    "Keep the module on its deterministic static sample; no provider "
    "handling is needed."
)

# ---------------------------------------------------------------------------
# Module data-mode registry.
# (id, name, category, route, data_mode, demo_safe, test_safe, ext_required,
#  fallback, default_demo_deterministic, providers, fixtures,
#  failure_behavior, label, limitation, handling)
# ---------------------------------------------------------------------------
_MODULES = [
    ("global_markets_globe", "Global Markets Globe", "platform", "globe",
     "optional_external_provider", True, True, False, True, True,
     ["static_fixtures", "internal_sample_registry", "yfinance_optional", "fred_optional", "globe_delayed_quotes"],
     [],
     "Optional FRED / delayed-quote adapters are disabled by default and fail "
     "closed to static fields with a source_status warning — the globe never "
     "blocks on a provider.",
     "Static sample with optional opt-in enrichment",
     "Enrichment is opt-in, per-field, and never claimed live; disabled/erroring adapters leave every field static.",
     "Leave the optional adapters disabled for demos and tests; the static dossier is the deterministic path."),
    ("backtest_studio", "Backtest Studio", "backtesting", "backtest",
     "optional_external_provider", True, True, True, True, False,
     ["yfinance_optional", "static_fixtures", "user_input"],
     ["pairs_demo_fallback"],
     "Live tickers raise a friendly validation error when the provider returns "
     "no data; the built-in KO/PEP pairs demo always falls back to the "
     "deterministic sample generator, and tests monkeypatch the fetch layer.",
     "User-configured backtests via an optional provider",
     "Single-asset runs on arbitrary tickers depend on the optional yfinance provider being reachable; only the built-in pairs demo carries a deterministic fixture.",
     "Use the built-in KO/PEP pairs demo for offline presentations; treat arbitrary-ticker runs as network-dependent."),
    ("strategy_comparison", "Strategy Comparison", "backtesting", "comparison",
     "optional_external_provider", True, True, True, True, False,
     ["yfinance_optional", "static_fixtures", "user_input"],
     ["pairs_demo_fallback"],
     "Runs the same backtest endpoints — friendly errors for unavailable "
     "tickers; the demo pair stays on the deterministic fixture; tests "
     "monkeypatch the fetch layer.",
     "User-configured comparisons via an optional provider",
     "Comparisons on arbitrary tickers inherit the optional provider dependency of the backtest engine.",
     "Compare strategies on the built-in demo pair when offline; treat other tickers as network-dependent."),
    ("portfolio_risk_lab", "Portfolio Risk Lab", "portfolio_risk", "risklab",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["portfolio_sample"],
     _STATIC_FAILURE, "Static sample data",
     "Deterministic sample portfolio; weights are user-editable but no market data is fetched.",
     _STATIC_HANDLING),
    ("macro_regime_lab", "Macro Regime Lab", "macro_cross_asset", "macroregime",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["macro_regime_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Hand-written macro states — no FRED or market data in this lab.",
     _STATIC_HANDLING),
    ("scenario_studio", "Scenario Studio", "macro_cross_asset", "scenariostudio",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["scenario_studio_templates"],
     _STATIC_FAILURE, "Static sample data",
     "Ten hand-written scenario templates; shocks are standardized illustrative units.",
     _STATIC_HANDLING),
    ("research_workspace", "Research Workspace", "research_workflow", "researchworkspace",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["research_workspace_presets"],
     _STATIC_FAILURE, "Static sample data",
     "Six hand-written research packs; optional drafts live only in browser localStorage.",
     _STATIC_HANDLING),
    ("demo_center", "Demo Center", "platform", "democenter",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry"], ["demo_center_metadata"],
     _STATIC_FAILURE, "Static demo metadata",
     "Hand-maintained walkthrough and health metadata about QuantLab's own modules.",
     _STATIC_HANDLING),
    ("crypto_derivatives_lab", "Crypto Derivatives Lab", "crypto", "cryptoderivatives",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["crypto_derivatives_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Static sample markets — never live exchange data or funding rates.",
     _STATIC_HANDLING),
    ("defi_risk_lab", "DeFi Risk Lab", "crypto", "defirisk",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["defi_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Static sample protocols — no wallets, RPC, or live protocol data.",
     _STATIC_HANDLING),
    ("tokenomics_lab", "Tokenomics Risk Lab", "crypto", "tokenomics",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["tokenomics_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Static sample tokens — no live token prices or on-chain data.",
     _STATIC_HANDLING),
    ("onchain_analytics_lab", "On-Chain Analytics Lab", "crypto", "onchain",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["onchain_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Static sample networks — no RPC, explorer, or exchange APIs.",
     _STATIC_HANDLING),
    ("alternative_data_lab", "Alternative Data Lab", "alternative_data", "altdata",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], ["alternative_data_samples"],
     _STATIC_FAILURE, "Static sample data",
     "Hand-written sample events — no live news, scraping, or LLM APIs.",
     _STATIC_HANDLING),
    ("market_microstructure_lab", "Market Microstructure Lab", "microstructure", "microstructure",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], [],
     _STATIC_FAILURE, "Static sample data",
     "Static sample order books and trade tapes — no live market data.",
     _STATIC_HANDLING),
    ("options_lab", "Options Lab", "derivatives_volatility", "options",
     "local_calculation", True, True, False, True, True,
     ["local_calculation_engine", "user_input"], [],
     _LOCAL_FAILURE, "Local calculation from user inputs",
     "Educational option pricing computed locally — no option-chain data is fetched.",
     "Keep inputs as user-entered parameters; no provider handling is needed."),
    ("volatility_lab", "Volatility Surface Lab", "derivatives_volatility", "volatility",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], [],
     _STATIC_FAILURE, "Static sample data",
     "Deterministic sample option chain — not a live surface.",
     _STATIC_HANDLING),
    ("futures_commodities_lab", "Futures & Commodities Lab", "derivatives_volatility", "futures",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], [],
     _STATIC_FAILURE, "Static sample data",
     "Deterministic sample futures curves — no live futures prices.",
     _STATIC_HANDLING),
    ("real_estate_lab", "Real Estate Lab", "real_assets_credit", "realestate",
     "static_sample", True, True, False, True, True,
     ["internal_sample_registry", "user_input"], [],
     _STATIC_FAILURE, "Static sample data",
     "Illustrative property/REIT/MBS samples — no live listings or rates.",
     _STATIC_HANDLING),
    ("credit_risk_lab", "Credit Risk Lab", "real_assets_credit", "credit",
     "local_calculation", True, True, False, True, True,
     ["local_calculation_engine", "user_input"], [],
     _LOCAL_FAILURE, "Local calculation from user inputs",
     "Educational credit models computed locally — no live spreads or ratings.",
     "Keep inputs as user-entered parameters; no provider handling is needed."),
    ("export_report", "Export Report", "platform", "reports",
     "local_calculation", True, True, False, True, True,
     ["local_calculation_engine"], [],
     "Reports are saved to the local SQLite file; a stopped backend shows the "
     "friendly offline panel with a retry control.",
     "Local storage of saved research outputs",
     "Saved reports live in the local SQLite database file — local-first, no cloud.",
     "Keep saved reports local; nothing syncs anywhere."),
]


def module_rows() -> List[ModuleDataModeRow]:
    return [
        ModuleDataModeRow(
            module_id=mid, module_name=name, category=cat, route=route,  # type: ignore[arg-type]
            data_mode=mode, demo_safe=demo, test_safe=test,  # type: ignore[arg-type]
            external_provider_required=ext, offline_fallback_available=fb,
            default_demo_deterministic=det, provider_names=providers,
            fixture_names=fixtures, failure_behavior=failure,
            user_visible_label=label, limitations=[limitation],
            recommended_handling=handling,
        )
        for (mid, name, cat, route, mode, demo, test, ext, fb, det, providers,
             fixtures, failure, label, limitation, handling) in _MODULES
    ]


# ---------------------------------------------------------------------------
# Provider registry.
# ---------------------------------------------------------------------------
def provider_rows() -> List[ProviderRow]:
    static_modules = [m[0] for m in _MODULES if "internal_sample_registry" in m[10]]
    user_modules = [m[0] for m in _MODULES if "user_input" in m[10]]
    local_modules = [m[0] for m in _MODULES if "local_calculation_engine" in m[10]]
    return [
        ProviderRow(
            provider_id="static_fixtures", provider_name="Static Fixtures",
            provider_type="static_fixture",
            used_by_modules=["backtest_studio", "strategy_comparison", "global_markets_globe"],
            is_external=False, requires_network=False, requires_api_key=False,
            allowed_in_tests=True, has_offline_fallback=True,
            default_failure_mode="static_only",
            limitations=["Deterministic hand-written or generated series — clearly labelled sample data, never live."],
            user_message="Deterministic built-in sample data — identical every run, no network.",
        ),
        ProviderRow(
            provider_id="internal_sample_registry", provider_name="Internal Sample Registry",
            provider_type="static_fixture",
            used_by_modules=static_modules,
            is_external=False, requires_network=False, requires_api_key=False,
            allowed_in_tests=True, has_offline_fallback=True,
            default_failure_mode="static_only",
            limitations=["The labs' GET /sample endpoints — hand-written static payloads served by the local backend."],
            user_message="Served by the local QuantLab backend from hand-written static samples.",
        ),
        ProviderRow(
            provider_id="local_calculation_engine", provider_name="Local Calculation Engine",
            provider_type="local_calculation",
            used_by_modules=local_modules,
            is_external=False, requires_network=False, requires_api_key=False,
            allowed_in_tests=True, has_offline_fallback=True,
            default_failure_mode="static_only",
            limitations=["Pure local computation from parameters — simplified educational models, no data fetched."],
            user_message="Computed locally in this app — no data leaves or enters.",
        ),
        ProviderRow(
            provider_id="user_input", provider_name="User Input",
            provider_type="user_input",
            used_by_modules=user_modules,
            is_external=False, requires_network=False, requires_api_key=False,
            allowed_in_tests=True, has_offline_fallback=True,
            default_failure_mode="friendly_error",
            limitations=["Values you type or upload (e.g. CSV backtests) — validated with friendly 422 errors, never fetched."],
            user_message="Your own inputs — validated locally with clear error messages.",
        ),
        ProviderRow(
            provider_id="yfinance_optional", provider_name="yfinance Optional Provider",
            provider_type="market_data",
            used_by_modules=["backtest_studio", "strategy_comparison", "global_markets_globe"],
            is_external=True, requires_network=True, requires_api_key=False,
            allowed_in_tests=False, has_offline_fallback=True,
            default_failure_mode="fallback_to_fixture",
            limitations=[
                "Availability is never guaranteed — tickers can return no data at any time.",
                "Tests never call it: backtest API tests monkeypatch the fetch layer, and the built-in KO/PEP pairs demo falls back to a deterministic fixture.",
                "Historical/delayed data only — never real-time and never claimed live.",
            ],
            user_message="Optional historical-data download. If it returns nothing you get a clear error — and the built-in demo pair always works offline.",
        ),
        ProviderRow(
            provider_id="fred_optional", provider_name="FRED Optional Provider",
            provider_type="macro_data",
            used_by_modules=["global_markets_globe"],
            is_external=True, requires_network=True, requires_api_key=True,
            allowed_in_tests=False, has_offline_fallback=True,
            default_failure_mode="fallback_to_fixture",
            limitations=[
                "Opt-in and disabled by default; requires a user-supplied API key read from the environment (never committed, never returned to the frontend).",
                "On disabled / missing-key / network-error / invalid-value it fails closed to static fields with a source_status warning.",
            ],
            user_message="Optional US macro enrichment for the globe — disabled by default; every failure falls back to the static sample.",
        ),
        ProviderRow(
            provider_id="globe_delayed_quotes", provider_name="Delayed Demo Quote Provider",
            provider_type="market_data",
            used_by_modules=["global_markets_globe"],
            is_external=True, requires_network=True, requires_api_key=False,
            allowed_in_tests=False, has_offline_fallback=True,
            default_failure_mode="fallback_to_fixture",
            limitations=[
                "Opt-in and disabled by default; wraps the existing yfinance dependency for a curated market set.",
                "Delayed, end-of-day-style quotes only — never real-time; failures leave fields static with a quote_unavailable status.",
            ],
            user_message="Optional delayed index/FX quotes for the globe — disabled by default; never real-time; fails closed to static.",
        ),
    ]


# ---------------------------------------------------------------------------
# Offline fixture registry.
# (id, name, type, used_by, count, range label, description, limitation)
# ---------------------------------------------------------------------------
_FIXTURES = [
    ("pairs_demo_fallback", "Pairs Trading Demo Fallback (KO/PEP)", "price_series",
     ["backtest_studio", "strategy_comparison"], 300,
     "Any requested range (business days; 300-day window for degenerate ranges)",
     "Deterministic network-free co-moving close series with a mean-reverting spread, generated for the built-in KO/PEP demo pair so the pairs demo never depends on a live Yahoo response.",
     "Two synthetic sine-driven series — clearly labelled static_sample, not real KO/PEP prices."),
    ("portfolio_sample", "Portfolio Risk Sample Portfolio", "lab_sample",
     ["portfolio_risk_lab"], 1, "Static — no date axis",
     "The deterministic sample portfolio (editable weights) behind the Portfolio Risk Lab.",
     "One illustrative portfolio — not market data."),
    ("macro_regime_samples", "Macro Regime Sample States", "macro_series",
     ["macro_regime_lab"], 6, "Static — indicators placed at chosen z-scores",
     "Six hand-written macro states with twelve indicators each plus a shared 11-asset assumption set.",
     "Constructed teaching examples — not measured macro data."),
    ("scenario_studio_templates", "Scenario Studio Templates", "scenario_template",
     ["scenario_studio"], 10, "Static — no date axis",
     "Ten deterministic cross-asset scenario templates with 19 standardized shock intensities each.",
     "Standardized illustrative shock units — not market returns."),
    ("research_workspace_presets", "Research Workspace Presets", "report_sample",
     ["research_workspace"], 6, "May–June 2026 static sample timestamps",
     "Six hand-written research packs with sample experiment runs for the journal workflow.",
     "Hand-written run metrics — not recorded lab outputs."),
    ("demo_center_metadata", "Demo Center Walkthrough Metadata", "report_sample",
     ["demo_center"], 29, "Static — no date axis",
     "Eight guided demo paths plus the 21-module health/capability catalog.",
     "Hand-maintained annotations — not telemetry."),
    ("crypto_derivatives_samples", "Crypto Derivatives Sample Markets", "lab_sample",
     ["crypto_derivatives_lab"], 4, "Static — no date axis",
     "Four deterministic sample markets (BTC/ETH/SOL perps + BTC quarterly futures).",
     "Static snapshots — never live exchange data."),
    ("defi_samples", "DeFi Risk Sample Protocols", "lab_sample",
     ["defi_risk_lab"], 5, "Static — no date axis",
     "Five deterministic samples (peg snapshots, kinked rate-model markets, collateralized positions).",
     "Generic educational parameters — not any protocol's actual configuration."),
    ("tokenomics_samples", "Tokenomics Sample Tokens", "lab_sample",
     ["tokenomics_lab"], 5, "Static — deterministic day offsets",
     "Five deterministic sample tokens with unlock schedules, treasuries, and holder concentration.",
     "Illustrative supply/holder numbers — no live token or vesting data."),
    ("onchain_samples", "On-Chain Sample Networks", "lab_sample",
     ["onchain_analytics_lab"], 5, "Static — single-24h snapshots",
     "Five deterministic sample networks with exchange flows, cohorts, and whale flows.",
     "Illustrative entity labels and single-day snapshots — not live on-chain data."),
    ("alternative_data_samples", "Alternative Data Sample Event Sets", "lab_sample",
     ["alternative_data_lab"], 5, "January 2026 static sample timeline",
     "Five hand-written event sets with sentiment scores and observed return paths.",
     "Hand-assigned scores and returns — workflow illustration, not evidence of alpha."),
]


def fixture_rows() -> List[OfflineFixtureRow]:
    return [
        OfflineFixtureRow(
            fixture_id=fid, fixture_name=name, fixture_type=ftype,  # type: ignore[arg-type]
            used_by_modules=used_by, observation_count=count,
            date_range_label=range_label, deterministic=True, test_safe=True,
            description=description, limitations=[limitation],
        )
        for (fid, name, ftype, used_by, count, range_label, description, limitation) in _FIXTURES
    ]


def default_request() -> DataReliabilityRequest:
    return DataReliabilityRequest(
        selected_category=None,
        include_external_providers=True,
        include_static_fixtures=True,
        include_test_safety=True,
        selected_modules=None,
        report_sections=list(SECTION_TITLES.keys()),  # type: ignore[arg-type]
    )


def build_sample_response() -> DataReliabilitySampleResponse:
    return DataReliabilitySampleResponse(
        module_modes=module_rows(),
        providers=provider_rows(),
        offline_fixtures=fixture_rows(),
        sections=[
            SectionCatalogEntry(section_id=sid, section_title=title)  # type: ignore[arg-type]
            for sid, title in SECTION_TITLES.items()
        ],
        categories=[
            CategoryCatalogEntry(category=cid, category_label=label)  # type: ignore[arg-type]
            for cid, label in CATEGORY_LABELS.items()
        ],
        default_request=default_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "A hand-maintained registry of QuantLab's own data modes, providers, "
            "and offline fixtures — fact-checked against the code when written, "
            "not telemetry or runtime introspection.",
            "Optional external providers (yfinance, FRED, delayed quotes) are "
            "disabled by default, fail closed, and are never relied on in tests; "
            "their availability is never guaranteed.",
            "Educational only — a product reliability layer, not a data "
            "governance system, and not investment or trading advice.",
        ],
    )
