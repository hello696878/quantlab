"""
Deterministic static demo metadata for the Product Demo Center (Phase 34.0).

Eight hand-written guided demo paths and a 21-module health/capability catalog
describing QuantLab's own modules (status labels, data modes, capability
flags, sidebar routes). Every label is a static illustrative annotation
maintained by hand — not telemetry, not runtime introspection, not live data,
and not a quality certification. Identical every run and every test. Not
advice.
"""

from __future__ import annotations

from typing import List

from app.demo_center.models import (
    DemoCenterRequest,
    DemoCenterSampleResponse,
    DemoPath,
    DemoStep,
    ModuleHealthRow,
    SectionCatalogEntry,
)

DISCLAIMER = (
    "Static illustrative demo metadata. Demo center, module health, and "
    "walkthrough scripts are educational and not investment, trading, "
    "asset-allocation, legal, tax, compliance, or risk-management advice."
)

SCRIPT_SECTION_TITLES = {
    "opening": "Opening",
    "product_overview": "Product Overview",
    "guided_steps": "Guided Steps",
    "module_highlights": "Module Highlights",
    "limitations": "Limitations",
    "closing": "Closing",
}

AUDIENCES = ["founder", "investor", "quant_researcher", "recruiter", "student", "general"]

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

# ---------------------------------------------------------------------------
# Module health catalog (hand-maintained static labels).
# (id, name, category, route, status, data_mode,
#  backend, charts, controls, formulas, export, limitation, demo path, review label)
# ---------------------------------------------------------------------------
_MODULES = [
    ("global_markets_globe", "Global Markets Globe", "platform", "globe",
     "stable_demo", "static_sample", True, True, True, False, False,
     "Static sample market dossiers; optional opt-in FRED / delayed-quote adapters are disabled by default and fail closed to static.",
     "founder_investor_product_tour", "Phase 20.5 (static label)"),
    ("backtest_studio", "Backtest Studio", "backtesting", "backtest",
     "stable_demo", "user_input", True, True, True, False, False,
     "User-configured educational backtests; see the module's own docs for data sourcing — never live or real-time trading.",
     "quant_research_workflow_tour", "Phase 13 era (static label)"),
    ("strategy_comparison", "Strategy Comparison", "backtesting", "comparison",
     "stable_demo", "user_input", True, True, True, False, False,
     "Compares educational backtests side by side; results are historical simulations, not forward performance.",
     "quant_research_workflow_tour", "Phase 13 era (static label)"),
    ("export_report", "Export Report", "platform", "reports",
     "stable_demo", "local_calculation", True, False, False, False, True,
     "Saves and exports educational research summaries locally — not production reporting or record-keeping.",
     "full_platform_showcase_tour", "Phase 13 era (static label)"),
    ("portfolio_risk_lab", "Portfolio Risk Lab", "portfolio_risk", "risklab",
     "stable_demo", "static_sample", True, False, True, True, False,
     "Deterministic sample portfolio risk analytics; simplified educational models, not a production risk engine.",
     "macro_portfolio_stress_tour", "Phase 21 era (static label)"),
    ("macro_regime_lab", "Macro Regime Lab", "macro_cross_asset", "macroregime",
     "static_sample_only", "static_sample", True, False, True, True, False,
     "Hand-written macro states placed at chosen z-scores; educational allocation constructions, never portfolio guidance.",
     "macro_portfolio_stress_tour", "Phase 31.0 (static label)"),
    ("scenario_studio", "Scenario Studio", "macro_cross_asset", "scenariostudio",
     "static_sample_only", "static_sample", True, True, True, True, True,
     "Documented linear teaching weights on standardized shocks — does not call the other labs' engines.",
     "macro_portfolio_stress_tour", "Phase 32.0 (static label)"),
    ("research_workspace", "Research Workspace", "research_workflow", "researchworkspace",
     "static_sample_only", "static_sample", True, True, True, True, True,
     "Hand-written research packs — not recorded lab outputs; reproducibility score is a documentation count.",
     "quant_research_workflow_tour", "Phase 33.0 (static label)"),
    ("crypto_derivatives_lab", "Crypto Derivatives Lab", "crypto", "cryptoderivatives",
     "static_sample_only", "static_sample", True, True, True, True, False,
     "Approximate educational liquidation estimates on static sample markets — never live exchange data.",
     "crypto_risk_research_tour", "Phase 31.5 (static label)"),
    ("defi_risk_lab", "DeFi Risk Lab", "crypto", "defirisk",
     "static_sample_only", "static_sample", True, True, True, True, False,
     "Single-collateral educational health factors on static samples — no wallets, RPC, or protocol data.",
     "crypto_risk_research_tour", "Phase 31.5 (static label)"),
    ("tokenomics_lab", "Tokenomics Risk Lab", "crypto", "tokenomics",
     "static_sample_only", "static_sample", True, True, True, True, False,
     "Illustrative unlock/treasury/holder samples — unlocks are potential float, not predictions of selling.",
     "crypto_risk_research_tour", "Phase 31.5 (static label)"),
    ("onchain_analytics_lab", "On-Chain Analytics Lab", "crypto", "onchain",
     "static_sample_only", "static_sample", True, True, True, True, False,
     "Single-24h sample snapshots with illustrative entity labels — not live on-chain data or whale tracking.",
     "crypto_risk_research_tour", "Phase 31.5 (static label)"),
    ("alternative_data_lab", "Alternative Data Lab", "alternative_data", "altdata",
     "static_sample_only", "static_sample", True, True, True, True, False,
     "Hand-assigned sentiment scores and return paths — IC/decay figures illustrate the workflow, not alpha.",
     "alternative_data_signal_tour", "Phase 31.5 (static label)"),
    ("market_microstructure_lab", "Market Microstructure Lab", "microstructure", "microstructure",
     "stable_demo", "static_sample", True, False, True, True, False,
     "Static sample order books and trade tapes; educational closed-form approximations, not a TCA product.",
     "microstructure_execution_tour", "Phase 25.2 (static label)"),
    ("options_lab", "Options Lab", "derivatives_volatility", "options",
     "stable_demo", "local_calculation", True, True, True, True, False,
     "Local educational option pricing from user parameters — no live option chains or market data.",
     "full_platform_showcase_tour", "Phase 36.0 review (static label)"),
    ("volatility_lab", "Volatility Surface Lab", "derivatives_volatility", "volatility",
     "stable_demo", "static_sample", True, False, True, True, False,
     "Deterministic sample option chain; simplified variance-swap approximation, not the official VIX methodology.",
     "full_platform_showcase_tour", "Phase 25.1 (static label)"),
    ("futures_commodities_lab", "Futures & Commodities Lab", "derivatives_volatility", "futures",
     "stable_demo", "static_sample", True, False, True, True, False,
     "Deterministic sample futures curves; cost-of-carry teaching models, no live futures prices.",
     "full_platform_showcase_tour", "Phase 23.0 (static label)"),
    ("real_estate_lab", "Real Estate Lab", "real_assets_credit", "realestate",
     "stable_demo", "static_sample", True, False, True, True, False,
     "Illustrative property/REIT/MBS samples — not an appraisal, underwriting, or valuation tool.",
     "real_estate_credit_tour", "Phase 22.1 (static label)"),
    ("credit_risk_lab", "Credit Risk Lab", "real_assets_credit", "credit",
     "stable_demo", "local_calculation", True, True, True, True, False,
     "Local educational Merton / hazard / CDS teaching models from user parameters — no live credit data.",
     "real_estate_credit_tour", "Phase 36.0 review (static label)"),
    ("cross_sectional_scanner", "Cross-Sectional Scanner", "backtesting", "scanner",
     "experimental", "static_sample", True, True, True, False, False,
     "Second engine on a synthetic universe with a disclosed built-in reversal — workflow demo, not evidence of alpha.",
     "quant_research_workflow_tour", "Phase 18.0 (static label)"),
    ("afml_methodology_lab", "AFML Methodology Lab", "research_workflow", "finml",
     "experimental", "static_sample", True, True, True, False, False,
     "Pre-modeling methodology toolkit on a synthetic path — no features, no fitted model, no performance claims.",
     "quant_research_workflow_tour", "Phase 19.3 (static label)"),
]


