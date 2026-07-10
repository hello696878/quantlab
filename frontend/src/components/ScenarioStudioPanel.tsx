"use client";

/**
 * Unified Scenario Studio & Cross-Lab Report Builder v1 (Phase 32.0).
 *
 * A deterministic educational workflow layer: pick a scenario template, adjust
 * global shock controls, and see documented cross-lab impact scores, a
 * composite severity, a scenario-regime read, a module × shock-group heatmap,
 * baseline-vs-stress comparisons, and a deterministic Markdown report builder.
 *
 * All numbers come from the backend static-sample API — the impact layer is a
 * transparent teaching approximation that does NOT call the other labs'
 * engines. No live macro, market, crypto, or news data; educational only, not
 * investment, trading, or asset-allocation advice; not a production risk
 * report.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import ShockSlider from "@/components/controls/ShockSlider";
import { GroupedBarChart, ScenarioBarChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  analyzeScenarioStudio,
  fetchScenarioStudioSample,
  num,
  pct,
  signedNum,
  type ImpactBucket,
  type ReportSectionId,
  type ScenarioModuleId,
  type ScenarioShockOverrides,
  type ScenarioStudioAnalysisResponse,
  type ScenarioStudioRequest,
  type ScenarioStudioSampleResponse,
  type ShockKey,
} from "@/lib/scenarioStudio";

// The interactive global controls (a curated subset of the 19 shocks; the
// rest stay at their template values and are listed in the shock table).
const SLIDERS: { key: ShockKey; label: string; min: number; max: number; step: number; mult?: boolean }[] = [
  { key: "growth_shock", label: "Growth shock", min: -3, max: 3, step: 0.1 },
  { key: "inflation_shock", label: "Inflation shock", min: -3, max: 3, step: 0.1 },
  { key: "policy_shock", label: "Policy shock", min: -3, max: 3, step: 0.1 },
  { key: "liquidity_shock", label: "Liquidity shock", min: -3, max: 3, step: 0.1 },
  { key: "credit_shock", label: "Credit shock", min: -3, max: 3, step: 0.1 },
  { key: "crypto_price_shock", label: "Crypto price shock", min: -3, max: 3, step: 0.1 },
  { key: "volatility_multiplier", label: "Volatility ×", min: 0.5, max: 3, step: 0.05, mult: true },
  { key: "sentiment_shock", label: "Sentiment shock", min: -3, max: 3, step: 0.1 },
  { key: "stablecoin_depeg_shock", label: "Stablecoin depeg shock", min: -3, max: 3, step: 0.1 },
  { key: "exchange_inflow_multiplier", label: "Exchange inflow ×", min: 0, max: 4, step: 0.1, mult: true },
  { key: "token_unlock_multiplier", label: "Token unlock ×", min: 0, max: 4, step: 0.1, mult: true },
  { key: "publication_lag_shock", label: "Publication lag shock", min: 0, max: 3, step: 0.1 },
];

const BUCKET_COLOR: Record<ImpactBucket, string> = {
  low: "var(--emerald)",
  moderate: "var(--accent-text)",
  elevated: "var(--warn)",
  high: "var(--warn)",
  severe: "var(--risk)",
};

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  benign_cross_asset: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  macro_policy_stress: { color: "var(--warn)", bg: "var(--warn-soft)" },
  credit_liquidity_stress: { color: "var(--warn)", bg: "var(--warn-soft)" },
  crypto_specific_stress: { color: "var(--warn)", bg: "var(--warn-soft)" },
  data_quality_stress: { color: "var(--warn)", bg: "var(--warn-soft)" },
  broad_risk_off: { color: "var(--risk)", bg: "var(--warn-soft)" },
  severe_systemic_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

const MODULE_SHORT: Record<ScenarioModuleId, string> = {
  macro_regime: "Macro",
  portfolio_risk: "Portfolio",
  crypto_derivatives: "Crypto deriv",
  defi_risk: "DeFi",
  tokenomics: "Tokenomics",
  onchain_analytics: "On-chain",
  alternative_data: "Alt data",
  market_microstructure: "Microstructure",
};

const STUDIO_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Cross-lab impact scoring",
    formulas: [
      {
        label: "Module impact score",
        latex: "I_m = \\mathrm{clip}_{0,100}\\left( \\sum_k w_{m,k} \\, |s_k| \\right)",
        note: "Multiplier shocks contribute max(m − 1, 0) instead of |s|.",
      },
      { label: "Composite severity", latex: "S = \\frac{1}{M} \\sum_{m=1}^{M} I_m" },
    ],
  },
  {
    title: "Baseline vs stress",
    formulas: [
      { label: "Change", latex: "\\Delta x = x_{\\mathrm{stress}} - x_{\\mathrm{base}}" },
      {
        label: "Percentage change",
        latex: "\\Delta x_{\\%} = \\frac{x_{\\mathrm{stress}} - x_{\\mathrm{base}}}{|x_{\\mathrm{base}}| + \\epsilon}",
      },
    ],
  },
  {
    title: "Report builder",
    formulas: [
      {
        label: "Section coverage",
        latex: "C = \\frac{N_{\\mathrm{included}}}{N_{\\mathrm{available}}}",
        note: "The Limitations section is always included.",
      },
    ],
  },
];

function ImpactRadar({ rows }: { rows: { label: string; value: number }[] }) {
  if (rows.length < 3) {
    return (
      <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>
        Include at least three modules to draw the radar.
      </p>
    );
  }
  const cx = 110;
  const cy = 102;
  const radius = 72;
  const pt = (i: number, r: number): [number, number] => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / rows.length;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  };
  const polygon = rows
    .map((row, i) => pt(i, (Math.min(Math.max(row.value, 0), 100) / 100) * radius))
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox="0 0 220 204" className="mx-auto block w-full max-w-[320px]" role="img" aria-label="Module impact radar">
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon
          key={f}
          points={rows.map((_, i) => pt(i, radius * f).map((v) => v.toFixed(1)).join(",")).join(" ")}
          fill="none"
          stroke="var(--line)"
          strokeWidth="1"
        />
      ))}
      {rows.map((_, i) => {
        const [x, y] = pt(i, radius);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line)" strokeWidth="1" />;
      })}
      <polygon points={polygon} fill="rgba(var(--accent-rgb),0.22)" stroke="var(--accent)" strokeWidth="1.5" />
      {rows.map((row, i) => {
        const [x, y] = pt(i, radius + 14);
        return (
          <text
            key={row.label}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="8.5"
            fill="var(--text-mut)"
          >
            {row.label}
          </text>
        );
      })}
    </svg>
  );
}

export default function ScenarioStudioPanel() {
  const [sample, setSample] = useState<ScenarioStudioSampleResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string>("soft_landing");
  const [overrides, setOverrides] = useState<ScenarioShockOverrides>({});
  const [includedModules, setIncludedModules] = useState<ScenarioModuleId[]>([]);
  const [includedSections, setIncludedSections] = useState<ReportSectionId[]>([]);
  const [result, setResult] = useState<ScenarioStudioAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchScenarioStudioSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelectedId(s.default_request.selected_scenario_id);
        setIncludedModules(s.default_request.included_modules);
        setIncludedSections(s.default_request.report_sections);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const template = sample?.templates.find((t) => t.scenario_id === selectedId) ?? null;
  const overridesActive = Object.keys(overrides).length > 0;

  function selectTemplate(id: string) {
    setSelectedId(id);
    setOverrides({});
  }

  function resolved(key: ShockKey): number {
    return overrides[key] ?? (template ? template[key] : 0);
  }

  function setShock(key: ShockKey) {
    return (v: number) => setOverrides((o) => ({ ...o, [key]: v }));
  }

  function toggleModule(id: ScenarioModuleId) {
    setIncludedModules((mods) =>
      mods.includes(id) ? (mods.length > 1 ? mods.filter((m) => m !== id) : mods) : [...mods, id],
    );
  }

  function toggleSection(id: ReportSectionId) {
    if (id === "limitations") return; // always included
    setIncludedSections((secs) =>
      secs.includes(id) ? (secs.length > 1 ? secs.filter((s) => s !== id) : secs) : [...secs, id],
    );
  }

  const request = useMemo<ScenarioStudioRequest | null>(() => {
    if (!sample || !template || includedModules.length === 0 || includedSections.length === 0) return null;
    // Canonical catalog order keeps the request (and reqKey) stable.
    const mods = sample.modules.map((m) => m.module_id).filter((m) => includedModules.includes(m));
    const secs = sample.sections.map((s) => s.section_id).filter((s) => includedSections.includes(s));
    return {
      selected_scenario_id: template.scenario_id,
      custom_overrides: overridesActive ? overrides : null,
      included_modules: mods,
      report_sections: secs,
    };
  }, [sample, template, overrides, overridesActive, includedModules, includedSections]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeScenarioStudio(request, ctrl.signal)
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
  const heatmapColumns = useMemo(() => {
    const cols: string[] = [];
    for (const cell of r?.heatmap ?? []) {
      if (!cols.includes(cell.column_label)) cols.push(cell.column_label);
    }
    return cols;
  }, [r]);
  const heatmapRows = useMemo(() => {
    const rows: string[] = [];
    for (const cell of r?.heatmap ?? []) {
      if (!rows.includes(cell.row_label)) rows.push(cell.row_label);
    }
    return rows;
  }, [r]);

  async function copyReport() {
    if (!r) return;
    try {
      await navigator.clipboard.writeText(r.generated_report.markdown);
      setCopyStatus("Copied ✓");
    } catch {
      setCopyStatus("Copy failed — select the preview text instead");
    }
    window.setTimeout(() => setCopyStatus(null), 2500);
  }

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Unified Scenario Studio &amp; Report Builder</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This workspace uses the backend static-sample analytics API. Start the QuantLab API and reopen it.
        </p>
      </div>
    );
  }

  const regimeTone = r ? REGIME_TONE[r.scenario_regime.regime_id] ?? { color: "var(--text-hi)", bg: "var(--glass)" } : null;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              Unified Scenario Studio &amp; Report Builder
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Pick a deterministic scenario template, adjust global shock controls, and see
              documented cross-lab impact scores across macro, portfolio, crypto derivatives,
              DeFi, tokenomics, on-chain, alternative data, and microstructure — then build a
              copy-friendly educational report. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Unified scenario, cross-lab impact, and report-builder analytics are educational and not investment, trading, asset-allocation, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Scenario template selector ───────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Scenario template</p>
        <div className="flex flex-wrap gap-1.5">
          {sample?.templates.map((t) => (
            <button
              key={t.scenario_id}
              type="button"
              onClick={() => selectTemplate(t.scenario_id)}
              aria-pressed={selectedId === t.scenario_id}
              className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
              style={{
                background: selectedId === t.scenario_id ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selectedId === t.scenario_id ? "var(--accent-line)" : "var(--line)"}`,
                color: selectedId === t.scenario_id ? "var(--accent-text)" : "var(--text-mut)",
              }}
            >
              {t.scenario_name}
            </button>
          ))}
        </div>
        {template && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-mut)" }}>{template.description}</p>
        )}
      </div>

      {/* ── Global scenario controls ─────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Global scenario controls</p>
          {overridesActive && (
            <button
              type="button"
              onClick={() => setOverrides({})}
              className="rounded-md px-2.5 py-1 text-xs font-semibold"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
            >
              Reset to template
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
          {SLIDERS.map((s) => (
            <ShockSlider
              key={s.key}
              label={s.label}
              value={resolved(s.key)}
              min={s.min}
              max={s.max}
              step={s.step}
              format={(v) => (s.mult ? `×${v.toFixed(2)}` : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`)}
              onChange={setShock(s.key)}
            />
          ))}
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Shocks are standardized illustrative intensities (z-score-like units; multipliers
          neutral at ×1.00) applied deterministically on top of the selected template —
          hypothetical what-ifs, not forecasts, not investment, trading, or allocation advice.
          Remaining template shocks (USD, equity, rates, spreads, funding, DeFi liquidity, whale
          concentration) stay at their template values.
        </p>
      </div>

      {/* ── Impact dashboard ─────────────────────────────────────────────── */}
      {r && regimeTone && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Scenario impact dashboard</p>
            <span
              className="rounded-full px-3 py-1 text-[12px] font-semibold uppercase tracking-wide"
              style={{ background: regimeTone.bg, border: "1px solid var(--line)", color: regimeTone.color }}
            >
              {r.scenario_regime.regime_label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MetricCard
              label="Composite severity"
              value={`${num(r.composite_severity, 1)}/100`}
              tone={r.composite_severity >= 55 ? "danger" : r.composite_severity >= 35 ? "warn" : "accent"}
            />
            <MetricCard label="Regime severity (all modules)" value={`${num(r.scenario_regime.severity_score, 1)}/100`} />
            <MetricCard label="Modules included" value={`${r.module_impacts.length} / 8`} />
            <MetricCard label="Report coverage" value={pct(r.report_builder.section_coverage, 0)} />
          </div>
          {/* Severity gauge */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
              <span>Severity gauge</span>
              <span className="mono">{num(r.composite_severity, 1)}/100</span>
            </div>
            <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.min(Math.max(r.composite_severity, 0), 100)}%`,
                  background: r.composite_severity >= 55 ? "var(--risk)" : r.composite_severity >= 35 ? "var(--warn)" : "var(--accent)",
                }}
              />
            </div>
          </div>
          <p className="mt-3 text-sm" style={{ color: "var(--text-hi)" }}>{r.scenario_regime.explanation}</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {r.scenario_regime.drivers.map((d) => <li key={d}>{d}</li>)}
          </ul>
        </div>
      )}

      {/* ── Charts: module impacts / baseline vs stress / radar ─────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4">
            <p className="section-title mb-2">Module impact scores</p>
            <ScenarioBarChart
              ariaLabel="Module impact scores by module, 0 to 100"
              data={r.module_impacts.map((m) => ({
                label: MODULE_SHORT[m.module_id],
                value: m.impact_score,
                color: BUCKET_COLOR[m.impact_bucket],
              }))}
              format={(v) => `${v.toFixed(1)}/100`}
              height={230}
            />
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Baseline vs stressed module scores</p>
            <GroupedBarChart
              data={r.module_impacts.map((m) => ({
                label: MODULE_SHORT[m.module_id],
                baseline: m.baseline_score,
                stressed: m.stressed_score,
              }))}
              series={[
                { key: "baseline", label: "Baseline", color: seriesColor(0) },
                { key: "stressed", label: "Stressed", color: seriesColor(4) },
              ]}
              format={(v) => v.toFixed(1)}
              height={230}
            />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Baselines are illustrative calm-state sample readings; stressed = baseline + impact
              (capped at 100).
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Cross-module impact radar</p>
            <ImpactRadar
              rows={r.module_impacts.map((m) => ({ label: MODULE_SHORT[m.module_id], value: m.impact_score }))}
            />
          </div>
        </div>
      )}

      {/* ── Heatmap ──────────────────────────────────────────────────────── */}
      {r && heatmapRows.length > 0 && (
        <div className="card p-4">
          <p className="section-title mb-2">Scenario heatmap — module × shock group</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Module</th>
                  {heatmapColumns.map((c) => (
                    <th key={c} className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmapRows.map((row) => (
                  <tr key={row} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row}</td>
                    {heatmapColumns.map((col) => {
                      const cell = r.heatmap.find((c) => c.row_label === row && c.column_label === col);
                      const v = cell?.value ?? 0;
                      return (
                        <td key={col} className="px-1 py-1">
                          <div
                            className="mono rounded-md px-1 py-1 text-center text-[11px]"
                            title={cell ? `${row} × ${col}: ${num(v, 1)} pts (${cell.bucket})` : undefined}
                            style={{
                              background: `rgba(var(--accent-rgb), ${(0.04 + 0.55 * (Math.min(v, 100) / 100)).toFixed(3)})`,
                              color: v >= 45 ? "var(--text-hi)" : "var(--text-mut)",
                            }}
                          >
                            {v.toFixed(0)}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Each cell is the shock group&apos;s weighted contribution (points) to that module&apos;s
            impact score — a documented teaching decomposition, not a risk measurement.
          </p>
        </div>
      )}

      {/* ── Module impact cards (click to include/exclude) ──────────────── */}
      {sample && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Module impact cards</p>
            <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
              Click a card to include/exclude the module (at least one stays included).
            </span>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {sample.modules.map((m) => {
              const included = includedModules.includes(m.module_id);
              const row = r?.module_impacts.find((x) => x.module_id === m.module_id);
              return (
                <button
                  key={m.module_id}
                  type="button"
                  onClick={() => toggleModule(m.module_id)}
                  aria-pressed={included}
                  className="rounded-xl p-3 text-left transition-opacity"
                  style={{
                    background: "var(--glass)",
                    border: `1px solid ${included ? "var(--accent-line)" : "var(--line)"}`,
                    opacity: included ? 1 : 0.45,
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{m.module_label}</span>
                    {row && (
                      <span className="mono text-sm font-semibold" style={{ color: BUCKET_COLOR[row.impact_bucket] }}>
                        {row.impact_score.toFixed(1)}
                      </span>
                    )}
                  </div>
                  {row ? (
                    <>
                      <p className="mt-1 text-[11px] uppercase tracking-wide" style={{ color: BUCKET_COLOR[row.impact_bucket] }}>
                        {row.impact_bucket} stress
                      </p>
                      <ul className="mt-1 space-y-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                        {row.drivers.slice(0, 2).map((d) => <li key={d}>• {d}</li>)}
                      </ul>
                    </>
                  ) : (
                    <p className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
                      {included ? "Awaiting analysis…" : "Excluded from this run"}
                    </p>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Baseline vs stress metric table ──────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Baseline vs stressed sample metrics</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Metric</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Baseline</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Stressed</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Change</th>
                </tr>
              </thead>
              <tbody>
                {r.baseline_vs_stress.map((row) => (
                  <tr key={row.metric_name} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.metric_name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(row.baseline_value, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(row.stressed_value, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: Math.abs(row.change) < 1e-9 ? "var(--text-mut)" : row.change > 0 ? "var(--warn)" : "var(--accent-text)" }}>
                      {signedNum(row.change, 3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Illustrative sample metrics with simplified linear transforms — not portfolio,
            position, or protocol measurements.
          </p>
        </div>
      )}

      {/* ── Report builder ───────────────────────────────────────────────── */}
      {sample && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4">
            <p className="section-title mb-2">Report builder — sections</p>
            <div className="space-y-1.5">
              {sample.sections.map((s) => {
                const included = s.section_id === "limitations" || includedSections.includes(s.section_id);
                return (
                  <label
                    key={s.section_id}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                    style={{ background: included ? "var(--accent-softer)" : "var(--glass)", border: "1px solid var(--line)" }}
                  >
                    <input
                      type="checkbox"
                      checked={included}
                      disabled={s.section_id === "limitations"}
                      onChange={() => toggleSection(s.section_id)}
                      style={{ accentColor: "var(--accent)" }}
                    />
                    <span style={{ color: included ? "var(--text-hi)" : "var(--text-mut)" }}>{s.section_title}</span>
                    {s.section_id === "limitations" && (
                      <span className="ml-auto text-[10px] uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>always on</span>
                    )}
                  </label>
                );
              })}
            </div>
            {r && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
                  <span>Section coverage</span>
                  <span className="mono">{pct(r.report_builder.section_coverage, 0)}</span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                  <div className="h-full rounded-full" style={{ width: `${r.report_builder.section_coverage * 100}%`, background: "var(--accent)" }} />
                </div>
              </div>
            )}
          </div>
          <div className="card p-4 xl:col-span-2">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="section-title">Generated report preview (Markdown)</p>
              <div className="flex items-center gap-2">
                {copyStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{copyStatus}</span>}
                <button
                  type="button"
                  onClick={copyReport}
                  disabled={!r}
                  className="rounded-md px-2.5 py-1 text-xs font-semibold"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)", opacity: r ? 1 : 0.5 }}
                >
                  📋 Copy report Markdown
                </button>
              </div>
            </div>
            {r ? (
              <pre
                className="mono max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg p-3 text-[11.5px] leading-relaxed"
                style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
              >
                {r.generated_report.markdown}
              </pre>
            ) : (
              <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>Awaiting analysis…</p>
            )}
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              A deterministic educational summary assembled from the scores above — not a
              production risk report and not investment research.
            </p>
          </div>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={STUDIO_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Deterministic static sample scenario templates — no live macro, market, crypto, or news data; no scraping, LLM, or provider APIs.</li>
          <li>Module impact scores are documented linear teaching weights on standardized shock units — they do not call the underlying lab engines and are not risk measurements.</li>
          <li>The scenario regime uses fixed deterministic thresholds — a constructed classification, not a market regime detector.</li>
          <li>Educational only — not investment, trading, asset-allocation, legal, tax, or risk-management advice, and not a production risk report.</li>
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
