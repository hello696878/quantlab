"use client";

import { useMemo, useState } from "react";
import { runCustomBacktest } from "@/lib/api";
import type {
  BacktestResponse,
  CustomIndicatorName,
  CustomOperand,
  CustomOperator,
  CustomRule,
  CustomStrategyRequest,
} from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";

// ---------------------------------------------------------------------------
// Operand / indicator metadata
// ---------------------------------------------------------------------------

const INDICATORS: { id: CustomIndicatorName; label: string; needsStd: boolean }[] = [
  { id: "sma", label: "SMA", needsStd: false },
  { id: "rsi", label: "RSI", needsStd: false },
  { id: "momentum", label: "Momentum", needsStd: false },
  { id: "bb_upper", label: "BB Upper", needsStd: true },
  { id: "bb_middle", label: "BB Middle", needsStd: false },
  { id: "bb_lower", label: "BB Lower", needsStd: true },
];

const OPERATORS: { id: CustomOperator; label: string }[] = [
  { id: ">", label: ">" },
  { id: ">=", label: "≥" },
  { id: "<", label: "<" },
  { id: "<=", label: "≤" },
];

type OperandKind = "close" | "constant" | "indicator";

// UI representation — numbers held as strings so fields stay freely editable.
interface UIOperand {
  kind: OperandKind;
  value: string; // constant value
  name: CustomIndicatorName; // indicator name
  window: string;
  numStd: string;
}

interface UIRule {
  id: string;
  left: UIOperand;
  operator: CustomOperator;
  right: UIOperand;
}

let _idSeq = 0;
const nextId = () => `r${_idSeq++}`;

function makeOperand(partial: Partial<UIOperand> = {}): UIOperand {
  return {
    kind: "indicator",
    value: "0",
    name: "sma",
    window: "50",
    numStd: "2",
    ...partial,
  };
}

function makeRule(left: Partial<UIOperand>, op: CustomOperator, right: Partial<UIOperand>): UIRule {
  return { id: nextId(), left: makeOperand(left), operator: op, right: makeOperand(right) };
}

// Sensible starting strategy: SMA(20) crossover of SMA(50).
const DEFAULT_ENTRY: UIRule[] = [
  makeRule({ kind: "indicator", name: "sma", window: "20" }, ">", {
    kind: "indicator",
    name: "sma",
    window: "50",
  }),
];
const DEFAULT_EXIT: UIRule[] = [
  makeRule({ kind: "indicator", name: "sma", window: "20" }, "<=", {
    kind: "indicator",
    name: "sma",
    window: "50",
  }),
];

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

const selCls = inputCls + " pr-7";

// ---------------------------------------------------------------------------
// Conversion + validation
// ---------------------------------------------------------------------------

function parseIntStrict(raw: string): number | null {
  const t = raw.trim();
  if (t === "") return null;
  const v = Number(t);
  return Number.isInteger(v) ? v : null;
}

