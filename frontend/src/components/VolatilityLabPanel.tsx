"use client";

/**
 * Volatility Surface & Variance Swap Lab v1 (Phase 24.0).
 *
 * Deterministic static-sample derivatives-volatility analytics: implied-vol
 * inversion, smile / skew / term structure, a 2-D volatility surface, realized-vol
 * comparison, a simplified educational variance-swap fair-strike approximation,
 * vega exposure, and volatility scenario stress.
 *
 * All numbers come from the backend static-sample API — no live option chains,
 * educational only, not investment / trading advice, not official VIX methodology.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeVolatility,
  compact,
  fetchVolatilitySample,
  num,
  pct,
  type UnderlyingInput,
  type VolatilityAnalysisRequest,
  type VolatilityAnalysisResponse,
  type VolatilitySampleResponse,
} from "@/lib/volatility";

const VOLATILITY_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Black-Scholes & Greeks",
    formulas: [
      { label: "Call price", latex: "C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2)" },
      { label: "Put price", latex: "P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)" },
      { label: "d₁, d₂", latex: "d_1 = \\frac{\\ln(S/K) + (r - q + \\tfrac{1}{2}\\sigma^2)T}{\\sigma\\sqrt{T}}, \\quad d_2 = d_1 - \\sigma\\sqrt{T}" },
      { label: "Vega", latex: "\\nu = S e^{-qT} \\varphi(d_1)\\sqrt{T}" },
      { label: "Implied volatility", latex: "\\text{solve } C_{\\mathrm{BS}}(\\sigma) = C_{\\mathrm{mid}} \\;\\text{ (bisection)}" },
    ],
  },
  {
    title: "Realized vol & variance swap",
    formulas: [
      { label: "Realized volatility", latex: "\\sigma_{\\mathrm{realized}} = \\mathrm{stdev}(r_t)\\sqrt{252}" },
      { label: "Variance swap fair strike", latex: "K_{\\mathrm{var}}^2 \\approx \\frac{2 e^{rT}}{T}\\sum_i \\frac{\\Delta K_i}{K_i^2} Q(K_i)", note: "Simplified option-strip approximation — not official VIX methodology." },
      { label: "Skew slope", latex: "\\mathrm{Skew} = \\frac{\\mathrm{IV}_{110\\%} - \\mathrm{IV}_{90\\%}}{0.2}" },
      { label: "Vega exposure", latex: "\\mathcal{V}_p = \\sum_i \\nu_i\\, n_i", note: "Position-weighted vega by maturity / moneyness." },
    ],
  },
];

const UNDERLYING_FIELDS = [
  { key: "spot_price", label: "Spot price", step: "10" },
  { key: "risk_free_rate", label: "Risk-free rate", step: "0.0025" },
  { key: "dividend_yield", label: "Dividend yield", step: "0.0025" },
];

function ivColor(v: number, atm: number): string {
  const d = v - atm;
  return d > 0.005 ? "var(--neg)" : d < -0.005 ? "var(--pos)" : "var(--text-hi)";
}

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

export default function VolatilityLabPanel() {
  const [sample, setSample] = useState<VolatilitySampleResponse | null>(null);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<VolatilityAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [smileMaturity, setSmileMaturity] = useState(30);

  function fieldsFrom(u: UnderlyingInput): Record<string, string> {
    const uu = u as unknown as Record<string, number>;
    return Object.fromEntries(UNDERLYING_FIELDS.map((f) => [f.key, String(uu[f.key])]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchVolatilitySample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setFieldStr(fieldsFrom(s.request.underlying));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const request = useMemo<VolatilityAnalysisRequest | null>(() => {
    if (!sample) return null;
    const base = sample.request;
    const bu = base.underlying as unknown as Record<string, number>;
    const overrides: Record<string, number> = {};
    UNDERLYING_FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      overrides[f.key] = Number.isFinite(v) ? v : bu[f.key];
    });
    return {
      ...base,
      underlying: { ...base.underlying, ...overrides } as UnderlyingInput,
    };
  }, [sample, fieldStr]);

  const reqKey = request ? JSON.stringify(request.underlying) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeVolatility(request, ctrl.signal)
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
  }, [reqKey]);

  const r = result;

  // Surface grid (maturity rows × strike cols) from smile points.
  const surface = useMemo(() => {
    if (!r) return null;
    const strikes = Array.from(new Set(r.smile_points.map((p) => p.strike))).sort((a, b) => a - b);
    const mats = Array.from(new Set(r.smile_points.map((p) => p.maturity_days))).sort((a, b) => a - b);
    const lookup = new Map<string, number>();
    r.smile_points.forEach((p) => lookup.set(`${p.maturity_days}_${p.strike}`, p.implied_volatility));
    return { strikes, mats, lookup };
  }, [r]);

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Volatility Surface &amp; Variance Swap Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const maturities = r ? Array.from(new Set(r.smile_points.map((p) => p.maturity_days))).sort((a, b) => a - b) : [];
  const smileRows = r ? r.smile_points.filter((p) => p.maturity_days === smileMaturity) : [];
  const atmForMaturity = r?.term_structure.find((t) => t.maturity_days === smileMaturity)?.atm_implied_volatility ?? r?.surface_summary.atm_iv_30d ?? 0;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Volatility Surface &amp; Variance Swap Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Invert implied vols from a sample option chain and explore the smile, skew, term
              structure, and 2-D surface, plus realized vol, a simplified variance-swap fair
              strike, vega exposure, and volatility scenario stress — all on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Volatility analytics are educational and not investment, trading, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Underlying assumptions ───────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="section-title">Underlying assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.underlying.symbol} · {r.option_quotes.length} quotes</span>}
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {UNDERLYING_FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
              <input
                type="number"
                step={f.step}
                inputMode="decimal"
                aria-label={f.label}
                value={fieldStr[f.key] ?? ""}
                onChange={(e) => setFieldStr((s) => ({ ...s, [f.key]: e.target.value }))}
                className="ql-input mt-1 w-full px-2 py-1 text-sm"
              />
            </label>
          ))}
        </div>
      </div>

      {/* ── Key metrics ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Key metrics</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="ATM 30d IV" value={pct(r.surface_summary.atm_iv_30d)} tone="accent" />
            <MetricCard label="ATM 90d IV" value={pct(r.surface_summary.atm_iv_90d)} />
            <MetricCard label="ATM 1Y IV" value={pct(r.surface_summary.atm_iv_1y)} />
            <MetricCard label="Realized vol" value={pct(r.realized_volatility.realized_vol_annual)} />
            <MetricCard label="Implied − realized" value={pct(r.implied_realized_spread.spread)} tone={r.implied_realized_spread.spread >= 0 ? "positive" : "warn"} />
            <MetricCard label="Var-swap vol strike" value={pct(r.variance_swap.volatility_strike)} tone="accent" />
            <MetricCard label="Total vega" value={compact(r.vega_exposure.total_vega)} />
            <MetricCard label="Term slope (1Y−30d)" value={pct(r.surface_summary.term_structure_slope)} tone={r.surface_summary.term_structure_slope >= 0 ? "positive" : "warn"} />
          </div>
        </div>
      )}

      {/* ── Smile / skew + term structure ────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="card p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="section-title">Volatility smile</p>
              <div className="flex flex-wrap gap-1.5">
                {maturities.map((m) => (
                  <button key={m} type="button" onClick={() => setSmileMaturity(m)} aria-pressed={smileMaturity === m}
                    className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                    style={{
                      background: smileMaturity === m ? "var(--accent-softer)" : "var(--glass)",
                      border: `1px solid ${smileMaturity === m ? "var(--accent-line)" : "var(--line)"}`,
                      color: smileMaturity === m ? "var(--accent-text)" : "var(--text-hi)",
                    }}>{m}d</button>
                ))}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Strike</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Moneyness</th>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Type</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Implied vol</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Vega</th>
                  </tr>
                </thead>
                <tbody>
                  {smileRows.map((p) => (
                    <tr key={p.strike} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="mono px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{num(p.strike, 0)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.moneyness, 0)}</td>
                      <td className="px-2 py-1.5 text-[11px] uppercase" style={{ color: "var(--text-mut)" }}>{p.option_type}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: ivColor(p.implied_volatility, atmForMaturity) }}>{pct(p.implied_volatility)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(p.vega, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Downside puts (low moneyness) trade richer than upside calls — the equity skew.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Term structure &amp; skew</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Maturity</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">ATM IV</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">90% put IV</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">110% call IV</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Skew slope</th>
                  </tr>
                </thead>
                <tbody>
                  {r.skew_metrics.map((s) => (
                    <tr key={s.maturity_days} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.maturity_days}d</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{pct(s.atm_iv)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--neg)" }}>{pct(s.put_90_iv)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--pos)" }}>{pct(s.call_110_iv)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(-s.skew_slope) }}>{num(s.skew_slope, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Surface grid ─────────────────────────────────────────────────── */}
      {r && surface && (
        <div className="card p-4">
          <p className="section-title mb-2">Volatility surface (implied vol)</p>
          <div className="overflow-x-auto">
            <table className="mono w-full text-[11px]">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-1.5 py-1 text-left">Maturity \\ Strike</th>
                  {surface.strikes.map((k) => (
                    <th key={k} className="px-1.5 py-1 text-right">{num(k, 0)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {surface.mats.map((m) => (
                  <tr key={m} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-1.5 py-1 font-semibold" style={{ color: "var(--text-hi)" }}>{m}d</td>
                    {surface.strikes.map((k) => {
                      const iv = surface.lookup.get(`${m}_${k}`);
                      return (
                        <td key={k} className="px-1.5 py-1 text-right" style={{ color: iv != null ? ivColor(iv, r.surface_summary.atm_iv_90d) : "var(--text-faint)" }}>
                          {iv != null ? pct(iv, 1) : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Min {pct(r.surface_summary.min_iv)} · max {pct(r.surface_summary.max_iv)} · average {pct(r.surface_summary.average_iv)} · steepest skew at {r.surface_summary.steepest_skew_maturity}d.
          </p>
        </div>
      )}

      {/* ── Variance swap + vega exposure ────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Variance swap (educational approximation)</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Maturity" value={`${r.variance_swap.maturity_days}d`} />
              <MetricCard label="Forward" value={num(r.variance_swap.forward, 0)} />
              <MetricCard label="Variance strike" value={num(r.variance_swap.variance_strike, 4)} />
              <MetricCard label="Vol strike" value={pct(r.variance_swap.volatility_strike)} tone="accent" />
            </div>
            <div className="mt-3 overflow-x-auto" style={{ maxHeight: 220 }}>
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-1.5 py-1 text-left">Strike</th>
                    <th className="px-1.5 py-1 text-left">OTM</th>
                    <th className="px-1.5 py-1 text-right">Price</th>
                    <th className="px-1.5 py-1 text-right">ΔK</th>
                    <th className="px-1.5 py-1 text-right">Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {r.variance_swap.strip_points.map((sp) => (
                    <tr key={sp.strike} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-1.5 py-1" style={{ color: "var(--text-hi)" }}>{num(sp.strike, 0)}</td>
                      <td className="px-1.5 py-1" style={{ color: "var(--text-mut)" }}>{sp.otm_type}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{num(sp.otm_price, 2)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{num(sp.delta_k, 0)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{sp.contribution.toExponential(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Simplified option-strip approximation — NOT official VIX / exchange methodology.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Vega exposure (sample book)</p>
            <MetricCard label="Total portfolio vega" value={compact(r.vega_exposure.total_vega)} tone="accent" />
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Vega by maturity</p>
                <div className="mt-1 space-y-1">
                  {r.vega_exposure.vega_by_maturity.map((g) => (
                    <div key={g.key} className="flex items-baseline justify-between text-xs">
                      <span style={{ color: "var(--text-mut)" }}>{g.key}</span>
                      <span className="mono font-semibold" style={{ color: pnlColor(g.vega) }}>{compact(g.vega)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Vega by moneyness</p>
                <div className="mt-1 space-y-1">
                  {r.vega_exposure.vega_by_moneyness.map((g) => (
                    <div key={g.key} className="flex items-baseline justify-between text-xs">
                      <span style={{ color: "var(--text-mut)" }}>{g.key}</span>
                      <span className="mono font-semibold" style={{ color: pnlColor(g.vega) }}>{compact(g.vega)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              First-order vega on an illustrative sample book — not a trade recommendation.
            </p>
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Volatility scenario stress</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Shifted ATM 30d</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">ATM IV Δ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Skew Δ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Term slope</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Portfolio Δvalue</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{pct(s.shifted_atm_iv_30d)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.atm_iv_change) }}>{pct(s.atm_iv_change)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.skew_change, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.term_structure_slope)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(s.portfolio_value_change) }}>{compact(s.portfolio_value_change)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            First-order (vega/delta) value changes on the sample book — deterministic illustrative scenarios, not forecasts or trading advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={VOLATILITY_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not a live option chain.</li>
          <li>The implied-vol solver and variance-swap fair strike are simplified educational models — NOT official VIX / exchange methodology.</li>
          <li>Vega/scenario value changes are first-order approximations; no second-order or full revaluation.</li>
          <li>Educational only — not investment, trading, legal, tax, or risk-management advice.</li>
        </ul>
        {r?.notes && (
          <ul className="mt-3 space-y-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {r.notes.map((n) => <li key={n}>• {n}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}
