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
  type MonteCarloSummary,
  type PortfolioAnalysisResponse,
  type PortfolioAsset,
  type SamplePortfolioResponse,
} from "@/lib/portfolioRisk";
import FormulaReference from "@/components/math/FormulaReference";
import { PORTFOLIO_RISK_FORMULA_GROUPS } from "@/components/math/portfolioRiskFormulas";

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

/** Diverging colour for a beta/exposure cell scaled by the matrix's max |value|. */
function betaColor(v: number, scale: number): string {
  const t = scale > 0 ? Math.max(-1, Math.min(1, v / scale)) : 0;
  if (t >= 0) return `color-mix(in oklch, var(--pos) ${Math.round(t * 50)}%, transparent)`;
  return `color-mix(in oklch, var(--neg) ${Math.round(-t * 50)}%, transparent)`;
}

/** Factor ids highlighted in the compact "Portfolio factor exposure" strip. */
const KEY_FACTORS = ["equity_market", "rates", "credit", "fx_dollar", "commodity", "volatility"];

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
// Monte Carlo fan chart (dependency-free SVG)
// --------------------------------------------------------------------------- //
function FanChart({ mc }: { mc: MonteCarloSummary }) {
  const w = 560;
  const h = 240;
  const pad = { l: 56, r: 12, t: 12, b: 28 };
  const pts = mc.fan_chart_points;
  if (pts.length < 2) return null;
  const maxDay = pts[pts.length - 1].day || 1;
  const lows = pts.map((p) => p.p05);
  const highs = pts.map((p) => p.p95);
  const yMin = Math.min(...lows, mc.initial_value);
  const yMax = Math.max(...highs);
  const ySpan = yMax - yMin || 1;
  const sx = (d: number) => pad.l + (d / maxDay) * (w - pad.l - pad.r);
  const sy = (v: number) => h - pad.b - ((v - yMin) / ySpan) * (h - pad.t - pad.b);
  const area = (top: (p: typeof pts[number]) => number, bot: (p: typeof pts[number]) => number) => {
    const up = pts.map((p) => `${sx(p.day).toFixed(1)},${sy(top(p)).toFixed(1)}`).join(" ");
    const down = [...pts].reverse().map((p) => `${sx(p.day).toFixed(1)},${sy(bot(p)).toFixed(1)}`).join(" ");
    return `${up} ${down}`;
  };
  const line = (f: (p: typeof pts[number]) => number) =>
    pts.map((p) => `${sx(p.day).toFixed(1)},${sy(f(p)).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Monte Carlo wealth fan chart">
      <polygon points={area((p) => p.p95, (p) => p.p05)} fill="var(--accent)" opacity={0.12} />
      <polygon points={area((p) => p.p75, (p) => p.p25)} fill="var(--accent)" opacity={0.2} />
      <polyline points={line((p) => p.median)} fill="none" stroke="var(--accent)" strokeWidth={1.8} />
      <line x1={pad.l} y1={sy(mc.initial_value)} x2={w - pad.r} y2={sy(mc.initial_value)} stroke="var(--text-faint)" strokeDasharray="3 3" />
      <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="var(--line)" />
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={h - pad.b} stroke="var(--line)" />
      <text x={pad.l - 6} y={pad.t + 8} textAnchor="end" fontSize="9" fill="var(--text-faint)">{Math.round(yMax).toLocaleString()}</text>
      <text x={pad.l - 6} y={h - pad.b} textAnchor="end" fontSize="9" fill="var(--text-faint)">{Math.round(yMin).toLocaleString()}</text>
      <text x={w - pad.r} y={h - pad.b + 14} textAnchor="end" fontSize="9" fill="var(--text-faint)">day {maxDay}</text>
      <text x={(pad.l + w - pad.r) / 2} y={h - 4} textAnchor="middle" fontSize="10" fill="var(--text-mut)">Wealth paths · p05–p95 band, median line</text>
    </svg>
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
  const [scenarioId, setScenarioId] = useState("equity_selloff");
  const [maxWeightStr, setMaxWeightStr] = useState("0.40");
  const [targetReturnStr, setTargetReturnStr] = useState("");
  const [targetVolStr, setTargetVolStr] = useState("");
  const [compareId, setCompareId] = useState("max_sharpe");
  const [simHorizon, setSimHorizon] = useState(252);
  const [simPaths, setSimPaths] = useState(500);
  const [simSeed, setSimSeed] = useState(42);

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

  // Optimization constraints (long-only box + optional targets).
  const maxWeightNum = (() => {
    const v = Number.parseFloat(maxWeightStr);
    return Number.isFinite(v) && v > 0 && v <= 1 ? v : 0.4;
  })();
  const targetReturnNum = (() => {
    const v = Number.parseFloat(targetReturnStr);
    return Number.isFinite(v) ? v : undefined;
  })();
  const targetVolNum = (() => {
    const v = Number.parseFloat(targetVolStr);
    return Number.isFinite(v) && v > 0 ? v : undefined;
  })();

  // Auto-run analysis (debounced) whenever inputs change.
  const reqKey = `${JSON.stringify(parsedWeights.out)}|${riskFree}|${confidence}|${maxWeightNum}|${targetReturnNum}|${targetVolNum}|${simHorizon}|${simPaths}|${simSeed}`;
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
          optimization_constraints: {
            max_weight: maxWeightNum,
            target_return: targetReturnNum ?? null,
            target_volatility: targetVolNum ?? null,
          },
          simulation_config: {
            horizon_days: simHorizon,
            num_paths: simPaths,
            seed: simSeed,
            method: "parametric_gaussian",
          },
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

  const order = result?.asset_order ?? assets.map((a) => a.id);
  const tickerOf = (id: string) => assets.find((a) => a.id === id)?.ticker ?? id;
  const factorShort: Record<string, string> = {
    equity_market: "Eq Mkt",
    size: "Size",
    value: "Value",
    momentum: "Mom",
    rates: "Rates",
    credit: "Credit",
    fx_dollar: "USD",
    commodity: "Comm",
    volatility: "Vol",
  };
  const selectedScenario =
    result?.scenario_results.find((s) => s.scenario_id === scenarioId) ??
    result?.scenario_results[0] ??
    null;

  // Optimization / Black-Litterman derived views.
  const opt = result?.optimization_results ?? null;
  const bl = result?.black_litterman ?? null;
  const optRows = opt
    ? [
        opt.current_portfolio,
        opt.max_sharpe_portfolio,
        opt.min_variance_portfolio,
        opt.risk_parity_portfolio,
        opt.equal_weight_portfolio,
        ...(opt.target_return_portfolio ? [opt.target_return_portfolio] : []),
        ...(opt.target_volatility_portfolio ? [opt.target_volatility_portfolio] : []),
      ]
    : [];
  const compareTargets =
    opt && bl
      ? [
          { id: "max_sharpe", label: "Max Sharpe", weights: opt.max_sharpe_portfolio.weights },
          { id: "min_variance", label: "Min variance", weights: opt.min_variance_portfolio.weights },
          { id: "risk_parity", label: "Risk parity", weights: opt.risk_parity_portfolio.weights },
          { id: "black_litterman", label: "Black-Litterman", weights: bl.bl_optimized_portfolio.weights },
        ]
      : [];
  const selectedCompare = compareTargets.find((c) => c.id === compareId) ?? compareTargets[0] ?? null;
  const largestWeight = (weights: Record<string, number>): string => {
    const entries = Object.entries(weights);
    if (entries.length === 0) return "—";
    const [id, v] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
    return `${tickerOf(id)} ${pct(v, 0)}`;
  };

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

          {/* ── Factor exposure matrix ───────────────────────────────────── */}
          <div className="card p-4">
            <p className="section-title mb-1">Factor exposure</p>
            <p className="mb-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Deterministic illustrative betas (not estimated from live data).
            </p>
            <div className="overflow-x-auto">
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="px-1.5 py-1 text-left" style={{ color: "var(--text-mut)" }}>Asset</th>
                    {result.factor_order.map((fid) => (
                      <th key={fid} className="px-1.5 py-1 text-center" style={{ color: "var(--text-mut)" }}>{factorShort[fid] ?? fid}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.factor_exposures.map((row, i) => {
                    const scale = Math.max(1, ...result.factor_exposures.flat().map((x) => Math.abs(x)));
                    return (
                      <tr key={order[i]}>
                        <td className="px-1.5 py-1 font-semibold" style={{ color: "var(--text-hi)" }}>{tickerOf(order[i])}</td>
                        {row.map((v, j) => (
                          <td key={j} className="px-1.5 py-1 text-center" style={{ background: betaColor(v, scale), color: "var(--text-hi)" }}>
                            {v.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Portfolio factor exposure + factor risk decomposition ────── */}
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <div className="card p-4">
              <p className="section-title mb-2">Portfolio factor exposure</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {KEY_FACTORS.map((fid) => {
                  const fx = result.portfolio_factor_exposure.find((p) => p.factor_id === fid);
                  if (!fx) return null;
                  return <MetricCard key={fid} label={`${fx.name} β`} value={num(fx.exposure, 2)} tone={fx.exposure >= 0 ? "accent" : "danger"} />;
                })}
              </div>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Portfolio beta to each factor = Bᵀw (weighted asset betas).
              </p>
            </div>

            <div className="card p-4">
              <p className="section-title mb-2">Factor risk decomposition</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--text-mut)" }}>
                      <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Factor</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exposure</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Vol contrib</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">% Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.portfolio_factor_exposure.map((fx) => (
                      <tr key={fx.factor_id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{fx.name}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(fx.exposure, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(fx.contribution_to_volatility, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{pct(fx.percent_risk_contribution, 1)}</td>
                      </tr>
                    ))}
                    <tr style={{ borderTop: "2px solid var(--line)" }}>
                      <td className="px-2 py-1.5 font-semibold" style={{ color: "var(--text-hi)" }}>Specific (idiosyncratic)</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>—</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(result.specific_risk_contribution.contribution_to_volatility, 2)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{pct(result.specific_risk_contribution.percent_risk_contribution, 1)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Variance-share convention: factor % + specific % = 100%. Model vol ≈ {pct(result.factor_model.model_volatility, 1)}.
              </p>
            </div>
          </div>

          {/* ── Scenario stress ──────────────────────────────────────────── */}
          <div className="card p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="section-title">Scenario stress</p>
              <div className="flex flex-wrap gap-1.5">
                {result.scenario_library.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setScenarioId(s.id)}
                    aria-pressed={selectedScenario?.scenario_id === s.id}
                    className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                    style={{
                      background: selectedScenario?.scenario_id === s.id ? "var(--accent-softer)" : "var(--glass)",
                      border: `1px solid ${selectedScenario?.scenario_id === s.id ? "var(--accent-line)" : "var(--line)"}`,
                      color: selectedScenario?.scenario_id === s.id ? "var(--accent-text)" : "var(--text-hi)",
                    }}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
            {selectedScenario && (
              <>
                {(() => {
                  const def = result.scenario_library.find((s) => s.id === selectedScenario.scenario_id);
                  return def ? <p className="mb-2 text-xs" style={{ color: "var(--text-mut)" }}>{def.description}</p> : null;
                })()}
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <div className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                    <span className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Portfolio impact</span>
                    <p className="mono text-lg font-bold" style={{ color: changeColor(selectedScenario.portfolio_return_impact) }}>
                      {pct(selectedScenario.portfolio_return_impact)}
                    </p>
                  </div>
                  <span className="text-xs" style={{ color: "var(--text-mut)" }}>
                    Worst: <span className="font-semibold" style={{ color: "var(--neg)" }}>{tickerOf(selectedScenario.worst_asset)}</span>
                    {"  ·  "}Best: <span className="font-semibold" style={{ color: "var(--pos)" }}>{tickerOf(selectedScenario.best_asset)}</span>
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div>
                    <p className="section-title mb-1">Asset impact</p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr style={{ color: "var(--text-mut)" }}>
                            <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                            <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Impact</th>
                            <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Contribution</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedScenario.asset_impact.map((ai) => (
                            <tr key={ai.asset_id} style={{ borderTop: "1px solid var(--line)" }}>
                              <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{tickerOf(ai.asset_id)}</td>
                              <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(ai.impact) }}>{pct(ai.impact)}</td>
                              <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(ai.contribution) }}>{pct(ai.contribution)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div>
                    <p className="section-title mb-1">Factor impact</p>
                    {selectedScenario.factor_impact.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr style={{ color: "var(--text-mut)" }}>
                              <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Factor</th>
                              <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Shock</th>
                              <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Impact</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedScenario.factor_impact.map((fi) => (
                              <tr key={fi.factor_id} style={{ borderTop: "1px solid var(--line)" }}>
                                <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{fi.name}</td>
                                <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(fi.shock) }}>{pct(fi.shock)}</td>
                                <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(fi.impact) }}>{pct(fi.impact)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: "var(--text-mut)" }}>No factor shocks in this scenario.</p>
                    )}
                    <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
                      Factor impact = portfolio beta × factor shock; asset-specific shocks (if any) are shown only on the assets, so there is no double counting.
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* ── Optimization Lab ─────────────────────────────────────────── */}
          {opt && (
            <div className="card p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="section-title">Optimization Lab</p>
                <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>
                  {opt.candidate_count} candidates · long-only · weights in [{pct(opt.constraints.min_weight, 0)}, {pct(opt.constraints.max_weight, 0)}]
                </span>
              </div>
              <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                <label className="block">
                  <span className="section-title">Max weight</span>
                  <input type="number" step="0.05" inputMode="decimal" aria-label="Maximum weight per asset"
                    value={maxWeightStr} onChange={(e) => setMaxWeightStr(e.target.value)}
                    className="ql-input mt-1 w-full px-2 py-1 text-sm" />
                </label>
                <label className="block">
                  <span className="section-title">Target return (optional)</span>
                  <input type="number" step="0.01" inputMode="decimal" aria-label="Target return (decimal, optional)"
                    placeholder="e.g. 0.06" value={targetReturnStr} onChange={(e) => setTargetReturnStr(e.target.value)}
                    className="ql-input mt-1 w-full px-2 py-1 text-sm" />
                </label>
                <label className="block">
                  <span className="section-title">Target volatility (optional)</span>
                  <input type="number" step="0.01" inputMode="decimal" aria-label="Target volatility (decimal, optional)"
                    placeholder="e.g. 0.12" value={targetVolStr} onChange={(e) => setTargetVolStr(e.target.value)}
                    className="ql-input mt-1 w-full px-2 py-1 text-sm" />
                </label>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--text-mut)" }}>
                      <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Portfolio</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exp return</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Volatility</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Sharpe</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Turnover</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Largest weight</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optRows.map((p) => (
                      <tr key={p.id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>
                          {p.name}
                          {!p.feasible && <span className="ml-1.5 text-[10px]" style={{ color: "var(--warn)" }}>(exceeds cap)</span>}
                        </td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.expected_return)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.volatility)}</td>
                        <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{num(p.sharpe_ratio, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.turnover, 1)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{largestWeight(p.weights)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {opt.notes.filter((n) => /not achievable|below the minimum/i.test(n)).map((n) => (
                <p key={n} role="status" className="mt-2 rounded-lg px-2.5 py-1.5 text-[11px]" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>{n}</p>
              ))}
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Deterministic candidate search, not a production optimiser. Educational construction only — not investment advice.
              </p>
            </div>
          )}

          {/* ── Weight comparison + hypothetical rebalance ───────────────── */}
          {selectedCompare && (
            <div className="card p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="section-title">Current vs optimized weights</p>
                <div className="flex flex-wrap gap-1.5">
                  {compareTargets.map((c) => (
                    <button key={c.id} type="button" onClick={() => setCompareId(c.id)}
                      aria-pressed={selectedCompare.id === c.id}
                      className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      style={{
                        background: selectedCompare.id === c.id ? "var(--accent-softer)" : "var(--glass)",
                        border: `1px solid ${selectedCompare.id === c.id ? "var(--accent-line)" : "var(--line)"}`,
                        color: selectedCompare.id === c.id ? "var(--accent-text)" : "var(--text-hi)",
                      }}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
              {(() => {
                const cur = result.normalized_weights;
                const tgt = selectedCompare.weights;
                const deltas = order.map((id) => ({ id, cur: cur[id] ?? 0, tgt: tgt[id] ?? 0, d: (tgt[id] ?? 0) - (cur[id] ?? 0) }));
                const turnover = 0.5 * deltas.reduce((s, x) => s + Math.abs(x.d), 0);
                const inc = deltas.reduce((a, b) => (b.d > a.d ? b : a));
                const dec = deltas.reduce((a, b) => (b.d < a.d ? b : a));
                return (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr style={{ color: "var(--text-mut)" }}>
                            <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                            <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Current</th>
                            <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Target</th>
                            <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Hypothetical Δ</th>
                          </tr>
                        </thead>
                        <tbody>
                          {deltas.map((x) => (
                            <tr key={x.id} style={{ borderTop: "1px solid var(--line)" }}>
                              <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{tickerOf(x.id)}</td>
                              <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(x.cur)}</td>
                              <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(x.tgt)}</td>
                              <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: changeColor(x.d) }}>{x.d >= 0 ? "+" : ""}{pct(x.d)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <div className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                        <span className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Absolute turnover</span>
                        <p className="mono text-base font-bold" style={{ color: "var(--text-hi)" }}>{pct(turnover, 1)}</p>
                      </div>
                      <span className="text-xs" style={{ color: "var(--text-mut)" }}>
                        Largest hypothetical increase: <span className="font-semibold" style={{ color: "var(--pos)" }}>{tickerOf(inc.id)} {inc.d >= 0 ? "+" : ""}{pct(inc.d)}</span>
                        {"  ·  "}decrease: <span className="font-semibold" style={{ color: "var(--neg)" }}>{tickerOf(dec.id)} {pct(dec.d)}</span>
                      </span>
                    </div>
                    <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                      Hypothetical rebalance delta (target − current). Illustrative only — not a trade order or buy/sell recommendation.
                    </p>
                  </>
                );
              })()}
            </div>
          )}

          {/* ── Black-Litterman ──────────────────────────────────────────── */}
          {bl && (
            <div className="card p-4">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <p className="section-title">Black-Litterman</p>
                <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>δ = {num(bl.risk_aversion, 2)} · τ = {num(bl.tau, 2)}</span>
              </div>
              <p className="mb-2 text-[11px]" style={{ color: "var(--warn)" }}>Sample views are illustrative only and are not forecasts.</p>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <p className="section-title mb-1">Returns (annual)</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ color: "var(--text-mut)" }}>
                          <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                          <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Prior</th>
                          <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Implied</th>
                          <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Posterior</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bl.returns.map((r) => (
                          <tr key={r.asset_id} style={{ borderTop: "1px solid var(--line)" }}>
                            <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{tickerOf(r.asset_id)}</td>
                            <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(r.prior_return)}</td>
                            <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(r.implied_return)}</td>
                            <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: changeColor(r.posterior_return - r.prior_return) }}>{pct(r.posterior_return)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <p className="section-title mb-1">Sample views</p>
                  <div className="space-y-1.5">
                    {bl.views.map((v) => (
                      <div key={v.id} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                        <p className="text-xs" style={{ color: "var(--text-hi)" }}>{v.description}</p>
                        <p className="mono mt-0.5 text-[10px]" style={{ color: "var(--text-mut)" }}>view = {pct(v.view_return)} · confidence {pct(v.confidence, 0)}{v.is_sample ? " · illustrative" : ""}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 rounded-lg px-3 py-2" style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--accent-text)" }}>{bl.bl_optimized_portfolio.name}</p>
                    <p className="mono mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                      μ {pct(bl.bl_optimized_portfolio.expected_return)} · σ {pct(bl.bl_optimized_portfolio.volatility)} · Sharpe {num(bl.bl_optimized_portfolio.sharpe_ratio, 2)} · turnover {pct(bl.bl_optimized_portfolio.turnover, 1)}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {order.map((id) => (
                        <span key={id} className="mono rounded px-1.5 py-0.5 text-[10px]" style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
                          {tickerOf(id)} {pct(bl.bl_optimized_portfolio.weights[id] ?? 0, 0)}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Monte Carlo simulation ───────────────────────────────────── */}
          {result.monte_carlo && (() => {
            const mc = result.monte_carlo;
            const money = (v: number) => Math.round(v).toLocaleString();
            return (
              <div className="card p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="section-title">Monte Carlo simulation</p>
                  <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>
                    {mc.method === "parametric_gaussian" ? "Parametric Gaussian" : "Historical bootstrap"} · {mc.num_paths} paths · {mc.horizon_days}d · seed {mc.seed} · start {money(mc.initial_value)}
                  </span>
                </div>
                <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <label className="block">
                    <span className="section-title">Horizon (days)</span>
                    <select aria-label="Simulation horizon in days" value={simHorizon} onChange={(e) => setSimHorizon(Number.parseInt(e.target.value, 10))} className="ql-input mt-1 w-full px-2 py-1 text-sm">
                      {[63, 126, 252, 504].map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className="section-title">Paths</span>
                    <select aria-label="Number of simulation paths" value={simPaths} onChange={(e) => setSimPaths(Number.parseInt(e.target.value, 10))} className="ql-input mt-1 w-full px-2 py-1 text-sm">
                      {[200, 500, 1000, 2000].map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className="section-title">Seed</span>
                    <input type="number" inputMode="numeric" aria-label="Simulation random seed" value={simSeed} onChange={(e) => setSimSeed(Number.parseInt(e.target.value, 10) || 0)} className="ql-input mt-1 w-full px-2 py-1 text-sm" />
                  </label>
                  <div className="flex items-end">
                    <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>DD threshold {pct(mc.drawdown_threshold)}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
                  <MetricCard label="Terminal mean" value={money(mc.terminal_wealth_mean)} tone="accent" />
                  <MetricCard label="Median" value={money(mc.terminal_wealth_median)} />
                  <MetricCard label="P05" value={money(mc.terminal_wealth_p05)} tone="warn" />
                  <MetricCard label="P95" value={money(mc.terminal_wealth_p95)} tone="positive" />
                  <MetricCard label="Prob of loss" value={pct(mc.probability_of_loss, 1)} tone="warn" />
                  <MetricCard label={`Prob DD < ${pct(mc.drawdown_threshold, 0)}`} value={pct(mc.probability_drawdown_breach, 1)} tone="danger" />
                  <MetricCard label="Sim VaR 95 (horizon)" value={pct(mc.simulated_var_95)} tone="warn" />
                  <MetricCard label="Sim CVaR 95 (horizon)" value={pct(mc.simulated_cvar_95)} tone="danger" />
                  <MetricCard label="Max DD mean" value={pct(mc.max_drawdown_mean)} />
                  <MetricCard label="Max DD p05" value={pct(mc.max_drawdown_p05)} tone="danger" />
                </div>
                <div className="mt-3"><FanChart mc={mc} /></div>
                <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                  Simulation uses deterministic sample data and a fixed seed. It is not a forecast.
                </p>
              </div>
            );
          })()}

          {/* ── Bootstrap robustness ─────────────────────────────────────── */}
          {result.bootstrap_robustness && (() => {
            const boot = result.bootstrap_robustness;
            const money = (v: number) => Math.round(v).toLocaleString();
            return (
              <div className="card p-4">
                <p className="section-title mb-2">Bootstrap robustness</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
                  <MetricCard label="Terminal mean" value={money(boot.terminal_wealth_mean)} tone="accent" />
                  <MetricCard label="P05" value={money(boot.terminal_wealth_p05)} tone="warn" />
                  <MetricCard label="P95" value={money(boot.terminal_wealth_p95)} tone="positive" />
                  <MetricCard label="Prob of loss" value={pct(boot.probability_of_loss, 1)} tone="warn" />
                  <MetricCard label="Max DD mean" value={pct(boot.max_drawdown_mean)} />
                  <MetricCard label="Sim CVaR 95" value={pct(boot.simulated_cvar_95)} tone="danger" />
                </div>
                <div className="mt-3"><FanChart mc={boot} /></div>
                <ul className="mt-2 space-y-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
                  {boot.notes.map((n) => <li key={n}>• {n}</li>)}
                </ul>
              </div>
            );
          })()}

          {/* ── Assumption sensitivity ───────────────────────────────────── */}
          {result.assumption_sensitivity.length > 0 && (
            <div className="card p-4">
              <p className="section-title mb-2">Assumption sensitivity</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--text-mut)" }}>
                      <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exp return</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Volatility</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Sharpe</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">VaR</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">CVaR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.assumption_sensitivity.map((s) => (
                      <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                        <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.expected_return)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.volatility)}</td>
                        <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{num(s.sharpe_ratio, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--warn)" }}>{pct(s.historical_var)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--neg)" }}>{pct(s.historical_cvar)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Illustrative assumption shifts on the current portfolio — not forecasts.
              </p>
            </div>
          )}

          {/* ── Optimization robustness ──────────────────────────────────── */}
          {result.optimization_robustness.length > 0 && (
            <div className="card p-4">
              <p className="section-title mb-2">Optimization robustness</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--text-mut)" }}>
                      <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Portfolio</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Base Sharpe</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Worst-case Sharpe</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Sharpe range</th>
                      <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Rank stability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.optimization_robustness.map((r) => (
                      <tr key={r.portfolio_id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{r.name}</td>
                        <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{num(r.base_sharpe, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: changeColor(r.worst_case_sharpe) }}>{num(r.worst_case_sharpe, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(r.sharpe_range, 2)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(r.rank_stability, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Sample robustness across the assumption shifts — Sharpe stability, not optimality. Not advice.
              </p>
            </div>
          )}
        </>
      )}

      {/* ── Explanation ──────────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={PORTFOLIO_RISK_FORMULA_GROUPS} />
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Why this matters</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>Volatility and Sharpe summarise risk-adjusted return at the portfolio level.</li>
              <li>Risk contributions show which assets actually drive portfolio risk — not just which have the largest weights.</li>
              <li>VaR/CVaR quantify tail loss; CVaR captures the average severity beyond the VaR threshold.</li>
              <li>The frontier, minimum-variance, and risk-parity portfolios illustrate different objectives.</li>
              <li><span className="font-semibold">Factor exposure</span> (portfolio β = Bᵀw) shows which systematic risks the portfolio carries; factor covariance turns those betas into a risk view.</li>
              <li><span className="font-semibold">Specific risk</span> is the idiosyncratic part not explained by the factors; with the variance-share convention factor % + specific % = 100%.</li>
              <li><span className="font-semibold">Scenario shocks</span> translate factor moves into asset and portfolio P&amp;L — a transparent “what if this factor moves” lens.</li>
              <li><span className="font-semibold">Mean-variance optimization</span> finds high-return-per-unit-risk portfolios; <span className="font-semibold">max Sharpe</span> maximises excess return ÷ volatility, and box <span className="font-semibold">constraints</span> (long-only, per-asset cap) keep results diversified.</li>
              <li><span className="font-semibold">Black-Litterman</span> starts from market-implied equilibrium returns and tilts them toward your views — blending a prior with opinions instead of trusting raw return estimates.</li>
              <li><span className="font-semibold">Turnover</span> (½·Σ|Δweight|) measures how much trading a rebalance would imply — higher turnover means more cost in practice.</li>
              <li><span className="font-semibold">Monte Carlo</span> simulates many fixed-seed wealth paths to show a distribution of outcomes (terminal wealth, drawdown, probability of loss) rather than a single point estimate.</li>
              <li><span className="font-semibold">Bootstrap</span> resamples the sample return series instead of assuming a Gaussian — a non-parametric robustness cross-check.</li>
              <li><span className="font-semibold">Robustness</span> re-scores portfolios under shifted assumptions (returns, volatility, correlation, rates) — a stable Sharpe across scenarios is more trustworthy than a fragile one.</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Limitations</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>Static illustrative sample data — not live, not a forecast, not advice.</li>
              <li>Long-only v1; covariance ties stated annual volatilities to the sample correlation.</li>
              <li>Historical VaR/CVaR are a monthly-horizon example from a short sample series.</li>
              <li>The efficient frontier is a deterministic sample demonstration, not an optimiser guarantee.</li>
              <li>Factor betas are <span className="font-semibold">deterministic illustrative values</span>, not estimated from data; factors are treated as orthogonal in v1, and specific variance is a floored residual.</li>
              <li>Scenarios are <span className="font-semibold">educational sample shocks</span>, not a current macro view — a simplified factor model, not a production risk model.</li>
              <li>The optimizer is a <span className="font-semibold">deterministic candidate search</span>, not a production optimizer; Black-Litterman views are <span className="font-semibold">illustrative, not forecasts</span>; rebalance deltas are <span className="font-semibold">hypothetical, not trade orders</span> — no buy/sell recommendations.</li>
              <li>Monte Carlo and bootstrap paths are <span className="font-semibold">fixed-seed simulations on illustrative sample data</span> — distributions of outcomes, <span className="font-semibold">not forecasts</span> or guaranteed probabilities; the bootstrap uses a short monthly sample (wide uncertainty), and this is not a production risk model.</li>
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
