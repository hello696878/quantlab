/**
 * Canonical workspace registry (Phase 63.0).
 *
 * QuantLab's navigation identity lives in three product surfaces: the sidebar
 * (`NAV_GROUPS` in `@/components/Sidebar`), the command palette, and the root
 * workspace switcher in `src/app/page.tsx`. This module is the single place
 * that ties them together for verification, and it holds the MINIMUM metadata
 * needed for that:
 *
 * * `WORKSPACES` — one entry per sidebar item (not internal views), derived so
 *   product ordering, labels and grouping stay exactly where the product
 *   defines them (this module never re-declares a label);
 * * `WORKSPACE_VISIBILITY` — a `Record<View, …>`, so the compiler forces an
 *   explicit visibility decision for every new view id;
 * * `WORKSPACE_COMMANDS` — the palette's navigation command data (titles and
 *   search keywords), moved here verbatim from the page component so drift
 *   guards and component tests can read it without importing the whole app.
 *
 * Deliberately NOT here: transient sub-views (portfolio tabs, library/paper/
 * disaster slugs, options tabs). Those are internal state within a workspace,
 * not routed workspaces, and forcing them into this registry would make it
 * describe something the router does not own.
 *
 * See `docs/FRONTEND_REGISTRY_DRIFT_GUARDS.md`.
 */

import type { View } from "@/components/AppShell";
import { NAV_GROUPS } from "@/components/Sidebar";

/**
 * How a routed view reaches the user.
 *
 * `sidebar` — a public workspace listed in the sidebar navigation.
 * `internal` — routed but deliberately absent from the sidebar; every such
 *   view MUST carry a reason in `INTERNAL_VIEW_REASONS` below.
 */
export type WorkspaceVisibility = "sidebar" | "internal";

/**
 * Exhaustive visibility classification. Because this is a `Record<View, …>`,
 * adding a member to the `View` union without classifying it is a TypeScript
 * error rather than a silently unreachable workspace.
 *
 * Today every routed view is a public sidebar workspace; the map still exists
 * so the first hidden view has to declare itself.
 */
export const WORKSPACE_VISIBILITY: Record<View, WorkspaceVisibility> = {
  home: "sidebar",
  globe: "sidebar",
  backtest: "sidebar",
  library: "sidebar",
  replications: "sidebar",
  disasters: "sidebar",
  options: "sidebar",
  events: "sidebar",
  rates: "sidebar",
  fx: "sidebar",
  credit: "sidebar",
  scanner: "sidebar",
  finml: "sidebar",
  risklab: "sidebar",
  realestate: "sidebar",
  futures: "sidebar",
  volatility: "sidebar",
  microstructure: "sidebar",
  cryptoderivatives: "sidebar",
  defirisk: "sidebar",
  tokenomics: "sidebar",
  onchain: "sidebar",
  altdata: "sidebar",
  macroregime: "sidebar",
  scenariostudio: "sidebar",
  researchworkspace: "sidebar",
  experimentregistry: "sidebar",
  datasetlineage: "sidebar",
  modelvalidation: "sidebar",
  metalabeling: "sidebar",
  featurediagnostics: "sidebar",
  overfittingdiagnostics: "sidebar",
  regimediagnostics: "sidebar",
  costdiagnostics: "sidebar",
  portfoliodiagnostics: "sidebar",
  portfoliostress: "sidebar",
  portfolioattribution: "sidebar",
  factordiagnostics: "sidebar",
  signaldecay: "sidebar",
  signalensemble: "sidebar",
  democenter: "sidebar",
  datareliability: "sidebar",
  qacommandcenter: "sidebar",
  portfolioshowcase: "sidebar",
  developeronboarding: "sidebar",
  releasenotes: "sidebar",
  publicreleasecandidate: "sidebar",
  csv: "sidebar",
  builder: "sidebar",
  portfolio: "sidebar",
  sweep: "sidebar",
  "train-test": "sidebar",
  "walk-forward": "sidebar",
  comparison: "sidebar",
  saved: "sidebar",
  reports: "sidebar",
  settings: "sidebar",
};

