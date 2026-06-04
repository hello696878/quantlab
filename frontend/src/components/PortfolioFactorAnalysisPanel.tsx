"use client";

import { useMemo, useState } from "react";
import { runFactorAnalysis } from "@/lib/api";
import type { FactorAnalysisRequest, FactorAnalysisResponse } from "@/lib/types";
import EquityCurveChart from "@/components/EquityCurveChart";
import ExportReportButton from "@/components/ExportReportButton";
import { buildFactorAnalysisReport } from "@/lib/reportExport";
import { fmtPct, fmtRatio } from "@/lib/format";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

// Default "Core ETF Factors" preset.
const FACTOR_PRESET: { name: string; ticker: string }[] = [
  { name: "market", ticker: "SPY" },
  { name: "tech_growth", ticker: "QQQ" },
  { name: "small_cap", ticker: "IWM" },
  { name: "bonds", ticker: "TLT" },
  { name: "gold", ticker: "GLD" },
];

interface UIFactor {
  id: string;
  name: string;
  ticker: string;
}

let _fid = 0;
const newFactor = (f: { name: string; ticker: string }): UIFactor => ({ id: `f${_fid++}`, ...f });

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

function parseNum(raw: string): number | null {
  const t = raw.trim();
  if (t === "") return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

function parseTickers(raw: string): { ok: boolean; tickers: string[]; msg?: string } {
  const parts = raw
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  if (parts.length === 0) return { ok: false, tickers: [], msg: "Enter at least one ticker." };
  if (parts.length > 20) return { ok: false, tickers: [], msg: "At most 20 tickers." };
  const seen = new Set<string>();
  for (const p of parts) {
    if (seen.has(p)) return { ok: false, tickers: [], msg: `Duplicate ticker: ${p}.` };
    seen.add(p);
  }
  return { ok: true, tickers: parts };
}

function corrColor(c: number): string {
  if (c >= 0) {
    const r = Math.round(251 + (248 - 251) * c);
    const g = Math.round(191 + (113 - 191) * c);
    const b = Math.round(36 + (113 - 36) * c);
    return `rgba(${r},${g},${b},${(0.12 + 0.6 * c).toFixed(3)})`;
  }
  const a = 0.12 + 0.6 * Math.min(1, Math.abs(c));
  return `rgba(34,211,238,${a.toFixed(3)})`;
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="card p-4">
      <p className="uplabel">{label}</p>
      <p className="mono text-xl font-bold mt-1" style={{ color: color ?? "var(--text-hi)" }}>
        {value}
      </p>
    </div>
  );
}

export default function PortfolioFactorAnalysisPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [weightMode, setWeightMode] = useState<"equal" | "custom">("equal");
  const [customWeights, setCustomWeights] = useState<Record<string, string>>({});
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [capitalStr, setCapitalStr] = useState("100000");
  const [factors, setFactors] = useState<UIFactor[]>(FACTOR_PRESET.map(newFactor));

  const [result, setResult] = useState<FactorAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsedTickers = useMemo(() => parseTickers(tickersStr), [tickersStr]);

  function distributeEqually() {
    if (!parsedTickers.ok) return;
    const eq = String(1 / parsedTickers.tickers.length);
    setCustomWeights(Object.fromEntries(parsedTickers.tickers.map((t) => [t, eq])));
  }
  function loadPreset() {
    setFactors(FACTOR_PRESET.map(newFactor));
  }
  function addFactor() {
    setFactors((f) => [...f, newFactor({ name: "", ticker: "" })]);
  }
  function updateFactor(id: string, patch: Partial<UIFactor>) {
    setFactors((f) => f.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }
  function removeFactor(id: string) {
    setFactors((f) => f.filter((x) => x.id !== id));
  }

  const customSum = useMemo(() => {
    if (!parsedTickers.ok) return null;
    let sum = 0;
    for (const t of parsedTickers.tickers) {
      const v = parseNum(customWeights[t] ?? "");
      if (v === null) return null;
      sum += v;
    }
    return sum;
  }, [parsedTickers, customWeights]);

  const { request, validationMsg } = useMemo((): {
    request: FactorAnalysisRequest | null;
    validationMsg: string | null;
  } => {
    if (!parsedTickers.ok) return { request: null, validationMsg: parsedTickers.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const capital = parseNum(capitalStr);
    if (capital === null || capital <= 0) {
      return { request: null, validationMsg: "Initial capital must be > 0." };
    }

    const factor_tickers: Record<string, string> = {};
    const names = new Set<string>();
    if (factors.length === 0) return { request: null, validationMsg: "Add at least one factor." };
    if (factors.length > 10) return { request: null, validationMsg: "At most 10 factors." };
    for (const f of factors) {
      const nm = f.name.trim();
      const tk = f.ticker.trim().toUpperCase();
      if (!nm || !tk) return { request: null, validationMsg: "Each factor needs a name and ticker." };
      if (names.has(nm)) return { request: null, validationMsg: `Duplicate factor name: ${nm}.` };
      names.add(nm);
      factor_tickers[nm] = tk;
    }

    let weights: Record<string, number> | null = null;
    if (weightMode === "custom") {
      const wd: Record<string, number> = {};
      for (const t of parsedTickers.tickers) {
        const v = parseNum(customWeights[t] ?? "");
        if (v === null || v < 0) return { request: null, validationMsg: "Each custom weight must be ≥ 0." };
        wd[t] = v;
      }
      const sum = Object.values(wd).reduce((a, b) => a + b, 0);
      if (Math.abs(sum - 1) > 1e-6) {
        return { request: null, validationMsg: `Custom weights must sum to 1 (currently ${sum.toFixed(3)}).` };
      }
      weights = wd;
    }

    return {
      request: {
        tickers: parsedTickers.tickers,
        weights,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        factor_tickers,
      },
      validationMsg: null,
    };
  }, [parsedTickers, startDate, endDate, capitalStr, factors, weightMode, customWeights]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runFactorAnalysis(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Factor analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = useMemo(
    () =>
      result
        ? result.actual_equity_curve.map((p, i) => ({
            date: p.date,
            strategy: p.value,
            benchmark: result.fitted_equity_curve[i]?.value ?? p.value,
          }))
        : [],
    [result],
  );

  const factorNames = result ? Object.keys(result.factor_tickers) : [];
  const maxAbsBeta = useMemo(
    () => (result ? Math.max(...Object.values(result.betas).map((b) => Math.abs(b)), 1e-9) : 1),
    [result],
  );

  return (
    <div className="space-y-6">
      {/* Warning */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Historical factor regression.</span>{" "}
          Betas are estimated by OLS on the chosen ETF proxies over the selected
          window and depend on those choices. Highly correlated factors can make
          individual betas unstable. Not investment advice.
        </p>
      </div>

      {/* Inputs */}
      <div className="card p-6 space-y-5">
        <Field label="Portfolio Tickers" hint="comma-separated · long-only · max 20">
          <input
            className={inputCls}
            value={tickersStr}
            onChange={(e) => setTickersStr(e.target.value)}
            placeholder="SPY, QQQ, GLD, TLT"
            disabled={loading}
          />
        </Field>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Field label="Start">
            <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="End">
            <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Initial Capital" hint="USD">
            <input type="number" className={inputCls} value={capitalStr} onChange={(e) => setCapitalStr(e.target.value)} disabled={loading} />
          </Field>
        </div>

        {/* Weights mode */}
        <Field label="Weights">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs">
              {(["equal", "custom"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setWeightMode(m)}
                  disabled={loading}
                  className={
                    "px-3 py-1 rounded-md font-medium transition-colors " +
                    (weightMode === m ? "bg-blue-600 text-white" : "text-slate-500 hover:text-slate-700")
                  }
                >
                  {m === "equal" ? "Equal Weight" : "Custom Weights"}
                </button>
              ))}
            </div>
            {weightMode === "custom" && (
              <>
                <button
                  type="button"
                  onClick={distributeEqually}
                  disabled={loading}
                  className="text-xs px-2.5 py-1 rounded-md border border-slate-300 text-slate-600 hover:border-slate-400"
                >
                  Distribute equally
                </button>
                {customSum !== null && (
                  <span className={"text-xs mono " + (Math.abs(customSum - 1) <= 1e-6 ? "text-green-700" : "text-red-600")}>
                    Σ = {customSum.toFixed(3)}
                  </span>
                )}
              </>
            )}
          </div>
        </Field>

        {weightMode === "custom" && parsedTickers.ok && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {parsedTickers.tickers.map((t) => (
              <Field key={t} label={t}>
                <input
                  type="number"
                  step="0.05"
                  className={inputCls}
                  value={customWeights[t] ?? ""}
                  onChange={(e) => setCustomWeights((w) => ({ ...w, [t]: e.target.value }))}
                  placeholder="0.25"
                  disabled={loading}
                />
              </Field>
            ))}
          </div>
        )}

        {/* Factors */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Factor Proxies (ETFs)</p>
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={loadPreset}
                disabled={loading}
                className="text-[11px] px-2 py-1 rounded-md border border-slate-300 text-slate-600 hover:border-slate-400"
              >
                Core ETF Factors
              </button>
              <button
                type="button"
                onClick={addFactor}
                disabled={loading}
                className="text-[11px] px-2 py-1 rounded-md border border-blue-300 text-blue-700 hover:bg-blue-50"
              >
                + Add factor
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {factors.map((f) => (
              <div key={f.id} className="flex items-center gap-2">
                <input
                  className={inputCls + " flex-1"}
                  value={f.name}
                  onChange={(e) => updateFactor(f.id, { name: e.target.value })}
                  placeholder="factor name (e.g. market)"
                  disabled={loading}
                />
                <input
                  className={inputCls + " w-32"}
                  value={f.ticker}
                  onChange={(e) => updateFactor(f.id, { ticker: e.target.value })}
                  placeholder="ETF"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => removeFactor(f.id)}
                  disabled={loading}
                  className="text-xs px-2 py-1 rounded-md border border-red-200 text-red-600 hover:bg-red-50"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRun}
            disabled={!request || loading}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600
                       hover:bg-blue-700 transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {loading ? "Running…" : "Run Factor Analysis"}
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
            <p className="text-sm font-semibold text-red-700">Factor analysis failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex justify-end">
            <ExportReportButton
              getReport={(tpl) => buildFactorAnalysisReport(result, tpl)}
              templates={["standard", "executive_summary", "risk_report"]}
            />
          </div>

          {result.diagnostics.multicollinearity_warning && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
              ⚠ Collinear factors detected — the design matrix is rank-deficient,
              so individual betas may be unstable. Consider removing overlapping
              proxies.
            </div>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="R²" value={fmtRatio(result.r_squared, 3)} />
            <StatCard
              label="Annualized Alpha"
              value={fmtPct(result.alpha_annualized, 2)}
              color={result.alpha_annualized >= 0 ? "#34d399" : "#f87171"}
            />
            <StatCard label="Residual Volatility" value={fmtPct(result.residual_volatility, 1)} />
            <StatCard
              label="Largest Exposure"
              value={result.diagnostics.absolute_largest_exposure ?? "—"}
              color="#4d8bff"
            />
          </div>

          {/* Beta table + correlation heatmap */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card p-6">
              <p className="section-title mb-4">Factor Betas</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2 pr-3">Factor</th>
                    <th className="py-2 pr-3">ETF</th>
                    <th className="py-2 text-right">Beta</th>
                  </tr>
                </thead>
                <tbody className="mono">
                  {factorNames.map((name) => {
                    const beta = result.betas[name];
                    return (
                      <tr key={name} className="border-b border-slate-50">
                        <td className="py-1.5 pr-3 text-slate-700">{name}</td>
                        <td className="py-1.5 pr-3 text-slate-500">{result.factor_tickers[name]}</td>
                        <td className="py-1.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-1.5 w-20 rounded-full bg-slate-100 overflow-hidden">
                              <div
                                className="h-full"
                                style={{
                                  width: `${(Math.abs(beta) / maxAbsBeta) * 100}%`,
                                  background: beta >= 0 ? "#34d399" : "#f87171",
                                  marginLeft: "auto",
                                }}
                              />
                            </div>
                            <span className={beta >= 0 ? "text-green-700" : "text-red-700"}>
                              {fmtRatio(beta, 2)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="card p-6">
              <p className="section-title mb-4">Factor Correlation</p>
              <div className="overflow-x-auto">
                <table className="text-xs mono border-collapse">
                  <thead>
                    <tr>
                      <th className="p-2"></th>
                      {factorNames.map((t) => (
                        <th key={t} className="p-2 text-slate-400 font-semibold">{t}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {factorNames.map((rowT) => (
                      <tr key={rowT}>
                        <td className="p-2 text-slate-400 font-semibold text-right">{rowT}</td>
                        {factorNames.map((colT) => {
                          const c = result.factor_correlation_matrix[rowT][colT];
                          return (
                            <td
                              key={colT}
                              className="p-2 text-center tabular"
                              style={{ background: corrColor(c), color: "var(--text-hi)", minWidth: 48 }}
                              title={`${rowT}/${colT}: ${c.toFixed(2)}`}
                            >
                              {c.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Actual vs fitted equity */}
          <div className="card p-6">
            <p className="section-title mb-4">
              Actual vs Fitted Equity{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                (fitted = factor model prediction)
              </span>
            </p>
            <EquityCurveChart data={chartData} />
          </div>
        </>
      )}
    </div>
  );
}
