"use client";

import { useState } from "react";
import {
  ACCENT_OPTIONS,
  ANNUALIZATION_OPTIONS,
  DATE_RANGE_OPTIONS,
  applyAccent,
  loadSettings,
  resetSettings,
  saveSettings,
  type AccentColor,
  type AnnualizationConvention,
  type AppSettings,
  type DateRangeOption,
} from "@/lib/settings";
import { REPORT_TEMPLATES, type ReportTemplate } from "@/lib/reportExport";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none " +
  "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

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
      <label className="text-xs font-medium uppercase tracking-wide text-slate-600">
        {label}
        {hint && (
          <span className="ml-1 normal-case font-normal text-slate-400">{hint}</span>
        )}
      </label>
      {children}
    </div>
  );
}

export default function SettingsPanel() {
  const [initial] = useState<AppSettings>(loadSettings);

  // Numeric fields use string state so partial edits ("0.", "") don't reset.
  const [capitalStr, setCapitalStr] = useState(() =>
    String(initial.default_initial_capital),
  );
  const [costStr, setCostStr] = useState(() =>
    String(initial.default_transaction_cost_bps),
  );
  const [benchmark, setBenchmark] = useState(initial.default_benchmark_ticker);
  const [rfStr, setRfStr] = useState(() => String(initial.default_risk_free_rate));
  const [dateRange, setDateRange] = useState<DateRangeOption>(
    initial.default_date_range,
  );
  const [customStart, setCustomStart] = useState(initial.custom_start_date);
  const [customEnd, setCustomEnd] = useState(initial.custom_end_date);
  const [annualization, setAnnualization] = useState<AnnualizationConvention>(
    initial.annualization_convention,
  );
  const [accent, setAccent] = useState<AccentColor>(initial.accent_color);
  const [template, setTemplate] = useState<ReportTemplate>(
    initial.default_report_template,
  );

  const [savedFlash, setSavedFlash] = useState(false);

  // ── Validation ────────────────────────────────────────────────────────────
  const capital = Number(capitalStr);
  const cost = Number(costStr);
  const rf = Number(rfStr);
  const capitalOk = capitalStr.trim() !== "" && Number.isFinite(capital) && capital > 0;
  const costOk = costStr.trim() !== "" && Number.isFinite(cost) && cost >= 0;
  const rfOk = rfStr.trim() !== "" && Number.isFinite(rf) && rf >= 0;
  const customOk =
    dateRange !== "custom" || (customStart !== "" && customEnd !== "" && customStart < customEnd);
  const benchmarkOk = benchmark.trim().length > 0;
  const allOk = capitalOk && costOk && rfOk && customOk && benchmarkOk;

  function currentDraft(): AppSettings {
    return {
      default_initial_capital: capital,
      default_transaction_cost_bps: cost,
      default_benchmark_ticker: benchmark.trim().toUpperCase(),
      default_risk_free_rate: rf,
      default_date_range: dateRange,
      custom_start_date: customStart,
      custom_end_date: customEnd,
      annualization_convention: annualization,
      accent_color: accent,
      default_report_template: template,
    };
  }

  function applyToFields(s: AppSettings) {
    setCapitalStr(String(s.default_initial_capital));
    setCostStr(String(s.default_transaction_cost_bps));
    setBenchmark(s.default_benchmark_ticker);
    setRfStr(String(s.default_risk_free_rate));
    setDateRange(s.default_date_range);
    setCustomStart(s.custom_start_date);
    setCustomEnd(s.custom_end_date);
    setAnnualization(s.annualization_convention);
    setAccent(s.accent_color);
    setTemplate(s.default_report_template);
  }

  // Accent applies immediately (live preview) and is persisted right away so it
  // survives a reload even before "Save settings" is pressed.
  function handleAccent(next: AccentColor) {
    setAccent(next);
    applyAccent(next);
    saveSettings({ ...loadSettings(), accent_color: next });
  }

  function handleSave() {
    if (!allOk) return;
    const stored = saveSettings(currentDraft());
    applyToFields(stored);
    applyAccent(stored.accent_color);
    setSavedFlash(true);
    window.setTimeout(() => setSavedFlash(false), 2000);
  }

  function handleReset() {
    const defaults = resetSettings();
    applyToFields(defaults);
    applyAccent(defaults.accent_color);
    setSavedFlash(false);
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
        Preferences are stored locally in your browser (<span className="font-mono">localStorage</span>) — there is
        no account and no cloud sync. They prefill new forms and control display
        conventions; they don&apos;t change how the backend computes metrics.
      </div>

      {/* ── Defaults ───────────────────────────────────────────────────────── */}
      <div className="card p-5">
        <p className="section-title mb-4">Defaults</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Initial capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              min={1}
              step={1000}
              onChange={(e) => setCapitalStr(e.target.value)}
            />
            {!capitalOk && (
              <span className="text-xs text-red-500">Must be a number &gt; 0.</span>
            )}
          </Field>
          <Field label="Transaction cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={costStr}
              min={0}
              step={1}
              onChange={(e) => setCostStr(e.target.value)}
            />
            {!costOk && (
              <span className="text-xs text-red-500">Must be a number ≥ 0.</span>
            )}
          </Field>
          <Field label="Benchmark ticker">
            <input
              type="text"
              className={`${inputCls} uppercase`}
              value={benchmark}
              maxLength={12}
              onChange={(e) => setBenchmark(e.target.value.toUpperCase())}
              placeholder="SPY"
            />
            {!benchmarkOk && (
              <span className="text-xs text-red-500">Required.</span>
            )}
          </Field>
          <Field label="Risk-free rate" hint="decimal, e.g. 0.02">
            <input
              type="number"
              className={inputCls}
              value={rfStr}
              min={0}
              step={0.005}
              onChange={(e) => setRfStr(e.target.value)}
            />
            {!rfOk && (
              <span className="text-xs text-red-500">Must be a number ≥ 0.</span>
            )}
          </Field>
          <Field label="Default date range">
            <select
              className={inputCls}
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as DateRangeOption)}
            >
              {DATE_RANGE_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          {dateRange === "custom" && (
            <div className="grid grid-cols-2 gap-2">
              <Field label="Custom start">
                <input
                  type="date"
                  className={inputCls}
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                />
              </Field>
              <Field label="Custom end">
                <input
                  type="date"
                  className={inputCls}
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                />
              </Field>
            </div>
          )}
        </div>
        {!customOk && (
          <p className="mt-2 text-xs text-red-500">
            Custom start date must be before the end date.
          </p>
        )}
        <p className="mt-3 text-xs text-slate-400">
          Relative ranges resolve from today when a form loads (e.g. “Last 10
          years” → today minus 10 years).
        </p>
      </div>

      {/* ── Analytics conventions ──────────────────────────────────────────── */}
      <div className="card p-5">
        <p className="section-title mb-4">Analytics conventions</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Annualization convention">
            <select
              className={inputCls}
              value={annualization}
              onChange={(e) =>
                setAnnualization(e.target.value as AnnualizationConvention)
              }
            >
              {ANNUALIZATION_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">Applied to new runs:</span>{" "}
          single-asset Backtest and Strategy Comparison requests use this
          convention for CAGR, Calmar, volatility, Sharpe, and Sortino. It does
          not change trades, equity curves, total return, or drawdown.
          {annualization === "auto" && (
            <>
              {" "}Auto resolves recognized crypto tickers to 365 periods/year
              and otherwise falls back to 252 with a backend caveat when the
              asset class is uncertain.
            </>
          )}
          <span className="block pt-1 text-slate-400">
            Portfolio analytics remain on the existing 252 trading-day
            convention in this version.
          </span>
        </div>
      </div>

      {/* ── Appearance ─────────────────────────────────────────────────────── */}
      <div className="card p-5">
        <p className="section-title mb-4">Appearance</p>
        <Field label="Theme accent color">
          <div className="flex flex-wrap gap-2">
            {ACCENT_OPTIONS.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => handleAccent(a.id)}
                title={a.label}
                className={
                  "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors " +
                  (accent === a.id
                    ? "border-blue-500 text-slate-800 ring-2 ring-blue-500"
                    : "border-slate-300 text-slate-600 hover:border-slate-400")
                }
              >
                <span
                  className="inline-block h-3.5 w-3.5 rounded-full"
                  style={{ background: a.swatch }}
                />
                {a.label}
              </button>
            ))}
          </div>
        </Field>
        <p className="mt-2 text-xs text-slate-400">
          Applies immediately and is saved right away.
        </p>
      </div>

      {/* ── Reporting ──────────────────────────────────────────────────────── */}
      <div className="card p-5">
        <p className="section-title mb-4">Reporting</p>
        <Field label="Default report template">
          <select
            className={inputCls}
            value={template}
            onChange={(e) => setTemplate(e.target.value as ReportTemplate)}
          >
            {REPORT_TEMPLATES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <p className="mt-2 text-xs text-slate-400">
          New export panels preselect this template (where the analysis supports
          it).
        </p>
      </div>

      {/* ── Actions ────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!allOk}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white
                     transition-colors hover:bg-blue-700 disabled:cursor-not-allowed
                     disabled:opacity-50"
        >
          Save settings
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-semibold
                     text-slate-600 transition-colors hover:border-slate-400"
        >
          Reset to defaults
        </button>
        {savedFlash && (
          <span className="text-xs font-medium text-emerald-600">Saved ✓</span>
        )}
        {!allOk && (
          <span className="text-xs text-slate-400">
            Fix the highlighted fields to save.
          </span>
        )}
      </div>
    </div>
  );
}
