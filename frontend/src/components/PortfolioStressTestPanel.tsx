"use client";

import { useMemo, useState } from "react";
import { runStressTest } from "@/lib/api";
import type { StressTestRequest, StressTestResponse } from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import ExportReportButton from "@/components/ExportReportButton";
import { buildStressTestReport } from "@/lib/reportExport";
import { fmtPct } from "@/lib/format";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

// Built-in historical stress windows.
const PRESETS: { name: string; start_date: string; end_date: string }[] = [
  { name: "COVID Crash", start_date: "2020-02-19", end_date: "2020-03-23" },
  { name: "2022 Rate Hike Drawdown", start_date: "2022-01-03", end_date: "2022-10-14" },
  { name: "2018 Q4 Selloff", start_date: "2018-09-20", end_date: "2018-12-24" },
  { name: "2011 US Debt Ceiling / Euro Crisis", start_date: "2011-07-22", end_date: "2011-10-03" },
  { name: "2008 Global Financial Crisis", start_date: "2007-10-09", end_date: "2009-03-09" },
];

interface UIScenario {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
}

let _sid = 0;
const newScenario = (s: { name: string; start_date: string; end_date: string }): UIScenario => ({
  id: `s${_sid++}`,
  ...s,
});

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

/** Diverging heatmap colour: negative → cyan, high positive → amber → red. */
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

const numCell = (v: number, positiveGood = true) => {
  const color =
    v > 0
      ? positiveGood
        ? "text-green-700"
        : "text-red-700"
      : v < 0
        ? positiveGood
          ? "text-red-700"
          : "text-green-700"
        : "text-slate-500";
  return <span className={"mono " + color}>{fmtPct(v, 1)}</span>;
};

