/**
 * Strategy Library model registry (v1).
 *
 * Single source of truth for the Strategy Library index + detail pages and
 * their Backtest Studio links.  Entries marked `status: "live"` are the
 * strategies actually implemented in the backend today; everything else is
 * explicitly planned/research/future per Master Blueprint v3 and must never
 * grow a "Run backtest" button until it ships.
 *
 * All content is educational research material — hypotheses, assumptions, and
 * failure modes — not trading recommendations.
 */

import type { StrategyType } from "@/lib/types";

export type ModelStatus = "live" | "planned" | "research" | "future";
export type ModelDifficulty = "core" | "advanced" | "frontier";

export interface ModelParamDoc {
  name: string;
  defaultValue: string;
  meaning: string;
  range: string;
  extremes: string;
}

export interface ModelFeatureSupport {
  backtest: boolean;
  benchmark: boolean;
  robustness: boolean;
  sensitivity: boolean;
  longShort: boolean;
}

export interface ModelEntry {
  id: string;
  slug: string;
  name: string;
  category: string;
  status: ModelStatus;
  difficulty: ModelDifficulty;
  description: string;
  /** Live strategies only — the Backtest Studio strategy id. */
  strategyId?: StrategyType;
  defaultTicker?: string;
  supportedFeatures?: ModelFeatureSupport;
  /** Detail-page content (live strategies only). */
  overview?: string;
  hypothesis?: string;
  signalLogic?: string[];
  params?: ModelParamDoc[];
  strengths?: string[];
  failureModes?: string[];
  costNotes?: string;
  interactionNotes?: string;
}

const FULL_SUPPORT: ModelFeatureSupport = {
  backtest: true,
  benchmark: true,
  robustness: true,
  sensitivity: false,
  longShort: false,
};

