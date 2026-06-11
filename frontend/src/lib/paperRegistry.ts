/**
 * Paper Replication Series registry (v1).
 *
 * Single source of truth for the Paper Replications index + detail pages and
 * their Backtest Studio presets.  Honesty rules:
 *
 * * `status: "live"` means QuantLab can run *something* related today — and
 *   `replicationLevel` says exactly how much: v1 ships **inspired demos**
 *   (single-asset approximations), never full academic replications.
 * * `full_replication` must not be used until methodology, universe, and data
 *   genuinely match the original paper design.
 * * Planned/future papers have no `runPreset`, so no run button can exist.
 * * No original-paper performance numbers are reproduced here — summaries
 *   describe the research question and method, not invented results.
 */

import type { StrategyType } from "@/lib/types";

export type PaperStatus = "live" | "planned" | "future";
export type ReplicationLevel =
  | "full_replication"
  | "simplified_replication"
  | "inspired_demo"
  | "planned";

export interface PaperRunPreset {
  /** Backtest Studio strategy to preselect. */
  strategyId: StrategyType;
  /** Ticker override for the demo (single-asset strategies). */
  ticker?: string;
  /** Short label shown on the button. */
  label: string;
}

export interface PaperEntry {
  id: string;
  slug: string;
  title: string;
  authors: string;
  year: number;
  category: string;
  status: PaperStatus;
  replicationLevel: ReplicationLevel;
  difficulty: "core" | "advanced" | "frontier";
  /** Strategy-registry ids this paper relates to (cross-links). */
  relatedStrategyIds: string[];
  summary: string;
  researchQuestion: string;
  coreIdea: string;
  originalMethod: string[];
  quantlabToday: string[];
  dataRequirements: string[];
  limitations: string[];
  runPreset?: PaperRunPreset;
  reference: string;
}

