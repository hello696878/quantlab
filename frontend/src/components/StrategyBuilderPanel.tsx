"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createCustomStrategyTemplate,
  deleteCustomStrategyTemplate,
  exportCustomStrategyTemplate,
  getStrategyGalleryTemplate,
  getCustomStrategyTemplate,
  importCustomStrategyTemplate,
  listCustomStrategyTemplates,
  listStrategyGallery,
  runCustomBacktest,
  updateCustomStrategyTemplate,
} from "@/lib/api";
import type {
  BacktestResponse,
  CustomIndicatorName,
  CustomOperand,
  CustomOperator,
  CustomRule,
  CustomStrategyRequest,
  CustomStrategyTemplateCreate,
  CustomStrategyTemplateSummary,
  GalleryTemplate,
} from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import ExportReportButton from "@/components/ExportReportButton";
import { buildBacktestReport } from "@/lib/reportExport";
import { markChecklistStep } from "@/lib/onboarding";
import { toast } from "@/lib/toast";

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

/** Convert a list of UI rules to API rules; ok=false if any is incomplete. */
function rulesToApiList(rules: UIRule[]): { ok: boolean; api: CustomRule[] } {
  const api: CustomRule[] = [];
  for (const r of rules) {
    const a = ruleToApi(r);
    if (!a) return { ok: false, api: [] };
    api.push(a);
  }
  return { ok: true, api };
}

/** Reverse conversion: API operand → editable UI operand (strings preserved). */
function apiOperandToUi(op: CustomOperand): UIOperand {
  if (op.type === "close") return makeOperand({ kind: "close" });
  if (op.type === "constant") {
    return makeOperand({ kind: "constant", value: String(op.value) });
  }
  return makeOperand({
    kind: "indicator",
    name: op.name,
    window: String(op.params.window),
    numStd: op.params.num_std != null ? String(op.params.num_std) : "2",
  });
}

function apiRuleToUi(rule: CustomRule): UIRule {
  return {
    id: nextId(),
    left: apiOperandToUi(rule.left),
    operator: rule.operator,
    right: apiOperandToUi(rule.right),
  };
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

/** Readable label for an API operand, e.g. "SMA(50)" / "close" / "30". */
function apiOperandLabel(op: CustomOperand): string {
  if (op.type === "close") return "close";
  if (op.type === "constant") return String(op.value);
  const meta = INDICATORS.find((i) => i.id === op.name);
  const label = meta?.label ?? op.name;
  return op.params.num_std != null
    ? `${label}(${op.params.window}, ${op.params.num_std}σ)`
    : `${label}(${op.params.window})`;
}

/** Readable label for an API rule, e.g. "SMA(50) > SMA(200)". */
function apiRuleLabel(rule: CustomRule): string {
  return `${apiOperandLabel(rule.left)} ${opSymbol(rule.operator)} ${apiOperandLabel(
    rule.right,
  )}`;
}

/** "SMA + RSI Filter" → "sma-rsi-filter" (for export filenames). */
function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "template"
  );
}

