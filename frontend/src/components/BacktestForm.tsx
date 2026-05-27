"use client";

import type {
  BacktestRequest,
  BbBacktestRequest,
  MomentumBacktestRequest,
  PairsBacktestRequest,
  RsiBacktestRequest,
  StrategyType,
  VbBacktestRequest,
} from "@/lib/types";

// Quick-pick tickers (single-asset strategies only)
const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "GLD", "BTC-USD"];

// Quick-pick pairs (pairs strategy)
const POPULAR_PAIRS: { y: string; x: string }[] = [
  { y: "KO", x: "PEP" },
  { y: "C", x: "JPM" },
  { y: "GS", x: "MS" },
  { y: "XOM", x: "CVX" },
];

interface Props {
  strategy: StrategyType;
  onStrategyChange: (s: StrategyType) => void;
  smaParams: BacktestRequest;
  onSmaParamsChange: (p: BacktestRequest) => void;
  rsiParams: RsiBacktestRequest;
  onRsiParamsChange: (p: RsiBacktestRequest) => void;
  bbParams: BbBacktestRequest;
  onBbParamsChange: (p: BbBacktestRequest) => void;
  momentumParams: MomentumBacktestRequest;
  onMomentumParamsChange: (p: MomentumBacktestRequest) => void;
  vbParams: VbBacktestRequest;
  onVbParamsChange: (p: VbBacktestRequest) => void;
  pairsParams: PairsBacktestRequest;
  onPairsParamsChange: (p: PairsBacktestRequest) => void;
  onSubmit: () => void;
  loading: boolean;
}

// ---------------------------------------------------------------------------
// Small reusable pieces
// ---------------------------------------------------------------------------

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">
        {label}
        {hint && (
          <span className="ml-1 normal-case font-normal text-slate-400">{hint}</span>
        )}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

// ---------------------------------------------------------------------------
// Strategy tab definitions
// ---------------------------------------------------------------------------