def module_health_rows() -> List[ModuleHealthRow]:
    return [
        ModuleHealthRow(
            module_id=mid, module_name=name, category=cat,  # type: ignore[arg-type]
            route=route, status=status, data_mode=mode,  # type: ignore[arg-type]
            has_backend_endpoint=backend, has_charts=charts,
            has_interactive_controls=controls, has_formula_panel=formulas,
            has_report_export=export, limitations=[limitation],
            recommended_demo_path=path, last_review_label=review,
        )
        for (mid, name, cat, route, status, mode, backend, charts, controls,
             formulas, export, limitation, path, review) in _MODULES
    ]


def module_by_id(module_id: str) -> ModuleHealthRow:
    for row in module_health_rows():
        if row.module_id == module_id:
            return row
    raise KeyError(module_id)


# ---------------------------------------------------------------------------
# Demo paths
# ---------------------------------------------------------------------------
def _step(step_id, title, description, module, route, action, output, tip) -> DemoStep:
    return DemoStep(
        step_id=step_id, title=title, description=description,
        linked_module=module, route=route, expected_user_action=action,
        expected_output=output, demo_tip=tip,
    )


def sample_demo_paths() -> List[DemoPath]:
    """The eight deterministic guided demo paths (fresh copies each call)."""
    return [
        DemoPath(
            path_id="founder_investor_product_tour",
            title="Founder / Investor Product Tour",
            audience="founder",
            estimated_minutes=15,
            summary=(
                "A product-first pass: the globe as the visual hook, one "
                "polished lab flow, and the cross-lab studio to show breadth "
                "— everything on deterministic sample data."
            ),
            modules=["global_markets_globe", "backtest_studio", "scenario_studio", "research_workspace"],
            steps=[
                _step("fi_globe", "Open the Global Markets Globe",
                      "Start on the canvas globe and open one market dossier.",
                      "global_markets_globe", "globe",
                      "Drag the globe, click a market marker, walk the dossier panels.",
                      "A market dossier with sample indices, macro vitals, and headlines.",
                      "Point out the 'Sample' labels — the honesty is a feature."),
                _step("fi_backtest", "Run one backtest",
                      "Show the core engine with a simple SMA crossover run.",
                      "backtest_studio", "backtest",
                      "Pick a preset strategy and run it.",
                      "Equity curve, drawdown chart, metrics grid, trade table.",
                      "Keep parameters at defaults — speed matters more than tuning."),
                _step("fi_studio", "Stress everything at once",
                      "Open Scenario Studio and flip between two scenario templates.",
                      "scenario_studio", "scenariostudio",
                      "Switch Soft Landing → Severe Combo and drag one shock slider.",
                      "Module impact chart, heatmap, and regime pill re-draw instantly.",
                      "The severe combo's all-red heatmap is the money shot."),
                _step("fi_workspace", "Show the research product loop",
                      "End in the Research Workspace and copy a Markdown summary.",
                      "research_workspace", "researchworkspace",
                      "Open a preset, flip to Export, click Copy Markdown.",
                      "A structured research summary lands on the clipboard.",
                      "Paste the Markdown into any editor to close the loop."),
            ],
            learning_goals=[
                "See the platform's breadth in under twenty minutes.",
                "Understand the deterministic, education-first data policy.",
                "See a full research loop from model to exported summary.",
            ],
            suggested_talking_points=[
                "Every module runs locally on deterministic sample data — no keys, no feeds, no accounts.",
                "One shared design system: theme tokens, charts, LaTeX formulas, command palette.",
                "The platform is a teaching and research-workflow product, not a trading system.",
            ],
            limitations=[
                "All figures shown are illustrative static samples — no live market data.",
                "Nothing in the tour is investment research or a production risk output.",
            ],
            output_artifacts=["Copied Research Workspace Markdown summary", "A saved local draft (optional)"],
        ),
        DemoPath(
            path_id="quant_research_workflow_tour",
            title="Quant Research Workflow Tour",
            audience="quant_researcher",
            estimated_minutes=25,
            summary=(
                "The methodology story: backtest → compare → validate risk → "
                "regime context → cross-lab stress → journaled research pack."
            ),
            modules=[
                "backtest_studio", "strategy_comparison", "portfolio_risk_lab",
                "macro_regime_lab", "scenario_studio", "research_workspace",
            ],
            steps=[
                _step("qr_backtest", "Baseline a strategy",
                      "Run a strategy with explicit costs and timing rules.",
                      "backtest_studio", "backtest",
                      "Run SMA crossover with non-zero transaction costs.",
                      "Metrics grid with cost-adjusted returns and trade log.",
                      "Mention the lookahead-safety conventions up front."),
                _step("qr_compare", "Compare against alternatives",
                      "Put two strategies side by side on the same window.",
                      "strategy_comparison", "comparison",
                      "Load two strategies and compare their curves.",
                      "Side-by-side equity curves and metric deltas.",
                      "Highlight that comparison ≠ selection — it frames questions."),
                _step("qr_risk", "Check portfolio risk",
                      "Move from single-strategy to portfolio-level reads.",
                      "portfolio_risk_lab", "risklab",
                      "Edit sample weights and re-run the risk read.",
                      "Risk metrics and stress panels update deterministically.",
                      "Point at the documented formula panel while it recomputes."),
                _step("qr_macro", "Add macro context",
                      "Show regime scores over hand-placed indicator z-scores.",
                      "macro_regime_lab", "macroregime",
                      "Switch between two macro states.",
                      "Category scores and the regime pill flip.",
                      "Stress that indicators are placed by hand — a teaching set."),
                _step("qr_studio", "Stress across labs",
                      "Map one scenario into every module's impact score.",
                      "scenario_studio", "scenariostudio",
                      "Pick Credit Stress and read the module impact chart.",
                      "Credit/liquidity cluster wins the regime classification.",
                      "The weight tables are documented — open the formula panel."),
                _step("qr_journal", "Journal the pass",
                      "Stage runs in a research pack and export the summary.",
                      "research_workspace", "researchworkspace",
                      "Stage runs, write a note, copy the JSON export.",
                      "A reproducibility-checked research summary.",
                      "Show the methodology checklist catching a missing note."),
            ],
            learning_goals=[
                "Follow a full research loop with explicit methodology checks.",
                "See where leakage, cost, and documentation guards live.",
                "Understand the deterministic teaching-data policy end to end.",
            ],
            suggested_talking_points=[
                "Methodology first: costs, timing rules, purge/embargo, and leakage guards are visible features.",
                "Every score is a documented formula — nothing is a black box.",
                "The journal layer turns lab outputs into a reviewable research narrative.",
            ],
            limitations=[
                "Backtests are educational simulations — not forward performance.",
                "Workspace packs are hand-written samples, not recorded results.",
            ],
            output_artifacts=["Copied research JSON export", "A comparison read across two strategies"],
        ),
        DemoPath(
            path_id="crypto_risk_research_tour",
            title="Crypto Risk Research Tour",
            audience="quant_researcher",
            estimated_minutes=20,
            summary=(
                "The four crypto labs in sequence — funding/basis, DeFi "
                "lending, token supply, and on-chain flows — ending in the "
                "cross-lab crypto stress read."
            ),
            modules=[
                "crypto_derivatives_lab", "defi_risk_lab", "tokenomics_lab",
                "onchain_analytics_lab", "scenario_studio",
            ],
            steps=[
                _step("cr_perp", "Funding & basis mechanics",
                      "Walk the perp funding math and liquidation estimate.",
                      "crypto_derivatives_lab", "cryptoderivatives",
                      "Drag the funding and spot shock sliders.",
                      "Basis curve and liquidation-distance charts re-draw.",
                      "Label the liquidation price as the educational estimate it is."),
                _step("cr_defi", "DeFi lending stress",
                      "Show the kinked rate curve and health-factor stress.",
                      "defi_risk_lab", "defirisk",
                      "Drag the depeg and collateral shock sliders.",
                      "Health factor and peg charts move; HF stays finite.",
                      "Push utilization past the kink for the rate spike."),
                _step("cr_token", "Token supply pressure",
                      "Unlock schedule, runway, and concentration reads.",
                      "tokenomics_lab", "tokenomics",
                      "Set unlock ×2 and flip the 30/90/180/365d selector.",
                      "Unlock bars and runway chart re-draw.",
                      "The cumulative unlock line tells the dilution story."),
                _step("cr_chain", "Exchange flows & whales",
                      "Flow, reserve, cohort, and velocity reads.",
                      "onchain_analytics_lab", "onchain",
                      "Drag the inflow multiplier to ×3.",
                      "Net-flow bars flip positive; NVT and velocity shift.",
                      "Note the illustrative entity labels — honestly synthetic."),
                _step("cr_studio", "Cross-lab crypto stress",
                      "Roll it up with the Crypto Risk-Off template.",
                      "scenario_studio", "scenariostudio",
                      "Select Crypto Risk-Off and read the crypto cluster.",
                      "Crypto-specific stress regime with high crypto impacts.",
                      "Contrast with Soft Landing to show the range."),
            ],
            learning_goals=[
                "Connect funding, lending, supply, and flow mechanics.",
                "Read the same stress through four different lenses.",
                "See deterministic what-if controls on every lab.",
            ],
            suggested_talking_points=[
                "No exchange keys, no wallets, no RPC — every crypto number is a labeled static sample.",
                "The educational liquidation and health-factor estimates are deliberately simplified and say so.",
                "The cross-lab studio turns four labs into one coherent stress story.",
            ],
            limitations=[
                "Crypto samples are static snapshots — never live prices or funding.",
                "Simplified margin/health models — not exchange or protocol engines.",
            ],
            output_artifacts=["Cross-lab crypto stress read", "Copied Scenario Studio report (optional)"],
        ),
        DemoPath(
            path_id="macro_portfolio_stress_tour",
            title="Macro and Portfolio Stress Tour",
            audience="investor",
            estimated_minutes=15,
            summary=(
                "Macro regime scores, portfolio risk reads, and the cross-lab "
                "stress studio in one arc."
            ),
            modules=["macro_regime_lab", "portfolio_risk_lab", "scenario_studio"],
            steps=[
                _step("mp_macro", "Read the macro state",
                      "Category scores and regime classification.",
                      "macro_regime_lab", "macroregime",
                      "Switch Goldilocks → Stagflation.",
                      "Scores flip and the regime pill changes.",
                      "The six samples land on six distinct regimes."),
                _step("mp_risk", "Portfolio risk under stress",
                      "Sample portfolio metrics and stress scenarios.",
                      "portfolio_risk_lab", "risklab",
                      "Open the stress panel and walk two scenarios.",
                      "Deterministic stressed risk metrics.",
                      "Keep the formula panel open for transparency."),
                _step("mp_studio", "One dial for everything",
                      "Scenario Studio's macro templates.",
                      "scenario_studio", "scenariostudio",
                      "Pick Inflation Reacceleration; drag the policy slider.",
                      "Macro/policy stress regime; impact bars shift.",
                      "End on the severity gauge for a clean close."),
            ],
            learning_goals=[
                "Understand regime scoring on placed z-scores.",
                "See portfolio stress reads with documented formulas.",
                "Connect macro shocks to module-level impact scores.",
            ],
            suggested_talking_points=[
                "Macro states are constructed teaching examples — placed, not measured.",
                "Allocation outputs are educational constructions, never advice.",
                "The studio's weight tables are printed in the formula panel.",
            ],
            limitations=[
                "No live macro or market data in these labs.",
                "Educational allocations and scores — not portfolio guidance.",
            ],
            output_artifacts=["Macro stress narrative across three modules"],
        ),
        DemoPath(
            path_id="microstructure_execution_tour",
            title="Market Microstructure and Execution Tour",
            audience="quant_researcher",
            estimated_minutes=15,
            summary=(
                "Order-book reads, execution analytics, TCA attribution, and "
                "order-flow toxicity on static sample instruments."
            ),
            modules=["market_microstructure_lab"],
            steps=[
                _step("ms_book", "Read the order book",
                      "Spread, depth imbalance, and microprice.",
                      "market_microstructure_lab", "microstructure",
                      "Switch instruments (BTC, SPY, CL, TSM).",
                      "Book summary and depth ladder update.",
                      "Microprice vs mid is the quick sophistication signal."),
                _step("ms_exec", "Execution & schedule comparison",
                      "Implementation shortfall and four schedule styles.",
                      "market_microstructure_lab", "microstructure",
                      "Walk the schedule comparison table.",
                      "Cost decomposition per schedule style.",
                      "Stress that no schedule is endorsed — it is a comparison."),
                _step("ms_tox", "Order-flow toxicity",
                      "VPIN-style, Kyle-lambda, and Amihud approximations.",
                      "market_microstructure_lab", "microstructure",
                      "Open the toxicity section and the liquidity regime.",
                      "Toxicity metrics with the regime label.",
                      "Name-check the simplifications — it is not exchange VPIN."),
            ],
            learning_goals=[
                "Read a static order book like a microstructure researcher.",
                "Understand TCA attribution as a transparent decomposition.",
                "See toxicity metrics as teaching approximations.",
            ],
            suggested_talking_points=[
                "Every microstructure number is closed-form and documented.",
                "The TCA components sum to the shortfall by construction — an honest illustration.",
                "No order routing, no execution, no live books anywhere.",
            ],
            limitations=[
                "Static sample books and tapes — no live market data.",
                "Educational approximations — not a production TCA system.",
            ],
            output_artifacts=["A walked-through TCA attribution example"],
        ),
        DemoPath(
            path_id="alternative_data_signal_tour",
            title="Alternative Data and Signal Quality Tour",
            audience="quant_researcher",
            estimated_minutes=15,
            summary=(
                "Event scoring, freshness decay, leakage guards, and signal "
                "quality — then journal the read in the workspace."
            ),
            modules=["alternative_data_lab", "research_workspace"],
            steps=[
                _step("ad_events", "Score sample events",
                      "Weighted sentiment through novelty and freshness.",
                      "alternative_data_lab", "altdata",
                      "Walk the event table; drag the lag slider.",
                      "Signals fade as the freshness decay bites.",
                      "The macro sample is built orthogonal — a designed failure."),
                _step("ad_decay", "Decay & leakage",
                      "IC by horizon, half-life, and the leakage guard.",
                      "alternative_data_lab", "altdata",
                      "Flip the 1/5/20d selector; show the leakage scenario.",
                      "IC/hit chart re-highlights; leakage flags appear.",
                      "Zero leakage on valid inputs is the guard working."),
                _step("ad_journal", "Journal the signal review",
                      "The signal-quality research pack.",
                      "research_workspace", "researchworkspace",
                      "Open the Alternative Data Signal Quality pack.",
                      "Severity-ranked runs with the zero-baseline Δ% guard.",
                      "The ε-guarded Δ% rendering as — is a nice detail."),
            ],
            learning_goals=[
                "See a sentiment pipeline with hand-assigned, honest scores.",
                "Understand decay, half-life, and leakage checks.",
                "Turn a signal review into a journaled research pack.",
            ],
            suggested_talking_points=[
                "No scraping, no NLP, no LLMs — scores are hand-written so the math stays inspectable.",
                "Designed failures (orthogonal returns) teach more than cherry-picked wins.",
                "The leakage guard is a workflow feature, not an afterthought.",
            ],
            limitations=[
                "Fictional sample events with hand-assigned scores.",
                "IC and hit-rate figures illustrate workflow — not evidence of alpha.",
            ],
            output_artifacts=["Journaled signal-quality pack read"],
        ),
        DemoPath(
            path_id="real_estate_credit_tour",
            title="Real Estate and Credit Risk Tour",
            audience="student",
            estimated_minutes=15,
            summary=(
                "Cap rates, DSCR, MBS prepayment, then structural and "
                "reduced-form credit models — the real-assets classroom arc."
            ),
            modules=["real_estate_lab", "credit_risk_lab"],
            steps=[
                _step("re_cap", "Property economics",
                      "NOI, cap rate, DSCR, and cash-on-cash.",
                      "real_estate_lab", "realestate",
                      "Edit rent and vacancy assumptions.",
                      "Valuation and DSCR update deterministically.",
                      "Cap-rate expansion scenarios make the risk visceral."),
                _step("re_mbs", "MBS prepayment",
                      "CPR/SMM/PSA cash flows, WAL, duration.",
                      "real_estate_lab", "realestate",
                      "Switch the PSA speed and re-run.",
                      "Cash-flow profile and WAL shift.",
                      "The PSA ramp chart is the teaching moment."),
                _step("re_credit", "Credit risk models",
                      "Merton distance-to-default and hazard curves.",
                      "credit_risk_lab", "credit",
                      "Edit leverage and vol in the Merton panel.",
                      "Distance-to-default and spread reads update.",
                      "Connect structural vs reduced-form on one screen."),
            ],
            learning_goals=[
                "Price property economics with explicit assumptions.",
                "Understand prepayment mechanics and their duration effects.",
                "Contrast structural and reduced-form credit views.",
            ],
            suggested_talking_points=[
                "Classroom-grade transparency: every formula renders in LaTeX beside the numbers.",
                "Simplified on purpose — the models teach mechanics, not valuations.",
                "All inputs are editable sample assumptions.",
            ],
            limitations=[
                "Illustrative samples — not appraisals, underwriting, or credit ratings.",
                "Simplified educational models throughout.",
            ],
            output_artifacts=["A worked property + credit teaching example"],
        ),
        DemoPath(
            path_id="full_platform_showcase_tour",
            title="Full Platform Showcase Tour",
            audience="general",
            estimated_minutes=35,
            summary=(
                "The long cut: platform shell, core engines, five asset-class "
                "labs, the cross-lab studio, and the research workspace."
            ),
            modules=[
                "global_markets_globe", "backtest_studio", "strategy_comparison",
                "portfolio_risk_lab", "options_lab", "volatility_lab",
                "futures_commodities_lab", "market_microstructure_lab",
                "crypto_derivatives_lab", "alternative_data_lab",
                "macro_regime_lab", "scenario_studio", "research_workspace",
                "export_report",
            ],
            steps=[
                _step("fp_shell", "Platform shell",
                      "Sidebar, dashboard, command palette, theming.",
                      "global_markets_globe", "globe",
                      "Ctrl/Cmd+K through three modules; switch the accent.",
                      "Instant navigation and a full re-skin.",
                      "The palette search is the fastest wow moment."),
                _step("fp_engines", "Core engines",
                      "Backtest, comparison, and portfolio risk.",
                      "backtest_studio", "backtest",
                      "Run one backtest; open comparison; open risk lab.",
                      "Charts, metrics, and stress reads.",
                      "Keep each stop under three minutes."),
                _step("fp_assets", "Asset-class labs",
                      "Options → volatility → futures → microstructure.",
                      "options_lab", "options",
                      "One highlight per lab (greeks, surface, curve, book).",
                      "Each lab's signature visual.",
                      "Pre-choose the one panel you show per lab."),
                _step("fp_crypto", "Crypto & alternative data",
                      "One crypto lab plus the alt-data leakage guard.",
                      "crypto_derivatives_lab", "cryptoderivatives",
                      "Drag one shock slider in each.",
                      "Deterministic chart updates.",
                      "The leakage guard earns the methodology credibility."),
                _step("fp_studio", "Cross-lab stress & journal",
                      "Scenario Studio into the Research Workspace.",
                      "scenario_studio", "scenariostudio",
                      "Severe combo → workspace pack → copy Markdown.",
                      "The exported research summary.",
                      "End with the copied Markdown in an editor."),
                _step("fp_reports", "Saved outputs",
                      "Saved backtests and exported reports.",
                      "export_report", "reports",
                      "Open a saved report.",
                      "Locally saved research output.",
                      "Close on the local-first, no-accounts story."),
            ],
            learning_goals=[
                "See the entire platform surface in one sitting.",
                "Understand the shared design system and data policy.",
                "Leave with exported artifacts that prove the loop.",
            ],
            suggested_talking_points=[
                "Twenty-plus deterministic educational modules behind one shell.",
                "Local-first: no accounts, no keys, no telemetry, no cloud.",
                "Everything explains itself — formulas, limitations, and sample labels are UI features.",
            ],
            limitations=[
                "A long tour — rehearse the per-lab highlight choices.",
                "All modules are educational — none are production trading systems.",
            ],
            output_artifacts=["Copied cross-lab report", "Copied workspace Markdown", "A saved local report"],
        ),
    ]


