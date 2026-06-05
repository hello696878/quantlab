"use client";

/**
 * Small, non-error informational card shown when a backtest generates few or no
 * trades.  This is expected behaviour for long-only strategies (especially
 * trend/breakout ones during downtrends), so the styling is deliberately an
 * info/amber tone — never a red error.
 */

// Single-asset strategies here are long-only and can legitimately sit in cash.
const LONG_ONLY_STRATEGIES = new Set([
  "sma_crossover",
  "rsi_mean_reversion",
  "bollinger_band",
  "momentum",
  "volatility_breakout",
]);

const TREND_STRATEGIES = new Set([
  "sma_crossover",
  "momentum",
  "volatility_breakout",
]);

export default function SignalDiagnostics({
  numTrades,
  strategy,
}: {
  numTrades: number;
  strategy: string;
}) {
  const isLongOnly = LONG_ONLY_STRATEGIES.has(strategy);
  const isTrend = TREND_STRATEGIES.has(strategy);
  const zeroTradeSuggestion =
    strategy === "pairs"
      ? "Try a lower entry z-score, a wider date range, or a different pair."
      : "Try a more responsive preset, or run a Parameter Sweep to explore the parameter space.";
  const lowTradeSuggestion =
    strategy === "pairs"
      ? "Consider a lower entry z-score, a wider date range, or another pair."
      : "Consider a more responsive preset, or validate with the Parameter Sweep, Train/Test, and Walk-Forward research tools.";

  if (numTrades === 0) {
    return (
      <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <span className="mt-0.5 flex-shrink-0 text-amber-500">ⓘ</span>
        <div className="text-sm">
          <p className="font-semibold text-amber-800">
            0 trades generated — the strategy stayed in cash for the whole period.
          </p>
          <p className="mt-0.5 text-amber-700">
            The entry condition was never triggered, or the parameters are too
            strict. {zeroTradeSuggestion}
            {isLongOnly &&
              " This strategy is long-only, so staying flat means it held cash instead of forcing exposure."}
            {isTrend &&
              " Trend strategies may stay flat during downtrends — that is expected behaviour, not an error."}
          </p>
        </div>
      </div>
    );
  }

  if (numTrades < 3) {
    return (
      <div className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <span className="mt-0.5 flex-shrink-0 text-slate-400">ⓘ</span>
        <div className="text-sm">
          <p className="font-semibold text-slate-700">
            Very few trades generated ({numTrades}).
          </p>
          <p className="mt-0.5 text-slate-500">
            {lowTradeSuggestion}
            {isLongOnly &&
              " Long-only strategies can hold cash when conditions are not met."}
            {isTrend &&
              " Long-only trend strategies can stay flat during downtrends."}
          </p>
        </div>
      </div>
    );
  }

  return null;
}
