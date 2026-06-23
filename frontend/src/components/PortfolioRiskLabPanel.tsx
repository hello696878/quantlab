"use client";

/**
 * Portfolio Risk Lab v1 (Phase 21.0).
 *
 * Deterministic static-sample portfolio analytics: expected return, volatility,
 * Sharpe, covariance/correlation, marginal & component risk contributions,
 * historical VaR/CVaR, stress P&L, a deterministic efficient frontier, the
 * minimum-variance portfolio, and a basic risk-parity portfolio.
 *
 * All numbers come from the backend static-sample API — no live data, not
 * investment advice, not a production risk engine.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import MetricCard from "@/components/MetricCard";
import {
  analyzePortfolio,
  fetchSamplePortfolio,
  num,
  pct,
  PORTFOLIO_FORMULAS,
  type PortfolioAnalysisResponse,
  type PortfolioAsset,
  type SamplePortfolioResponse,
} from "@/lib/portfolioRisk";

const CONFIDENCE_OPTIONS = [0.9, 0.95, 0.99];

function changeColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

/** Diverging colour for a correlation cell (−1 red · 0 neutral · +1 green). */
function corrColor(v: number): string {
  const t = Math.max(-1, Math.min(1, v));
  if (t >= 0) return `color-mix(in oklch, var(--pos) ${Math.round(t * 55)}%, transparent)`;
  return `color-mix(in oklch, var(--neg) ${Math.round(-t * 55)}%, transparent)`;
}

// --------------------------------------------------------------------------- //
// Efficient frontier scatter (dependency-free SVG)
// --------------------------------------------------------------------------- //
function FrontierChart({ result }: { result: PortfolioAnalysisResponse }) {
  const w = 560;
  const h = 300;
  const pad = { l: 52, r: 16, t: 16, b: 40 };
  const pts = result.efficient_frontier;
  const markers = [
    { label: "Current", vol: result.volatility, ret: result.expected_return, color: "var(--accent)" },
    {
      label: "Min variance",
      vol: result.min_variance_portfolio.volatility,
      ret: result.min_variance_portfolio.expected_return,
      color: "var(--emerald)",
    },
    {
      label: "Risk parity",
      vol: result.risk_parity_portfolio.volatility,
      ret: result.risk_parity_portfolio.expected_return,
      color: "var(--warn)",
    },
  ];
  const xs = [...pts.map((p) => p.volatility), ...markers.map((m) => m.vol)];
  const ys = [...pts.map((p) => p.expected_return), ...markers.map((m) => m.ret)];
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const sx = (v: number) => pad.l + ((v - xMin) / xSpan) * (w - pad.l - pad.r);
  const sy = (v: number) => h - pad.b - ((v - yMin) / ySpan) * (h - pad.t - pad.b);

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Efficient frontier scatter">
        {/* axes */}
        <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="var(--line)" />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={h - pad.b} stroke="var(--line)" />
        {/* frontier candidate points */}
        {pts.map((p, i) => (
          <circle key={i} cx={sx(p.volatility)} cy={sy(p.expected_return)} r={2.5} fill="var(--text-faint)" opacity={0.7} />
        ))}
        {/* named-portfolio markers */}
        {markers.map((m) => (
          <g key={m.label}>
            <circle cx={sx(m.vol)} cy={sy(m.ret)} r={6} fill={m.color} stroke="rgba(0,0,0,0.4)" />
          </g>
        ))}
        {/* axis labels */}
        <text x={(pad.l + w - pad.r) / 2} y={h - 8} textAnchor="middle" fontSize="11" fill="var(--text-mut)">
          Volatility (annual)
        </text>
        <text x={14} y={(pad.t + h - pad.b) / 2} textAnchor="middle" fontSize="11" fill="var(--text-mut)" transform={`rotate(-90 14 ${(pad.t + h - pad.b) / 2})`}>
          Expected return
        </text>
        {/* corner ticks */}
        <text x={pad.l} y={h - pad.b + 14} fontSize="9" fill="var(--text-faint)">{pct(xMin, 1)}</text>
        <text x={w - pad.r} y={h - pad.b + 14} textAnchor="end" fontSize="9" fill="var(--text-faint)">{pct(xMax, 1)}</text>
        <text x={pad.l - 6} y={h - pad.b} textAnchor="end" fontSize="9" fill="var(--text-faint)">{pct(yMin, 1)}</text>
        <text x={pad.l - 6} y={pad.t + 8} textAnchor="end" fontSize="9" fill="var(--text-faint)">{pct(yMax, 1)}</text>
      </svg>
      <div className="mt-1 flex flex-wrap gap-3">
        {markers.map((m) => (
          <span key={m.label} className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: m.color }} />
            {m.label} · σ {pct(m.vol, 1)} · μ {pct(m.ret, 1)}
          </span>
        ))}
        <span className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
          <span className="h-2 w-2 rounded-full" style={{ background: "var(--text-faint)" }} />
          Long-only candidate portfolios
        </span>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Main panel