/**
 * Why a routed view is intentionally absent from the sidebar. Empty today —
 * the drift guard requires an entry here for every `internal` view, so a
 * hidden workspace can never appear without a stated reason.
 */
export const INTERNAL_VIEW_REASONS: Partial<Record<View, string>> = {};

/** One routed workspace, joined from the product's own navigation data. */
export interface WorkspaceEntry {
  id: View;
  /** Canonical label — read from the sidebar, never re-declared here. */
  label: string;
  /** Sidebar group heading the entry belongs to. */
  group: string;
  visibility: WorkspaceVisibility;
  /** True when the workspace is reachable from the public sidebar. */
  publicWorkspace: boolean;
}

/**
 * The canonical workspace list, in sidebar order. Derived rather than
 * duplicated: if the sidebar's labels, grouping or order change, this follows
 * automatically and the guards compare against the real product surface.
 */
export const WORKSPACES: readonly WorkspaceEntry[] = NAV_GROUPS.flatMap((group) =>
  group.items.map((item) => {
    const visibility = WORKSPACE_VISIBILITY[item.id];
    return {
      id: item.id,
      label: item.label,
      group: group.label,
      visibility,
      publicWorkspace: visibility === "sidebar",
    };
  }),
);

/** Lookup by view id. */
export const WORKSPACE_BY_ID: Partial<Record<View, WorkspaceEntry>> =
  Object.fromEntries(WORKSPACES.map((w) => [w.id, w])) as Partial<
    Record<View, WorkspaceEntry>
  >;

/** Sidebar group headings, in product order. */
export const WORKSPACE_GROUPS: readonly string[] = NAV_GROUPS.map((g) => g.label);

/** Every classified view id, whether sidebar-visible or internal. */
export const ALL_VIEW_IDS: readonly View[] = Object.keys(
  WORKSPACE_VISIBILITY,
) as View[];

/**
 * Command-palette navigation commands.
 *
 * Moved verbatim out of the page component (Phase 63.0) so both the palette
 * and its drift guards read one list. A view may legitimately carry more than
 * one command (`sweep` is reachable as both "Research Tools" and "Parameter
 * Sweep"); the guards allow that and only reject unknown views or duplicated
 * command identities. `keywords` are search words, not unique routing aliases.
 */