export const PAPER_REGISTRY: PaperEntry[] = [
  {
    id: "jegadeesh_titman_1993",
    slug: "jegadeesh-titman-1993-momentum",
    title: "Returns to Buying Winners and Selling Losers",
    authors: "Jegadeesh & Titman",
    year: 1993,
    category: "Equities · Momentum",
    status: "live",
    replicationLevel: "inspired_demo",
    difficulty: "core",
    relatedStrategyIds: ["momentum"],
    summary:
      "The classic cross-sectional momentum paper: past 3–12 month winners kept outperforming past losers.",
    researchQuestion:
      "Do stocks that outperformed their peers over the past 3–12 months continue to outperform over the next 3–12 months?",
    coreIdea:
      "Relative past performance carries information about near-future relative performance — under-reaction and slow information diffusion create return continuation across stocks.",
    originalMethod: [
      "Universe: NYSE/AMEX stocks.",
      "Each month, rank all stocks by trailing J-month return (J = 3, 6, 9, 12).",
      "Buy the top decile (winners), short the bottom decile (losers), equal-weighted.",
      "Hold for K months (K = 3, 6, 9, 12) with overlapping portfolios.",
      "Study the winner-minus-loser spread across J/K combinations.",
    ],
    quantlabToday: [
      "QuantLab can run single-asset time-series momentum (trailing-return sign on one ticker).",
      "That tests trend persistence on one asset — related to, but not the same as, the paper's cross-sectional winner-minus-loser decile design.",
      "Use the demo to study how trailing-return signals behave; do not read it as the paper's anomaly.",
    ],
    dataRequirements: [
      "Survivorship-bias-free cross-sectional stock universe (thousands of stocks).",
      "Point-in-time constituent lists and delisting returns.",
      "Monthly total returns including dividends.",
    ],
    limitations: [
      "Single asset instead of a ranked universe — no cross-sectional spread.",
      "No short leg of the loser decile in the demo preset.",
      "Daily yfinance data, simplified costs, no borrow or liquidity modelling.",
    ],
    runPreset: {
      strategyId: "momentum",
      ticker: "SPY",
      label: "Run inspired demo (single-asset momentum)",
    },
    reference:
      "Jegadeesh, N., & Titman, S. (1993). Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. Journal of Finance, 48(1).",
  },
  {
    id: "gatev_2006_pairs",
    slug: "gatev-goetzmann-rouwenhorst-2006-pairs",
    title: "Pairs Trading: Performance of a Relative-Value Arbitrage Rule",
    authors: "Gatev, Goetzmann & Rouwenhorst",
    year: 2006,
    category: "Equities · Statistical Arbitrage",
    status: "live",
    replicationLevel: "inspired_demo",
    difficulty: "advanced",
    relatedStrategyIds: ["pairs"],
    summary:
      "Formalized pairs trading: match stocks with historically parallel prices, trade divergences back to parity.",
    researchQuestion:
      "Does a simple, mechanical relative-value rule — trade temporary divergences between historically co-moving stocks — earn returns after costs?",
    coreIdea:
      "If two assets share fundamentals, their normalized price gap is mean-reverting; divergence is more often noise/flows than permanent repricing.",
    originalMethod: [
      "12-month formation period: match pairs by minimum distance between normalized price paths over the full CRSP universe.",
      "6-month trading period: open when the spread diverges beyond 2 historical standard deviations.",
      "Close on convergence (prices cross) or at period end; long the cheap leg, short the rich leg.",
      "Aggregate across the top 5/20/101–120 distance-ranked pairs.",
    ],
    quantlabToday: [
      "QuantLab can run a single, user-chosen pair (e.g. KO/PEP) with a rolling z-score entry/exit on the log-price spread.",
      "That demonstrates the trade mechanics on one pair — the paper's edge came from systematic pair *selection* over a broad universe.",
    ],
    dataRequirements: [
      "Broad survivorship-bias-free equity universe for pair formation.",
      "Total-return series (dividends) for normalized price paths.",
      "Realistic short borrow availability and costs.",
    ],
    limitations: [
      "One hand-picked pair instead of distance-ranked universe selection.",
      "z-score window replaces the paper's formation/trading period structure.",
      "No borrow/funding costs; daily closes only; cost/sizing/risk engines don't apply to pairs in v1.",
    ],
    runPreset: {
      strategyId: "pairs",
      label: "Run inspired demo (single-pair z-score)",
    },
    reference:
      "Gatev, E., Goetzmann, W., & Rouwenhorst, K.G. (2006). Pairs Trading: Performance of a Relative-Value Arbitrage Rule. Review of Financial Studies, 19(3).",
  },
  {
    id: "moskowitz_ooi_pedersen_2012",
    slug: "moskowitz-ooi-pedersen-2012-tsmom",
    title: "Time Series Momentum",
    authors: "Moskowitz, Ooi & Pedersen",
    year: 2012,
    category: "Futures & Commodities · Trend",
    status: "live",
    replicationLevel: "inspired_demo",
    difficulty: "advanced",
    relatedStrategyIds: ["momentum", "sma_crossover"],
    summary:
      "An asset's own past 12-month return predicts its next-month return across 58 futures markets.",
    researchQuestion:
      "Is there return continuation in an asset's *own* time series (not relative to peers), and does it hold across asset classes?",
    coreIdea:
      "Sign of trailing return → direction of next position, per market, scaled to constant volatility and diversified across dozens of futures.",
    originalMethod: [
      "58 liquid futures (equities, bonds, FX, commodities), 1965–2009.",
      "Each month, long markets with positive trailing 12-month excess return, short negative ones.",
      "Scale each position to a constant ex-ante volatility target (~40% annualized per market).",
      "Equal-weight the diversified portfolio of per-market positions.",
    ],
    quantlabToday: [
      "QuantLab's time-series momentum on one ticker is the per-market building block of TSMOM (long/short mode mirrors the sign rule).",
      "Volatility-target position sizing approximates the paper's constant-vol scaling on that single asset.",
      "Missing: the diversified multi-market futures portfolio, which is where most of the paper's result lives.",
    ],
    dataRequirements: [
      "Continuous futures price series across asset classes (roll-adjusted).",
      "Excess-return construction over funding rates.",
      "Per-market volatility estimates for position scaling.",
    ],
    limitations: [
      "One ETF/crypto ticker instead of 58 futures markets.",
      "No roll yield / futures term structure; daily ETF data as a stand-in.",
      "Diversification across markets — central to the paper — is absent.",
    ],
    runPreset: {
      strategyId: "momentum",
      ticker: "SPY",
      label: "Run inspired demo (single-asset TSMOM building block)",
    },
    reference:
      "Moskowitz, T., Ooi, Y.H., & Pedersen, L.H. (2012). Time Series Momentum. Journal of Financial Economics, 104(2).",
  },
  {
    id: "fama_french_1993",
    slug: "fama-french-1993-factors",
    title: "Common Risk Factors in the Returns on Stocks and Bonds",
    authors: "Fama & French",
    year: 1993,
    category: "Equities · Factor Models",
    status: "planned",
    replicationLevel: "planned",
    difficulty: "advanced",
    relatedStrategyIds: [],
    summary:
      "The three-factor model: market, size (SMB), and value (HML) factors explain cross-sectional stock returns.",
    researchQuestion:
      "Can a small set of common factors — beyond the market — explain the cross-section of average stock and bond returns?",
    coreIdea:
      "Sort the universe by size and book-to-market, build long/short factor portfolios, and regress asset returns on the factor returns.",
    originalMethod: [
      "Double-sort NYSE/AMEX/NASDAQ stocks into size and book-to-market buckets.",
      "Construct SMB (small-minus-big) and HML (high-minus-low) factor returns.",
      "Time-series regressions of portfolio returns on market, SMB, and HML.",
    ],
    quantlabToday: [
      "Not runnable yet: requires factor return data and portfolio sorts. QuantLab's portfolio factor-analysis panel does related regression diagnostics on user portfolios, but it is not a Fama–French replication.",
    ],
    dataRequirements: [
      "Point-in-time fundamentals (book equity) for the full universe.",
      "Survivorship-bias-free returns with delistings.",
      "Or, pragmatically, the published Ken French factor return library.",
    ],
    limitations: ["Planned — no run preset until a factor engine exists."],
    reference:
      "Fama, E., & French, K. (1993). Common Risk Factors in the Returns on Stocks and Bonds. Journal of Financial Economics, 33(1).",
  },
  {
    id: "frazzini_pedersen_2014",
    slug: "frazzini-pedersen-2014-bab",
    title: "Betting Against Beta",
    authors: "Frazzini & Pedersen",
    year: 2014,
    category: "Portfolio & Risk · Factors",
    status: "planned",
    replicationLevel: "planned",
    difficulty: "frontier",
    relatedStrategyIds: [],
    summary:
      "Leverage-constrained investors overpay for high-beta assets; a beta-neutral low-beta-vs-high-beta portfolio earned a premium.",
    researchQuestion:
      "Why do low-beta assets deliver higher risk-adjusted returns than the CAPM predicts, and can a factor harvest it?",
    coreIdea:
      "Investors who cannot lever up bid up high-beta assets instead; the BAB factor goes long levered low-beta and short de-levered high-beta.",
    originalMethod: [
      "Estimate rolling betas for a broad cross-section.",
      "Rank into low/high beta portfolios, lever the long leg and de-lever the short leg to beta-neutrality.",
      "Study the factor across equities, bonds, credit, and futures.",
    ],
    quantlabToday: [
      "Not runnable yet: requires cross-sectional beta estimation and explicit leverage — QuantLab's engines are deliberately no-leverage today.",
    ],
    dataRequirements: [
      "Cross-sectional universe with rolling beta estimates.",
      "Leverage and financing-cost modelling.",
    ],
    limitations: ["Planned — would also require relaxing the no-leverage convention in a clearly-scoped sandbox."],
    reference:
      "Frazzini, A., & Pedersen, L.H. (2014). Betting Against Beta. Journal of Financial Economics, 111(1).",
  },
  {
    id: "avellaneda_stoikov_2008",
    slug: "avellaneda-stoikov-2008-market-making",
    title: "High-Frequency Trading in a Limit Order Book",
    authors: "Avellaneda & Stoikov",
    year: 2008,
    category: "Market Microstructure & HFT",
    status: "future",
    replicationLevel: "planned",
    difficulty: "frontier",
    relatedStrategyIds: [],
    summary:
      "Optimal market-making quotes derived from inventory risk and order-arrival intensity in a limit order book.",
    researchQuestion:
      "How should a market maker set bid/ask quotes to balance spread capture against inventory risk?",
    coreIdea:
      "A reservation price shifted by inventory, with quote distances from a Hamilton–Jacobi–Bellman solution under exponential utility and Poisson order flow.",
    originalMethod: [
      "Model the mid-price as Brownian motion and order arrivals as intensity-decaying Poisson processes.",
      "Solve for optimal bid/ask offsets as functions of inventory, risk aversion, and time horizon.",
      "Simulate the strategy in a synthetic limit order book.",
    ],
    quantlabToday: [
      "Not runnable: needs the future Microstructure & HFT Lab (educational LOB simulations on synthetic data) — daily-bar backtesting cannot express this paper.",
    ],
    dataRequirements: [
      "Limit-order-book simulator (synthetic) — explicitly not live market data.",
    ],
    limitations: ["Future — belongs to the HFT Lab phase; educational simulation only, never live HFT execution."],
    reference:
      "Avellaneda, M., & Stoikov, S. (2008). High-Frequency Trading in a Limit Order Book. Quantitative Finance, 8(3).",
  },
  {
    id: "black_scholes_1973",
    slug: "black-scholes-1973-options",
    title: "The Pricing of Options and Corporate Liabilities",
    authors: "Black & Scholes",
    year: 1973,
    category: "Options & Volatility",
    status: "planned",
    replicationLevel: "planned",
    difficulty: "advanced",
    relatedStrategyIds: [],
    summary:
      "The no-arbitrage option pricing model: continuous hedging replicates the option payoff, yielding a closed-form price.",
    researchQuestion:
      "What is the fair value of a European option if continuous riskless hedging is possible?",
    coreIdea:
      "A dynamically rebalanced stock + bond portfolio replicates the option, so its price must satisfy a PDE with a closed-form solution under lognormal prices.",
    originalMethod: [
      "Model the stock as geometric Brownian motion with constant volatility.",
      "Construct the riskless hedge portfolio and derive the pricing PDE.",
      "Solve for the European call/put closed forms.",
    ],
    quantlabToday: [
      "Not runnable yet — the Options Pricing Engine v1 (pricing, Greeks, simple IV surface) is the planned home for this page's demo.",
    ],
    dataRequirements: ["None for the pricing demo (model-based); options chains only for IV surfaces."],
    limitations: ["Planned — page will activate with the Options Engine phase."],
    reference:
      "Black, F., & Scholes, M. (1973). The Pricing of Options and Corporate Liabilities. Journal of Political Economy, 81(3).",
  },
  {
    id: "black_litterman_1992",
    slug: "black-litterman-1992",
    title: "Global Portfolio Optimization",
    authors: "Black & Litterman",
    year: 1992,
    category: "Portfolio & Risk · Allocation",
    status: "planned",
    replicationLevel: "planned",
    difficulty: "advanced",
    relatedStrategyIds: [],
    summary:
      "Blends market-equilibrium returns with investor views to produce stable, intuitive optimal portfolios.",
    researchQuestion:
      "How can mean-variance optimization be made usable when expected-return inputs are noisy and unstable?",
    coreIdea:
      "Start from equilibrium (reverse-optimized) returns and update them with explicit, confidence-weighted views in a Bayesian blend.",
    originalMethod: [
      "Reverse-optimize equilibrium expected returns from market-cap weights.",
      "Express investor views as linear constraints with uncertainty.",
      "Blend via Bayesian updating; feed the posterior into mean-variance optimization.",
    ],
    quantlabToday: [
      "Not runnable yet: QuantLab's Portfolio Lab does historical mean-variance and risk-parity-style studies, not equilibrium/view blending.",
    ],
    dataRequirements: ["Market-cap weights, covariance estimates, and a view-specification interface."],
    limitations: ["Planned — a natural Portfolio Studio extension."],
    reference:
      "Black, F., & Litterman, R. (1992). Global Portfolio Optimization. Financial Analysts Journal, 48(5).",
  },
];

export const LIVE_PAPERS = PAPER_REGISTRY.filter((p) => p.status === "live");
export const PLANNED_PAPERS = PAPER_REGISTRY.filter((p) => p.status !== "live");

export function findPaperBySlug(slug: string): PaperEntry | undefined {
  return PAPER_REGISTRY.find((p) => p.slug === slug);
}

/** Papers related to a Strategy Library model id (for Related Papers links). */
export function papersForStrategy(strategyRegistryId: string): PaperEntry[] {
  return PAPER_REGISTRY.filter((p) => p.relatedStrategyIds.includes(strategyRegistryId));
}
