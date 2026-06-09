"use client";

import type {
  BacktestRequest,
  BbBacktestRequest,
  CostModel,
  CostModelType,
  MomentumBacktestRequest,
  PairsBacktestRequest,
  PositionMode,
  PositionSizing,
  PositionSizingType,
  RsiBacktestRequest,
  StrategyType,
  VbBacktestRequest,
} from "@/lib/types";
import { useEffect, useState } from "react";
import ShortSellingWarning from "@/components/ShortSellingWarning";

// Cost model options for the single-asset backtest form.
const COST_MODEL_OPTIONS: { id: CostModelType; label: string }[] = [
  { id: "simple_bps", label: "Simple BPS" },
  { id: "commission_slippage", label: "Commission + Slippage" },
  { id: "conservative", label: "Conservative" },
];
// Conservative preset (mirrors the backend cost_model.py constants).
const CONSERVATIVE = { commission: 10, slippage: 10, spread: 5 } as const;

// Position sizing options (single-asset directional strategies).
const SIZING_OPTIONS: { id: PositionSizingType; label: string }[] = [
  { id: "full", label: "Full Allocation" },
  { id: "fixed_fraction", label: "Fixed Fraction" },
  { id: "volatility_target", label: "Volatility Target" },
  { id: "max_exposure", label: "Max Exposure" },
];

// Direction modes (supported by SMA Crossover, Momentum, Volatility Breakout).
const MODE_OPTIONS: { id: PositionMode; label: string }[] = [
  { id: "long_only", label: "Long only" },
  { id: "short_only", label: "Short only" },
  { id: "long_short", label: "Long & Short" },
];
const MODE_STRATEGIES = new Set<StrategyType>([
  "sma_crossover",
  "momentum",
  "volatility_breakout",
]);

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
      "Dollar-neutral: trades Y versus X when spread z-score diverges; exits on reversion.",
  },
];

// ---------------------------------------------------------------------------
// One-click parameter presets. They include the demo-friendly defaults plus
// classic/stricter variants so users can opt into slower or less frequent
// signal behaviour without losing manual editability.
// ---------------------------------------------------------------------------

