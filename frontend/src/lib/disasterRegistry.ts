/**
 * Quant Disasters Series registry (v1).
 *
 * Single source of truth for the risk-education case studies: what happened,
 * why it matters for systematic research, what a naive backtest would miss,
 * and which QuantLab tools help — or honestly cannot help yet.
 *
 * Content rules:
 * * Neutral, educational tone — no legal accusations; legally sensitive cases
 *   use "reports and court proceedings described/alleged …" phrasing.
 * * Simplified educational summaries, never full forensic investigations
 *   (every page carries that caveat).
 * * No invented precise figures; mechanisms over numbers.
 * * v1 pages are educational only — no runnable scenario simulations exist,
 *   so the registry has no run-preset field at all.
 */

export type DisasterSeverity =
  | "Market Crash"
  | "Fund Blowup"
  | "Liquidity Crisis"
  | "Volatility Shock"
  | "Execution Failure"
  | "Governance / Counterparty Failure";

export interface TrustChecklistItem {
  tool: string;
  /** What the tool can (or cannot) tell you about this failure mode. */
  note: string;
  /** False = honestly not available in QuantLab yet. */
  available: boolean;
}

export interface DisasterEntry {
  id: string;
  slug: string;
  title: string;
  year: number;
  severity: DisasterSeverity;
  category: string;
  status: "live" | "planned";
  shortDescription: string;
  failureModes: string[];
  relatedConcepts: string[];
  /** Strategy-registry ids for Related Disasters links on model pages. */
  relatedStrategyIds: string[];
  /** Paper-registry slugs for Related Disasters links on paper pages. */
  relatedPaperSlugs: string[];
  overview: string;
  whyItMatters: string;
  simplifiedMechanism: string;
  naiveBacktestMisses: string[];
  trustChecklist: TrustChecklistItem[];
  cannotModelYet: string[];
  lessons: string[];
}