export default function PortfolioStressTestPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [weightMode, setWeightMode] = useState<"equal" | "custom">("equal");
  const [customWeights, setCustomWeights] = useState<Record<string, string>>({});
  const [startDate, setStartDate] = useState("2007-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [capitalStr, setCapitalStr] = useState("100000");
  const [benchmarkStr, setBenchmarkStr] = useState("SPY");
  const [scenarios, setScenarios] = useState<UIScenario[]>([
    newScenario(PRESETS[0]),
    newScenario(PRESETS[1]),
  ]);

  const [result, setResult] = useState<StressTestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(0);

  const parsedTickers = useMemo(() => parseTickers(tickersStr), [tickersStr]);

  function setWeight(ticker: string, value: string) {
    setCustomWeights((w) => ({ ...w, [ticker]: value }));
  }
  function distributeEqually() {
    if (!parsedTickers.ok) return;
    const eq = String(1 / parsedTickers.tickers.length);
    setCustomWeights(Object.fromEntries(parsedTickers.tickers.map((t) => [t, eq])));
  }
  function addScenario(preset?: (typeof PRESETS)[number]) {
    setScenarios((s) => [
      ...s,
      newScenario(preset ?? { name: "Custom scenario", start_date: "2020-01-01", end_date: "2020-06-30" }),
    ]);
  }
  function updateScenario(id: string, patch: Partial<UIScenario>) {
    setScenarios((s) => s.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }
  function removeScenario(id: string) {
    setScenarios((s) => s.filter((x) => x.id !== id));
  }

  // Sum of custom weights (for the inline indicator).
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
    request: StressTestRequest | null;
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
    if (benchmarkStr.trim() === "") {
      return { request: null, validationMsg: "Enter a benchmark ticker." };
    }
    if (scenarios.length === 0) {
      return { request: null, validationMsg: "Add at least one scenario." };
    }
    for (const s of scenarios) {
      if (s.name.trim() === "") return { request: null, validationMsg: "Scenario name cannot be empty." };
      if (!s.start_date || !s.end_date || s.start_date >= s.end_date) {
        return { request: null, validationMsg: `Scenario "${s.name}": start must be before end.` };
      }
    }

    let weights: Record<string, number> | null = null;
    if (weightMode === "custom") {
      const wd: Record<string, number> = {};
      for (const t of parsedTickers.tickers) {
        const v = parseNum(customWeights[t] ?? "");
        if (v === null || v < 0) {
          return { request: null, validationMsg: "Each custom weight must be ≥ 0." };
        }
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
        transaction_cost_bps: 0,
        benchmark_ticker: benchmarkStr.trim().toUpperCase(),
        scenarios: scenarios.map((s) => ({
          name: s.name.trim(),
          start_date: s.start_date,
          end_date: s.end_date,
        })),
      },
      validationMsg: null,
    };
  }, [parsedTickers, startDate, endDate, capitalStr, benchmarkStr, scenarios, weightMode, customWeights]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runStressTest(request);
      setResult(data);
      setSelected(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test failed.");
    } finally {
      setLoading(false);
    }
  }

  const sel = result?.scenarios[selected];
  const selChart = useMemo(
    () =>
      sel
        ? sel.portfolio_equity_curve.map((p, i) => ({
            date: p.date,
            strategy: p.value,
            benchmark: sel.benchmark_equity_curve[i]?.value ?? p.value,
          }))
        : [],
    [sel],
  );
  const selTickers = result?.tickers ?? [];

  return (
    <div className="space-y-6">
      {/* Warning */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Historical scenario analysis.</span>{" "}
          These results show how a static portfolio would have moved through past
          stress windows. They do not guarantee or predict future behaviour. Not
          investment advice.
        </p>
      </div>

      {/* Inputs */}
      <div className="card p-6 space-y-5">
        <Field label="Tickers" hint="comma-separated · long-only · max 20">
          <input
            className={inputCls}
            value={tickersStr}
            onChange={(e) => setTickersStr(e.target.value)}
            placeholder="SPY, QQQ, GLD, TLT"
            disabled={loading}
          />
        </Field>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Start">
            <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="End">
            <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Initial Capital" hint="USD">
            <input type="number" className={inputCls} value={capitalStr} onChange={(e) => setCapitalStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Benchmark">
            <input className={inputCls} value={benchmarkStr} onChange={(e) => setBenchmarkStr(e.target.value)} disabled={loading} />
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
                  <span
                    className={
                      "text-xs mono " +
                      (Math.abs(customSum - 1) <= 1e-6 ? "text-green-700" : "text-red-600")
                    }
                  >
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
                  onChange={(e) => setWeight(t, e.target.value)}
                  placeholder="0.25"
                  disabled={loading}
                />
              </Field>
            ))}
          </div>
        )}

        {/* Scenarios */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Stress Scenarios</p>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => addScenario(p)}
                  disabled={loading}
                  className="text-[11px] px-2 py-1 rounded-md border border-slate-300 text-slate-600 hover:border-slate-400"
                  title={`${p.start_date} → ${p.end_date}`}
                >
                  + {p.name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => addScenario()}
                disabled={loading}
                className="text-[11px] px-2 py-1 rounded-md border border-blue-300 text-blue-700 hover:bg-blue-50"
              >
                + Custom
              </button>
            </div>
          </div>

          <div className="space-y-2">
            {scenarios.map((s) => (
              <div key={s.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 p-2">
                <input
                  className={inputCls + " flex-1 min-w-[160px]"}
                  value={s.name}
                  onChange={(e) => updateScenario(s.id, { name: e.target.value })}
                  placeholder="Scenario name"
                  disabled={loading}
                />
                <input
                  type="date"
                  className={inputCls + " w-auto"}
                  value={s.start_date}
                  onChange={(e) => updateScenario(s.id, { start_date: e.target.value })}
                  disabled={loading}
                />
                <input
                  type="date"
                  className={inputCls + " w-auto"}
                  value={s.end_date}
                  onChange={(e) => updateScenario(s.id, { end_date: e.target.value })}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => removeScenario(s.id)}
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
            {loading ? "Running…" : "Run Stress Test"}
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
            <p className="text-sm font-semibold text-red-700">Stress test failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex justify-end">
            <ExportReportButton
              getReport={(tpl) => buildStressTestReport(result, tpl)}
            />
          </div>

          {/* Scenario comparison table */}
          <div className="card p-6">
            <p className="section-title mb-4">Scenario Comparison</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2 pr-3">Scenario</th>
                    <th className="py-2 pr-3 text-right">Portfolio</th>
                    <th className="py-2 pr-3 text-right">Benchmark</th>
                    <th className="py-2 pr-3 text-right">Excess</th>
                    <th className="py-2 pr-3 text-right">Max DD</th>
                    <th className="py-2 pr-3 text-right">Bench DD</th>
                    <th className="py-2 pr-3 text-right">Worst Day</th>
                    <th className="py-2 pr-3 text-right">Best Day</th>
                    <th className="py-2 text-right">Volatility</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scenarios.map((s, i) => (
                    <tr
                      key={s.name + i}
                      onClick={() => setSelected(i)}
                      className={
                        "border-b border-slate-50 cursor-pointer transition-colors " +
                        (i === selected ? "bg-blue-50" : "hover:bg-slate-50")
                      }
                    >
                      <td className="py-2 pr-3 font-medium text-slate-800">{s.name}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.total_return)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.benchmark_total_return)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.excess_return)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.max_drawdown, false)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.benchmark_max_drawdown, false)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.worst_day_return, false)}</td>
                      <td className="py-2 pr-3 text-right">{numCell(s.best_day_return)}</td>
                      <td className="py-2 text-right mono text-slate-600">
                        {fmtPct(s.annualized_volatility, 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400 mt-2">Click a scenario row to chart it below.</p>
          </div>

          {/* Selected scenario chart + heatmap */}
          {sel && (
            <div className="card p-6 space-y-4">
              <p className="section-title">
                {sel.name}{" "}
                <span className="normal-case font-normal text-slate-400 ml-1">
                  {sel.start_date} → {sel.end_date} · portfolio vs {result.benchmark_ticker}
                </span>
              </p>
              <EquityCurveChart data={selChart} />

              <div>
                <p className="uplabel mb-2">Correlation during scenario</p>
                <div className="overflow-x-auto">
                  <table className="text-xs mono border-collapse">
                    <thead>
                      <tr>
                        <th className="p-2"></th>
                        {selTickers.map((t) => (
                          <th key={t} className="p-2 text-slate-400 font-semibold">{t}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {selTickers.map((rowT) => (
                        <tr key={rowT}>
                          <td className="p-2 text-slate-400 font-semibold text-right">{rowT}</td>
                          {selTickers.map((colT) => {
                            const c = sel.correlation_matrix[rowT][colT];
                            return (
                              <td
                                key={colT}
                                className="p-2 text-center tabular"
                                style={{ background: corrColor(c), color: "var(--text-hi)", minWidth: 52 }}
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
          )}

          {/* Full-period summary */}
          <div className="space-y-2">
            <p className="section-title">
              Full-Period Summary{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                {result.start_date} → {result.end_date}
              </span>
            </p>
            <MetricsGrid
              strategy={result.full_period_metrics}
              benchmark={result.benchmark_full_period_metrics}
              ticker={result.benchmark_ticker}
              strategyLabel="Portfolio"
            />
            <div className="card p-6">
              <p className="section-title mb-4">Full-Period Equity</p>
              <EquityCurveChart
                data={result.full_equity_curve.map((p, i) => ({
                  date: p.date,
                  strategy: p.value,
                  benchmark: result.benchmark_equity_curve[i]?.value ?? p.value,
                }))}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