const SMA_PRESETS = [
  { label: "Responsive 20/100", fast: 20, slow: 100 },
  { label: "Classic 50/200", fast: 50, slow: 200 },
  { label: "Short 10/50", fast: 10, slow: 50 },
];
const RSI_PRESETS = [
  { label: "Conservative 30/50", ob: 30, exit: 50 },
  { label: "Balanced 35/55", ob: 35, exit: 55 },
  { label: "Aggressive 40/60", ob: 40, exit: 60 },
];
const BB_PRESETS = [
  { label: "Classic 2.0σ", std: 2.0 },
  { label: "Balanced 1.8σ", std: 1.8 },
  { label: "Active 1.5σ", std: 1.5 },
];
const MOM_PRESETS = [
  { label: "3-month (63)", window: 63 },
  { label: "6-month (126)", window: 126 },
  { label: "12-month (252)", window: 252 },
];
// Entry = prior rolling high + multiplier × prior range; lower multiplier ⇒
// more (more responsive) breakouts.  Balanced 0.3× is the demo default.
const VB_PRESETS = [
  { label: "Responsive 0.2×", lookback: 20, mult: 0.2, exit: 10 },
  { label: "Balanced 0.3×", lookback: 20, mult: 0.3, exit: 10 },
  { label: "Conservative 0.5×", lookback: 20, mult: 0.5, exit: 10 },
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
  // ── String states for every numeric input ─────────────────────────────────
  // Storing as strings lets users type partial values ("0.", "-", "12")
  // without the field auto-resetting on each keystroke.  Parsing happens at
  // validation/submit time only.  The parent state is kept in sync via the
  // setter calls below (only called when the parsed value is a finite number).
  // Common (shared across all strategies)
  const [costBpsStr, setCostBpsStr] = useState(String(smaParams.transaction_cost_bps));
  const [capitalStr, setCapitalStr] = useState(String(smaParams.initial_capital));
  // Cost model (shared across all strategies; initialised from saved params).
  const _initialCm = smaParams.cost_model;
  const [costModelType, setCostModelType] = useState<CostModelType>(
    _initialCm?.type ?? "simple_bps",
  );
  const [commissionStr, setCommissionStr] = useState(
    String(_initialCm?.commission_bps ?? 5),
  );
  const [slippageStr, setSlippageStr] = useState(
    String(_initialCm?.slippage_bps ?? 5),
  );
  const [spreadStr, setSpreadStr] = useState(String(_initialCm?.spread_bps ?? 2));
  // Position sizing (shared across all strategies; initialised from saved params).
  const _initialPs = smaParams.position_sizing;
  const [sizingType, setSizingType] = useState<PositionSizingType>(
    _initialPs?.type ?? "full",
  );
  const [fractionStr, setFractionStr] = useState(
    String(_initialPs?.fraction ?? 0.5),
  );
  const [targetVolStr, setTargetVolStr] = useState(
    String(_initialPs?.target_volatility ?? 0.15),
  );
  const [volLookbackStr, setVolLookbackStr] = useState(
    String(_initialPs?.vol_lookback ?? 20),
  );
  const [maxExposureStr, setMaxExposureStr] = useState(
    String(_initialPs?.max_exposure ?? 0.8),
  );
  // SMA Crossover
  const [smaFastStr, setSmaFastStr] = useState(String(smaParams.fast_window));
  const [smaSlowStr, setSmaSlowStr] = useState(String(smaParams.slow_window));
  // RSI Mean Reversion
  const [rsiWindowStr, setRsiWindowStr] = useState(String(rsiParams.rsi_window));
  const [rsiOversoldStr, setRsiOversoldStr] = useState(String(rsiParams.oversold_threshold));
  const [rsiExitStr, setRsiExitStr] = useState(String(rsiParams.exit_threshold));
  // Bollinger Band
  const [bbWindowStr, setBbWindowStr] = useState(String(bbParams.bb_window));
  const [bbNumStdStr, setBbNumStdStr] = useState(String(bbParams.num_std));
  // Momentum
  const [momWindowStr, setMomWindowStr] = useState(String(momentumParams.momentum_window));
  const [momEntryStr, setMomEntryStr] = useState(String(momentumParams.entry_threshold));
  const [momExitStr, setMomExitStr] = useState(String(momentumParams.exit_threshold));
  // Volatility Breakout
  const [vbLookbackStr, setVbLookbackStr] = useState(String(vbParams.lookback_window));
  const [vbMultStr, setVbMultStr] = useState(String(vbParams.breakout_multiplier));
  const [vbExitWindowStr, setVbExitWindowStr] = useState(String(vbParams.exit_window));
  // Pairs Trading
  const [pairsLookbackStr, setPairsLookbackStr] = useState(String(pairsParams.lookback_window));
  const [pairsEntryZStr, setPairsEntryZStr] = useState(String(pairsParams.entry_z_score));
  const [pairsExitZStr, setPairsExitZStr] = useState(String(pairsParams.exit_z_score));

  // Derived numbers — parsed from string states
  const costBps = parseFloat(costBpsStr);
  const capital = parseFloat(capitalStr);
  const smaFast = parseInt(smaFastStr, 10);
  const smaSlow = parseInt(smaSlowStr, 10);
  const rsiWindow = parseInt(rsiWindowStr, 10);
  const rsiOversold = parseFloat(rsiOversoldStr);
  const rsiExit = parseFloat(rsiExitStr);
  const bbWindow = parseInt(bbWindowStr, 10);
  const bbNumStd = parseFloat(bbNumStdStr);
  const momWindow = parseInt(momWindowStr, 10);
  const momEntry = parseFloat(momEntryStr);
  const momExit = parseFloat(momExitStr);
  const vbLookback = parseInt(vbLookbackStr, 10);
  const vbMult = parseFloat(vbMultStr);
  const vbExitWindow = parseInt(vbExitWindowStr, 10);
  const pairsLookback = parseInt(pairsLookbackStr, 10);
  const pairsEntryZ = parseFloat(pairsEntryZStr);
  const pairsExitZ = parseFloat(pairsExitZStr);

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

  type CommonPatch = Partial<{
    ticker: string;
    start_date: string;
    end_date: string;
    transaction_cost_bps: number;
    initial_capital: number;
    cost_model: CostModel | undefined;
    position_sizing: PositionSizing | undefined;
  }>;

  /** Update every strategy's common fields simultaneously so switching strategy
   *  never loses a date or cost setting.  Skips "ticker" for pairs since
   *  PairsBacktestRequest uses asset_y / asset_x instead. */
  function setCommonFields(patch: CommonPatch) {
    onSmaParamsChange({ ...smaParams, ...patch } as BacktestRequest);
    onRsiParamsChange({ ...rsiParams, ...patch } as RsiBacktestRequest);
    onBbParamsChange({ ...bbParams, ...patch } as BbBacktestRequest);
    onMomentumParamsChange({
      ...momentumParams,
      ...patch,
    } as MomentumBacktestRequest);
    onVbParamsChange({ ...vbParams, ...patch } as VbBacktestRequest);
    // Pairs shares start_date / end_date / cost / capital but NOT ticker.
    const { ticker: _ticker, ...pairsPatch } = patch;
    onPairsParamsChange({
      ...pairsParams,
      ...pairsPatch,
    } as PairsBacktestRequest);
  }

  function setCommon<K extends keyof CommonPatch>(key: K, value: CommonPatch[K]) {
    setCommonFields({ [key]: value } as CommonPatch);
  }

  // ── Cost model wiring ──────────────────────────────────────────────────────
  // The cost model is a shared field (like cost / capital), so it is synced
  // across every strategy.  Legacy callers can still omit cost_model, but the
  // Backtest form sends the selected mode so reports can echo it.
  useEffect(() => {
    const v = parseFloat(costBpsStr);
    if (!isNaN(v) && v >= 0) {
      if (
        _initialCm &&
        _initialCm.type !== "simple_bps"
      ) {
        return;
      }
      if (
        _initialCm?.type === "simple_bps" &&
        _initialCm.transaction_cost_bps === v
      ) {
        return;
      }
      setCommonFields({
        cost_model: { type: "simple_bps", transaction_cost_bps: v },
      });
    }
    // Run once on mount. The form is keyed/remounted when demo/settings
    // defaults need to re-hydrate local string state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pushSimpleBps(raw: string) {
    const v = parseFloat(raw);
    if (isNaN(v) || v < 0) return;
    setCommonFields({
      transaction_cost_bps: v,
      cost_model: { type: "simple_bps", transaction_cost_bps: v },
    });
  }

  function pushCommissionSlippage(
    commission: string,
    slippage: string,
    spread: string,
  ) {
    const c = parseFloat(commission);
    const s = parseFloat(slippage);
    const sp = spread.trim() === "" ? 0 : parseFloat(spread);
    if (isNaN(c) || c < 0 || isNaN(s) || s < 0 || isNaN(sp) || sp < 0) return;
    setCommon("cost_model", {
      type: "commission_slippage",
      commission_bps: c,
      slippage_bps: s,
      spread_bps: sp,
    } as CostModel);
  }

  function handleCostTypeChange(t: CostModelType) {
    setCostModelType(t);
    if (t === "simple_bps") {
      pushSimpleBps(costBpsStr);
    } else if (t === "conservative") {
      setCommon("cost_model", { type: "conservative" } as CostModel);
    } else {
      pushCommissionSlippage(commissionStr, slippageStr, spreadStr);
    }
  }

  // ── Position sizing wiring ─────────────────────────────────────────────────
  // Sizing is a shared field too.  "Full Allocation" omits position_sizing so
  // the request is byte-identical to the old full-allocation behaviour.
  function pushFixedFraction(fraction: string) {
    const f = parseFloat(fraction);
    if (isNaN(f) || f <= 0 || f > 1) return;
    setCommon("position_sizing", {
      type: "fixed_fraction",
      fraction: f,
    } as PositionSizing);
  }

  function pushMaxExposure(maxExposure: string) {
    const m = parseFloat(maxExposure);
    if (isNaN(m) || m <= 0 || m > 1) return;
    setCommon("position_sizing", {
      type: "max_exposure",
      max_exposure: m,
    } as PositionSizing);
  }

  function pushVolTarget(targetVol: string, lookback: string) {
    const tv = parseFloat(targetVol);
    const lb = parseInt(lookback, 10);
    if (isNaN(tv) || tv <= 0 || isNaN(lb) || lb < 2) return;
    setCommon("position_sizing", {
      type: "volatility_target",
      target_volatility: tv,
      vol_lookback: lb,
    } as PositionSizing);
  }

  function handleSizingTypeChange(t: PositionSizingType) {
    setSizingType(t);
    if (t === "full") {
      setCommon("position_sizing", undefined);
    } else if (t === "fixed_fraction") {
      pushFixedFraction(fractionStr);
    } else if (t === "max_exposure") {
      pushMaxExposure(maxExposureStr);
    } else {
      pushVolTarget(targetVolStr, volLookbackStr);
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
  // Parameter presets — set the numeric string state AND the parent params so
  // editing behaviour is unchanged; a preset is just a one-click value setter.
  // ---------------------------------------------------------------------------
  function applySmaPreset(i: number) {
    const p = SMA_PRESETS[i];
    setSmaFastStr(String(p.fast));
    setSmaSlowStr(String(p.slow));
    onSmaParamsChange({ ...smaParams, fast_window: p.fast, slow_window: p.slow });
  }
  function applyRsiPreset(i: number) {
    const p = RSI_PRESETS[i];
    setRsiOversoldStr(String(p.ob));
    setRsiExitStr(String(p.exit));
    onRsiParamsChange({
      ...rsiParams,
      oversold_threshold: p.ob,
      exit_threshold: p.exit,
    });
  }
  function applyBbPreset(i: number) {
    const p = BB_PRESETS[i];
    setBbNumStdStr(String(p.std));
    onBbParamsChange({ ...bbParams, num_std: p.std });
  }
  function applyMomPreset(i: number) {
    const p = MOM_PRESETS[i];
    setMomWindowStr(String(p.window));
    onMomentumParamsChange({ ...momentumParams, momentum_window: p.window });
  }
  function applyVbPreset(i: number) {
    const p = VB_PRESETS[i];
    setVbLookbackStr(String(p.lookback));
    setVbMultStr(String(p.mult));
    setVbExitWindowStr(String(p.exit));
    onVbParamsChange({
      ...vbParams,
      lookback_window: p.lookback,
      breakout_multiplier: p.mult,
      exit_window: p.exit,
    });
  }

  const smaActiveIdx = SMA_PRESETS.findIndex(
    (p) => p.fast === smaParams.fast_window && p.slow === smaParams.slow_window,
  );
  const rsiActiveIdx = RSI_PRESETS.findIndex(
    (p) =>
      p.ob === rsiParams.oversold_threshold && p.exit === rsiParams.exit_threshold,
  );
  const bbActiveIdx = BB_PRESETS.findIndex((p) => p.std === bbParams.num_std);
  const momActiveIdx = MOM_PRESETS.findIndex(
    (p) => p.window === momentumParams.momentum_window,
  );
  const vbActiveIdx = VB_PRESETS.findIndex(
    (p) =>
      p.lookback === vbParams.lookback_window &&
      p.mult === vbParams.breakout_multiplier &&
      p.exit === vbParams.exit_window,
  );

  // ── Direction mode (long / short / long-short) ────────────────────────────
  const supportsMode = MODE_STRATEGIES.has(strategy);
  const currentMode: PositionMode =
    strategy === "sma_crossover"
      ? smaParams.position_mode ?? "long_only"
      : strategy === "momentum"
        ? momentumParams.position_mode ?? "long_only"
        : vbParams.position_mode ?? "long_only";
  function setMode(m: PositionMode) {
    if (strategy === "sma_crossover") {
      onSmaParamsChange({ ...smaParams, position_mode: m });
    } else if (strategy === "momentum") {
      onMomentumParamsChange({ ...momentumParams, position_mode: m });
    } else if (strategy === "volatility_breakout") {
      onVbParamsChange({ ...vbParams, position_mode: m });
    }
  }

  function renderPresets(
    items: { label: string }[],
    activeIdx: number,
    pick: (i: number) => void,
  ) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Presets
        </span>
        {items.map((p, i) => (
          <button
            key={p.label}
            type="button"
            disabled={loading}
            onClick={() => pick(i)}
            className={
              "px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors " +
              (activeIdx === i
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
            }
          >
            {p.label}
          </button>
        ))}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------
  const dateInvalid = active.start_date >= active.end_date;

  // Cost-model derived values (display + validation).
  const commissionVal = parseFloat(commissionStr);
  const slippageVal = parseFloat(slippageStr);
  const spreadVal = spreadStr.trim() === "" ? 0 : parseFloat(spreadStr);
  const costOk =
    costModelType === "conservative"
      ? true
      : costModelType === "commission_slippage"
        ? !isNaN(commissionVal) &&
          commissionVal >= 0 &&
          !isNaN(slippageVal) &&
          slippageVal >= 0 &&
          !isNaN(spreadVal) &&
          spreadVal >= 0
        : !isNaN(costBps) && costBps >= 0;
  const effectiveBps =
    costModelType === "conservative"
      ? CONSERVATIVE.commission + CONSERVATIVE.slippage + CONSERVATIVE.spread
      : costModelType === "commission_slippage"
        ? (isNaN(commissionVal) ? 0 : commissionVal) +
          (isNaN(slippageVal) ? 0 : slippageVal) +
          (isNaN(spreadVal) ? 0 : spreadVal)
        : isNaN(costBps)
          ? 0
          : costBps;

  // Position-sizing validation.
  const fractionVal = parseFloat(fractionStr);
  const targetVolVal = parseFloat(targetVolStr);
  const volLookbackVal = parseInt(volLookbackStr, 10);
  const maxExposureVal = parseFloat(maxExposureStr);
  const sizingOk =
    sizingType === "full"
      ? true
      : sizingType === "fixed_fraction"
        ? !isNaN(fractionVal) && fractionVal > 0 && fractionVal <= 1
        : sizingType === "max_exposure"
          ? !isNaN(maxExposureVal) && maxExposureVal > 0 && maxExposureVal <= 1
          : !isNaN(targetVolVal) &&
            targetVolVal > 0 &&
            !isNaN(volLookbackVal) &&
            volLookbackVal >= 2;

  const commonNumericOk =
    costOk && sizingOk && !isNaN(capital) && capital > 0;
  const smaInvalid =
    strategy === "sma_crossover" &&
    (isNaN(smaFast) || isNaN(smaSlow) || smaFast >= smaSlow);
  const rsiInvalid =
    strategy === "rsi_mean_reversion" &&
    (isNaN(rsiWindow) || rsiWindow < 2 ||
      isNaN(rsiOversold) || isNaN(rsiExit) ||
      rsiOversold >= rsiExit);
  const bbInvalid =
    strategy === "bollinger_band" &&
    (isNaN(bbWindow) || bbWindow < 2 || isNaN(bbNumStd) || bbNumStd <= 0);
  const momentumInvalid =
    strategy === "momentum" &&
    (isNaN(momWindow) || momWindow < 1 ||
      isNaN(momEntry) || momEntry < -1 || momEntry > 1 ||
      isNaN(momExit) || momExit < -1 || momExit > 1 ||
      momEntry < momExit);
  const vbInvalid =
    strategy === "volatility_breakout" &&
    (isNaN(vbLookback) || vbLookback < 2 ||
      isNaN(vbMult) || vbMult <= 0 ||
      isNaN(vbExitWindow) || vbExitWindow < 1);
  const pairsInvalid =
    strategy === "pairs" &&
    (isNaN(pairsLookback) || pairsLookback < 10 ||
      isNaN(pairsEntryZ) || isNaN(pairsExitZ) ||
      pairsEntryZ <= pairsExitZ || pairsExitZ < 0 ||
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
    commonNumericOk &&
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
        <div className="grid grid-cols-1 gap-4 mb-5 sm:grid-cols-3">
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
          <Field label="Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              min={1}
              step={1000}
              onChange={(e) => {
                setCapitalStr(e.target.value);
                const v = parseFloat(e.target.value);
                if (!isNaN(v)) setCommon("initial_capital", v);
              }}
              disabled={loading}
            />
          </Field>
        </div>

        {/* ── Cost model ────────────────────────────────────────────────── */}
        <div className="mb-5 rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Cost model
            </span>
            <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
              {COST_MODEL_OPTIONS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  disabled={loading}
                  onClick={() => handleCostTypeChange(o.id)}
                  className={
                    "px-3 py-1.5 text-xs font-medium transition-colors " +
                    (costModelType === o.id
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50")
                  }
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {costModelType === "simple_bps" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Transaction cost" hint="bps">
                <input
                  type="number"
                  className={inputCls}
                  value={costBpsStr}
                  min={0}
                  max={200}
                  step={1}
                  onChange={(e) => {
                    setCostBpsStr(e.target.value);
                    pushSimpleBps(e.target.value);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          )}

          {costModelType === "commission_slippage" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Commission" hint="bps">
                <input
                  type="number"
                  className={inputCls}
                  value={commissionStr}
                  min={0}
                  step={1}
                  onChange={(e) => {
                    setCommissionStr(e.target.value);
                    pushCommissionSlippage(e.target.value, slippageStr, spreadStr);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Slippage" hint="bps">
                <input
                  type="number"
                  className={inputCls}
                  value={slippageStr}
                  min={0}
                  step={1}
                  onChange={(e) => {
                    setSlippageStr(e.target.value);
                    pushCommissionSlippage(commissionStr, e.target.value, spreadStr);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Spread" hint="bps · optional">
                <input
                  type="number"
                  className={inputCls}
                  value={spreadStr}
                  min={0}
                  step={1}
                  onChange={(e) => {
                    setSpreadStr(e.target.value);
                    pushCommissionSlippage(commissionStr, slippageStr, e.target.value);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          )}

          {costModelType === "conservative" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Commission" hint="bps">
                <input type="number" className={inputCls} value={CONSERVATIVE.commission} readOnly disabled />
              </Field>
              <Field label="Slippage" hint="bps">
                <input type="number" className={inputCls} value={CONSERVATIVE.slippage} readOnly disabled />
              </Field>
              <Field label="Spread" hint="bps">
                <input type="number" className={inputCls} value={CONSERVATIVE.spread} readOnly disabled />
              </Field>
            </div>
          )}

          <p className="mt-2.5 text-xs text-slate-600">
            Effective cost:{" "}
            <span className="font-semibold text-slate-800">{effectiveBps} bps</span>{" "}
            per side
            {costModelType === "conservative" && (
              <span className="ml-1 text-slate-400">
                · Conservative: higher assumed execution friction
              </span>
            )}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            Costs are applied to turnover. Long → short flips count as 2x turnover.
          </p>
          <p className="text-[11px] text-slate-400">
            These are simplified assumptions and do not model order book depth or
            market impact.
          </p>
        </div>

        {/* ── Position sizing ───────────────────────────────────────────── */}
        <div className="mb-5 rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Position sizing
            </span>
            <div className="inline-flex flex-wrap overflow-hidden rounded-lg border border-slate-300">
              {SIZING_OPTIONS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  disabled={loading}
                  onClick={() => handleSizingTypeChange(o.id)}
                  className={
                    "px-3 py-1.5 text-xs font-medium transition-colors " +
                    (sizingType === o.id
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50")
                  }
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {sizingType === "full" && (
            <p className="text-xs text-slate-500">
              Full allocation: ±100% exposure on a signal (current default).
            </p>
          )}

          {sizingType === "fixed_fraction" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Fraction" hint="0–1">
                <input
                  type="number"
                  className={inputCls}
                  value={fractionStr}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(e) => {
                    setFractionStr(e.target.value);
                    pushFixedFraction(e.target.value);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          )}

          {sizingType === "max_exposure" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Max exposure" hint="0–1">
                <input
                  type="number"
                  className={inputCls}
                  value={maxExposureStr}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(e) => {
                    setMaxExposureStr(e.target.value);
                    pushMaxExposure(e.target.value);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          )}

          {sizingType === "volatility_target" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Target vol" hint="annualized, e.g. 0.15">
                <input
                  type="number"
                  className={inputCls}
                  value={targetVolStr}
                  min={0}
                  step={0.01}
                  onChange={(e) => {
                    setTargetVolStr(e.target.value);
                    pushVolTarget(e.target.value, volLookbackStr);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Vol lookback" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={volLookbackStr}
                  min={2}
                  step={1}
                  onChange={(e) => {
                    setVolLookbackStr(e.target.value);
                    pushVolTarget(targetVolStr, e.target.value);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          )}

          <p className="mt-2.5 text-[11px] text-slate-400">
            Sizing scales exposure magnitude only — signal timing and direction
            are unchanged. No leverage: |exposure| ≤ 1 (volatility targeting only
            de-levers in high-vol regimes).
          </p>
        </div>

        {/* ── Strategy-specific fields ───────────────────────────────────── */}
        <div className="mb-5 p-4 rounded-lg bg-blue-50/60 border border-blue-100">
          {supportsMode && (
            <div className="mb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                  Direction
                </span>
                <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
                  {MODE_OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      disabled={loading}
                      onClick={() => setMode(o.id)}
                      className={
                        "px-3 py-1 text-xs font-medium transition-colors " +
                        (currentMode === o.id
                          ? "bg-blue-600 text-white"
                          : "bg-white text-slate-600 hover:bg-blue-50")
                      }
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-1.5 text-[11px] text-slate-400">
                {currentMode === "long_only"
                  ? "Long-only strategies can stay in cash during downtrends."
                  : currentMode === "short_only"
                    ? "Short-only mode trades only bearish signals. This is experimental and does not model borrow costs."
                    : "Advanced research mode. Long/short mode may underperform on upward-trending assets due to whipsaws, higher turnover, and short-selling risk."}
              </p>
              {currentMode !== "long_only" && (
                <ShortSellingWarning className="mt-2" />
              )}
            </div>
          )}
          {!supportsMode && strategy !== "pairs" && (
            <p className="mb-3 inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">
              <span className="rounded bg-slate-100 px-1.5 py-0.5">Long-only strategy</span>
              <span className="normal-case font-normal text-slate-400">
                — direction modes are available for SMA, Momentum, and Volatility Breakout.
              </span>
            </p>
          )}
          {strategy === "sma_crossover" &&
            renderPresets(SMA_PRESETS, smaActiveIdx, applySmaPreset)}
          {strategy === "rsi_mean_reversion" &&
            renderPresets(RSI_PRESETS, rsiActiveIdx, applyRsiPreset)}
          {strategy === "bollinger_band" &&
            renderPresets(BB_PRESETS, bbActiveIdx, applyBbPreset)}
          {strategy === "momentum" &&
            renderPresets(MOM_PRESETS, momActiveIdx, applyMomPreset)}
          {strategy === "volatility_breakout" &&
            renderPresets(VB_PRESETS, vbActiveIdx, applyVbPreset)}
          {strategy === "sma_crossover" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Fast SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaFastStr}
                  min={2}
                  max={smaParams.slow_window - 1}
                  step={1}
                  onChange={(e) => {
                    setSmaFastStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setSma("fast_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Slow SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaSlowStr}
                  min={smaParams.fast_window + 1}
                  step={1}
                  onChange={(e) => {
                    setSmaSlowStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setSma("slow_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "rsi_mean_reversion" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="RSI window" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiWindowStr}
                  min={2}
                  max={100}
                  step={1}
                  onChange={(e) => {
                    setRsiWindowStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setRsi("rsi_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Oversold" hint="enter <">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiOversoldStr}
                  min={1}
                  max={rsiParams.exit_threshold - 1}
                  step={1}
                  onChange={(e) => {
                    setRsiOversoldStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setRsi("oversold_threshold", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Exit" hint="exit ≥">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiExitStr}
                  min={rsiParams.oversold_threshold + 1}
                  max={100}
                  step={1}
                  onChange={(e) => {
                    setRsiExitStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setRsi("exit_threshold", v);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "bollinger_band" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="BB Window" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={bbWindowStr}
                  min={2}
                  max={500}
                  step={1}
                  onChange={(e) => {
                    setBbWindowStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setBb("bb_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Std Dev" hint="σ">
                <input
                  type="number"
                  className={inputCls}
                  value={bbNumStdStr}
                  min={0.1}
                  max={10}
                  step={0.1}
                  onChange={(e) => {
                    setBbNumStdStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setBb("num_std", v);
                  }}
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
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Lookback" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={momWindowStr}
                  min={1}
                  max={1000}
                  step={1}
                  onChange={(e) => {
                    setMomWindowStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setMomentum("momentum_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Entry threshold" hint="decimal">
                <input
                  type="number"
                  className={inputCls}
                  value={momEntryStr}
                  min={-1}
                  max={1}
                  step={0.01}
                  onChange={(e) => {
                    setMomEntryStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setMomentum("entry_threshold", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Exit threshold" hint="decimal">
                <input
                  type="number"
                  className={inputCls}
                  value={momExitStr}
                  min={-1}
                  max={1}
                  step={0.01}
                  onChange={(e) => {
                    setMomExitStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setMomentum("exit_threshold", v);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          ) : strategy === "volatility_breakout" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Lookback" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={vbLookbackStr}
                  min={2}
                  max={500}
                  step={1}
                  onChange={(e) => {
                    setVbLookbackStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setVb("lookback_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Multiplier" hint="× range">
                <input
                  type="number"
                  className={inputCls}
                  value={vbMultStr}
                  min={0.1}
                  max={10}
                  step={0.1}
                  onChange={(e) => {
                    setVbMultStr(e.target.value);
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) setVb("breakout_multiplier", v);
                  }}
                  disabled={loading}
                />
              </Field>
              <Field label="Exit mean" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={vbExitWindowStr}
                  min={1}
                  max={500}
                  step={1}
                  onChange={(e) => {
                    setVbExitWindowStr(e.target.value);
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setVb("exit_window", v);
                  }}
                  disabled={loading}
                />
              </Field>
            </div>
          ) : (
            /* ── Pairs Trading fields ───────────────────────────────────── */
            <div className="space-y-4">
              {/* Asset inputs + quick-picks */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Field label="Lookback" hint="days">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsLookbackStr}
                    min={10}
                    max={500}
                    step={1}
                    onChange={(e) => {
                      setPairsLookbackStr(e.target.value);
                      const v = parseInt(e.target.value, 10);
                      if (!isNaN(v)) setPairs("lookback_window", v);
                    }}
                    disabled={loading}
                  />
                </Field>
                <Field label="Entry Z-Score" hint="strict">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsEntryZStr}
                    min={0.1}
                    max={5}
                    step={0.1}
                    onChange={(e) => {
                      setPairsEntryZStr(e.target.value);
                      const v = parseFloat(e.target.value);
                      if (!isNaN(v)) setPairs("entry_z_score", v);
                    }}
                    disabled={loading}
                  />
                </Field>
                <Field label="Exit Z-Score" hint="reversion">
                  <input
                    type="number"
                    className={inputCls}
                    value={pairsExitZStr}
                    min={0}
                    max={4.9}
                    step={0.1}
                    onChange={(e) => {
                      setPairsExitZStr(e.target.value);
                      const v = parseFloat(e.target.value);
                      if (!isNaN(v)) setPairs("exit_z_score", v);
                    }}
                    disabled={loading}
                  />
                </Field>
              </div>
            </div>
          )}
        </div>

        {/* Demo-friendly defaults notice */}
        <p className="mb-4 text-xs text-slate-400">
          Default parameters are{" "}
          <span className="font-medium text-slate-500">demo-friendly, not optimized</span>{" "}
          — classic long-term presets are available above. Validate parameters with the{" "}
          <span className="font-medium text-slate-500">
            Parameter Sweep, Train/Test, and Walk-Forward
          </span>{" "}
          research tools; defaults are not recommendations.
        </p>

        {/* ── Inline validation ─────────────────────────────────────────── */}
        {(!commonNumericOk ||
          dateInvalid ||
          smaInvalid ||
          rsiInvalid ||
          bbInvalid ||
          momentumInvalid ||
          vbInvalid ||
          pairsInvalid) && (
          <div className="mb-4 space-y-1">
            {!commonNumericOk && (
              <p className="text-xs text-red-600">
                ⚠ {!costOk
                  ? "Cost model values must be valid numbers (≥ 0)."
                  : !sizingOk
                    ? "Position sizing values must be valid (fraction / max exposure in (0–1], target vol > 0, lookback ≥ 2)."
                    : isNaN(capital)
                      ? "Initial capital must be a valid number (> 0)."
                      : "Initial capital must be greater than 0."}
              </p>
            )}
            {dateInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Start date must be before end date.
              </p>
            )}
            {smaInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(smaFast) || isNaN(smaSlow))
                  ? "SMA windows must be valid numbers."
                  : "Fast SMA window must be less than slow SMA window."}
              </p>
            )}
            {rsiInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(rsiWindow) || isNaN(rsiOversold) || isNaN(rsiExit))
                  ? "RSI fields must be valid numbers."
                  : "Oversold threshold must be less than exit threshold."}
              </p>
            )}
            {bbInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(bbWindow) || isNaN(bbNumStd))
                  ? "BB fields must be valid numbers."
                  : "BB window must be ≥ 2 and std dev must be > 0."}
              </p>
            )}
            {momentumInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(momWindow) || isNaN(momEntry) || isNaN(momExit))
                  ? "Momentum fields must be valid numbers."
                  : "Momentum lookback must be ≥ 1, thresholds must be between -1 and 1, and entry must be ≥ exit."}
              </p>
            )}
            {vbInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(vbLookback) || isNaN(vbMult) || isNaN(vbExitWindow))
                  ? "Volatility Breakout fields must be valid numbers."
                  : "Lookback must be ≥ 2, multiplier must be > 0, hold bars must be ≥ 1."}
              </p>
            )}
            {pairsInvalid && (
              <p className="text-xs text-red-600">
                ⚠ {(isNaN(pairsLookback) || isNaN(pairsEntryZ) || isNaN(pairsExitZ))
                  ? "Pairs fields must be valid numbers."
                  : "Assets must differ, lookback ≥ 10, and entry Z-score must be strictly greater than exit Z-score ≥ 0."}
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
