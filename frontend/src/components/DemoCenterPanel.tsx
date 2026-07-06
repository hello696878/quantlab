"use client";

/**
 * Product Demo Center, Guided Walkthroughs & Module Health Dashboard v1
 * (Phase 34.0).
 *
 * A product-UX layer over static demo metadata: pick a guided walkthrough,
 * tailor it to an audience and time budget, inspect module health / data-mode
 * badges and the capability matrix, and copy an audience-specific demo script
 * (Markdown or JSON). Step cards deep-link into the actual modules via the
 * app's normal navigation.
 *
 * Optional demo preferences persist via localStorage only (client-side,
 * loaded after mount so SSR never depends on storage; guarded for
 * unavailable storage; explicit reset control). No telemetry, no live data,
 * no login. Educational only — not investment, trading, asset-allocation, or
 * compliance advice; no module is a production trading system.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import { ScenarioBarChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  AUDIENCE_LABELS,
  DATA_MODE_LABELS,
  STATUS_LABELS,
  analyzeDemoCenter,
  fetchDemoCenterSample,
  num,
  pct,
  type AudienceId,
  type DemoCenterAnalysisResponse,
  type DemoCenterRequest,
  type DemoCenterSampleResponse,
  type ModuleStatus,
  type ScriptSectionId,
} from "@/lib/demoCenter";

const STATUS_TONE: Record<ModuleStatus, string> = {
  stable_demo: "var(--emerald)",
  static_sample_only: "var(--accent-text)",
  experimental: "var(--warn)",
  review_needed: "var(--risk)",
};

const CATEGORY_LABELS: Record<string, string> = {
  platform: "Platform",
  backtesting: "Backtesting",
  portfolio_risk: "Portfolio Risk",
  macro_cross_asset: "Macro & Cross-Asset",
  research_workflow: "Research Workflow",
  crypto: "Crypto",
  alternative_data: "Alternative Data",
  microstructure: "Microstructure",
  derivatives_volatility: "Derivatives & Vol",
  real_assets_credit: "Real Assets & Credit",
};

const CAPABILITY_COLUMNS = [
  { key: "has_backend_endpoint", label: "Backend" },
  { key: "has_charts", label: "Charts" },
  { key: "has_interactive_controls", label: "Controls" },
  { key: "has_formula_panel", label: "Formulas" },
  { key: "has_report_export", label: "Export" },
] as const;

const DEMO_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Demo coverage & readiness",
    formulas: [
      { label: "Category coverage", latex: "C = \\frac{N_{\\mathrm{categories\\ included}}}{N_{\\mathrm{categories\\ available}}}" },
      {
        label: "Readiness score",
        latex: "R = \\frac{1}{N} \\sum_{i=1}^{N} r_i",
        note: "r: stable demo 1.0, static sample only 0.85, experimental 0.65, review needed 0.5.",
      },
    ],
  },
  {
    title: "Script & complexity",
    formulas: [
      {
        label: "Demo complexity",
        latex: "D = 0.4\\,M_{\\mathrm{norm}} + 0.3\\,S_{\\mathrm{norm}} + 0.3\\,T_{\\mathrm{norm}}",
        note: "Normalizers: 10 modules, 10 steps, 60 minutes ≙ 1.0 (clamped).",
      },
      { label: "Script coverage", latex: "Q = \\frac{N_{\\mathrm{selected\\ sections}}}{N_{\\mathrm{available\\ sections}}}" },
      { label: "Capability score", latex: "K = \\frac{N_{\\mathrm{enabled\\ capabilities}}}{N_{\\mathrm{total\\ capabilities}}}" },
    ],
  },
];

// --------------------------------------------------------------------------- //
// Browser-local demo preferences (localStorage only; guarded; post-mount)
// --------------------------------------------------------------------------- //
const PREFS_KEY = "quantlab.demo_center.prefs.v1";

interface DemoPrefs {
  path_id: string;
  audience: AudienceId;
  time_budget: number;
  script_sections: ScriptSectionId[];
  include_limitations: boolean;
  include_technical_notes: boolean;
}

function readPrefs(): DemoPrefs | null {
  try {
    const raw = window.localStorage.getItem(PREFS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (typeof p?.path_id !== "string" || !Array.isArray(p?.script_sections)) return null;
    return p as DemoPrefs;
  } catch {
    return null;
  }
}

function writePrefs(prefs: DemoPrefs): void {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // storage unavailable — preferences simply don't persist
  }
}

export default function DemoCenterPanel({ onNav }: { onNav?: (route: string) => void }) {
  const [sample, setSample] = useState<DemoCenterSampleResponse | null>(null);
  const [selectedId, setSelectedId] = useState("founder_investor_product_tour");
  const [audience, setAudience] = useState<AudienceId>("general");
  const [timeBudget, setTimeBudget] = useState(20);
  const [sections, setSections] = useState<ScriptSectionId[]>([]);
  const [includeLimitations, setIncludeLimitations] = useState(true);
  const [includeTechNotes, setIncludeTechNotes] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [result, setResult] = useState<DemoCenterAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [prefsLoaded, setPrefsLoaded] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchDemoCenterSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        // Defaults first; then stored preferences (client-only, validated).
        setSelectedId(s.default_request.selected_path_id);
        setAudience(s.default_request.selected_audience);
        setTimeBudget(s.default_request.time_budget_minutes);
        setSections(s.default_request.script_sections);
        setIncludeLimitations(s.default_request.include_limitations);
        setIncludeTechNotes(s.default_request.include_technical_notes);
        const prefs = typeof window !== "undefined" ? readPrefs() : null;
        if (prefs) {
          if (s.demo_paths.some((p) => p.path_id === prefs.path_id)) setSelectedId(prefs.path_id);
          if (s.audiences.includes(prefs.audience)) setAudience(prefs.audience);
          if (Number.isFinite(prefs.time_budget) && prefs.time_budget > 0) setTimeBudget(prefs.time_budget);
          const validSections = new Set(s.script_sections.map((x) => x.section_id));
          const secs = prefs.script_sections.filter((x) => validSections.has(x));
          if (secs.length > 0) setSections(secs);
          setIncludeLimitations(prefs.include_limitations !== false);
          setIncludeTechNotes(prefs.include_technical_notes === true);
        }
        setPrefsLoaded(true);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  // Persist preferences after the initial load (guarded; client-only).
  useEffect(() => {
    if (!prefsLoaded) return;
    writePrefs({
      path_id: selectedId,
      audience,
      time_budget: timeBudget,
      script_sections: sections,
      include_limitations: includeLimitations,
      include_technical_notes: includeTechNotes,
    });
  }, [prefsLoaded, selectedId, audience, timeBudget, sections, includeLimitations, includeTechNotes]);

  function resetPrefs() {
    try {
      window.localStorage.removeItem(PREFS_KEY);
    } catch {
      // storage unavailable — nothing to clear
    }
    if (!sample) return;
    setSelectedId(sample.default_request.selected_path_id);
    setAudience(sample.default_request.selected_audience);
    setTimeBudget(sample.default_request.time_budget_minutes);
    setSections(sample.default_request.script_sections);
    setIncludeLimitations(sample.default_request.include_limitations);
    setIncludeTechNotes(sample.default_request.include_technical_notes);
    setCategoryFilter("all");
  }

  function toggleSection(id: ScriptSectionId) {
    setSections((secs) =>
      secs.includes(id) ? (secs.length > 1 ? secs.filter((s) => s !== id) : secs) : [...secs, id],
    );
  }

  const path = sample?.demo_paths.find((p) => p.path_id === selectedId) ?? null;

  const request = useMemo<DemoCenterRequest | null>(() => {
    if (!sample || !path || sections.length === 0) return null;
    const orderedSections = sample.script_sections
      .map((s) => s.section_id)
      .filter((s) => sections.includes(s));
    return {
      selected_path_id: path.path_id,
      selected_audience: audience,
      included_modules: null,
      script_sections: orderedSections,
      time_budget_minutes: timeBudget,
      include_limitations: includeLimitations,
      include_technical_notes: includeTechNotes,
    };
  }, [sample, path, audience, sections, timeBudget, includeLimitations, includeTechNotes]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeDemoCenter(request, ctrl.signal)
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
  const health = r?.module_health ?? sample?.module_health ?? [];
  const categories = useMemo(() => {
    const seen: string[] = [];
    health.forEach((row) => {
      if (!seen.includes(row.category)) seen.push(row.category);
    });
    return seen;
  }, [health]);
  const filteredHealth = health.filter((row) => categoryFilter === "all" || row.category === categoryFilter);

  const readinessChart = useMemo(() => {
    if (!r) return [];
    const byId = new Map(r.module_health.map((row) => [row.module_id, row]));
    const weights: Record<string, number> = {
      stable_demo: 1.0, static_sample_only: 0.85, experimental: 0.65, review_needed: 0.5,
    };
    return r.selected_path.modules
      .map((mid) => byId.get(mid))
      .filter((row): row is NonNullable<typeof row> => row != null)
      .map((row) => ({
        label: row.module_name,
        value: (weights[row.status] ?? 0.5) * 100,
        color: STATUS_TONE[row.status],
      }));
  }, [r]);

  const categoryChart = useMemo(() => {
    if (!r) return [];
    const byId = new Map(r.module_health.map((row) => [row.module_id, row]));
    const counts: Record<string, number> = {};
    r.selected_path.modules.forEach((mid) => {
      const row = byId.get(mid);
      if (row) counts[row.category] = (counts[row.category] ?? 0) + 1;
    });
    return categories.map((c) => ({
      label: CATEGORY_LABELS[c] ?? c,
      value: counts[c] ?? 0,
      color: (counts[c] ?? 0) > 0 ? seriesColor(0) : "var(--line)",
    }));
  }, [r, categories]);

  const capabilityChart = useMemo(() => {
    if (health.length === 0) return [];
    return CAPABILITY_COLUMNS.map((col, i) => ({
      label: col.label,
      value: health.filter((row) => row[col.key]).length,
      color: seriesColor(i),
    }));
  }, [health]);

  async function copyText(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${what} copied ✓`);
    } catch {
      setCopyStatus("Copy failed — select the preview text instead");
    }
    window.setTimeout(() => setCopyStatus(null), 2500);
  }

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Product Demo Center &amp; Guided Walkthroughs</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This workspace uses the backend static demo-metadata API. Start the QuantLab API and reopen it.
        </p>
      </div>
    );
  }

  const summary = r?.readiness_summary;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              Product Demo Center &amp; Guided Walkthroughs
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Follow guided product walkthroughs, inspect module health and capability coverage,
              build audience-specific demo scripts, and jump straight into the right QuantLab
              modules — all from hand-written static demo metadata.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static demo metadata
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative demo metadata. Demo center, module health, and walkthrough scripts are educational and not investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Demo path + audience + controls ─────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Guided demo paths</p>
          <button type="button" onClick={resetPrefs}
            className="rounded-md px-2.5 py-1 text-xs font-semibold"
            style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
            Reset demo preferences
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {sample?.demo_paths.map((p) => (
            <button key={p.path_id} type="button" onClick={() => setSelectedId(p.path_id)} aria-pressed={selectedId === p.path_id}
              className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
              style={{
                background: selectedId === p.path_id ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selectedId === p.path_id ? "var(--accent-line)" : "var(--line)"}`,
                color: selectedId === p.path_id ? "var(--accent-text)" : "var(--text-mut)",
              }}>{p.title}</button>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Audience</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {sample?.audiences.map((a) => (
                <button key={a} type="button" onClick={() => setAudience(a)} aria-pressed={audience === a}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                  style={{
                    background: audience === a ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${audience === a ? "var(--accent-line)" : "var(--line)"}`,
                    color: audience === a ? "var(--accent-text)" : "var(--text-mut)",
                  }}>{AUDIENCE_LABELS[a]}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="block">
              <span className="flex items-baseline justify-between gap-2">
                <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Time budget</span>
                <span className="mono text-[11px] font-semibold" style={{ color: "var(--accent-text)" }}>{timeBudget} min</span>
              </span>
              <input type="range" min={5} max={60} step={5} value={timeBudget} aria-label="Time budget (minutes)"
                onChange={(e) => {
                  const v = Number.parseInt(e.target.value, 10);
                  if (Number.isFinite(v) && v > 0) setTimeBudget(v);
                }}
                className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full"
                style={{ background: "var(--glass)", accentColor: "var(--accent)" }} />
            </label>
            <div className="mt-2 flex flex-wrap gap-3">
              <label className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
                <input type="checkbox" checked={includeLimitations} onChange={(e) => setIncludeLimitations(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
                Include limitations
              </label>
              <label className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
                <input type="checkbox" checked={includeTechNotes} onChange={(e) => setIncludeTechNotes(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
                Include technical notes
              </label>
            </div>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Script sections</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {sample?.script_sections.map((s) => {
                const on = sections.includes(s.section_id);
                return (
                  <button key={s.section_id} type="button" onClick={() => toggleSection(s.section_id)} aria-pressed={on}
                    className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                    style={{
                      background: on ? "var(--accent-softer)" : "var(--glass)",
                      border: `1px solid ${on ? "var(--accent-line)" : "var(--line)"}`,
                      color: on ? "var(--accent-text)" : "var(--text-mut)",
                    }}>{s.section_title}</button>
                );
              })}
            </div>
            <p className="mt-1 text-[10px]" style={{ color: "var(--text-faint)" }}>
              Preferences persist only in this browser (localStorage) — use the reset button to clear them.
            </p>
          </div>
        </div>
      </div>

      {/* ── Path overview ────────────────────────────────────────────────── */}
      {r && path && summary && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Demo path overview</p>
            <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: r.path_summary.fits_time_budget ? "var(--accent-softer)" : "var(--warn-soft)",
                border: "1px solid var(--line)",
                color: r.path_summary.fits_time_budget ? "var(--accent-text)" : "var(--warn)",
              }}>
              {r.path_summary.fits_time_budget ? "Fits time budget" : "Over time budget"}
            </span>
          </div>
          <p className="text-sm" style={{ color: "var(--text-mut)" }}>{path.summary}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Estimated" value={`${num(r.path_summary.estimated_minutes, 0)} min`} />
            <MetricCard label="Modules" value={String(r.path_summary.module_count)} />
            <MetricCard label="Steps" value={String(r.path_summary.step_count)} />
            <MetricCard label="Talking points" value={String(r.path_summary.talking_point_count)} />
            <MetricCard label="Readiness" value={pct(summary.readiness_score)} tone="positive" />
            <MetricCard label="Complexity" value={pct(summary.demo_complexity_score)} tone={summary.demo_complexity_score >= 0.7 ? "warn" : "default"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Learning goals</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
                {path.learning_goals.map((g) => <li key={g}>{g}</li>)}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Output artifacts</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
                {path.output_artifacts.map((a) => <li key={a}>{a}</li>)}
              </ul>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>{r.path_summary.time_note}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Walkthrough timeline ─────────────────────────────────────────── */}
      {path && (
        <div className="card p-4">
          <p className="section-title mb-2">Guided walkthrough</p>
          <ol className="grid grid-cols-1 gap-2 lg:grid-cols-2">
            {path.steps.map((step, i) => (
              <li key={step.step_id} className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                    <span className="mono mr-1.5 text-[11px]" style={{ color: "var(--accent-text)" }}>{i + 1}.</span>
                    {step.title}
                  </p>
                  {onNav && (
                    <button type="button" onClick={() => onNav(step.route)}
                      className="flex-shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold"
                      style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}>
                      Open module →
                    </button>
                  )}
                </div>
                <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{step.description}</p>
                <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>
                  <span style={{ color: "var(--text-hi)" }}>Action:</span> {step.expected_user_action}
                </p>
                <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>
                  <span style={{ color: "var(--text-hi)" }}>Expect:</span> {step.expected_output}
                </p>
                <p className="mt-1 text-[11px] italic" style={{ color: "var(--text-faint)" }}>💡 {step.demo_tip}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* ── Charts ───────────────────────────────────────────────────────── */}
      {r && summary && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4">
            <p className="section-title mb-2">Module readiness (selected path)</p>
            <ScenarioBarChart data={readinessChart} format={(v) => `${v.toFixed(0)}/100`} height={200} />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Documented status weights — hand-maintained labels, not telemetry.
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Category coverage</p>
            <ScenarioBarChart data={categoryChart} format={(v) => `${v.toFixed(0)}`} height={200} />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Path modules per category — C = {pct(summary.category_coverage)} of {categoryChart.length} categories.
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Demo scores</p>
            {[
              { label: "Readiness R", value: summary.readiness_score, color: "var(--emerald)" },
              { label: "Complexity D", value: summary.demo_complexity_score, color: summary.demo_complexity_score >= 0.7 ? "var(--warn)" : "var(--accent)" },
              { label: "Script coverage Q", value: summary.script_coverage, color: "var(--accent)" },
              { label: "Category coverage C", value: summary.category_coverage, color: "var(--accent)" },
            ].map((row) => (
              <div key={row.label} className="mb-2.5">
                <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
                  <span>{row.label}</span>
                  <span className="mono">{pct(row.value)}</span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                  <div className="h-full rounded-full" style={{ width: `${row.value * 100}%`, background: row.color }} />
                </div>
              </div>
            ))}
            <div className="mt-3">
              <p className="section-title mb-2 text-[11px]">Capability counts (all modules)</p>
              <ScenarioBarChart data={capabilityChart} format={(v) => `${v.toFixed(0)} / ${health.length}`} height={130} />
            </div>
          </div>
        </div>
      )}

      {/* ── Completion checklist ─────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Demo completion checklist</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {r.completion_checklist.map((item) => (
              <div key={item.item_id} className="flex items-start gap-2.5 rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <span className="mono mt-0.5 flex-shrink-0 text-sm font-bold" style={{ color: item.passed ? "var(--emerald)" : "var(--warn)" }} aria-label={item.passed ? "passed" : "not passed"}>
                  {item.passed ? "✓" : "✗"}
                </span>
                <div className="min-w-0">
                  <p className="text-sm" style={{ color: "var(--text-hi)" }}>{item.label}</p>
                  <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>{item.notes}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Module health dashboard ──────────────────────────────────────── */}
      {health.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Module health dashboard</p>
            <div className="flex flex-wrap gap-1" role="group" aria-label="Category filter">
              <button type="button" onClick={() => setCategoryFilter("all")} aria-pressed={categoryFilter === "all"}
                className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                style={{
                  background: categoryFilter === "all" ? "var(--accent-softer)" : "var(--glass)",
                  border: `1px solid ${categoryFilter === "all" ? "var(--accent-line)" : "var(--line)"}`,
                  color: categoryFilter === "all" ? "var(--accent-text)" : "var(--text-mut)",
                }}>All</button>
              {categories.map((c) => (
                <button key={c} type="button" onClick={() => setCategoryFilter(c)} aria-pressed={categoryFilter === c}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                  style={{
                    background: categoryFilter === c ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${categoryFilter === c ? "var(--accent-line)" : "var(--line)"}`,
                    color: categoryFilter === c ? "var(--accent-text)" : "var(--text-mut)",
                  }}>{CATEGORY_LABELS[c] ?? c}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {filteredHealth.map((row) => (
              <div key={row.module_id} className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{row.module_name}</p>
                  {onNav && (
                    <button type="button" onClick={() => onNav(row.route)}
                      className="flex-shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold"
                      style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--accent-text)" }}>
                      Open →
                    </button>
                  )}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                    style={{ background: "var(--glass)", border: `1px solid ${STATUS_TONE[row.status]}`, color: STATUS_TONE[row.status] }}>
                    {STATUS_LABELS[row.status]}
                  </span>
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                    style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
                    {DATA_MODE_LABELS[row.data_mode]}
                  </span>
                </div>
                <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{row.limitations[0]}</p>
                <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px]" style={{ color: "var(--text-faint)" }}>
                  {CAPABILITY_COLUMNS.map((col) => (
                    <span key={col.key} style={{ color: row[col.key] ? "var(--emerald)" : "var(--text-faint)" }}>
                      {row[col.key] ? "✓" : "—"} {col.label}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-[10px]" style={{ color: "var(--text-faint)" }}>{row.last_review_label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Capability matrix ────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Capability matrix</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Module</th>
                  {CAPABILITY_COLUMNS.map((c) => (
                    <th key={c.key} className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">{c.label}</th>
                  ))}
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">K</th>
                </tr>
              </thead>
              <tbody>
                {r.capability_matrix.map((row) => (
                  <tr key={row.module_id} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.module_name}</td>
                    {CAPABILITY_COLUMNS.map((c) => (
                      <td key={c.key} className="mono px-2 py-1.5 text-center" style={{ color: row[c.key] ? "var(--emerald)" : "var(--text-faint)" }}>
                        {row[c.key] ? "✓" : "—"}
                      </td>
                    ))}
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: row.capability_score >= 0.8 ? "var(--emerald)" : "var(--text-hi)" }}>
                      {pct(row.capability_score)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            K = enabled capabilities ÷ 5 — hand-maintained static flags, not runtime introspection.
          </p>
        </div>
      )}

      {/* ── Generated demo script ────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Generated demo script (Markdown)</p>
          <div className="flex items-center gap-2">
            {copyStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{copyStatus}</span>}
            <button type="button" disabled={!r} onClick={() => r && copyText(r.export_payload.markdown, "Markdown")}
              className="rounded-md px-2.5 py-1 text-xs font-semibold"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)", opacity: r ? 1 : 0.5 }}>
              📋 Copy Markdown
            </button>
            <button type="button" disabled={!r} onClick={() => r && copyText(r.export_payload.json_payload, "JSON")}
              className="rounded-md px-2.5 py-1 text-xs font-semibold"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)", opacity: r ? 1 : 0.5 }}>
              📋 Copy JSON
            </button>
          </div>
        </div>
        {r ? (
          <pre className="mono max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg p-3 text-[11.5px] leading-relaxed"
            style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}>
            {r.generated_script.markdown}
          </pre>
        ) : (
          <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>Awaiting analysis…</p>
        )}
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          A deterministic educational walkthrough script — not investment research and not a
          production runbook.
        </p>
      </div>

      {/* ── Limitations panel ────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Limitations</p>
        <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Every module runs on deterministic static sample, synthetic, or user-entered data — no live or current market data anywhere.</li>
          <li>Health/status labels and capability flags are hand-maintained static annotations — not telemetry, analytics tracking, or a quality certification.</li>
          <li>Generated demo scripts are educational summaries — not investment research, production runbooks, or compliance material.</li>
          <li>QuantLab is an educational research platform — no module is a production trading system, and nothing here is investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice.</li>
        </ul>
      </div>

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={DEMO_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Demo paths and module health rows are hand-written static demo metadata about QuantLab&apos;s own modules.</li>
          <li>Readiness, coverage, complexity, and capability scores are documented deterministic teaching formulas over those labels.</li>
          <li>Demo preferences (if saved) live only in this browser&apos;s localStorage — no login, no cloud sync, no telemetry.</li>
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