function parseFloatStrict(raw: string): number | null {
  const t = raw.trim();
  if (t === "") return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

/** Convert a UI operand to the API operand, or null if invalid. */
function operandToApi(op: UIOperand): CustomOperand | null {
  if (op.kind === "close") return { type: "close" };
  if (op.kind === "constant") {
    const v = parseFloatStrict(op.value);
    return v === null ? null : { type: "constant", value: v };
  }
  // indicator
  const w = parseIntStrict(op.window);
  if (w === null || w < 1) return null;
  const meta = INDICATORS.find((i) => i.id === op.name)!;
  const params: { window: number; num_std?: number } = { window: w };
  if (meta.needsStd) {
    const s = parseFloatStrict(op.numStd);
    if (s === null || s <= 0) return null;
    params.num_std = s;
  }
  return { type: "indicator", name: op.name, params };
}

function ruleToApi(rule: UIRule): CustomRule | null {
  const left = operandToApi(rule.left);
  const right = operandToApi(rule.right);
  if (!left || !right) return null;
  return { left, operator: rule.operator, right };
}

/** Human-readable operand label, e.g. "SMA(50)" or "close" or "30". */
function operandLabel(op: UIOperand): string {
  if (op.kind === "close") return "close";
  if (op.kind === "constant") return op.value.trim() === "" ? "?" : op.value;
  const meta = INDICATORS.find((i) => i.id === op.name)!;
  return meta.needsStd
    ? `${meta.label}(${op.window}, ${op.numStd}σ)`
    : `${meta.label}(${op.window})`;
}

function opSymbol(op: CustomOperator): string {
  return OPERATORS.find((o) => o.id === op)?.label ?? op;
}

// ---------------------------------------------------------------------------
// Operand editor
// ---------------------------------------------------------------------------

function OperandEditor({
  value,
  onChange,
  disabled,
}: {
  value: UIOperand;
  onChange: (o: UIOperand) => void;
  disabled: boolean;
}) {
  const meta = INDICATORS.find((i) => i.id === value.name)!;
  const set = (patch: Partial<UIOperand>) => onChange({ ...value, ...patch });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className={selCls + " w-auto"}
        value={value.kind}
        onChange={(e) => set({ kind: e.target.value as OperandKind })}
        disabled={disabled}
      >
        <option value="indicator">Indicator</option>
        <option value="close">Close</option>
        <option value="constant">Constant</option>
      </select>

      {value.kind === "constant" && (
        <input
          type="number"
          className={inputCls + " w-28"}
          value={value.value}
          onChange={(e) => set({ value: e.target.value })}
          placeholder="value"
          disabled={disabled}
        />
      )}

      {value.kind === "indicator" && (
        <>
          <select
            className={selCls + " w-auto"}
            value={value.name}
            onChange={(e) => set({ name: e.target.value as CustomIndicatorName })}
            disabled={disabled}
          >
            {INDICATORS.map((i) => (
              <option key={i.id} value={i.id}>
                {i.label}
              </option>
            ))}
          </select>
          <input
            type="number"
            className={inputCls + " w-20"}
            value={value.window}
            onChange={(e) => set({ window: e.target.value })}
            placeholder="window"
            title="Look-back window (days)"
            disabled={disabled}
          />
          {meta.needsStd && (
            <input
              type="number"
              className={inputCls + " w-20"}
              value={value.numStd}
              onChange={(e) => set({ numStd: e.target.value })}
              placeholder="σ"
              title="Standard deviations"
              disabled={disabled}
            />
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rule list editor
// ---------------------------------------------------------------------------

function RuleListEditor({
  title,
  rules,
  onChange,
  logic,
  onLogicChange,
  disabled,
  emptyHint,
}: {
  title: string;
  rules: UIRule[];
  onChange: (r: UIRule[]) => void;
  logic: "all" | "any";
  onLogicChange: (l: "all" | "any") => void;
  disabled: boolean;
  emptyHint: string;
}) {
  function updateRule(id: string, patch: Partial<UIRule>) {
    onChange(rules.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }
  function addRule() {
    onChange([...rules, makeRule({ kind: "close" }, ">", { kind: "constant", value: "0" })]);
  }
  function removeRule(id: string) {
    onChange(rules.filter((r) => r.id !== id));
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="section-title">{title}</p>
        {rules.length > 1 && (
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-400">match</span>
            <div className="flex rounded-lg bg-slate-100 p-0.5">
              {(["all", "any"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => onLogicChange(l)}
                  disabled={disabled}
                  className={
                    "px-2 py-0.5 rounded-md font-medium transition-colors " +
                    (logic === l
                      ? "bg-blue-600 text-white"
                      : "text-slate-500 hover:text-slate-700")
                  }
                >
                  {l === "all" ? "ALL (and)" : "ANY (or)"}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {rules.length === 0 && (
        <p className="text-xs text-slate-400">{emptyHint}</p>
      )}

      <div className="space-y-2">
        {rules.map((rule, i) => (
          <div
            key={rule.id}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 p-3"
          >
            {i > 0 && (
              <span className="text-[10px] font-semibold uppercase text-slate-400 w-8">
                {logic === "all" ? "and" : "or"}
              </span>
            )}
            <OperandEditor
              value={rule.left}
              onChange={(o) => updateRule(rule.id, { left: o })}
              disabled={disabled}
            />
            <select
              className={selCls + " w-auto"}
              value={rule.operator}
              onChange={(e) =>
                updateRule(rule.id, { operator: e.target.value as CustomOperator })
              }
              disabled={disabled}
            >
              {OPERATORS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
            <OperandEditor
              value={rule.right}
              onChange={(o) => updateRule(rule.id, { right: o })}
              disabled={disabled}
            />
            <button
              type="button"
              onClick={() => removeRule(rule.id)}
              disabled={disabled}
              className="ml-auto text-xs px-2 py-1 rounded-md border border-slate-200
                         text-red-600 hover:bg-red-50 transition-colors"
              title="Remove rule"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addRule}
        disabled={disabled}
        className="text-xs px-3 py-1.5 rounded-lg border border-slate-300
                   text-slate-600 hover:border-slate-400 transition-colors"
      >
        + Add rule
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field helper
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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StrategyBuilderPanel() {
  const [ticker, setTicker] = useState("SPY");
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [costStr, setCostStr] = useState("10");
  const [capitalStr, setCapitalStr] = useState("100000");

  const [entryRules, setEntryRules] = useState<UIRule[]>(DEFAULT_ENTRY);
  const [entryLogic, setEntryLogic] = useState<"all" | "any">("all");
  const [exitRules, setExitRules] = useState<UIRule[]>(DEFAULT_EXIT);
  const [exitLogic, setExitLogic] = useState<"all" | "any">("any");

  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Build + validate the request ────────────────────────────────────────
  const { request, validationMsg } = useMemo(() => {
    if (ticker.trim() === "") {
      return { request: null, validationMsg: "Enter a ticker symbol." };
    }
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const cost = parseFloatStrict(costStr);
    const capital = parseFloatStrict(capitalStr);
    if (cost === null || cost < 0) {
      return { request: null, validationMsg: "Transaction cost must be ≥ 0 bps." };
    }
    if (capital === null || capital <= 0) {
      return { request: null, validationMsg: "Initial capital must be > 0." };
    }
    if (entryRules.length === 0) {
      return { request: null, validationMsg: "Add at least one entry rule." };
    }

    const entry: CustomRule[] = [];
    for (const r of entryRules) {
      const api = ruleToApi(r);
      if (!api) return { request: null, validationMsg: "Complete all entry rule fields." };
      entry.push(api);
    }
    const exit: CustomRule[] = [];
    for (const r of exitRules) {
      const api = ruleToApi(r);
      if (!api) return { request: null, validationMsg: "Complete all exit rule fields." };
      exit.push(api);
    }

    const req: CustomStrategyRequest = {
      ticker: ticker.trim().toUpperCase(),
      start_date: startDate,
      end_date: endDate,
      transaction_cost_bps: cost,
      initial_capital: capital,
      entry_rules: entry,
      entry_logic: entryLogic,
      exit_rules: exit,
      exit_logic: exitLogic,
    };
    return { request: req, validationMsg: null as string | null };
  }, [
    ticker,
    startDate,
    endDate,
    costStr,
    capitalStr,
    entryRules,
    entryLogic,
    exitRules,
    exitLogic,
  ]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runCustomBacktest(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Custom backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  // Human-readable summary of the current rules.
  const entrySummary = entryRules
    .map((r) => `${operandLabel(r.left)} ${opSymbol(r.operator)} ${operandLabel(r.right)}`)
    .join(entryLogic === "all" ? "  AND  " : "  OR  ");
  const exitSummary = exitRules
    .map((r) => `${operandLabel(r.left)} ${opSymbol(r.operator)} ${operandLabel(r.right)}`)
    .join(exitLogic === "all" ? "  AND  " : "  OR  ");

  return (
    <div className="space-y-6">
      <div className="card p-6 space-y-6">
        {/* Universe */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Ticker">
            <input
              className={inputCls}
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Start">
            <input
              type="date"
              className={inputCls}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="End">
            <input
              type="date"
              className={inputCls}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              onChange={(e) => setCapitalStr(e.target.value)}
              disabled={loading}
            />
          </Field>
        </div>

        <RuleListEditor
          title="Entry rules — go long when…"
          rules={entryRules}
          onChange={setEntryRules}
          logic={entryLogic}
          onLogicChange={setEntryLogic}
          disabled={loading}
          emptyHint="Add at least one entry rule."
        />

        <RuleListEditor
          title="Exit rules — return to cash when…"
          rules={exitRules}
          onChange={setExitRules}
          logic={exitLogic}
          onLogicChange={setExitLogic}
          disabled={loading}
          emptyHint="No exit rules — once long, the position is held to the end."
        />

        {/* Cost + run */}
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Transaction Cost" hint="bps">
            <input
              type="number"
              className={inputCls + " w-32"}
              value={costStr}
              onChange={(e) => setCostStr(e.target.value)}
              disabled={loading}
            />
          </Field>
          <button
            type="button"
            onClick={handleRun}
            disabled={!request || loading}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600
                       hover:bg-blue-700 transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {loading ? "Running…" : "Run Strategy"}
          </button>
          {validationMsg && !loading && (
            <span className="text-xs text-slate-400">{validationMsg}</span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Custom backtest failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="text-xs text-slate-400">
              Custom · {result.transaction_cost_bps} bps · {result.num_trades} trade events
            </span>
          </div>

          <div className="card p-4 text-xs text-slate-500 space-y-1">
            <p>
              <span className="font-semibold text-slate-600">Entry:</span> {entrySummary}
            </p>
            <p>
              <span className="font-semibold text-slate-600">Exit:</span>{" "}
              {exitSummary || "— (hold once long)"}
            </p>
          </div>

          <MetricsGrid
            strategy={result.strategy_metrics}
            benchmark={result.benchmark_metrics}
            ticker={result.ticker}
            strategyLabel="Custom Strategy"
          />

          <div className="card p-6">
            <p className="section-title mb-4">Equity Curve</p>
            <EquityCurveChart data={result.equity_curve} />
          </div>

          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={result.equity_curve} />
          </div>

          <div className="card p-6">
            <p className="section-title mb-4">
              Trade Log{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.num_trades} events)
              </span>
            </p>
            <TradeTable trades={result.trades} />
          </div>
        </>
      )}
    </div>
  );
}
