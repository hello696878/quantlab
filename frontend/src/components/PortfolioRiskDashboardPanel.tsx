"use client";

import { useMemo, useState } from "react";
import { runRiskDashboard } from "@/lib/api";
import type { RiskDashboardResponse } from "@/lib/types";
import ExportReportButton from "@/components/ExportReportButton";
import { buildRiskDashboardReport } from "@/lib/reportExport";
import { fmtPct, fmtRatio } from "@/lib/format";
import { markChecklistStep } from "@/lib/onboarding";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
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

/**
 * Diverging heatmap colour: negative/low correlation → cyan, high positive →
 * amber → red.  Alpha scales with magnitude so the matrix reads at a glance.
 */
function corrColor(c: number): string {
  if (c >= 0) {
    // amber (251,191,36) → red (248,113,113) as c: 0 → 1
    const r = Math.round(251 + (248 - 251) * c);
    const g = Math.round(191 + (113 - 191) * c);
    const b = Math.round(36 + (113 - 36) * c);
    return `rgba(${r},${g},${b},${(0.12 + 0.6 * c).toFixed(3)})`;
  }
  const a = 0.12 + 0.6 * Math.min(1, Math.abs(c));
  return `rgba(34,211,238,${a.toFixed(3)})`; // cyan
}

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="card p-4">
      <p className="uplabel">{label}</p>
      <p className="mono text-xl font-bold mt-1" style={{ color: color ?? "var(--text-hi)" }}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function PortfolioRiskDashboardPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");

  const [result, setResult] = useState<RiskDashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { request, validationMsg } = useMemo(() => {
    const parsed = parseTickers(tickersStr);
    if (!parsed.ok) return { request: null, validationMsg: parsed.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    return {
      request: { tickers: parsed.tickers, start_date: startDate, end_date: endDate },
      validationMsg: null as string | null,
    };
  }, [tickersStr, startDate, endDate]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runRiskDashboard(request);
      setResult(data);
      markChecklistStep("viewed_risk");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Risk dashboard failed.");
    } finally {
      setLoading(false);
    }
  }

  const tickers = result?.tickers ?? [];
  const maxRC = useMemo(
    () =>
      result
        ? Math.max(...Object.values(result.risk_contribution), 1e-9)
        : 1,
    [result],
  );

  return (
    <div className="space-y-6">
      {/* Historical caveat */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Historical estimates.</span> Returns,
          volatilities, correlations, and risk contributions are estimated from
          past data over the selected window and may not persist. Not investment
          advice.
        </p>
      </div>

      {/* Inputs */}
      <div className="card p-6 space-y-5">
        <Field label="Tickers" hint="comma-separated · max 20">
          <input
            className={inputCls}
            value={tickersStr}
            onChange={(e) => setTickersStr(e.target.value)}
            placeholder="SPY, QQQ, GLD, TLT"
            disabled={loading}
          />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Start">
            <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="End">
            <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </Field>
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
            {loading ? "Computing…" : "Run Risk Dashboard"}
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
            <p className="text-sm font-semibold text-red-700">Risk dashboard failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex justify-end">
            <ExportReportButton
              getReport={(tpl) => buildRiskDashboardReport(result, tpl)}
              templates={["standard", "executive_summary", "risk_report"]}
            />
          </div>

          {/* Diagnostic cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Avg Pairwise Corr"
              value={fmtRatio(result.correlation_diagnostics.average_pairwise_correlation, 2)}
            />
            <StatCard
              label="Diversification Ratio"
              value={fmtRatio(result.equal_weight_portfolio.diversification_ratio, 2)}
              sub="weighted avg vol ÷ portfolio vol"
              color="#34d399"
            />
            <StatCard
              label="Most Correlated"
              value={
                result.correlation_diagnostics.most_correlated_pair
                  ? result.correlation_diagnostics.most_correlated_pair.join(" · ")
                  : "—"
              }
              sub={fmtRatio(result.correlation_diagnostics.max_pairwise_correlation, 2)}
              color="#f87171"
            />
            <StatCard
              label="Least Correlated"
              value={
                result.correlation_diagnostics.least_correlated_pair
                  ? result.correlation_diagnostics.least_correlated_pair.join(" · ")
                  : "—"
              }
              sub={fmtRatio(result.correlation_diagnostics.min_pairwise_correlation, 2)}
              color="#22d3ee"
            />
          </div>

          {/* Equal-weight summary */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              label="Equal-Weight Return"
              value={fmtPct(result.equal_weight_portfolio.expected_return, 1)}
            />
            <StatCard
              label="Equal-Weight Volatility"
              value={fmtPct(result.equal_weight_portfolio.volatility, 1)}
            />
            <StatCard
              label="Assets"
              value={String(tickers.length)}
              sub={tickers.join(" · ")}
            />
          </div>

          {/* Asset summary + risk contribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card p-6">
              <p className="section-title mb-4">Asset Summary</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2 pr-3">Ticker</th>
                    <th className="py-2 pr-3 text-right">Annual Return</th>
                    <th className="py-2 text-right">Annual Volatility</th>
                  </tr>
                </thead>
                <tbody className="mono">
                  {tickers.map((t) => (
                    <tr key={t} className="border-b border-slate-50">
                      <td className="py-1.5 pr-3 text-slate-700">{t}</td>
                      <td className="py-1.5 pr-3 text-right text-slate-700">
                        {fmtPct(result.asset_annual_returns[t], 1)}
                      </td>
                      <td className="py-1.5 text-right text-slate-700">
                        {fmtPct(result.asset_annual_volatilities[t], 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card p-6">
              <p className="section-title mb-4">
                Equal-Weight Risk Contribution{" "}
                <span className="normal-case font-normal text-slate-400 ml-1">
                  (% of portfolio risk)
                </span>
              </p>
              <div className="space-y-2">
                {tickers.map((t) => {
                  const rc = result.risk_contribution[t];
                  return (
                    <div key={t} className="flex items-center gap-2">
                      <span className="mono text-xs text-slate-600 w-16 flex-shrink-0">{t}</span>
                      <div className="flex-1 h-2.5 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full bg-blue-600"
                          style={{ width: `${Math.min(100, (rc / maxRC) * 100)}%` }}
                        />
                      </div>
                      <span className="mono text-xs text-slate-500 w-12 text-right flex-shrink-0">
                        {(rc * 100).toFixed(1)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Correlation heatmap */}
          <div className="card p-6">
            <p className="section-title mb-4">Correlation Matrix</p>
            <div className="overflow-x-auto">
              <table
                className="text-xs mono"
                style={{ borderCollapse: "separate", borderSpacing: 3 }}
              >
                <thead>
                  <tr>
                    <th className="p-2"></th>
                    {tickers.map((t) => (
                      <th key={t} className="p-2 text-slate-400 font-semibold">
                        {t}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tickers.map((rowT) => (
                    <tr key={rowT}>
                      <td className="p-2 text-slate-400 font-semibold text-right">{rowT}</td>
                      {tickers.map((colT) => {
                        const c = result.correlation_matrix[rowT][colT];
                        // Off-diagonal strong correlations get a neon halo:
                        // red for high positive (concentration risk), cyan for
                        // strong negative (diversifying). The diverging fill
                        // already encodes magnitude; this just draws the eye.
                        const strong = rowT !== colT && Math.abs(c) >= 0.7;
                        const halo = strong
                          ? c >= 0
                            ? "inset 0 0 12px -2px rgba(248,113,113,0.70)"
                            : "inset 0 0 12px -2px rgba(34,211,238,0.60)"
                          : undefined;
                        return (
                          <td
                            key={colT}
                            className="p-2 text-center tabular"
                            style={{
                              background: corrColor(c),
                              color: "var(--text-hi)",
                              minWidth: 52,
                              borderRadius: 7,
                              border: "1px solid rgba(255,255,255,0.05)",
                              boxShadow: halo,
                            }}
                            title={`${rowT} / ${colT}: ${c.toFixed(2)}`}
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
            <div className="flex items-center gap-2 mt-3">
              <span className="text-[10px] uppercase tracking-wide text-slate-400">Low / negative</span>
              <span
                className="h-2 w-32 rounded-full"
                style={{
                  background:
                    "linear-gradient(90deg, rgba(34,211,238,0.7), rgba(251,191,36,0.5), rgba(248,113,113,0.75))",
                }}
              />
              <span className="text-[10px] uppercase tracking-wide text-slate-400">High</span>
            </div>
          </div>

          {/* Covariance matrix (collapsible) */}
          <details className="card p-6">
            <summary className="section-title cursor-pointer select-none">
              Covariance Matrix (annualised)
            </summary>
            <div className="overflow-x-auto mt-4">
              <table className="text-xs mono border-collapse">
                <thead>
                  <tr>
                    <th className="p-2"></th>
                    {tickers.map((t) => (
                      <th key={t} className="p-2 text-slate-400 font-semibold">
                        {t}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tickers.map((rowT) => (
                    <tr key={rowT} className="border-b border-slate-50">
                      <td className="p-2 text-slate-400 font-semibold text-right">{rowT}</td>
                      {tickers.map((colT) => (
                        <td key={colT} className="p-2 text-right text-slate-600 tabular">
                          {result.covariance_matrix[rowT][colT].toFixed(4)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </div>
  );
}