export const MODEL_REGISTRY: ModelEntry[] = [
  // ── Live strategies ────────────────────────────────────────────────────────
  {
    id: "sma_crossover",
    slug: "sma-crossover",
    name: "SMA Crossover",
    category: "Equities · Trend Following",
    status: "live",
    difficulty: "core",
    strategyId: "sma_crossover",
    defaultTicker: "SPY",
    description:
      "Classic trend filter: hold the asset while a fast moving average is above a slow one.",
    supportedFeatures: { ...FULL_SUPPORT, sensitivity: true, longShort: true },
    overview:
      "Two simple moving averages of price are compared each day. When the fast " +
      "(short-window) average sits above the slow (long-window) average the " +
      "strategy treats the market as being in an up-trend and holds the asset; " +
      "otherwise it steps aside to cash (or goes short in long/short mode).",
    hypothesis:
      "Trend-following assumes price trends persist long enough for moving " +
      "averages to identify directional regimes after their lag — a hypothesis " +
      "about behavioural under-reaction and slow capital flows, not a law.",
    signalLogic: [
      "Compute fast SMA and slow SMA of daily closes (fast window < slow window).",
      "Fast SMA above slow SMA → bullish regime → hold the asset (long).",
      "Fast SMA below slow SMA → bearish regime → cash (long-only) or short (long/short mode).",
      "Signals are shifted one bar: a crossover observed at today's close is traded at that close and earns from tomorrow — no lookahead.",
    ],
    params: [
      {
        name: "fast_window",
        defaultValue: "20",
        meaning: "Days in the fast SMA — how quickly the signal reacts.",
        range: "≈ 5–50",
        extremes: "Very small → whipsaw + cost churn; near slow_window → barely any signal.",
      },
      {
        name: "slow_window",
        defaultValue: "100",
        meaning: "Days in the slow SMA — the regime definition.",
        range: "≈ 50–250",
        extremes: "Very large → long lag, misses regime turns; too small → noise.",
      },
    ],
    strengths: [
      "Simple, transparent, and fully interpretable — a good baseline.",
      "Easy to stress: Stability Lab sweeps the fast×slow grid directly.",
      "Historically captures long multi-month trends with few decisions.",
    ],
    failureModes: [
      "Whipsaw in sideways/choppy markets — repeated small losses plus costs.",
      "Lag at trend reversals: gives back gains before exiting.",
      "Parameter overfitting: one lucky (fast, slow) pair on one period.",
      "Cost drag scales with crossover frequency (worse for fast settings).",
      "Short mode inherits all short-selling simplifications (no borrow costs).",
    ],
    costNotes:
      "Each crossover is a full position change, so transaction costs scale with " +
      "signal frequency. Fast settings can turn a paper edge negative — check " +
      "cost drag in the result and re-run with the conservative cost preset.",
    interactionNotes:
      "Position sizing scales exposure without changing crossover timing. Risk " +
      "rules (stops/trailing) can exit mid-trend and re-enter on the next " +
      "signal — they interact with trend length, so compare with rules off.",
  },
  {
    id: "rsi_mean_reversion",
    slug: "rsi-mean-reversion",
    name: "RSI Mean Reversion",
    category: "Equities · Mean Reversion",
    status: "live",
    difficulty: "core",
    strategyId: "rsi_mean_reversion",
    defaultTicker: "SPY",
    description:
      "Buys short-term oversold dips (low RSI) and exits when the oscillator recovers.",
    supportedFeatures: { ...FULL_SUPPORT },
    overview:
      "The Relative Strength Index (RSI) compresses recent up-versus-down move " +
      "magnitude into a 0–100 oscillator. The strategy buys when RSI drops " +
      "below an oversold threshold and exits when RSI recovers above an exit " +
      "threshold — betting that short-term sell-offs in a liquid asset tend to " +
      "snap back. Long-only by design.",
    hypothesis:
      "Short-horizon mean reversion: after sharp short-term selling, prices of " +
      "broad liquid assets tend to bounce as forced selling and overreaction " +
      "fade. This is regime-dependent — it fails when a dip is the start of a " +
      "real downtrend.",
    signalLogic: [
      "Compute RSI over rsi_window days (Wilder-style average gains vs losses).",
      "RSI below oversold_threshold → enter long (the dip).",
      "RSI back above exit_threshold → exit to cash (the bounce).",
      "One-bar signal shift as everywhere — no lookahead.",
    ],
    params: [
      {
        name: "rsi_window",
        defaultValue: "14",
        meaning: "Lookback for the oscillator.",
        range: "≈ 7–28",
        extremes: "Short → hyperactive, noisy entries; long → too smooth, rare signals.",
      },
      {
        name: "oversold_threshold",
        defaultValue: "35",
        meaning: "RSI level treated as oversold (entry).",
        range: "≈ 20–40",
        extremes: "Very low → almost never triggers; high → buys ordinary noise.",
      },
      {
        name: "exit_threshold",
        defaultValue: "55",
        meaning: "RSI level treated as recovered (exit).",
        range: "≈ 45–70",
        extremes: "Too close to entry → tiny trades + cost churn; too high → overstays.",
      },
    ],
    strengths: [
      "Captures a well-known short-horizon behavioural effect on index ETFs.",
      "Spends much of the time in cash — drawdowns are often (not always) shallower.",
      "Three interpretable parameters; easy to reason about threshold changes.",
    ],
    failureModes: [
      "Catching falling knives: buys dips that keep falling in real downtrends.",
      "Long flat stretches — opportunity cost vs buy-and-hold in strong bulls.",
      "Threshold overfitting (entry/exit pairs tuned to one period).",
      "Works differently across assets — trending assets mean-revert less.",
    ],
    costNotes:
      "Trade frequency is moderate; costs matter most when entry and exit " +
      "thresholds are close together (many small round-trips).",
    interactionNotes:
      "Stops interact awkwardly with dip-buying (a stop often sells exactly at " +
      "the oversold extreme); max-holding-days caps how long a failed bounce is " +
      "held. Sizing reduces both the bounce capture and the knife risk.",
  },
  {
    id: "bollinger_band",
    slug: "bollinger-mean-reversion",
    name: "Bollinger Mean Reversion",
    category: "Equities · Mean Reversion",
    status: "live",
    difficulty: "core",
    strategyId: "bollinger_band",
    defaultTicker: "SPY",
    description:
      "Buys statistically stretched prices below the lower Bollinger band; exits at the mean.",
    supportedFeatures: { ...FULL_SUPPORT },
    overview:
      "Bollinger bands wrap a rolling mean with ± k rolling standard deviations. " +
      "The strategy buys when price closes below the lower band — a " +
      "statistically unusual stretch — and exits when price reverts to the " +
      "middle (or upper) band. Long-only by design.",
    hypothesis:
      "Price deviations beyond a volatility-scaled envelope are more often " +
      "overreaction than new information, so they partially revert. The " +
      "assumption breaks precisely when a large move *is* new information.",
    signalLogic: [
      "Rolling mean and rolling σ over bb_window days form the bands: mean ± num_std × σ.",
      "Close below the lower band → enter long.",
      "Close back at the exit band (middle = rolling mean, or upper) → exit to cash.",
      "One-bar signal shift — no lookahead.",
    ],
    params: [
      {
        name: "bb_window",
        defaultValue: "20",
        meaning: "Rolling window for mean and σ.",
        range: "≈ 10–50",
        extremes: "Short → jumpy bands; long → stale bands that lag volatility regimes.",
      },
      {
        name: "num_std",
        defaultValue: "1.8",
        meaning: "Band half-width in standard deviations.",
        range: "≈ 1.5–3",
        extremes: "Small → frequent ordinary-noise entries; large → waits for crashes.",
      },
      {
        name: "exit_band",
        defaultValue: "middle",
        meaning: "Where the reversion trade is closed (middle or upper band).",
        range: "middle / upper",
        extremes: "Upper exit holds for a full swing — bigger wins and bigger giveback.",
      },
    ],
    strengths: [
      "Volatility-aware entries: the threshold adapts to the asset's own σ.",
      "Transparent statistics — easy to explain every trade after the fact.",
      "Pairs naturally with the Stability Lab idea of stressing num_std (planned).",
    ],
    failureModes: [
      "Band breaks in crashes are information, not noise — reversion fails hard.",
      "σ itself spikes after the entry, moving the exit target.",
      "Sideways drift below the band can hold a loser for a long time.",
      "Overfitting the (window, num_std, exit) trio to one calm period.",
    ],
    costNotes:
      "Lower trade frequency than RSI typically; cost drag is usually modest " +
      "but rises sharply if num_std is set small.",
    interactionNotes:
      "A stop-loss below the lower band contradicts the mean-reversion premise " +
      "(it sells deeper stretch); trailing stops fit the exit-at-mean leg " +
      "better. Test with risk rules on and off and compare.",
  },
  {
    id: "momentum",
    slug: "momentum",
    name: "Time-Series Momentum",
    category: "Equities · Momentum",
    status: "live",
    difficulty: "core",
    strategyId: "momentum",
    defaultTicker: "SPY",
    description:
      "Holds the asset when its own trailing return is positive; cash (or short) when negative.",
    supportedFeatures: { ...FULL_SUPPORT, longShort: true },
    overview:
      "Time-series (absolute) momentum looks only at the asset's own trailing " +
      "return over a lookback window. Positive trailing return → hold; " +
      "negative → cash, or short in long/short mode. One of the most studied " +
      "effects in the empirical asset-pricing literature.",
    hypothesis:
      "Past returns contain information about near-future returns — continuation " +
      "driven by gradual information diffusion, flows, and risk-premium " +
      "variation. Documented across centuries and asset classes, with crashes " +
      "concentrated at sharp regime turns.",
    signalLogic: [
      "Compute trailing momentum_window-day return at each close.",
      "Trailing return above entry_threshold → long.",
      "Trailing return below exit_threshold → cash (long-only) or short (long/short).",
      "Thresholds default to 0 (sign-of-return rule); one-bar shift — no lookahead.",
    ],
    params: [
      {
        name: "momentum_window",
        defaultValue: "63",
        meaning: "Trailing-return lookback (≈ 3 months of trading days).",
        range: "≈ 21–252",
        extremes: "Short → noise-chasing; very long → reacts a year late.",
      },
      {
        name: "entry_threshold",
        defaultValue: "0",
        meaning: "Trailing return required to enter.",
        range: "≈ 0–0.05",
        extremes: "High → rare entries; negative thresholds invert the logic.",
      },
      {
        name: "exit_threshold",
        defaultValue: "0",
        meaning: "Trailing return below which the position exits.",
        range: "≈ −0.05–0",
        extremes: "A gap between entry and exit adds hysteresis (fewer flips).",
      },
    ],
    strengths: [
      "Among the most replicated effects in finance — a serious baseline.",
      "Sign-of-return rule has only one real parameter (the window).",
      "Long/short mode lets you study bearish signal quality explicitly.",
    ],
    failureModes: [
      "Momentum crashes: sharp reversals after panics hit just as exposure flips.",
      "Whipsaw around zero trailing return in flat regimes.",
      "Lookback overfitting — 63 works on one asset/period, not universally.",
      "Short side inherits unmodelled borrow/funding costs.",
    ],
    costNotes:
      "Flips between long and short are 2× turnover — long/short mode roughly " +
      "doubles cost sensitivity versus long-only.",
    interactionNotes:
      "Volatility-target sizing pairs naturally with momentum (de-levers in " +
      "high-vol regimes where momentum crashes cluster). Stops add a second " +
      "exit channel that can fight the trailing-return exit.",
  },
  {
    id: "volatility_breakout",
    slug: "volatility-breakout",
    name: "Volatility Breakout",
    category: "Equities · Breakout",
    status: "live",
    difficulty: "core",
    strategyId: "volatility_breakout",
    defaultTicker: "SPY",
    description:
      "Enters when price clears its recent high by a volatility-scaled margin; exits to a rolling mean.",
    supportedFeatures: { ...FULL_SUPPORT, longShort: true },
    overview:
      "The strategy watches the rolling high and the typical daily range. When " +
      "price closes above the recent high by a multiple of that range — a move " +
      "unusually large for the asset's own volatility — it enters, expecting " +
      "follow-through. It exits when price falls back to a short rolling mean.",
    hypothesis:
      "Range expansion after compression marks the start of directional moves: " +
      "breakouts beyond what normal volatility explains are more likely to " +
      "continue than fade. False breakouts are the cost of admission.",
    signalLogic: [
      "Track the lookback_window rolling high and the average true-range-style daily range.",
      "Close above rolling high + breakout_multiplier × range → enter long (short mode mirrors below the rolling low).",
      "Close below the exit_window-day rolling mean → exit.",
      "One-bar shift — no lookahead.",
    ],
    params: [
      {
        name: "lookback_window",
        defaultValue: "20",
        meaning: "Window for the rolling high/low and range estimate.",
        range: "≈ 10–60",
        extremes: "Short → every wiggle is a 'breakout'; long → only rare monster moves.",
      },
      {
        name: "breakout_multiplier",
        defaultValue: "0.3",
        meaning: "How far beyond the high (in range units) price must close.",
        range: "≈ 0.1–1.0",
        extremes: "Tiny → noise entries; large → enters late after the move is spent.",
      },
      {
        name: "exit_window",
        defaultValue: "10",
        meaning: "Rolling-mean window for the exit.",
        range: "≈ 5–30",
        extremes: "Short → quick exits chop trends; long → gives back large gains.",
      },
    ],
    strengths: [
      "Volatility-normalized trigger adapts across calm and wild assets.",
      "Asymmetric by construction: small frequent losses, occasional large runs.",
      "Complements moving-average trend filters (different trigger geometry).",
    ],
    failureModes: [
      "False breakouts dominate in ranging markets — death by a thousand cuts.",
      "Gap entries: the close-based fill may be far above the breakout level.",
      "Three coupled parameters — high overfitting surface.",
      "Cost drag from frequent failed entries at tight multipliers.",
    ],
    costNotes:
      "Failed breakouts are quick round-trips, so costs compound fastest at " +
      "small multipliers and short exits — watch total transaction cost.",
    interactionNotes:
      "Trailing stops fit breakout logic well (ride the run, cap the give-back). " +
      "Fixed take-profits tend to amputate the rare big runs the strategy needs.",
  },
  {
    id: "pairs",
    slug: "pairs-trading",
    name: "Pairs Trading (Spread Mean Reversion)",
    category: "Event-Driven & Arbitrage · Statistical Arbitrage",
    status: "live",
    difficulty: "advanced",
    strategyId: "pairs",
    defaultTicker: "KO / PEP",
    description:
      "Trades the z-scored spread between two related assets — long the cheap leg, short the rich leg.",
    supportedFeatures: {
      backtest: true,
      benchmark: false,
      robustness: false,
      sensitivity: false,
      longShort: true,
    },
    overview:
      "Two economically linked assets (e.g. KO and PEP) are combined into a " +
      "log-price spread. When the spread's z-score stretches beyond a " +
      "threshold, the strategy goes long the underpriced leg and short the " +
      "overpriced leg — dollar-neutral — and exits when the spread normalizes.",
    hypothesis:
      "If two assets share fundamentals, their price ratio is mean-reverting " +
      "(approximately cointegrated): divergences reflect temporary flows, not " +
      "permanent repricing. The hypothesis dies when the economic link breaks.",
    signalLogic: [
      "Compute the rolling z-score of the log-price spread between asset Y and asset X.",
      "z above +entry threshold → short the spread (short Y, long X); below −entry → long the spread.",
      "|z| back under the exit threshold → close both legs.",
      "Dollar-neutral two-leg construction; one-bar shift — no lookahead.",
    ],
    params: [
      {
        name: "lookback_window",
        defaultValue: "60",
        meaning: "Rolling window for the spread mean and σ.",
        range: "≈ 30–120",
        extremes: "Short → z-score chases itself; long → stale relationship estimate.",
      },
      {
        name: "entry_z_score",
        defaultValue: "2.0",
        meaning: "Spread stretch required to open the trade.",
        range: "≈ 1.5–3",
        extremes: "Low → trades ordinary noise; high → waits for relationship breaks.",
      },
      {
        name: "exit_z_score",
        defaultValue: "0.5",
        meaning: "Normalization level at which the trade closes.",
        range: "≈ 0–1",
        extremes: "0 targets full reversion (longer holds); near entry → churn.",
      },
    ],
    strengths: [
      "Roughly market-neutral: profits depend on the spread, not direction.",
      "Statistically explicit — every input of the z-score is inspectable.",
      "A gateway to serious stat-arb concepts (cointegration, hedge ratios).",
    ],
    failureModes: [
      "Relationship breakdown: divergence that never reverts (the classic killer).",
      "Short-leg simplifications — borrow, funding, and margin are not modelled.",
      "z-score parameters overfit calm co-movement periods.",
      "Spread can widen far beyond entry before reverting — deep interim drawdowns.",
    ],
    costNotes:
      "Every round-trip touches two legs (double turnover), so per-side costs " +
      "bite twice. Tight exit thresholds multiply round-trips.",
    interactionNotes:
      "v1 runs pairs with full allocation and signal-based exits only — the " +
      "cost model / sizing / risk / benchmark / robustness engines apply to " +
      "single-asset strategies. Trust-layer coverage for pairs is planned.",
  },

  // ── Planned / research / future (Blueprint v3 — NOT implemented) ───────────
  {
    id: "cross_sectional_reversal",
    slug: "cross-sectional-reversal",
    name: "Cross-Sectional Linear Long-Short Reversion",
    category: "Equities · Mean Reversion",
    status: "planned",
    difficulty: "advanced",
    description:
      "Rank a universe by negative demeaned recent return; long the laggards, short the leaders, " +
      "dollar-neutral. Demonstrable now in the Cross-Sectional Scanner Lab on a synthetic universe " +
      "(scanner-compatible); a full live-universe version remains planned.",
  },
  {
    id: "cross_sectional_momentum",
    slug: "cross-sectional-momentum",
    name: "Cross-Sectional Momentum",
    category: "Equities · Momentum",
    status: "planned",
    difficulty: "advanced",
    description:
      "Rank a universe by trailing return; hold winners against losers. Demonstrable now in the " +
      "Cross-Sectional Scanner Lab on a synthetic universe (scanner-compatible); a full live-universe " +
      "version remains planned.",
  },
  {
    id: "fama_french_factors",
    slug: "fama-french-factors",
    name: "Fama–French Factor Model",
    category: "Portfolio & Risk · Factor Models",
    status: "planned",
    difficulty: "advanced",
    description:
      "Size/value/market factor regressions for return attribution and factor-tilt studies.",
  },
  {
    id: "kalman_hedge_ratio",
    slug: "kalman-hedge-ratio",
    name: "Kalman-Filter Hedge Ratio (Pairs v2)",
    category: "Event-Driven & Arbitrage · Statistical Arbitrage",
    status: "research",
    difficulty: "advanced",
    description:
      "Time-varying hedge ratio for pairs spreads via state-space filtering instead of a fixed window.",
  },
  {
    id: "hmm_regime",
    slug: "hmm-regime-detection",
    name: "HMM Regime Detection",
    category: "Machine Learning & AI · Regime Models",
    status: "research",
    difficulty: "frontier",
    description:
      "Hidden Markov Models classifying volatility/trend regimes to gate other strategies.",
  },
  {
    id: "black_scholes",
    slug: "black-scholes-options",
    name: "Black–Scholes Options Engine",
    category: "Options & Volatility",
    status: "planned",
    difficulty: "advanced",
    description:
      "European option pricing, Greeks, and a simple IV surface — educational pricing engine first.",
  },
  {
    id: "orderbook_imbalance",
    slug: "order-book-imbalance",
    name: "Order-Book Imbalance (HFT Lab)",
    category: "Market Microstructure & HFT",
    status: "future",
    difficulty: "frontier",
    description:
      "Educational microstructure simulations on synthetic data — never live HFT execution.",
  },
];

export const LIVE_MODELS = MODEL_REGISTRY.filter((m) => m.status === "live");
export const PLANNED_MODELS = MODEL_REGISTRY.filter((m) => m.status !== "live");

export function findModelBySlug(slug: string): ModelEntry | undefined {
  return MODEL_REGISTRY.find((m) => m.slug === slug);
}