def path_by_id(path_id: str) -> DemoPath:
    for p in sample_demo_paths():
        if p.path_id == path_id:
            return p
    raise KeyError(path_id)


def default_request() -> DemoCenterRequest:
    return DemoCenterRequest(
        selected_path_id="founder_investor_product_tour",
        selected_audience="general",
        included_modules=None,
        script_sections=list(SCRIPT_SECTION_TITLES.keys()),  # type: ignore[arg-type]
        time_budget_minutes=20.0,
        include_limitations=True,
        include_technical_notes=False,
    )


def build_sample_response() -> DemoCenterSampleResponse:
    return DemoCenterSampleResponse(
        demo_paths=sample_demo_paths(),
        module_health=module_health_rows(),
        script_sections=[
            SectionCatalogEntry(section_id=sid, section_title=title)  # type: ignore[arg-type]
            for sid, title in SCRIPT_SECTION_TITLES.items()
        ],
        audiences=list(AUDIENCES),  # type: ignore[arg-type]
        default_request=default_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "Eight hand-written guided demo paths and a 21-module health "
            "catalog — static illustrative demo metadata maintained by hand, "
            "not telemetry or runtime introspection.",
            "Status and capability labels are honest annotations for "
            "presenting the platform — not a quality certification.",
            "Educational only — not investment, trading, or asset-allocation "
            "advice; no module is a production trading system.",
        ],
    )