export const DISASTER_REGISTRY: DisasterEntry[] = [
  {
    id: "ltcm_1998",
    slug: "ltcm-1998",
    title: "Long-Term Capital Management",
    year: 1998,
    severity: "Fund Blowup",
    category: "Leverage · Convergence Trades · Liquidity",
    status: "live",
    shortDescription:
      "A fund with elite pedigree and years of smooth returns lost most of its capital in weeks when levered convergence trades widened together.",
    failureModes: [
      "Leverage",
      "Crowded trades",
      "Liquidity evaporation",
      "Correlation breakdown",
      "Forced deleveraging",
      "Model risk",
    ],
    relatedConcepts: [
      "Tail risk",
      "Position sizing",
      "Stress testing",
      "Sharpe ratio limits",
    ],
    relatedStrategyIds: ["pairs"],
    relatedPaperSlugs: ["gatev-goetzmann-rouwenhorst-2006-pairs"],
    overview:
      "LTCM ran relative-value convergence trades — long the cheaper of two closely related instruments, short the richer — at very high leverage. After Russia's 1998 default, spreads that 'always converged' widened sharply across many of its trades at once. Losses and margin calls forced selling into illiquid markets, and a consortium of banks coordinated a recapitalization to wind positions down.",
    whyItMatters:
      "It is the canonical case of a high-Sharpe, low-volatility track record concealing tail risk. Many QuantLab-style diagnostics (historical Sharpe, drawdown, even bootstrap resampling of past returns) would have looked excellent right up to the failure, because the failure mode — levered, crowded positions meeting a liquidity shock — was barely present in the historical sample.",
    simplifiedMechanism:
      "Convergence trades earn small expected profits with occasional large adverse moves. Leverage scales both. When a shock pushes spreads wider, mark-to-market losses trigger margin calls; selling to meet them widens spreads further (others hold the same trades), turning temporary divergence into realized loss. Historical correlations between 'independent' trades break down because the common factor is the holders, not the assets.",
    naiveBacktestMisses: [
      "Financing and margin: the backtest assumes positions can be held through drawdowns.",
      "Liquidity and market impact when exiting size under stress.",
      "Crowding — who else holds the trade and must sell when you do.",
      "Correlation breakdown between strategies that look independent in calm samples.",
      "The difference between mark-to-market loss and permanent loss only matters if you can survive the mark.",
    ],
    trustChecklist: [
      { tool: "Benchmark comparison", note: "Shows relative performance, not survival risk — necessary, not sufficient.", available: true },
      { tool: "Robustness Lab (bootstrap)", note: "Resamples observed history; a liquidity crisis absent from the sample cannot appear in the bootstrap.", available: true },
      { tool: "Stability Lab", note: "Parameter plateaus say nothing about leverage and funding fragility.", available: true },
      { tool: "Portfolio stress testing", note: "Historical crisis-window stress on portfolios is a partial, useful check.", available: true },
      { tool: "Scenario analysis (forward-looking shocks)", note: "Planned — spread-widening and funding-shock scenarios are future work.", available: false },
    ],
    cannotModelYet: [
      "Margin calls and forced liquidation paths",
      "Financing/borrow costs and funding withdrawal",
      "Crowding and who-else-holds-this risk",
      "Counterparty behaviour under stress",
    ],
    lessons: [
      "A smooth historical Sharpe is not evidence of small tail risk — it can be the signature of selling insurance.",
      "Position sizing must consider survival under widening, not just return scaling.",
      "Diversification measured in calm regimes can vanish exactly when needed.",
      "Liquidity is a position size relative to the market, not a property of the asset alone.",
    ],
  },
  {
    id: "portfolio_insurance_1987",
    slug: "portfolio-insurance-1987",
    title: "Portfolio Insurance & the 1987 Crash",
    year: 1987,
    severity: "Market Crash",
    category: "Dynamic Hedging · Feedback Loops · Market Impact",
    status: "live",
    shortDescription:
      "Mechanical 'sell as the market falls' hedging rules, followed by many participants at once, helped amplify the largest one-day US equity decline.",
    failureModes: [
      "Feedback loops",
      "Market impact",
      "Crowded mechanical rules",
      "Gap risk",
      "Execution assumptions",
    ],
    relatedConcepts: [
      "Risk-exit behaviour under gaps",
      "Execution modelling",
      "Systemic effects of common rules",
    ],
    relatedStrategyIds: ["sma_crossover", "momentum"],
    relatedPaperSlugs: ["moskowitz-ooi-pedersen-2012-tsmom"],
    overview:
      "Portfolio insurance replicated a protective put by selling index futures as the market fell and buying as it rose. Individually the rule is coherent; in October 1987, with a large share of institutional money following similar rules, the required selling into a falling market overwhelmed liquidity and contributed to a ~20% one-day drop, far beyond what continuous-market models assumed.",
    whyItMatters:
      "Trend-following exits, stop losses, vol-targeting de-risking, and QuantLab's own risk-management rules are all 'sell after declines' mechanics at heart. The case shows that a rule that backtests cleanly when your trades don't move the market can behave very differently when many participants run the same rule.",
    simplifiedMechanism:
      "Delta-replication requires selling more as prices fall. If aggregate replication flow is large relative to market depth, selling moves prices down, which triggers more required selling — a feedback loop. Continuous-price assumptions also fail: markets gap, so 'sell at the trigger level' becomes 'sell well below it'.",
    naiveBacktestMisses: [
      "Market impact of your own (and your crowd's) trading.",
      "Gaps: daily-close backtests execute at the close, not at the stop level.",
      "Liquidity that thins precisely when the rule demands the most trading.",
      "The systemic difference between one follower of a rule and a market full of them.",
    ],
    trustChecklist: [
      { tool: "Risk Management engine caveats", note: "QuantLab already labels risk exits as daily-close approximations that may differ from intraday stops — this case is why.", available: true },
      { tool: "Cost model", note: "Flat bps cannot represent impact that grows with stress; treat crash-period results with extra scepticism.", available: true },
      { tool: "Robustness Lab", note: "Resampling history that contains 1987-style days helps; resampling calm samples does not.", available: true },
      { tool: "Market-impact / crowding modelling", note: "Planned — size- and stress-dependent impact is future work.", available: false },
    ],
    cannotModelYet: [
      "Price impact of the strategy's own orders",
      "Intraday gap execution of stops",
      "Crowding of identical mechanical rules across the market",
    ],
    lessons: [
      "Ask what happens if everyone runs your rule — exits are most expensive when shared.",
      "Stops and dynamic hedges have gap risk; backtested exit prices are optimistic under stress.",
      "Strategy risk and systemic risk are different layers; a backtest only sees the first.",
    ],
  },
  {
    id: "flash_crash_2010",
    slug: "flash-crash-2010",
    title: "The Flash Crash",
    year: 2010,
    severity: "Liquidity Crisis",
    category: "Microstructure · Liquidity · Automated Execution",
    status: "live",
    shortDescription:
      "US equities dropped and mostly recovered within minutes as order-book liquidity evaporated and automated flows interacted violently.",
    failureModes: [
      "Liquidity evaporation",
      "Execution risk",
      "Order-book fragility",
      "Automated feedback",
      "Stale quotes / broken prints",
    ],
    relatedConcepts: [
      "Market microstructure",
      "Intraday vs daily data",
      "Data quality",
    ],
    relatedStrategyIds: ["volatility_breakout"],
    relatedPaperSlugs: ["avellaneda-stoikov-2008-market-making"],
    overview:
      "On 6 May 2010, US index futures and equities fell several percent in minutes — some single names printed at pennies or at extreme highs — before largely recovering. Official analysis described a large automated sell program interacting with high-frequency liquidity that withdrew as inventories and volatility spiked, leaving the book nearly empty.",
    whyItMatters:
      "Daily-bar research treats 'the close' as a price you could trade at. The flash crash shows that intraday liquidity is a fragile, dynamic quantity: quotes are not commitments, and depth can vanish in seconds. Any strategy with intraday triggers, market orders, or stop-losses inherits this risk invisibly in a daily backtest.",
    simplifiedMechanism:
      "Market makers quote both sides expecting balanced flow. A large one-sided flow fills their inventory limits; they widen or pull quotes. Remaining orders walk an empty book, printing extreme prices, which triggers more automated reactions (stops, hedges, withdrawal) — until pauses and bargain hunters restore two-sided flow.",
    naiveBacktestMisses: [
      "Order-book depth — daily bars contain no information about it.",
      "Stop orders executing at catastrophic prints rather than trigger levels.",
      "Quote withdrawal: displayed liquidity is not guaranteed liquidity.",
      "Broken/cancelled trades and data anomalies around the event.",
    ],
    trustChecklist: [
      { tool: "Data Quality Diagnostics", note: "Flags gaps and anomalies in daily data, but intraday fragility is invisible at daily frequency.", available: true },
      { tool: "Risk Management caveats", note: "QuantLab explicitly labels stops as daily-close simplifications — this event is the extreme counterexample.", available: true },
      { tool: "Microstructure & HFT Lab (synthetic LOB simulations)", note: "Future module — the honest home for studying this mechanism.", available: false },
    ],
    cannotModelYet: [
      "Order-book dynamics and quote withdrawal",
      "Intraday execution paths and stop cascades",
      "Venue fragmentation and broken prints",
    ],
    lessons: [
      "Displayed liquidity is conditional; assume less is available exactly when you need it.",
      "Intraday triggers carry risks a daily backtest cannot see, even in principle.",
      "Execution is a strategy component, not an afterthought.",
    ],
  },
  {
    id: "volmageddon_2018",
    slug: "volmageddon-2018",
    title: "Volmageddon (XIV)",
    year: 2018,
    severity: "Volatility Shock",
    category: "Short Volatility · Path Dependency · Product Structure",
    status: "live",
    shortDescription:
      "Years of steady gains from short-volatility products ended in one evening when a VIX spike forced rebalancing that destroyed a flagship product.",
    failureModes: [
      "Short-vol tail risk",
      "Path dependency",
      "Product structure / rebalancing",
      "Reflexive feedback",
      "Leverage embedded in products",
    ],
    relatedConcepts: [
      "Volatility regimes",
      "Tail risk vs smooth returns",
      "Robustness limits",
    ],
    relatedStrategyIds: ["volatility_breakout"],
    relatedPaperSlugs: ["black-scholes-1973-options"],
    overview:
      "Inverse-VIX exchange-traded products earned smooth returns for years by being short volatility futures. On 5 February 2018, a sharp VIX move forced these products to buy enormous amounts of VIX futures into the spike (their daily rebalancing requirement), pushing volatility higher still. One major product lost most of its value after hours and was terminated under its prospectus provisions.",
    whyItMatters:
      "It is the cleanest modern example of a return stream that looks like alpha and is structurally short tail risk. Multi-year backtests of short-vol carried Sharpe ratios that bootstrap resampling would have flattered — because the sample barely contained the regime that ends the strategy.",
    simplifiedMechanism:
      "An inverse product on volatility must trade in the direction of the move at the close to maintain its exposure: when volatility doubles, it must buy roughly its entire notional in vol futures. Known, rule-based flows of that size become reflexive — the rebalancing demand itself drives the underlying further, in the worst direction for the product.",
    naiveBacktestMisses: [
      "Path dependency: daily-rebalanced inverse/levered products compound differently from the index they track.",
      "The reflexive impact of the product's own forced rebalancing flows.",
      "Termination clauses and product mechanics that realize losses permanently.",
      "Regime shifts: a sample dominated by calm vol regimes understates the tail.",
    ],
    trustChecklist: [
      { tool: "Robustness Lab", note: "Explicitly warned territory: bootstrapping calm history cannot manufacture an absent vol regime — do not read it as tail-proof.", available: true },
      { tool: "Annualization & data quality", note: "Help compare vol regimes across samples honestly.", available: true },
      { tool: "Portfolio stress testing", note: "Historical crisis windows give partial insight for portfolios.", available: true },
      { tool: "Volatility Lab / scenario shocks", note: "Planned — vol-regime and shock scenarios are future modules.", available: false },
    ],
    cannotModelYet: [
      "Volatility-product structure (daily-rebalance path dependency, termination events)",
      "Reflexive flows from known rule-based rebalancing",
      "Forward-looking volatility shock scenarios",
    ],
    lessons: [
      "Smooth multi-year P&L can be the premium from selling tail insurance, not skill.",
      "Bootstrap and historical diagnostics inherit the regimes of their sample.",
      "Product mechanics (rebalancing, termination) can dominate the underlying signal.",
    ],
  },
  {
    id: "archegos_2021",
    slug: "archegos-2021",
    title: "Archegos",
    year: 2021,
    severity: "Execution Failure",
    category: "Hidden Leverage · Concentration · Forced Liquidation",
    status: "live",
    shortDescription:
      "A family office's concentrated, swap-financed positions unwound in days as prime brokers liquidated collateral, inflicting billions in losses on counterparties.",
    failureModes: [
      "Hidden leverage",
      "Concentration",
      "Counterparty risk",
      "Forced liquidation",
      "Margin spirals",
    ],
    relatedConcepts: [
      "Position sizing beyond return scaling",
      "Portfolio concentration",
      "Margin and financing",
    ],
    relatedStrategyIds: ["momentum"],
    relatedPaperSlugs: [],
    overview:
      "Archegos Capital Management held very large, concentrated equity exposures via total-return swaps across several prime brokers, so no single counterparty saw the full position. When key holdings fell in March 2021, margin calls could not be met; brokers liquidated the underlying shares into a falling market. Several banks reported multi-billion-dollar losses, and subsequent court proceedings addressed the conduct involved — this page treats the episode purely as a risk-management lesson.",
    whyItMatters:
      "Backtests size positions as fractions of capital and assume the position can always be held or exited at market prices. Archegos illustrates the missing layer: financing. Leverage obtained through derivatives, concentration relative to liquidity, and margin terms determine whether a drawdown is survivable — independent of whether the signal was 'right'.",
    simplifiedMechanism:
      "Swap financing turns price declines into immediate collateral demands. Concentrated positions several times daily volume cannot be exited without large impact. When one broker liquidates, prices fall further, triggering the next broker's margin call — a cascade in which the unwind itself produces the losses.",
    naiveBacktestMisses: [
      "Margin terms and collateral calls — absent from return-only simulations.",
      "Position size relative to average daily volume (exit feasibility).",
      "Counterparty visibility: risk distributed across brokers can hide aggregate leverage.",
      "The reflexive cost of forced unwinds in concentrated names.",
    ],
    trustChecklist: [
      { tool: "Position Sizing engine", note: "Scales exposure (and QuantLab deliberately models no leverage) — but it does not model margin, financing, or exit liquidity.", available: true },
      { tool: "Portfolio risk dashboard / concentration", note: "Portfolio weights and risk contributions give partial concentration insight.", available: true },
      { tool: "Margin / forced-liquidation modelling", note: "Not modelled — explicitly out of scope for the current engines.", available: false },
    ],
    cannotModelYet: [
      "Margin calls, collateral schedules, and liquidation cascades",
      "Derivative-financed (hidden) leverage",
      "Exit liquidity relative to position size",
      "Counterparty default and broker behaviour",
    ],
    lessons: [
      "Survivability is a financing question; returns-only backtests cannot answer it.",
      "Concentration should be measured against liquidity, not just portfolio weight.",
      "Leverage you cannot see (yours or the market's) is still leverage.",
    ],
  },
  {
    id: "ftx_2022",
    slug: "ftx-2022",
    title: "FTX / Alameda",
    year: 2022,
    severity: "Governance / Counterparty Failure",
    category: "Exchange Risk · Custody · Crypto Market Structure",
    status: "live",
    shortDescription:
      "A major crypto exchange collapsed within days of solvency doubts; customer assets were frozen in bankruptcy regardless of any trading strategy's quality.",
    failureModes: [
      "Counterparty / custody risk",
      "Governance failure",
      "Liquidity run",
      "Venue concentration",
      "Non-price risk",
    ],
    relatedConcepts: [
      "Crypto market structure",
      "Execution venue risk",
      "Risks outside the price series",
    ],
    relatedStrategyIds: ["momentum", "volatility_breakout"],
    relatedPaperSlugs: [],
    overview:
      "In November 2022, solvency concerns about FTX and its affiliated trading firm Alameda Research triggered a run on customer withdrawals; the exchange halted withdrawals and filed for bankruptcy within days. Court proceedings subsequently resulted in fraud convictions of senior executives. For research purposes, the essential point is simpler: assets held on the venue were frozen or lost regardless of what strategy they were running.",
    whyItMatters:
      "QuantLab's crypto backtests consume a price series (e.g. BTC-USD) and evaluate strategy logic. The collapse highlighted an entire risk layer that no price-series backtest contains: where assets are custodied, who the counterparty is, and whether the venue itself survives. A perfect strategy on a failed venue still loses.",
    simplifiedMechanism:
      "An exchange operating with rehypothecated or insufficiently segregated customer assets is structurally short a bank run: confidence shocks trigger withdrawals, withdrawals reveal the shortfall, and the venue halts — converting market participants into unsecured creditors. The speed comes from crypto's 24/7, fully digital withdrawal mechanics.",
    naiveBacktestMisses: [
      "Custody: the backtest assumes you hold the asset; on an exchange you hold a claim.",
      "Venue solvency and withdrawal halts.",
      "Governance and segregation of customer assets.",
      "Concentration of activity on a single venue.",
    ],
    trustChecklist: [
      { tool: "Data Quality Diagnostics", note: "Describes the price series (gaps, provider limits) — it cannot describe venue solvency.", available: true },
      { tool: "Crypto annualization & caveats", note: "QuantLab's crypto support is price-series research; docs explicitly exclude exchange/custody risk.", available: true },
      { tool: "Counterparty / venue risk modelling", note: "Out of scope for a backtesting platform — flagged as a permanent caveat rather than a roadmap item.", available: false },
    ],
    cannotModelYet: [
      "Exchange solvency, custody, and withdrawal risk",
      "Counterparty and governance failure",
      "Off-price-series operational risks",
    ],
    lessons: [
      "Strategy risk and venue risk are independent; backtests measure only the first.",
      "In crypto especially, custody arrangements are part of the risk budget.",
      "No diagnostic on a price series can certify the institution behind the price.",
    ],
  },
];

export const LIVE_DISASTERS = DISASTER_REGISTRY.filter((d) => d.status === "live");

export function findDisasterBySlug(slug: string): DisasterEntry | undefined {
  return DISASTER_REGISTRY.find((d) => d.slug === slug);
}

/** Disasters related to a Strategy Library model id. */
export function disastersForStrategy(strategyRegistryId: string): DisasterEntry[] {
  return DISASTER_REGISTRY.filter((d) =>
    d.relatedStrategyIds.includes(strategyRegistryId),
  );
}

/** Disasters related to a Paper Replications slug. */
export function disastersForPaper(paperSlug: string): DisasterEntry[] {
  return DISASTER_REGISTRY.filter((d) => d.relatedPaperSlugs.includes(paperSlug));
}
