"""
Deterministic static QA metadata for the QA Command Center (Phase 36.0).

A hand-maintained 21-module QA registry (capability flags fact-checked
against the actual routers, main.py endpoints, panel imports, and test files
when written), per-module smoke-test and manual regression steps, and the
exact verification commands the user runs locally. This layer lists the
commands but NEVER runs them and never claims tests or builds were executed.
Identical every run. Not advice; not a compliance system.
"""

from __future__ import annotations

from typing import List

from app.qa_command_center.models import (
    CategoryCatalogEntry,
    CommandChecklist,
    QACommandCenterRequest,
    QACommandCenterSampleResponse,
    QAModuleRow,
    SectionCatalogEntry,
)

DISCLAIMER = (
    "Static illustrative QA metadata. Release readiness, smoke-test matrix, "
    "and QA command center outputs are educational project-management aids "
    "and not investment, trading, legal, tax, compliance, or risk-management "
    "advice."
)

SECTION_TITLES = {
    "overview": "Overview",
    "readiness_summary": "Readiness Summary",
    "smoke_test_matrix": "Smoke Test Matrix",
    "regression_checklist": "Regression Checklist",
    "command_checklist": "Command Checklist",
    "known_limitations": "Known Limitations",
    "release_notes": "Release Notes",
    "release_decision": "Release Decision",
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

RELEASE_STATUSES = ["ready", "needs_review", "experimental", "blocked"]
PRIORITIES = ["critical", "high", "medium", "low"]

_EXPECTED = "All panels render with finite values; no crash; no NaN/Infinity anywhere."

# ---------------------------------------------------------------------------
# Module QA registry.
# (id, name, category, route, backend, charts, controls, formulas, tests,
#  data_mode, status, priority, smoke_steps, regression_steps, limitations)
# has_frontend_page and demo_safe are True for every row (all are shipped
# sidebar views with deterministic demo paths).
# ---------------------------------------------------------------------------
_MODULES = [
    ("global_markets_globe", "Global Markets Globe", "platform", "globe",
     True, True, True, False, True, "optional_external_provider", "ready", "critical",
     ["Open the globe; drag to rotate", "Click a market marker and walk the dossier"],
     ["Confirm 'Sample' labels render on index/FX values", "Confirm the keyboard-accessible market list works"],
     ["Static sample dossiers; optional adapters disabled by default and fail closed."]),
    ("backtest_studio", "Backtest Studio", "backtesting", "backtest",
     True, True, True, False, True, "optional_external_provider", "ready", "critical",
     ["Run the built-in KO/PEP pairs demo", "Confirm equity/drawdown charts and trade table render"],
     ["Run one SMA backtest with costs and confirm metrics", "Confirm a bad ticker shows a friendly error"],
     ["Arbitrary-ticker runs depend on the optional yfinance provider; only the pairs demo has a deterministic fixture."]),
    ("strategy_comparison", "Strategy Comparison", "backtesting", "comparison",
     True, True, True, False, True, "optional_external_provider", "ready", "high",
     ["Load two strategies side by side", "Confirm both equity curves render"],
     ["Confirm metric deltas match the two single runs"],
     ["Inherits the backtest engine's optional provider dependency."]),
    ("portfolio_risk_lab", "Portfolio Risk Lab", "portfolio_risk", "risklab",
     True, False, True, True, True, "static_sample", "ready", "high",
     ["Open the lab; confirm sample portfolio loads", "Edit a weight and confirm re-analysis"],
     ["Walk the stress panel and formula panel"],
     ["Deterministic sample portfolio; simplified educational risk models."]),
    ("macro_regime_lab", "Macro Regime Lab", "macro_cross_asset", "macroregime",
     True, False, True, True, True, "static_sample", "ready", "high",
     ["Switch two macro states; confirm regime pill flips", "Nudge the λ/η knobs"],
     ["Confirm the six samples land on six distinct regimes"],
     ["Hand-placed indicator z-scores; educational allocations, never portfolio guidance."]),
    ("scenario_studio", "Scenario Studio", "macro_cross_asset", "scenariostudio",
     True, True, True, True, True, "static_sample", "ready", "critical",
     ["Switch Soft Landing → Severe Combo", "Drag one shock slider; confirm heatmap re-draws"],
     ["Confirm the ten templates land on their documented regimes", "Copy the report Markdown"],
     ["Documented linear teaching weights; does not call the other labs' engines."]),
    ("research_workspace", "Research Workspace", "research_workflow", "researchworkspace",
     True, True, True, True, True, "static_sample", "ready", "high",
     ["Open a preset; flip the four view modes", "Stage/unstage a run; confirm severity chart updates"],
     ["Save/load/delete a local draft", "Copy the Markdown and JSON exports"],
     ["Hand-written research packs — not recorded lab outputs."]),
    ("demo_center", "Demo Center", "platform", "democenter",
     True, True, True, True, True, "static_sample", "ready", "critical",
     ["Switch demo paths and audiences", "Click a step's Open module deep link"],
     ["Confirm the module health cards and capability matrix render", "Copy the demo script"],
     ["Hand-maintained walkthrough/health metadata — not telemetry."]),
    ("data_reliability_center", "Data Reliability Center", "platform", "datareliability",
     True, True, True, True, True, "static_sample", "ready", "high",
     ["Open the center; confirm the reliability summary renders", "Filter to the Backtesting category and watch the score drop"],
     ["Confirm provider and fixture tables render", "Copy the reliability report"],
     ["Hand-maintained registry; external availability never guaranteed."]),
    ("crypto_derivatives_lab", "Crypto Derivatives Lab", "crypto", "cryptoderivatives",
     True, True, True, True, True, "static_sample", "ready", "high",
     ["Switch markets; drag the funding shock slider", "Confirm basis curve and liquidation charts re-draw"],
     ["Confirm the liquidation price is labelled an educational estimate"],
     ["Static sample markets; coarse closed-form liquidation approximation."]),
    ("defi_risk_lab", "DeFi Risk Lab", "crypto", "defirisk",
     True, True, True, True, True, "static_sample", "ready", "high",
     ["Drag the depeg slider; confirm peg chart moves", "Push utilization past the kink"],
     ["Confirm the health factor never renders NaN/Infinity"],
     ["Single-collateral educational health factors on static samples."]),
    ("tokenomics_lab", "Tokenomics Risk Lab", "crypto", "tokenomics",
     True, True, True, True, True, "static_sample", "ready", "medium",
     ["Set unlock ×2; flip the horizon selector", "Confirm unlock and runway charts re-draw"],
     ["Confirm the severe combo flips the regime"],
     ["Illustrative unlock/treasury samples; unlocks are potential float, not predictions."]),
    ("onchain_analytics_lab", "On-Chain Analytics Lab", "crypto", "onchain",
     True, True, True, True, True, "static_sample", "ready", "medium",
     ["Drag the inflow multiplier to ×3", "Confirm flow bars flip and NVT chart shifts"],
     ["Confirm cohort and whale panels render"],
     ["Single-24h sample snapshots with illustrative entity labels."]),
    ("alternative_data_lab", "Alternative Data Lab", "alternative_data", "altdata",
     True, True, True, True, True, "static_sample", "ready", "medium",
     ["Drag the lag slider; confirm decay chart moves", "Flip the 1/5/20d horizon selector"],
     ["Confirm the leakage scenario trips the guard and valid inputs show zero flags"],
     ["Hand-assigned scores and returns — workflow illustration, not alpha."]),
    ("market_microstructure_lab", "Market Microstructure Lab", "microstructure", "microstructure",
     True, False, True, True, True, "static_sample", "ready", "medium",
     ["Switch instruments; confirm book summary updates", "Open the toxicity section"],
     ["Walk the TCA attribution and confirm components sum to the shortfall"],
     ["Static sample books; educational closed-form approximations."]),
    ("options_lab", "Options Lab", "derivatives_volatility", "options",
     True, True, True, True, True, "local_calculation", "ready", "medium",
     ["Price an option; confirm greeks render", "Open the payoff builder"],
     ["Run the binomial tree and Monte Carlo panels once"],
     ["Educational pricing from user parameters — no live option chains."]),
    ("volatility_lab", "Volatility Surface Lab", "derivatives_volatility", "volatility",
     True, False, True, True, True, "static_sample", "ready", "medium",
     ["Load the sample chain; confirm smile/term tables render", "Walk the variance-swap panel"],
     ["Confirm the surface and scenario panels render"],
     ["Simplified variance-swap approximation — not the official VIX methodology."]),
    ("futures_commodities_lab", "Futures & Commodities Lab", "derivatives_volatility", "futures",
     True, False, True, True, True, "static_sample", "ready", "medium",
     ["Switch commodities; confirm curve table updates", "Edit a contract assumption"],
     ["Confirm curve-shape classification and margin panel render"],
     ["Deterministic sample curves; cost-of-carry teaching models."]),
    ("real_estate_lab", "Real Estate Lab", "real_assets_credit", "realestate",
     True, False, True, True, True, "static_sample", "ready", "medium",
     ["Edit rent/vacancy; confirm DSCR updates", "Run the MBS section once"],
     ["Confirm cap-rate stress and REIT NAV panels render"],
     ["Illustrative samples — not appraisal or underwriting."]),
    ("credit_risk_lab", "Credit Risk Lab", "real_assets_credit", "credit",
     True, True, True, True, True, "local_calculation", "ready", "medium",
     ["Edit leverage/vol in the Merton panel", "Confirm distance-to-default updates"],
     ["Walk the hazard and CDS panels once"],
     ["Educational structural/reduced-form teaching models — no live credit data."]),
    ("export_report", "Export Report", "platform", "reports",
     True, False, False, False, True, "local_calculation", "ready", "low",
     ["Open Saved Reports; open one saved report"],
     ["Stop the backend and confirm the friendly offline panel with retry"],
     ["Local SQLite storage — local-first, no cloud."]),
]


def qa_module_rows() -> List[QAModuleRow]:
    return [
        QAModuleRow(
            module_id=mid, module_name=name, category=cat, route=route,  # type: ignore[arg-type]
            has_backend_endpoint=backend, has_frontend_page=True,
            has_charts=charts, has_interactive_controls=controls,
            has_formula_panel=formulas, has_tests=tests, demo_safe=True,
            data_mode=mode, release_status=status, priority=priority,  # type: ignore[arg-type]
            smoke_test_steps=smoke, manual_regression_steps=regression,
            known_limitations=limitations,
        )
        for (mid, name, cat, route, backend, charts, controls, formulas, tests,
             mode, status, priority, smoke, regression, limitations) in _MODULES
    ]


def command_checklist() -> CommandChecklist:
    return CommandChecklist(
        backend_test_command=r"cd C:\quantlab; backend\venv\Scripts\python.exe -m pytest backend\tests -q",
        frontend_typecheck_command=r"cd C:\quantlab\frontend; npx tsc --noEmit",
        frontend_build_command_for_user=r"cd C:\quantlab\frontend; npm run build",
        backend_run_command=r"cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000",
        notes=[
            "These commands are listed for the user to run locally — this page never runs them and never verifies that they were run.",
            "The production build (npm run build) is run locally by the user only.",
            "After the backend suite, confirm C:\\quantlab\\artifacts does not exist.",
        ],
    )


def default_request() -> QACommandCenterRequest:
    return QACommandCenterRequest(
        selected_category=None,
        selected_release_statuses=None,
        selected_priorities=None,
        include_manual_steps=True,
        include_backend_checks=True,
        include_frontend_checks=True,
        include_known_limitations=True,
        report_sections=list(SECTION_TITLES.keys()),  # type: ignore[arg-type]
    )


def build_sample_response() -> QACommandCenterSampleResponse:
    return QACommandCenterSampleResponse(
        qa_modules=qa_module_rows(),
        sections=[
            SectionCatalogEntry(section_id=sid, section_title=title)  # type: ignore[arg-type]
            for sid, title in SECTION_TITLES.items()
        ],
        categories=[
            CategoryCatalogEntry(category=cid, category_label=label)  # type: ignore[arg-type]
            for cid, label in CATEGORY_LABELS.items()
        ],
        release_statuses=list(RELEASE_STATUSES),  # type: ignore[arg-type]
        priorities=list(PRIORITIES),  # type: ignore[arg-type]
        default_request=default_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "A hand-maintained 21-module QA registry — capability flags "
            "fact-checked against the routers, endpoints, panels, and test "
            "files when written; not telemetry or runtime checks.",
            "This layer lists verification commands but never runs them and "
            "never claims tests or builds were executed.",
            "Educational project-management aid only — not a production "
            "compliance or release-management system, and not advice.",
        ],
    )