/** Trigger a client-side download of a JSON object. */
function downloadJson(filename: string, obj: unknown): void {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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

// ---------------------------------------------------------------------------
// Saved template list (data comes from the backend — never faked)
// ---------------------------------------------------------------------------

function TemplateList({
  refreshKey,
  activeId,
  onLoad,
  onDeleted,
  disabled,
}: {
  refreshKey: number;
  activeId: number | null;
  onLoad: (id: number) => void;
  onDeleted: (id: number) => void;
  disabled: boolean;
}) {
  const [rows, setRows] = useState<CustomStrategyTemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [exportingId, setExportingId] = useState<number | null>(null);

  async function exportOne(id: number, name: string) {
    setExportingId(id);
    try {
      const doc = await exportCustomStrategyTemplate(id);
      const filename = `quantlab-strategy-${slugify(name)}.json`;
      downloadJson(filename, doc);
      toast.success("Template exported", filename);
    } catch (e) {
      toast.error("Export failed", e instanceof Error ? e.message : undefined);
    } finally {
      setExportingId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listCustomStrategyTemplates()
      .then((d) => !cancelled && setRows(d))
      .catch(
        (e) =>
          !cancelled &&
          setErr(e instanceof Error ? e.message : "Failed to load templates."),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  async function del(id: number, name: string) {
    if (!confirm(`Delete template "${name}"? This cannot be undone.`)) return;
    setDeletingId(id);
    try {
      await deleteCustomStrategyTemplate(id);
      setRows((p) => p.filter((r) => r.id !== id));
      onDeleted(id);
      toast.success("Template deleted", `"${name}" removed.`);
    } catch (e) {
      toast.error("Delete failed", e instanceof Error ? e.message : undefined);
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <p className="text-xs text-slate-400 px-1 py-2">Loading templates…</p>;
  }
  if (err) {
    return (
      <p className="text-xs text-red-600 px-1 py-2">⚠ {err}</p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="text-xs text-slate-400 px-1 py-2">
        No saved templates yet. Build a strategy and click “Save Template”.
      </p>
    );
  }

  return (
    <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
      {rows.map((t) => (
        <div
          key={t.id}
          className={
            "flex flex-wrap items-center gap-2 px-3 py-2 " +
            (t.id === activeId ? "bg-blue-50" : "")
          }
        >
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-slate-800 truncate">
              {t.name}
              {t.id === activeId && (
                <span className="ml-2 text-[10px] uppercase text-blue-700">loaded</span>
              )}
            </div>
            <div className="text-xs text-slate-400 truncate">
              {t.num_entry_rules} entry · {t.num_exit_rules} exit ·{" "}
              {t.entry_logic}/{t.exit_logic}
              {t.tags.length > 0 && <> · {t.tags.join(", ")}</>}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onLoad(t.id)}
            disabled={disabled}
            className="text-xs px-2.5 py-1 rounded-md border border-blue-200
                       text-blue-700 hover:bg-blue-50 transition-colors font-medium"
          >
            Load
          </button>
          <button
            type="button"
            onClick={() => exportOne(t.id, t.name)}
            disabled={disabled || exportingId === t.id}
            className="text-xs px-2.5 py-1 rounded-md border border-slate-300
                       text-slate-600 hover:border-slate-400 transition-colors font-medium
                       disabled:opacity-50"
            title="Download this template as a portable JSON file"
          >
            {exportingId === t.id ? "…" : "Export"}
          </button>
          <button
            type="button"
            onClick={() => del(t.id, t.name)}
            disabled={disabled || deletingId === t.id}
            className="text-xs px-2.5 py-1 rounded-md border border-red-200
                       text-red-600 hover:bg-red-50 transition-colors font-medium
                       disabled:opacity-50"
          >
            {deletingId === t.id ? "…" : "Delete"}
          </button>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Built-in gallery (data comes from the backend — never faked)
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  trend: "Trend",
  mean_reversion: "Mean Reversion",
  momentum: "Momentum",
};

/** One entry/exit rule block rendered as readable lines with AND/OR joiners. */
function RuleSummary({
  label,
  rules,
  logic,
}: {
  label: string;
  rules: CustomRule[];
  logic: "AND" | "OR";
}) {
  return (
    <div>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </span>
      <div className="mono text-xs text-slate-600">
        {rules.map((r, i) => (
          <div key={i}>
            {i > 0 && <span className="text-slate-400">{logic}&nbsp;</span>}
            {apiRuleLabel(r)}
          </div>
        ))}
      </div>
    </div>
  );
}

function GalleryPanel({
  onLoad,
  onSave,
  savingName,
  disabled,
}: {
  onLoad: (t: GalleryTemplate) => void;
  onSave: (t: GalleryTemplate) => void;
  savingName: string | null;
  disabled: boolean;
}) {
  const [rows, setRows] = useState<GalleryTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listStrategyGallery()
      .then((d) => !cancelled && setRows(d))
      .catch(
        (e) =>
          !cancelled &&
          setErr(e instanceof Error ? e.message : "Failed to load gallery."),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-xs text-slate-400 px-1 py-2">Loading gallery…</p>;
  }
  if (err) {
    return <p className="text-xs text-red-600 px-1 py-2">⚠ {err}</p>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      {rows.map((t) => (
        <div
          key={t.id}
          className="rounded-xl border border-slate-200 p-4 space-y-3 flex flex-col"
        >
          <div>
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-slate-800">{t.name}</h4>
              <div className="flex items-center gap-1 flex-shrink-0">
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">
                  {CATEGORY_LABELS[t.category] ?? t.category}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
                  {t.difficulty}
                </span>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-1">{t.description}</p>
          </div>

          <div className="space-y-2">
            <RuleSummary label="Entry" rules={t.entry_rules} logic={t.entry_logic} />
            <RuleSummary label="Exit" rules={t.exit_rules} logic={t.exit_logic} />
          </div>

          {t.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {t.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-2 mt-auto pt-1">
            <button
              type="button"
              onClick={() => onLoad(t)}
              disabled={disabled}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white font-semibold
                         hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              Load
            </button>
            <button
              type="button"
              onClick={() => onSave(t)}
              disabled={disabled || savingName === t.name}
              className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 text-slate-600
                         font-medium hover:border-slate-400 transition-colors disabled:opacity-50"
              title="Save a copy to your local templates"
            >
              {savingName === t.name ? "Saving…" : "Save to My Templates"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

interface StrategyBuilderPanelProps {
  /** Optional guided-demo gallery template to load on mount. */
  initialGalleryTemplateId?: string;
  /** Optional saved (My Templates) template id to load on mount. */
  initialSavedTemplateId?: number;
}

export default function StrategyBuilderPanel({
  initialGalleryTemplateId,
  initialSavedTemplateId,
}: StrategyBuilderPanelProps = {}) {
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

  // ── Template state ────────────────────────────────────────────────────────
  const [templateName, setTemplateName] = useState("");
  const [templateDesc, setTemplateDesc] = useState("");
  const [tagsStr, setTagsStr] = useState("");
  const [loadedId, setLoadedId] = useState<number | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [tplRefresh, setTplRefresh] = useState(0);
  const [savingTpl, setSavingTpl] = useState(false);
  const [tplMsg, setTplMsg] = useState<{
    kind: "info" | "error";
    text: string;
  } | null>(null);
  const [importing, setImporting] = useState(false);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [showGallery, setShowGallery] = useState(false);
  const [gallerySavingName, setGallerySavingName] = useState<string | null>(null);
  const initialGalleryLoadRef = useRef<string | null>(null);
  const initialSavedLoadRef = useRef<number | null>(null);

  /** Populate the builder from a template-like definition (gallery or saved). */
  function populateFromDefinition(def: {
    name: string;
    description: string;
    entry_logic: "AND" | "OR";
    exit_logic: "AND" | "OR";
    entry_rules: CustomRule[];
    exit_rules: CustomRule[];
    tags: string[];
  }) {
    setTemplateName(def.name);
    setTemplateDesc(def.description);
    setTagsStr(def.tags.join(", "));
    setEntryLogic(def.entry_logic === "AND" ? "all" : "any");
    setExitLogic(def.exit_logic === "AND" ? "all" : "any");
    setEntryRules(def.entry_rules.map(apiRuleToUi));
    setExitRules(def.exit_rules.map(apiRuleToUi));
    setResult(null);
    setError(null);
  }

  function handleLoadGalleryTemplate(t: GalleryTemplate) {
    populateFromDefinition(t);
    // A gallery load is a brand-new, unsaved local template.
    setLoadedId(null);
    setShowGallery(false);
    setTplMsg({
      kind: "info",
      text: `Loaded “${t.name}” from the gallery. Run it, or save it to My Templates.`,
    });
  }

  useEffect(() => {
    if (
      !initialGalleryTemplateId ||
      initialGalleryLoadRef.current === initialGalleryTemplateId
    ) {
      return;
    }

    let cancelled = false;
    initialGalleryLoadRef.current = initialGalleryTemplateId;
    setTplMsg({ kind: "info", text: "Loading guided demo template..." });

    getStrategyGalleryTemplate(initialGalleryTemplateId)
      .then((template) => {
        if (cancelled) return;
        populateFromDefinition(template);
        setLoadedId(null);
        setShowGallery(false);
        setTplMsg({
          kind: "info",
          text: `Loaded “${template.name}” demo template. Click Run Strategy to execute a real backend backtest.`,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setTplMsg({
          kind: "error",
          text:
            err instanceof Error
              ? err.message
              : "Failed to load guided demo template.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [initialGalleryTemplateId]);

  // Load a saved (My Templates) record on mount when requested (e.g. from the
  // command-palette global search).  Mirrors the gallery loader above.
  useEffect(() => {
    if (
      initialSavedTemplateId == null ||
      initialSavedLoadRef.current === initialSavedTemplateId
    ) {
      return;
    }

    let cancelled = false;
    initialSavedLoadRef.current = initialSavedTemplateId;
    setTplMsg({ kind: "info", text: "Loading saved template..." });

    getCustomStrategyTemplate(initialSavedTemplateId)
      .then((template) => {
        if (cancelled) return;
        populateFromDefinition(template);
        setLoadedId(template.id);
        setShowTemplates(false);
        setTplMsg({
          kind: "info",
          text: `Loaded “${template.name}”. Edit it, or click Run Strategy to execute a real backend backtest.`,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setTplMsg({
          kind: "error",
          text:
            err instanceof Error ? err.message : "Failed to load saved template.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [initialSavedTemplateId]);

  async function handleSaveGalleryTemplate(t: GalleryTemplate) {
    setGallerySavingName(t.name);
    setTplMsg(null);
    try {
      const created = await createCustomStrategyTemplate({
        name: t.name,
        description: t.description,
        entry_logic: t.entry_logic,
        exit_logic: t.exit_logic,
        entry_rules: t.entry_rules,
        exit_rules: t.exit_rules,
        tags: t.tags,
      });
      setTplRefresh((k) => k + 1);
      setTplMsg({ kind: "info", text: `Saved “${created.name}” to My Templates.` });
    } catch (err) {
      setTplMsg({
        kind: "error",
        text: err instanceof Error ? err.message : "Save failed.",
      });
    } finally {
      setGallerySavingName(null);
    }
  }

  function buildTemplatePayload(): CustomStrategyTemplateCreate | null {
    if (templateName.trim() === "") return null;
    const e = rulesToApiList(entryRules);
    const x = rulesToApiList(exitRules);
    if (!e.ok || !x.ok) return null;
    return {
      name: templateName.trim(),
      description: templateDesc.trim(),
      entry_logic: entryLogic === "all" ? "AND" : "OR",
      exit_logic: exitLogic === "all" ? "AND" : "OR",
      entry_rules: e.api,
      exit_rules: x.api,
      tags: tagsStr
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
  }

  const templateValid = buildTemplatePayload() !== null;

  async function handleSaveTemplate(asNew: boolean) {
    const payload = buildTemplatePayload();
    if (!payload) {
      setTplMsg({
        kind: "error",
        text: "Enter a template name and complete every rule first.",
      });
      return;
    }
    setSavingTpl(true);
    setTplMsg(null);
    try {
      if (loadedId !== null && !asNew) {
        const updated = await updateCustomStrategyTemplate(loadedId, payload);
        setTplMsg({ kind: "info", text: `Updated “${updated.name}”.` });
        toast.success("Template updated", `"${updated.name}" saved.`);
      } else {
        const created = await createCustomStrategyTemplate(payload);
        setLoadedId(created.id);
        setTplMsg({ kind: "info", text: `Saved “${created.name}”.` });
        toast.success("Template saved", `"${created.name}" added to My Templates.`);
      }
      setTplRefresh((k) => k + 1);
    } catch (err) {
      setTplMsg({
        kind: "error",
        text: err instanceof Error ? err.message : "Save failed.",
      });
      toast.error("Save failed", err instanceof Error ? err.message : undefined);
    } finally {
      setSavingTpl(false);
    }
  }

  async function handleLoadTemplate(id: number) {
    setTplMsg(null);
    try {
      const tpl = await getCustomStrategyTemplate(id);
      setTemplateName(tpl.name);
      setTemplateDesc(tpl.description);
      setTagsStr(tpl.tags.join(", "));
      setEntryLogic(tpl.entry_logic === "AND" ? "all" : "any");
      setExitLogic(tpl.exit_logic === "AND" ? "all" : "any");
      setEntryRules(tpl.entry_rules.map(apiRuleToUi));
      setExitRules(tpl.exit_rules.map(apiRuleToUi));
      setLoadedId(id);
      setResult(null);
      setError(null);
      setShowTemplates(false);
      setTplMsg({
        kind: "info",
        text: `Loaded “${tpl.name}”. Edit and run, or save changes.`,
      });
    } catch (err) {
      setTplMsg({
        kind: "error",
        text: err instanceof Error ? err.message : "Load failed.",
      });
    }
  }

  function handleNewTemplate() {
    setLoadedId(null);
    setTemplateName("");
    setTemplateDesc("");
    setTagsStr("");
    setTplMsg(null);
  }

  async function handleImportFile(file: File) {
    setImporting(true);
    setTplMsg(null);
    try {
      const text = await file.text();
      let doc: unknown;
      try {
        doc = JSON.parse(text);
      } catch {
        setTplMsg({ kind: "error", text: "That file is not valid JSON." });
        toast.warning("Import failed", "That file is not valid JSON.");
        return;
      }
      // The backend performs all schema + security validation.
      const created = await importCustomStrategyTemplate(doc);
      setTplRefresh((k) => k + 1);
      setShowTemplates(true);
      setTplMsg({
        kind: "info",
        text: `Imported “${created.name}”. Click Load to edit and run it.`,
      });
      toast.success("Template imported", `"${created.name}" added to My Templates.`);
    } catch (err) {
      setTplMsg({
        kind: "error",
        text: err instanceof Error ? err.message : "Import failed.",
      });
      toast.error("Import failed", err instanceof Error ? err.message : undefined);
    } finally {
      setImporting(false);
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

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
      markChecklistStep("built_strategy");
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
      {/* ── Strategy templates ─────────────────────────────────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <p className="section-title">Strategy Templates</p>
          <div className="flex items-center gap-2 text-xs">
            {loadedId !== null && (
              <span className="text-blue-700">Editing template #{loadedId}</span>
            )}
            <input
              ref={importInputRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleImportFile(f);
              }}
            />
            <button
              type="button"
              onClick={() => setShowGallery((s) => !s)}
              className={
                "px-2.5 py-1 rounded-md border font-medium transition-colors " +
                (showGallery
                  ? "border-blue-300 bg-blue-50 text-blue-700"
                  : "border-slate-300 text-slate-600 hover:border-slate-400")
              }
              title="Browse the built-in strategy gallery"
            >
              {showGallery ? "Hide gallery" : "Gallery"}
            </button>
            <button
              type="button"
              onClick={() => importInputRef.current?.click()}
              disabled={importing}
              className="px-2.5 py-1 rounded-md border border-slate-300 text-slate-600
                         hover:border-slate-400 transition-colors font-medium
                         disabled:opacity-50"
              title="Import a strategy template from a JSON file"
            >
              {importing ? "Importing…" : "Import Template"}
            </button>
            <button
              type="button"
              onClick={() => setShowTemplates((s) => !s)}
              className="px-2.5 py-1 rounded-md border border-slate-300 text-slate-600
                         hover:border-slate-400 transition-colors font-medium"
            >
              {showTemplates ? "Hide saved" : "Browse saved"}
            </button>
          </div>
        </div>

        {showGallery && (
          <div className="space-y-3">
            <p className="text-xs text-slate-400">
              Built-in templates — safe, validated rule definitions (not
              executable code). Load one into the builder, then run or save it.
            </p>
            <GalleryPanel
              onLoad={handleLoadGalleryTemplate}
              onSave={handleSaveGalleryTemplate}
              savingName={gallerySavingName}
              disabled={savingTpl || gallerySavingName !== null}
            />
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Field label="Template Name">
            <input
              className={inputCls}
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="e.g. SMA + RSI Trend Filter"
              disabled={savingTpl}
            />
          </Field>
          <Field label="Description" hint="optional">
            <input
              className={inputCls}
              value={templateDesc}
              onChange={(e) => setTemplateDesc(e.target.value)}
              placeholder="What this strategy does"
              disabled={savingTpl}
            />
          </Field>
          <Field label="Tags" hint="comma-separated">
            <input
              className={inputCls}
              value={tagsStr}
              onChange={(e) => setTagsStr(e.target.value)}
              placeholder="trend, rsi"
              disabled={savingTpl}
            />
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleSaveTemplate(false)}
            disabled={!templateValid || savingTpl}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold text-white bg-blue-600
                       hover:bg-blue-700 transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {savingTpl
              ? "Saving…"
              : loadedId !== null
                ? "Update Template"
                : "Save Template"}
          </button>
          {loadedId !== null && (
            <button
              type="button"
              onClick={() => handleSaveTemplate(true)}
              disabled={!templateValid || savingTpl}
              className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600
                         border border-slate-300 hover:border-slate-400 transition-colors
                         disabled:opacity-50"
            >
              Save as new
            </button>
          )}
          {loadedId !== null && (
            <button
              type="button"
              onClick={handleNewTemplate}
              disabled={savingTpl}
              className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-500
                         hover:text-slate-700 transition-colors"
            >
              Clear
            </button>
          )}
          {tplMsg && (
            <span
              className={
                "text-xs " +
                (tplMsg.kind === "error" ? "text-red-600" : "text-emerald-600")
              }
            >
              {tplMsg.text}
            </span>
          )}
        </div>

        {showTemplates && (
          <TemplateList
            refreshKey={tplRefresh}
            activeId={loadedId}
            onLoad={handleLoadTemplate}
            onDeleted={(id) => {
              if (id === loadedId) setLoadedId(null);
            }}
            disabled={savingTpl}
          />
        )}
      </div>

      {/* ── Builder ────────────────────────────────────────────────────── */}
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
            <span className="ml-auto">
              <ExportReportButton
                getReport={(tpl) =>
                  buildBacktestReport(
                    result,
                    {
                      analysisType: "Custom Strategy Backtest",
                      sourceType: "custom_strategy",
                      extraParameters: [
                        ["Entry logic", entryLogic === "all" ? "AND" : "OR"],
                        ["Entry rules", entrySummary],
                        ["Exit logic", exitLogic === "all" ? "AND" : "OR"],
                        ["Exit rules", exitSummary || "Hold once long"],
                      ],
                    },
                    tpl,
                  )
                }
              />
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