// --------------------------------------------------------------------------- //
export default function PortfolioRiskLabPanel() {
  const [sample, setSample] = useState<SamplePortfolioResponse | null>(null);
  const [assets, setAssets] = useState<PortfolioAsset[]>([]);
  const [weightStr, setWeightStr] = useState<Record<string, string>>({});
  const [riskFree, setRiskFree] = useState(0.02);
  const [confidence, setConfidence] = useState(0.95);
  const [result, setResult] = useState<PortfolioAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Load the deterministic sample portfolio on mount.
  useEffect(() => {
    const ctrl = new AbortController();
    fetchSamplePortfolio(ctrl.signal)
      .then((s) => {
        setSample(s);
        setAssets(s.assets);
        setWeightStr(Object.fromEntries(s.assets.map((a) => [a.id, String(a.weight)])));
        setRiskFree(s.risk_free_rate);
        setConfidence(s.confidence_level);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample portfolio.");
      });
    return () => ctrl.abort();
  }, []);

  // Parsed weights (invalid → 0) and whether the portfolio is analysable.
  const parsedWeights = useMemo(() => {
    const out: Record<string, number> = {};
    let sum = 0;
    for (const a of assets) {
      const v = Number.parseFloat(weightStr[a.id] ?? "");
      const w = Number.isFinite(v) ? v : 0;
      out[a.id] = w;
      sum += w;
    }
    return { out, sum };
  }, [assets, weightStr]);

  // Auto-run analysis (debounced) whenever weights / rf / confidence change.
  const reqKey = `${JSON.stringify(parsedWeights.out)}|${riskFree}|${confidence}`;
  useEffect(() => {
    if (!sample || assets.length === 0) return;
    if (parsedWeights.sum <= 0) {
      setResult(null);
      setAnalyzeError("Weights must sum to a positive number.");
      return;
    }
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzePortfolio(
        {
          assets: assets.map((a) => ({ ...a, weight: parsedWeights.out[a.id] ?? 0 })),
          risk_free_rate: riskFree,
          confidence_level: confidence,
          stress_scenario: sample.stress_scenario,
        },
        ctrl.signal,
      )
        .then((r) => {
          setResult(r);
          setAnalyzeError(null);
        })
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setAnalyzeError(e instanceof Error ? e.message : "Analysis failed.");
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey, sample, assets]);

  function normalizeWeights() {
    const sum = parsedWeights.sum;
    if (sum <= 0) return;
    setWeightStr(Object.fromEntries(assets.map((a) => [a.id, (parsedWeights.out[a.id] / sum).toFixed(4)])));
  }

  function resetSample() {
    if (!sample) return;
    setWeightStr(Object.fromEntries(sample.assets.map((a) => [a.id, String(a.weight)])));
    setRiskFree(sample.risk_free_rate);
    setConfidence(sample.confidence_level);
  }

  async function copyFormulas() {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(PORTFOLIO_FORMULAS);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // no-op; the formulas are visible in the panel for manual copy
    }
  }

  const order = result?.asset_order ?? assets.map((a) => a.id);
  const tickerOf = (id: string) => assets.find((a) => a.id === id)?.ticker ?? id;

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Portfolio Risk Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              Portfolio Risk Lab
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Analyse a sample portfolio&apos;s expected return, volatility, Sharpe, VaR/CVaR,
              risk contributions, stress scenarios, and simple frontier portfolios using
              deterministic illustrative data. Edit the weights to see every metric update.
            </p>
          </div>
          <span
            className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {result?.disclaimer ??
            "Static illustrative sample data. Portfolio analytics are educational and not investment advice."}
        </p>
      </div>

      {analyzeError && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        {/* ── Weights editor ─────────────────────────────────────────────── */}
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="section-title">Portfolio weights</p>
            <span className="mono text-[11px]" style={{ color: changeColor(parsedWeights.sum - 1) }}>
              Σ {pct(parsedWeights.sum, 1)}
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            {assets.map((a) => (
              <div key={a.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>{a.name}</span>
                  <span className="mono block truncate text-[10px]" style={{ color: "var(--text-mut)" }}>
                    {a.ticker} · {a.asset_class} · μ {pct(a.expected_return, 1)} · σ {pct(a.volatility, 1)}
                  </span>
                </span>
                <input
                  type="number"
                  step="0.01"
                  inputMode="decimal"
                  aria-label={`Weight for ${a.name}`}
                  value={weightStr[a.id] ?? ""}
                  onChange={(e) => setWeightStr((w) => ({ ...w, [a.id]: e.target.value }))}
                  className="ql-input w-20 px-2 py-1 text-right text-sm"
                />
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={normalizeWeights}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
              style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
            >
              Normalize weights
            </button>
            <button
              type="button"
              onClick={resetSample}
              className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
              style={{ border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              Reset sample
            </button>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <label className="block">
              <span className="section-title">Risk-free rate</span>
              <input
                type="number"
                step="0.005"
                inputMode="decimal"
                aria-label="Risk-free rate (annual, decimal)"
                value={riskFree}
                onChange={(e) => setRiskFree(Number.parseFloat(e.target.value) || 0)}
                className="ql-input mt-1 w-full px-2 py-1 text-sm"
              />
            </label>
            <label className="block">
              <span className="section-title">Confidence</span>
              <select
                aria-label="VaR/CVaR confidence level"
                value={confidence}
                onChange={(e) => setConfidence(Number.parseFloat(e.target.value))}
                className="ql-input mt-1 w-full px-2 py-1 text-sm"
              >
                {CONFIDENCE_OPTIONS.map((c) => (
                  <option key={c} value={c}>{pct(c, 0)}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {/* ── Key metrics + frontier ─────────────────────────────────────── */}
        <div className="space-y-5">
          <div className="card p-4">
            <p className="section-title mb-2">Key metrics</p>
            {result ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                <MetricCard label="Expected return" value={pct(result.expected_return)} tone="accent" />
                <MetricCard label="Volatility" value={pct(result.volatility)} />
                <MetricCard label="Sharpe" value={num(result.sharpe_ratio, 2)} tone={result.sharpe_ratio >= 0 ? "positive" : "danger"} />
                <MetricCard label={`VaR ${pct(confidence, 0)} (mo.)`} value={pct(result.historical_var)} tone="warn" />
                <MetricCard label={`CVaR ${pct(confidence, 0)} (mo.)`} value={pct(result.historical_cvar)} tone="danger" />
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--text-mut)" }}>Computing analytics…</p>
            )}
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Efficient frontier</p>
            {result ? (
              <FrontierChart result={result} />
            ) : (
              <p className="text-sm" style={{ color: "var(--text-mut)" }}>Computing frontier…</p>
            )}
          </div>
        </div>
      </div>

      {result && (
        <>
          {/* ── Risk contributions ───────────────────────────────────────── */}
          <div className="card p-4">
            <p className="section-title mb-2">Risk contributions</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Weight</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Marginal</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Component</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">% Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {result.asset_risk_contributions.map((c) => (
                    <tr key={c.id} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{c.name}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(c.weight)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(c.marginal_contribution, 4)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(c.component_contribution, 4)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{pct(c.percent_contribution, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Correlation + covariance ─────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <div className="card p-4">
              <p className="section-title mb-2">Correlation matrix</p>
              <div className="overflow-x-auto">
                <table className="mono w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="px-1.5 py-1" />
                      {order.map((id) => (
                        <th key={id} className="px-1.5 py-1 text-center" style={{ color: "var(--text-mut)" }}>{tickerOf(id)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.correlation_matrix.map((row, i) => (
                      <tr key={order[i]}>
                        <td className="px-1.5 py-1 font-semibold" style={{ color: "var(--text-mut)" }}>{tickerOf(order[i])}</td>
                        {row.map((v, j) => (
                          <td key={j} className="px-1.5 py-1 text-center" style={{ background: corrColor(v), color: "var(--text-hi)" }}>
                            {v.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card p-4">
              <p className="section-title mb-2">Covariance matrix (annual)</p>
              <div className="overflow-x-auto">
                <table className="mono w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="px-1.5 py-1" />
                      {order.map((id) => (
                        <th key={id} className="px-1.5 py-1 text-center" style={{ color: "var(--text-mut)" }}>{tickerOf(id)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.covariance_matrix.map((row, i) => (
                      <tr key={order[i]}>
                        <td className="px-1.5 py-1 font-semibold" style={{ color: "var(--text-mut)" }}>{tickerOf(order[i])}</td>
                        {row.map((v, j) => (
                          <td key={j} className="px-1.5 py-1 text-center" style={{ color: "var(--text-hi)" }}>{v.toFixed(3)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* ── Named portfolios + stress ────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="card p-4">
              <p className="section-title mb-2">Frontier portfolios</p>
              <div className="space-y-2">
                {[result.min_variance_portfolio, result.risk_parity_portfolio].map((p) => (
                  <div key={p.label} className="rounded-lg p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                    <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{p.label}</p>
                    <p className="mono mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                      μ {pct(p.expected_return)} · σ {pct(p.volatility)} · Sharpe {num(p.sharpe, 2)}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {order.map((id) => (
                        <span key={id} className="mono rounded px-1.5 py-0.5 text-[10px]" style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}>
                          {tickerOf(id)} {pct(p.weights[id] ?? 0, 0)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {result.stress_result && (
              <div className="card p-4">
                <p className="section-title mb-2">Stress scenario</p>
                <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{result.stress_result.name}</p>
                {sample?.stress_scenario?.description && (
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-mut)" }}>{sample.stress_scenario.description}</p>
                )}
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: "var(--text-mut)" }}>
                        <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                        <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Shock</th>
                        <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {order.map((id) => {
                        const shock = sample?.stress_scenario?.shocks[id] ?? 0;
                        const pnl = result.stress_result?.asset_pnl[id] ?? 0;
                        return (
                          <tr key={id} style={{ borderTop: "1px solid var(--line)" }}>
                            <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{tickerOf(id)}</td>
                            <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(shock) }}>{pct(shock)}</td>
                            <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(pnl) }}>{pct(pnl)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-2 flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                  <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>Estimated portfolio impact</span>
                  <span className="mono text-sm font-bold" style={{ color: changeColor(result.stress_result.portfolio_pnl) }}>
                    {pct(result.stress_result.portfolio_pnl)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Explanation ──────────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="section-title">Formulas &amp; notes</p>
          <button
            type="button"
            onClick={copyFormulas}
            aria-label="Copy the formula reference"
            className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
            style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
          >
            {copied ? "Copied ✓" : "📋 Copy formulas"}
          </button>
        </div>
        <pre className="mono overflow-x-auto rounded-lg p-3 text-[11px] leading-relaxed" style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
          {PORTFOLIO_FORMULAS}
        </pre>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Why this matters</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>Volatility and Sharpe summarise risk-adjusted return at the portfolio level.</li>
              <li>Risk contributions show which assets actually drive portfolio risk — not just which have the largest weights.</li>
              <li>VaR/CVaR quantify tail loss; CVaR captures the average severity beyond the VaR threshold.</li>
              <li>The frontier, minimum-variance, and risk-parity portfolios illustrate different objectives.</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Limitations</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>Static illustrative sample data — not live, not a forecast, not advice.</li>
              <li>Long-only v1; covariance ties stated annual volatilities to the sample correlation.</li>
              <li>Historical VaR/CVaR are a monthly-horizon example from a short sample series.</li>
              <li>The efficient frontier is a deterministic sample demonstration, not an optimiser guarantee.</li>
              <li>Not a production risk engine.</li>
            </ul>
          </div>
        </div>
        {result?.notes && (
          <ul className="mt-3 space-y-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {result.notes.map((n) => (
              <li key={n}>• {n}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
