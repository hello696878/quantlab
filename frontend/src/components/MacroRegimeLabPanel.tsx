"use client";

/**
 * Macro Regime & Cross-Asset Allocation Lab v1 (Phase 31.0).
 *
 * Deterministic static-sample macro-regime analytics: indicator z-scores and
 * category scores (growth, inflation, policy, liquidity, credit stress, USD
 * pressure), a composite macro score and regime classification, regime-adjusted
 * cross-asset assumptions, inverse-volatility / risk-parity-style /
 * regime-tilted educational allocations with risk contributions, and macro
 * stress scenarios.
 *
 * All numbers come from the backend static-sample API — no live macro or market
 * data (no FRED, no yfinance in this lab), educational only, not investment,
 * trading, or asset-allocation advice, and not a production allocation engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeMacroRegime,
  fetchMacroRegimeSample,
  num,
  pct,
  signedNum,
  signedPct,
  type MacroRegimeAnalysisRequest,
  type MacroRegimeAnalysisResponse,
  type MacroRegimeSampleResponse,
} from "@/lib/macroRegime";

const KNOBS = [
  { key: "risk_aversion_lambda", label: "Risk aversion λ", step: "0.05" },
  { key: "liquidity_preference_eta", label: "Liquidity pref. η", step: "0.005" },
];

const SAMPLE_LABELS: Record<string, string> = {
  GOLDILOCKS_SAMPLE: "Goldilocks Growth",
  INFLATION_SHOCK_SAMPLE: "Inflation Shock",
  RECESSION_CREDIT_SAMPLE: "Recession Credit Stress",
  STAGFLATION_SAMPLE: "Stagflation",
  LIQUIDITY_EASING_SAMPLE: "Liquidity Easing",
  STRONG_USD_SAMPLE: "Strong USD Tightening",
};

const MACRO_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Macro scoring",
    formulas: [
      { label: "Z-score", latex: "z_i = \\frac{x_i - \\mu_i}{\\sigma_i}" },
      { label: "Direction-adjusted score", latex: "s_i = d_i z_i", note: "d = +1 when higher is expansionary, −1 otherwise." },
      { label: "Category score", latex: "S_c = \\frac{\\sum_{i \\in c} w_i s_i}{\\sum_{i \\in c} w_i}" },
      { label: "Composite macro score", latex: "S_{\\mathrm{macro}} = w_g S_g + w_{\\pi} S_{\\pi} + w_p S_p + w_l S_l - w_c S_c" },
    ],
  },
  {
    title: "Asset assumptions",
    formulas: [
      { label: "Regime-adjusted expected return", latex: "\\mu_{a,\\mathrm{regime}} = \\mu_a + \\beta_{g,a} S_g + \\beta_{\\pi,a} S_{\\pi} + \\beta_{r,a} S_p + \\beta_{\\mathrm{usd},a} S_{\\mathrm{usd}} - \\beta_{\\mathrm{credit},a} S_{\\mathrm{credit}}" },
    ],
  },
  {
    title: "Allocation",
    formulas: [
      { label: "Inverse volatility weight", latex: "w_a = \\frac{1 / \\sigma_a}{\\sum_j 1 / \\sigma_j}" },
      { label: "Risk contribution approximation", latex: "RC_a = \\frac{w_a \\sigma_a}{\\sum_j w_j \\sigma_j}" },
      { label: "Regime-tilted score", latex: "T_a = \\mu_{a,\\mathrm{regime}} - \\lambda \\sigma_a + \\eta L_a", note: "L = liquidity score." },
      { label: "Normalized tilted weight", latex: "w_a = \\frac{\\max(T_a, 0)}{\\sum_j \\max(T_j, 0)}", note: "Falls back to inverse-vol when all scores are non-positive." },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  goldilocks_growth: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  liquidity_easing: { color: "var(--accent-text)", bg: "var(--accent-softer)" },
  inflation_shock: { color: "var(--warn)", bg: "var(--warn-soft)" },
  policy_tightening: { color: "var(--warn)", bg: "var(--warn-soft)" },
  strong_usd_pressure: { color: "var(--warn)", bg: "var(--warn-soft)" },
  stagflation: { color: "var(--risk)", bg: "var(--warn-soft)" },
  recession_credit_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
  severe_macro_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function scoreColor(v: number, higherIsBad: boolean): string {
  const bad = higherIsBad ? v > 0.5 : v < -0.5;
  const good = higherIsBad ? v < -0.5 : v > 0.5;
  return bad ? "var(--neg)" : good ? "var(--pos)" : "var(--text-hi)";
}

const METHOD_LABEL: Record<string, string> = {
  inverse_volatility: "Inverse vol",
  risk_parity_style: "Risk-parity style",
  regime_tilted: "Regime-tilted",
};

export default function MacroRegimeLabPanel() {
  const [sample, setSample] = useState<MacroRegimeSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<MacroRegimeAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: MacroRegimeAnalysisRequest): Record<string, string> {
    const src = req as unknown as Record<string, number>;
    return Object.fromEntries(KNOBS.map((f) => [f.key, String(src[f.key])]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMacroRegimeSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.samples[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const base = sample?.samples[selected] ?? null;
  function selectSample(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.samples[idx]));
  }

  const request = useMemo<MacroRegimeAnalysisRequest | null>(() => {
    if (!base) return null;
    const overrides: Record<string, number> = {};
    KNOBS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = (base as unknown as Record<string, number>)[f.key];
      overrides[f.key] = Number.isFinite(v) && v >= 0 ? v : fallback;
    });
    return { ...base, ...overrides };
  }, [base, fieldStr]);

  const reqKey = request
    ? JSON.stringify([request.sample_id, request.risk_aversion_lambda, request.liquidity_preference_eta])
    : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeMacroRegime(request, ctrl.signal)
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

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Macro Regime &amp; Cross-Asset Allocation Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const cs = r?.category_scores;
  const nameOf = (id: string) =>
    r?.asset_assumptions.find((a) => a.asset_id === id)?.asset_name.replace(" Sample", "") ?? id;
  const allocations = r?.allocation_results ?? [];
  const tilted = allocations.find((a) => a.method === "regime_tilted");

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Macro Regime &amp; Cross-Asset Allocation Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample macro states — indicator z-scores and category scores,
              a composite macro regime read, regime-adjusted cross-asset assumptions, inverse-vol /
              risk-parity-style / regime-tilted educational allocations with risk contributions, and
              macro stress scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Macro regime and cross-asset allocation analytics are educational and not investment, trading, asset-allocation, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Sample selector + knobs ──────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Macro state &amp; model assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.sample_summary.indicator_count} indicators · {r.sample_summary.asset_count} asset classes</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.samples.map((s, i) => (
            <button key={s.sample_id} type="button" onClick={() => selectSample(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{SAMPLE_LABELS[s.sample_id] ?? s.sample_id}</button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:max-w-md">
          {KNOBS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
              <input
                type="number"
                step={f.step}
                min="0"
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

      {/* ── Macro score cards ────────────────────────────────────────────── */}
      {r && cs && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Macro category scores</p>
            <span
              className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
              style={{ background: regimeTone(r.macro_regime.regime_id).bg, border: "1px solid var(--line)", color: regimeTone(r.macro_regime.regime_id).color }}
              title={r.macro_regime.explanation}
            >
              {r.macro_regime.regime_label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCard label="Growth" value={signedNum(cs.growth_score)} tone={cs.growth_score >= 0.3 ? "positive" : cs.growth_score <= -0.5 ? "danger" : "default"} />
            <MetricCard label="Inflation" value={signedNum(cs.inflation_score)} tone={cs.inflation_score >= 0.5 ? "danger" : "default"} />
            <MetricCard label="Policy tightness" value={signedNum(cs.policy_score)} tone={cs.policy_score >= 0.5 ? "warn" : "default"} />
            <MetricCard label="Liquidity" value={signedNum(cs.liquidity_score)} tone={cs.liquidity_score >= 0.5 ? "positive" : cs.liquidity_score <= -0.5 ? "warn" : "default"} />
            <MetricCard label="Credit stress" value={signedNum(cs.credit_stress_score)} tone={cs.credit_stress_score >= 0.5 ? "danger" : "default"} />
            <MetricCard label="USD pressure" value={signedNum(cs.usd_pressure_score)} tone={cs.usd_pressure_score >= 0.5 ? "warn" : "default"} />
            <MetricCard label="Composite" value={signedNum(cs.composite_macro_score)} tone="accent" />
          </div>
          <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {r.macro_regime.explanation} Drivers: {r.macro_regime.drivers.join(" · ")} · stress heat {num(r.macro_regime.score, 2)}.
          </p>
        </div>
      )}

      {/* ── Indicator table ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Indicator table</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Indicator</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Category</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Value</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">LR mean</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Z-score</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Dir-adj score</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Weight</th>
                </tr>
              </thead>
              <tbody>
                {r.indicator_table.map((row) => (
                  <tr key={row.name} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.name}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{row.category}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(row.value, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(row.long_run_mean, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{signedNum(row.z_score)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: row.direction_adjusted_score > 0.5 ? "var(--pos)" : row.direction_adjusted_score < -0.5 ? "var(--neg)" : "var(--text-hi)" }}>{signedNum(row.direction_adjusted_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{num(row.weight, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            The direction flag orients each indicator so a higher category score means stronger
            growth / hotter inflation / tighter policy / easier liquidity / more credit stress /
            stronger USD pressure.
          </p>
        </div>
      )}

      {/* ── Asset assumptions ────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Cross-asset assumptions</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset class</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">μ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">μ (regime)</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">σ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Liquidity</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">β growth</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">β infl</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">β rate</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">β USD</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">β credit</th>
                </tr>
              </thead>
              <tbody>
                {r.asset_assumptions.map((a) => (
                  <tr key={a.asset_id} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{a.asset_name.replace(" Sample", "")}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(a.expected_return)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: a.regime_adjusted_expected_return >= a.expected_return ? "var(--pos)" : "var(--neg)" }}>{pct(a.regime_adjusted_expected_return)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(a.volatility, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(a.liquidity_score, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{signedNum(a.growth_beta, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{signedNum(a.inflation_beta, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{signedNum(a.rate_beta, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{signedNum(a.usd_beta, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-faint)" }}>{signedNum(a.credit_beta, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Illustrative sample assumptions shifted by beta × category score — not estimates,
            forecasts, or recommendations.
          </p>
        </div>
      )}

      {/* ── Allocation comparison + risk contributions ───────────────────── */}
      {r && allocations.length > 0 && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Allocation comparison (educational)</p>
            <div className="mb-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {allocations.map((a) => (
                <MetricCard
                  key={a.method}
                  label={`${METHOD_LABEL[a.method] ?? a.method} · μ / σ`}
                  value={`${pct(a.portfolio_expected_return)} / ${pct(a.portfolio_volatility_approx)}`}
                  tone={a.method === "regime_tilted" ? "accent" : "default"}
                />
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                    {allocations.map((a) => (
                      <th key={a.method} className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">{METHOD_LABEL[a.method] ?? a.method}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.asset_assumptions.map((asset) => (
                    <tr key={asset.asset_id} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{asset.asset_name.replace(" Sample", "")}</td>
                      {allocations.map((a) => {
                        const w = a.weights[asset.asset_id] ?? 0;
                        return (
                          <td key={a.method} className="mono px-2 py-1.5 text-right" style={{ color: w >= 0.15 ? "var(--accent-text)" : "var(--text-mut)" }}>
                            {pct(w)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {tilted?.notes && (
              <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
                {tilted.notes.map((n) => <li key={n}>{n}</li>)}
              </ul>
            )}
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Risk contributions (regime-tilted)</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Asset</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Weight</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">σ</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">RC</th>
                  </tr>
                </thead>
                <tbody>
                  {r.asset_assumptions.map((asset) => {
                    const w = tilted?.weights[asset.asset_id] ?? 0;
                    const rc = tilted?.risk_contributions[asset.asset_id] ?? 0;
                    return (
                      <tr key={asset.asset_id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td className="px-2 py-1.5 text-[12px]" style={{ color: "var(--text-hi)" }}>{asset.asset_name.replace(" Sample", "")}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(w)}</td>
                        <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(asset.volatility, 0)}</td>
                        <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: rc >= 0.25 ? "var(--warn)" : "var(--text-hi)" }}>{pct(rc)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              RC = wσ / Σwσ — the simple approximation from the formulas panel.
            </p>
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Macro stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Growth</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Infl.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Policy</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Liq.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Credit</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">USD</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Port μ / σ</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Top weight</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: scoreColor(s.growth_score, false) }}>{signedNum(s.growth_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: scoreColor(s.inflation_score, true) }}>{signedNum(s.inflation_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{signedNum(s.policy_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: scoreColor(s.liquidity_score, false) }}>{signedNum(s.liquidity_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: scoreColor(s.credit_stress_score, true) }}>{signedNum(s.credit_stress_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: scoreColor(s.usd_pressure_score, true) }}>{signedNum(s.usd_pressure_score)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{signedPct(s.portfolio_expected_return, 1)} / {pct(s.portfolio_volatility_approx)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{nameOf(s.largest_weight_asset)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic score shocks (regime-tilted weights) on static sample data —
            not forecasts, not current, and not investment, trading, or allocation advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={MACRO_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — no live macro or market data (no FRED or yfinance in this lab).</li>
          <li>Betas, correlations, and allocation constructions are documented educational heuristics — not estimates, forecasts, or a production allocation engine.</li>
          <li>Regime classification and stress scenarios are hypothetical — no regime, weight, or scenario is a recommendation.</li>
          <li>Educational only — not investment, trading, asset-allocation, legal, tax, or risk-management advice.</li>
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