const STRATEGIES: { id: StrategyType; label: string; description: string }[] = [
  {
    id: "sma_crossover",
    label: "SMA Crossover",
    description: "Long when fast SMA > slow SMA. Classic trend-following approach.",
  },
  {
    id: "rsi_mean_reversion",
    label: "RSI Mean Reversion",
    description:
      "Long when RSI drops below an oversold level; exits when RSI recovers.",
  },
  {
    id: "bollinger_band",
    label: "Bollinger Bands",
    description:
      "Long when price breaks below the lower band; exits at middle or upper band.",
  },
  {
    id: "momentum",
    label: "Momentum",
    description:
      "Long when the trailing N-day return exceeds an entry threshold; hysteresis optional.",
  },
  {
    id: "volatility_breakout",
    label: "Vol Breakout",
    description:
      "Enters above the prior range breakout level; exits below the rolling mean.",
  },
  {
    id: "pairs",
    label: "Pairs Trading",
    description:
      "Dollar-neutral: long Y / short X when spread z-score diverges; exits on reversion.",
  },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function BacktestForm({
  strategy,
  onStrategyChange,
  smaParams,
  onSmaParamsChange,
  rsiParams,
  onRsiParamsChange,
  bbParams,
  onBbParamsChange,
  momentumParams,
  onMomentumParamsChange,
  vbParams,
  onVbParamsChange,
  pairsParams,
  onPairsParamsChange,
  onSubmit,
  loading,
}: Props) {
  // Active single-asset params used for the common fields section.
  // For the pairs strategy we fall back to vbParams because both share the same
  // common field keys (start_date, end_date, cost, capital) and setCommon keeps
  // all params in sync.
  const active =
    strategy === "sma_crossover"
      ? smaParams
      : strategy === "rsi_mean_reversion"
        ? rsiParams
        : strategy === "bollinger_band"
          ? bbParams
          : strategy === "momentum"
            ? momentumParams
            : vbParams; // covers "volatility_breakout" AND "pairs"

  /** Update every strategy's common fields simultaneously so switching strategy
   *  never loses a date or cost setting.  Skips "ticker" for pairs since
   *  PairsBacktestRequest uses asset_y / asset_x instead. */
  function setCommon<K extends keyof typeof active>(
    key: K,
    value: (typeof active)[K],
  ) {
    onSmaParamsChange({ ...smaParams, [key]: value } as BacktestRequest);
    onRsiParamsChange({ ...rsiParams, [key]: value } as RsiBacktestRequest);
    onBbParamsChange({ ...bbParams, [key]: value } as BbBacktestRequest);
    onMomentumParamsChange({
      ...momentumParams,
      [key]: value,
    } as MomentumBacktestRequest);
    onVbParamsChange({ ...vbParams, [key]: value } as VbBacktestRequest);
    // Pairs shares start_date / end_date / cost / capital but NOT ticker.
    if (key !== "ticker") {
      onPairsParamsChange({
        ...pairsParams,
        [key]: value,
      } as PairsBacktestRequest);
    }
  }

  function setSma<K extends keyof BacktestRequest>(
    key: K,
    value: BacktestRequest[K],
  ) {
    onSmaParamsChange({ ...smaParams, [key]: value });
  }

  function setRsi<K extends keyof RsiBacktestRequest>(
    key: K,
    value: RsiBacktestRequest[K],
  ) {
    onRsiParamsChange({ ...rsiParams, [key]: value });
  }

  function setBb<K extends keyof BbBacktestRequest>(
    key: K,
    value: BbBacktestRequest[K],
  ) {
    onBbParamsChange({ ...bbParams, [key]: value });
  }

  function setMomentum<K extends keyof MomentumBacktestRequest>(
    key: K,
    value: MomentumBacktestRequest[K],
  ) {
    onMomentumParamsChange({ ...momentumParams, [key]: value });
  }

  function setVb<K extends keyof VbBacktestRequest>(
    key: K,
    value: VbBacktestRequest[K],
  ) {
    onVbParamsChange({ ...vbParams, [key]: value });
  }

  function setPairs<K extends keyof PairsBacktestRequest>(
    key: K,
    value: PairsBacktestRequest[K],
  ) {
    onPairsParamsChange({ ...pairsParams, [key]: value });
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------
  const dateInvalid = active.start_date >= active.end_date;
  const smaInvalid =
    strategy === "sma_crossover" &&
    smaParams.fast_window >= smaParams.slow_window;
  const rsiInvalid =
    strategy === "rsi_mean_reversion" &&
    rsiParams.oversold_threshold >= rsiParams.exit_threshold;
  const bbInvalid =
    strategy === "bollinger_band" &&
    (bbParams.bb_window < 2 || bbParams.num_std <= 0);
  const momentumInvalid =
    strategy === "momentum" &&
    (momentumParams.momentum_window < 1 ||
      momentumParams.entry_threshold < -1 ||
      momentumParams.entry_threshold > 1 ||
      momentumParams.exit_threshold < -1 ||
      momentumParams.exit_threshold > 1 ||
      momentumParams.entry_threshold < momentumParams.exit_threshold);
  const vbInvalid =
    strategy === "volatility_breakout" &&
    (vbParams.lookback_window < 2 ||
      vbParams.breakout_multiplier <= 0 ||
      vbParams.exit_window < 1);
  const pairsInvalid =
    strategy === "pairs" &&
    (pairsParams.lookback_window < 10 ||
      pairsParams.entry_z_score <= pairsParams.exit_z_score ||
      pairsParams.exit_z_score < 0 ||
      pairsParams.asset_y.trim().toUpperCase() ===
        pairsParams.asset_x.trim().toUpperCase());

  const tickerOk =
    strategy === "pairs"
      ? pairsParams.asset_y.trim().length > 0 &&
        pairsParams.asset_x.trim().length > 0
      : active.ticker.trim().length > 0;

  const canSubmit =
    !loading &&
    tickerOk &&
    !dateInvalid &&
    !smaInvalid &&
    !rsiInvalid &&
    !bbInvalid &&
    !momentumInvalid &&
    !vbInvalid &&
    !pairsInvalid;

  return (
    <div className="card overflow-hidden">
      {/* ── Strategy tab bar ─────────────────────────────────────────── */}
      <div className="flex border-b border-slate-200 bg-slate-50">
        {STRATEGIES.map((s) => (
          <button
            key={s.id}
            type="button"
            disabled={loading}
            onClick={() => onStrategyChange(s.id)}
            className={
              "flex-1 px-5 py-3.5 text-sm font-medium transition-colors " +
              "focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 " +
              (strategy === s.id
                ? "bg-white text-blue-700 border-b-2 border-blue-600 shadow-sm"
                : "text-slate-500 hover:text-slate-800 hover:bg-white/60")
            }
          >
            <span className="block">{s.label}</span>
            <span className="hidden sm:block text-xs font-normal text-slate-400 mt-0.5 leading-tight">
              {s.description}
            </span>
          </button>
        ))}
      </div>

      <div className="p-6">
        {/* ── Ticker (single-asset strategies only) ────────────────────── */}
        {strategy !== "pairs" && (
          <div className="mb-5">
            <Field label="Ticker symbol">
              <div className="flex gap-2 flex-wrap">
                <input
                  type="text"
                  className={`${inputCls} w-32 uppercase`}
                  value={active.ticker}
                  onChange={(e) => setCommon("ticker", e.target.value.toUpperCase())}
                  placeholder="SPY"
                  disabled={loading}
                  maxLength={12}
                />
                <div className="flex gap-1 flex-wrap">
                  {POPULAR_TICKERS.map((t) => (
                    <button
                      key={t}
                      type="button"
                      disabled={loading}
                      onClick={() => setCommon("ticker", t)}
                      className={
                        "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                        (active.ticker === t
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
                      }
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </Field>
          </div>
        )}

        {/* ── Common fields ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
          <Field label="Start date">
            <input
              type="date"
              className={inputCls}
              value={active.start_date}
              onChange={(e) => setCommon("start_date", e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="End date">
            <input
              type="date"
              className={inputCls}
              value={active.end_date}
              onChange={(e) => setCommon("end_date", e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={active.transaction_cost_bps}
              min={0}
              max={200}
              step={1}
              onChange={(e) =>
                setCommon("transaction_cost_bps", parseFloat(e.target.value) || 0)
              }
              disabled={loading}
            />
          </Field>
          <Field label="Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={active.initial_capital}
              min={1}
              step={1000}
              onChange={(e) =>
                setCommon("initial_capital", parseFloat(e.target.value) || 100_000)
              }
              disabled={loading}
            />
          </Field>
        </div>

        {/* ── Strategy-specific fields ───────────────────────────────────── */}
        <div className="mb-5 p-4 rounded-lg bg-blue-50/60 border border-blue-100">
          {strategy === "sma_crossover" ? (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Fast SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaParams.fast_window}
                  min={2}
                  max={smaParams.slow_window - 1}
                  step={1}
                  onChange={(e) =>
                    setSma("fast_window", parseInt(e.target.value, 10) || 2)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Slow SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaParams.slow_window}
                  min={smaParams.fast_window + 1}
                  step={1}
                  onChange={(e) =>
                    setSma("slow_window", parseInt(e.target.value, 10) || 2)
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "rsi_mean_reversion" ? (
            <div className="grid grid-cols-3 gap-4">
              <Field label="RSI window" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.rsi_window}
                  min={2}
                  max={100}
                  step={1}
                  onChange={(e) =>
                    setRsi("rsi_window", parseInt(e.target.value, 10) || 14)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Oversold" hint="enter <">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.oversold_threshold}
                  min={1}
                  max={rsiParams.exit_threshold - 1}
                  step={1}
                  onChange={(e) =>
                    setRsi("oversold_threshold", parseFloat(e.target.value) || 30)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Exit" hint="exit ≥">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.exit_threshold}
                  min={rsiParams.oversold_threshold + 1}
                  max={100}
                  step={1}
                  onChange={(e) =>
                    setRsi("exit_threshold", parseFloat(e.target.value) || 50)
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "bollinger_band" ? (
            <div className="grid grid-cols-3 gap-4">
              <Field label="BB Window" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={bbParams.bb_window}
                  min={2}
                  max={500}
                  step={1}
                  onChange={(e) =>
                    setBb("bb_window", parseInt(e.target.value, 10) || 20)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Std Dev" hint="σ">
                <input
                  type="number"
                  className={inputCls}
                  value={bbParams.num_std}
                  min={0.1}
                  max={10}
                  step={0.1}
                  onChange={(e) =>
                    setBb("num_std", parseFloat(e.target.value) || 2.0)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Exit band">
                <select
                  className={inputCls}
                  value={bbParams.exit_band}
                  onChange={(e) =>
                    setBb("exit_band", e.target.value as "middle" | "upper")
                  }
                  disabled={loading}
                >
                  <option value="middle">Middle (SMA)</option>
                  <option value="upper">Upper band</option>
                </select>
              </Field>
            </div>
          ) : strategy === "momentum" ? (
            <div className="grid grid-cols-3 gap-4">
              <Field label="Lookback" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={momentumParams.momentum_window}
                  min={1}
                  max={1000}
                  step={1}
                  onChange={(e) =>
                    setMomentum(
                      "momentum_window",
                      parseInt(e.target.value, 10) || 126,
                    )
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Entry threshold" hint="decimal">
                <input
                  type="number"
                  className={inputCls}
                  value={momentumParams.entry_threshold}
                  min={-1}
                  max={1}
                  step={0.01}
                  onChange={(e) =>
                    setMomentum(
                      "entry_threshold",
                      parseFloat(e.target.value) || 0,
                    )
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Exit threshold" hint="decimal">
                <input
                  type="number"
                  className={inputCls}
                  value={momentumParams.exit_threshold}
                  min={-1}
                  max={1}
                  step={0.01}
                  onChange={(e) =>
                    setMomentum(
                      "exit_threshold",
                      parseFloat(e.target.value) || 0,
                    )
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "volatility_breakout" ? (
            <div className="grid grid-cols-3 gap-4">
              <Field label="Lookback" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={vbParams.lookback_window}
                  min={2}
                  max={500}
                  step={1}
                  onChange={(e) =>
                    setVb("lookback_window", parseInt(e.target.value, 10) || 20)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Multiplier" hint="× range">
                <input
                  type="number"
                  className={inputCls}
                  value={vbParams.breakout_multiplier}
                  min={0.1}
                  max={10}
                  step={0.1}
                  onChange={(e) =>
                    setVb(
                      "breakout_multiplier",
                      parseFloat(e.target.value) || 1.0,
                    )
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Exit mean" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={vbParams.exit_window}
                  min={1}
                  max={500}
                  step={1}
                  onChange={(e) =>
                    setVb("exit_window", parseInt(e.target.value, 10) || 10)
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          ) : (
            /* ── Pairs Trading fields ───────────────────────────────────── */
            <div className="space-y-4">
              {/* Asset inputs + quick-picks */}
              <div className="grid grid-cols-2 gap-4">
                <Field label="Asset Y" hint="long / short leg">
                  <input
                    type="text"
                    className={`${inputCls} uppercase`}
                    value={pairsParams.asset_y}
                    onChange={(e) =>
                      setPairs("asset_y", e.target.value.toUpperCase())
                    }
                    placeholder="KO"
                    disabled={loading}
                    maxLength={12}
                  />
                </Field>
                <Field label="Asset X" hint="short / long leg">
                  <input
                    type="text"
                    className={`${inputCls} uppercase`}
                    value={pairsParams.asset_x}
                    onChange={(e) =>
                      setPairs("asset_x", e.target.value.toUpperCase())
                    }
                    placeholder="PEP"
                    disabled={loading}
                    maxLength={12}
                  />
                </Field>
              </div>
              {/* Popular pair quick-picks */}
              <div className="flex gap-2 flex-wrap">
                {POPULAR_PAIRS.map(({ y, x }) => (
                  <button
                    key={`${y}/${x}`}
                    type="button"
                    disabled={loading}
                    onClick={() =>
                      onPairsParamsChange({ ...pairsParams, asset_y: y, asset_x: x })
                    }
                    className={
                      "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                      (pairsParams.asset_y === y && pairsParams.asset_x === x
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
                    }
                  >
                    {y}/{x}
                  </button>
                ))}
              </div>
              {/* Strategy-specific params */}
              <div className="grid grid-cols-3 gap-4">
                <Field label="Lookback" hint="days">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsParams.lookback_window}
                    min={10}
                    max={500}
                    step={1}
                    onChange={(e) =>
                      setPairs(
                        "lookback_window",
                        parseInt(e.target.value, 10) || 60,
                      )
                    }
                    disabled={loading}
                  />
                </Field>
                <Field label="Entry Z-Score" hint="|z| ≥ enter">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsParams.entry_z_score}
                    min={0.1}
                    max={5}
                    step={0.1}
                    onChange={(e) =>
                      setPairs(
                        "entry_z_score",
                        parseFloat(e.target.value) || 2.0,
                      )
                    }
                    disabled={loading}
                  />
                </Field>
                <Field label="Exit Z-Score" hint="|z| ≤ exit">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsParams.exit_z_score}
                    min={0}
                    max={4.9}
                    step={0.1}
                    onChange={(e) =>
                      setPairs(
                        "exit_z_score",
                        parseFloat(e.target.value) || 0.5,
                      )
                    }
                    disabled={loading}
                  />
                </Field>
              </div>
            </div>
          )}
        </div>

        {/* ── Inline validation ─────────────────────────────────────────── */}
        {(dateInvalid ||
          smaInvalid ||
          rsiInvalid ||
          bbInvalid ||
          momentumInvalid ||
          vbInvalid ||
          pairsInvalid) && (
          <div className="mb-4 space-y-1">
            {dateInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Start date must be before end date.
              </p>
            )}
            {smaInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Fast SMA window must be less than slow SMA window.
              </p>
            )}
            {rsiInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Oversold threshold must be less than exit threshold.
              </p>
            )}
            {bbInvalid && (
              <p className="text-xs text-red-600">
                ⚠ BB window must be ≥ 2 and std dev must be &gt; 0.
              </p>
            )}
            {momentumInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Momentum lookback must be ≥ 1, thresholds must be between -1
                and 1, and entry must be ≥ exit.
              </p>
            )}
            {vbInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Lookback must be ≥ 2, multiplier must be &gt; 0, hold bars
                must be ≥ 1.
              </p>
            )}
            {pairsInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Assets must differ, lookback ≥ 10, and entry Z-score must be
                strictly greater than exit Z-score ≥ 0.
              </p>
            )}
          </div>
        )}

        {/* ── Submit ────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            className={
              "flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold " +
              "transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 " +
              (canSubmit
                ? "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 shadow-sm"
                : "bg-slate-200 text-slate-400 cursor-not-allowed")
            }
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
                Running…
              </>
            ) : (
              "Run Backtest"
            )}
          </button>
          <span className="text-xs text-slate-400">
            One-way cost · signal shifted 1 day · adjusted close prices
          </span>
        </div>
      </div>
    </div>
  );
}