export const WORKSPACE_COMMANDS: { view: View; title: string; keywords: string }[] = [
  { view: "home", title: "Go to Home", keywords: "command center dashboard" },
  { view: "globe", title: "Open Global Markets Globe", keywords: "globe global markets world markets country macro fx indices market dossier united states japan taiwan germany india europe asia explore map 3d earth" },
  { view: "backtest", title: "Go to Backtest", keywords: "single asset run strategy" },
  { view: "library", title: "Open Strategy Library", keywords: "models catalog docs education strategy pages" },
  { view: "replications", title: "Open Paper Replications", keywords: "papers research academic momentum pairs replication" },
  { view: "disasters", title: "Open Quant Disasters", keywords: "risk education failures ltcm crash blowup lessons" },
  { view: "options", title: "Open Options Lab", keywords: "options black-scholes greeks implied volatility payoff straddle strangle covered call protective put" },
  { view: "events", title: "Open Event Lab", keywords: "event study abnormal return car caar merger arbitrage deal spread event-driven earnings event" },
  { view: "rates", title: "Open Yield Curve Lab", keywords: "yield curve rates zero rate discount factor forward rate duration convexity dv01 bond pricing fixed income short rate vasicek cir mean reversion" },
  { view: "fx", title: "Open FX Lab", keywords: "fx foreign exchange currency forward rate interest rate parity carry ppp purchasing power parity exposure garman kohlhagen fx option" },
  { view: "credit", title: "Open Credit Risk Lab", keywords: "credit credit risk merton structural model distance to default default probability hazard rate survival curve cds credit spread risky bond recovery rate" },
  { view: "scanner", title: "Open Cross-Sectional Scanner", keywords: "scanner cross-sectional rank long short universe equity scanner factor ranking mean reversion momentum dollar neutral scanner lab second engine" },
  { view: "finml", title: "Open AFML Methodology Lab", keywords: "afml financial ml machine learning triple barrier cusum event sampling sample uniqueness concurrency labeling meta-labeling purged k-fold embargo cross validation leakage label overlap sequential bootstrap fractional differentiation fracdiff stationarity cpcv lopez de prado" },
  { view: "risklab", title: "Open Portfolio Risk Lab", keywords: "portfolio risk lab analytics expected return volatility sharpe covariance correlation marginal component risk contribution value at risk var cvar expected shortfall stress scenario efficient frontier minimum variance risk parity allocation weights" },
  { view: "realestate", title: "Open Real Estate Lab", keywords: "real estate property reit noi net operating income cap rate valuation mortgage amortization ltv loan to value dscr debt service coverage cash on cash irr equity multiple rent vacancy stress nav premium discount ffo dividend yield" },
  { view: "futures", title: "Open Futures and Commodities Lab", keywords: "futures commodities commodity cost of carry convenience yield contango backwardation curve roll yield calendar spread margin leverage notional crude oil gold natural gas wheat basis scenario stress" },
  { view: "volatility", title: "Open Volatility Lab", keywords: "volatility surface variance swap implied vol iv smile skew term structure realized vol vega black scholes option chain fair strike vix scenario stress derivatives" },
  { view: "microstructure", title: "Open Market Microstructure Lab", keywords: "microstructure execution order book limit order book bid ask spread depth imbalance microprice vwap twap implementation shortfall slippage market impact participation rate liquidity stress execution schedule transaction cost analysis tca" },
  { view: "cryptoderivatives", title: "Open Crypto Derivatives Lab", keywords: "crypto derivatives perpetual perp futures funding rate basis annualized carry cash and carry liquidation margin leverage btc eth sol bitcoin ethereum solana contango backwardation funding pnl interactive shock slider basis curve chart" },
  { view: "defirisk", title: "Open DeFi Risk Lab", keywords: "defi decentralized finance stablecoin peg depeg lending borrow apy utilization kink interest rate model collateral health factor ltv loan to value liquidation threshold net apy carry usdc usdt dai aave protocol stress interactive shock slider rate curve chart" },
  { view: "tokenomics", title: "Open Tokenomics Risk Lab", keywords: "tokenomics token unlock schedule vesting cliff dilution fdv fully diluted valuation market cap float ratio emission inflation staking real yield treasury runway burn holder concentration crypto fundamentals interactive shock slider horizon chart" },
  { view: "onchain", title: "Open On-Chain Analytics Lab", keywords: "on-chain onchain exchange inflow outflow net flow exchange reserve active addresses transfer volume transaction count token velocity nvt whale concentration gini holder cohort crypto analytics interactive shock slider flow chart" },
  { view: "altdata", title: "Open Alternative Data Lab", keywords: "alternative data alt data news sentiment social sentiment earnings macro supply chain events novelty freshness leakage guard information coefficient ic hit rate signal decay alpha score event study interactive shock slider timeline decay chart" },
  { view: "macroregime", title: "Open Macro Regime Lab", keywords: "macro regime cross asset allocation growth inflation policy liquidity credit stress usd pressure z-score goldilocks stagflation recession risk parity inverse volatility regime tilt" },
  { view: "scenariostudio", title: "Open Scenario Studio", keywords: "scenario studio unified cross lab report builder stress template soft landing inflation growth shock liquidity crunch credit crypto risk off depeg inflow panic severe combo impact score heatmap severity regime markdown report" },
  { view: "researchworkspace", title: "Open Research Workspace", keywords: "research workspace experiment journal saved presets run comparison baseline stressed severity coverage reproducibility methodology checklist workflow timeline notes markdown json export local drafts" },
  { view: "experimentregistry", title: "Open Experiment Registry", keywords: "experiment registry reproducibility dashboard research run provenance fingerprint sha256 configuration result dataset random seed git commit metrics baseline compare diff status completed failed invalidated reproducible partially not reproducible lineage parent export json demo records local sqlite" },
  { view: "datasetlineage", title: "Open Dataset Lineage", keywords: "dataset lineage data provenance registry version schema drift fingerprint manifest content source quality checks transformation parent child derived fixture local file generated provider license storage locator experiment links compare versions invalidated export json demo lineage sqlite" },
  { view: "modelvalidation", title: "Open Model Validation Lab", keywords: "model validation purged cross validation cv cpcv combinatorial embargo leakage audit walk forward k-fold kfold fold split train test overlap information interval prediction evaluation time purge baseline fingerprint compare runs afml lopez de prado deterministic demo" },
  { view: "metalabeling", title: "Open Meta-Labeling Lab", keywords: "meta labeling meta-label secondary signal probability calibration platt sigmoid isotonic reliability curve brier log loss ece mce expected calibration error decision threshold coverage precision recall abstention out of fold oof primary side outcome policy threshold policy baseline compare export demo" },
  { view: "featurediagnostics", title: "Open Feature Diagnostics", keywords: "feature importance permutation importance held out held-out stability rank stability spearman kendall top-k overlap correlated features correlation groups multicollinearity distribution drift psi population stability index ks statistic importance drift impurity native importance coefficient decision tree logistic regression baseline compare export demo" },
  { view: "overfittingdiagnostics", title: "Open Overfitting Diagnostics", keywords: "backtest overfitting pbo probability of backtest overfitting cscv combinatorially symmetric cross validation selection bias deflated sharpe probabilistic sharpe psr dsr minimum track record mintrl multiple testing bonferroni holm benjamini hochberg false discovery rate fwer fdr p-value trials expected maximum sharpe candidate dependence lambda logit baseline compare export demo" },
  { view: "regimediagnostics", title: "Open Regime Diagnostics", keywords: "market regime volatility regime trend regime liquidity regime drawdown state combined regime conditional performance no look-ahead lookahead trailing window lag threshold quantile training-only full-sample coverage rank stability concentration herfindahl hhi entropy regime transition timeline effective label integrity baseline compare export demo" },
  { view: "costdiagnostics", title: "Open Cost & Capacity", keywords: "transaction cost commission fee spread slippage market impact square root impact capacity notional scaling participation rate adv average daily volume liquidity turnover gross net reconciliation waterfall break-even breakeven basis points bps ticks per contract per order sensitivity grid stress multiplier fill execution cost diagnostics baseline compare export demo" },
  { view: "portfoliodiagnostics", title: "Open Portfolio Diagnostics", keywords: "portfolio construction risk budgeting risk budget equal risk contribution erc inverse volatility minimum variance weight constraint group cap weight cap gross net exposure leverage turnover cap rebalance covariance shrinkage eigenvalue floor psd positive semidefinite condition number marginal component percentage risk contribution diversification ratio effective positions herfindahl concentration no look-ahead estimation window solver convergence baseline compare export demo" },
  { view: "portfoliostress", title: "Open Portfolio Stress Lab", keywords: "portfolio stress testing scenario shock stress scenario historical window replay hypothetical asset shock group shock global shock volatility stress correlation stress toward one supplied correlation liquidity cost stress spread multiplier adv participation drawdown episode attribution peak trough recovery unrecovered drifted weights constraint breach basis points bps percent return units precedence missing shock policy stressed covariance psd eigenvalue repair baseline vs stressed mcr ccr pcr rank change reconciliation baseline compare export demo" },
  { view: "signaldecay", title: "Open Signal Decay Lab", keywords: "signal decay forecast horizon holding period implementation lag information coefficient rank ic spearman pearson kendall quantile bucket return top minus bottom spread signal turnover rank turnover jaccard membership one way turnover holding cohort overlap forward return future return signal persistence autocorrelation decay curve half life sign change overlapping non overlapping cross sectional ic tie policy constant signal bootstrap block bootstrap multiple testing cost adjusted gross net regime held out validation factor residual baseline compare export demo" },
  { view: "signalensemble", title: "Open Signal Ensemble Lab", keywords: "signal ensemble signal combination redundancy pairwise correlation rank correlation similarity matrix distance hierarchical clustering linkage dendrogram effective signal count eigenvalue concentration matrix rank condition number strict intersection pairwise complete alignment missingness equal weight user weights static weights rank average majority sign component contribution reconciliation missing component require all renormalise leave one out turnover comparison cost adjusted regime held out validation factor residual tail co-occurrence bucket agreement jaccard bootstrap sensitivity baseline compare export demo" },
  { view: "factordiagnostics", title: "Open Factor Diagnostics", keywords: "factor exposure factor model return decomposition macro sensitivity regression ordinary least squares ols ridge beta coefficient intercept residual r squared adjusted r squared rmse standard error t statistic p value confidence interval condition number matrix rank multicollinearity variance inflation vif factor correlation rolling beta exposure stability lagged causal contemporaneous descriptive availability vintage first release basis point change trailing z score held out validation split purged embargo bonferroni holm benjamini hochberg sensitivity scenarios reconciliation baseline compare export demo" },
  { view: "portfolioattribution", title: "Open Portfolio Attribution", keywords: "performance attribution return contribution benchmark active return tracking error information ratio brinson fachler hood beebower allocation effect selection effect interaction effect residual multi period linking carino arithmetic geometric time weighted return twr contribution to return group sector attribution gross net cost attribution concentration herfindahl hit rate active drawdown beginning of period weights reconciliation baseline compare export demo" },
  { view: "democenter", title: "Open Demo Center", keywords: "demo center product walkthrough guided tour showcase presentation module health capability matrix readiness demo script builder audience founder investor recruiter portfolio" },
  { view: "datareliability", title: "Open Data Reliability Center", keywords: "data reliability center data mode registry offline fixtures provider registry yfinance fred test safety deterministic fallback external exposure reliability score" },
  { view: "qacommandcenter", title: "Open QA Command Center", keywords: "qa command center release readiness smoke test matrix regression checklist release notes commands pytest typecheck build known limitations release decision" },
  { view: "portfolioshowcase", title: "Open Portfolio Showcase", keywords: "portfolio showcase public presentation pitch recruiter quant technical demo path highlights launch pack resume interview linkedin" },
  { view: "developeronboarding", title: "Open Developer Onboarding", keywords: "developer onboarding local demo launcher environment doctor commands troubleshooting venv uvicorn pytest typecheck npm setup" },
  { view: "releasenotes", title: "Open Release Notes Center", keywords: "release notes center version manifest changelog milestone history project snapshot tag conventions release checklist" },
  { view: "publicreleasecandidate", title: "Open Public Release Candidate", keywords: "public release candidate final smoke test runbook demo freeze checklist launch readiness known limitations public final demo script rc status manual verification portfolio sharing" },
  { view: "csv", title: "Go to CSV Upload", keywords: "import upload data file" },
  { view: "builder", title: "Go to Custom Strategy Builder", keywords: "no code rules indicator" },
  { view: "portfolio", title: "Go to Portfolio Lab", keywords: "multi asset weights" },
  { view: "sweep", title: "Go to Research Tools", keywords: "sweep validation optimization research" },
  { view: "sweep", title: "Go to Parameter Sweep", keywords: "grid search sma fast slow" },
  { view: "train-test", title: "Go to Train/Test Validation", keywords: "in sample out of sample" },
  { view: "walk-forward", title: "Go to Walk-Forward Optimization", keywords: "rolling reoptimization" },
  { view: "comparison", title: "Go to Strategy Comparison", keywords: "compare strategies side by side" },
  { view: "saved", title: "Go to Saved Backtests", keywords: "history persisted sqlite" },
  { view: "reports", title: "Go to Saved Reports", keywords: "report gallery markdown" },
  { view: "settings", title: "Go to Settings", keywords: "preferences theme defaults" },
];
