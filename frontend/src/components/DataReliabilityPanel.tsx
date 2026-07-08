"use client";

/**
 * Data Mode Registry, Offline Fixtures & API Reliability Center v1
 * (Phase 35.0).
 *
 * A product reliability layer over hand-maintained static metadata: see which
 * modules are fully static/local, which may reach the optional external
 * providers (disabled by default, fail closed, never relied on in tests),
 * which offline fixtures back the default demos (including the KO/PEP pairs
 * demo fallback), and how missing data is handled — with documented rate
 * formulas, a reliability score, and a copyable Markdown/JSON report.
 *
 * This panel never calls the providers it describes. No telemetry, no live
 * data, no availability guarantees. Educational only — not investment,
 * trading, or compliance advice; not a data governance system.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import { ScenarioBarChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  BUCKET_LABELS,
  DATA_MODE_LABELS,
  FAILURE_MODE_LABELS,
  FIXTURE_TYPE_LABELS,
  analyzeDataReliability,
  fetchDataReliabilitySample,
  num,
  pct,
  type DataMode,
  type DataReliabilityAnalysisResponse,
  type DataReliabilityRequest,
  type DataReliabilitySampleResponse,
  type ReliabilitySectionId,
} from "@/lib/dataReliability";

const MODE_TONE: Record<DataMode, string> = {
  static_sample: "var(--accent-text)",
  delayed_sample: "var(--warn)",
  user_input: "var(--emerald)",
  local_calculation: "var(--emerald)",
  optional_external_provider: "var(--warn)",
};

const RELIABILITY_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Coverage rates",
    formulas: [
      { label: "Demo-safe rate", latex: "D = \\frac{N_{\\mathrm{demo\\ safe}}}{N_{\\mathrm{modules}}}" },
      { label: "Test-safe rate", latex: "T = \\frac{N_{\\mathrm{test\\ safe}}}{N_{\\mathrm{modules}}}" },
      { label: "Offline fallback coverage", latex: "F = \\frac{N_{\\mathrm{fallback}}}{N_{\\mathrm{modules}}}" },
      { label: "External provider exposure", latex: "E = \\frac{N_{\\mathrm{external}}}{N_{\\mathrm{modules}}}" },
    ],
  },
  {
    title: "Reliability score",
    formulas: [
      {
        label: "Reliability score",
        latex: "R = 100 \\left( 0.35D + 0.25T + 0.25F + 0.15(1 - E) \\right)",
        note: "A documented teaching formula over hand-maintained registry flags — not an SLA or uptime measurement.",
      },
    ],
  },
];

function yesNo(b: boolean): { text: string; color: string } {
  return b ? { text: "✓", color: "var(--emerald)" } : { text: "—", color: "var(--text-faint)" };
}

export default function DataReliabilityPanel() {
  const [sample, setSample] = useState<DataReliabilitySampleResponse | null>(null);
  const [category, setCategory] = useState<string>("all");
  const [selectedModules, setSelectedModules] = useState<string[] | null>(null); // null = all
  const [includeExternal, setIncludeExternal] = useState(true);
  const [includeFixtures, setIncludeFixtures] = useState(true);
  const [includeTestSafety, setIncludeTestSafety] = useState(true);
  const [sections, setSections] = useState<ReliabilitySectionId[]>([]);
  const [result, setResult] = useState<DataReliabilityAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchDataReliabilitySample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSections(s.default_request.report_sections);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const categoryLabel = useMemo(() => {
    const map: Record<string, string> = {};
    sample?.categories.forEach((c) => { map[c.category] = c.category_label; });
    return (id: string) => map[id] ?? id;
  }, [sample]);

  // Modules visible under the current category filter (for the selector chips).
  const categoryModules = useMemo(
    () => (sample?.module_modes ?? []).filter((m) => category === "all" || m.category === category),
    [sample, category],
  );

  function moduleSelected(id: string): boolean {
    return selectedModules === null || selectedModules.includes(id);
  }

  function toggleModule(id: string) {
    const all = categoryModules.map((m) => m.module_id);
    const current = selectedModules === null ? all : selectedModules;
    const next = current.includes(id)
      ? current.filter((m) => m !== id)
      : all.filter((m) => current.includes(m) || m === id);
    if (next.length === 0) return; // keep at least one module in scope
    setSelectedModules(next.length === all.length ? null : next);
  }

  function selectCategory(c: string) {
    setCategory(c);
    setSelectedModules(null);
  }

  function toggleSection(id: ReliabilitySectionId) {
    setSections((secs) =>
      secs.includes(id) ? (secs.length > 1 ? secs.filter((s) => s !== id) : secs) : [...secs, id],
    );
  }

  const request = useMemo<DataReliabilityRequest | null>(() => {
    if (!sample || sections.length === 0) return null;
    const orderedSections = sample.sections
      .map((s) => s.section_id)
      .filter((s) => sections.includes(s));
    return {
      selected_category: category === "all" ? null : category,
      include_external_providers: includeExternal,
      include_static_fixtures: includeFixtures,
      include_test_safety: includeTestSafety,
      selected_modules: selectedModules,
      report_sections: orderedSections,
    };
  }, [sample, category, selectedModules, includeExternal, includeFixtures, includeTestSafety, sections]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeDataReliability(request, ctrl.signal)
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
  const summary = r?.reliability_summary;

  const modeChart = useMemo(() => {
    if (!r) return [];
    const counts: Record<string, number> = {};
    r.module_modes.forEach((m) => { counts[m.data_mode] = (counts[m.data_mode] ?? 0) + 1; });
    return (Object.keys(DATA_MODE_LABELS) as DataMode[])
      .filter((mode) => (counts[mode] ?? 0) > 0)
      .map((mode, i) => ({ label: DATA_MODE_LABELS[mode], value: counts[mode] ?? 0, color: seriesColor(i) }));
  }, [r]);

  const providerChart = useMemo(() => {
    if (!r) return [];
    const scope = new Set(r.module_modes.map((m) => m.module_id));
    return r.providers.map((p) => ({
      label: p.provider_name.replace(" Optional Provider", " (optional)").replace(" Provider", ""),
      value: p.used_by_modules.filter((m) => scope.has(m)).length,
      color: p.is_external ? "var(--warn)" : seriesColor(0),
    }));
  }, [r]);

  const safetyChart = useMemo(() => {
    if (!r) return [];
    const rows = r.module_modes;
    return [
      { label: "Demo safe", value: rows.filter((m) => m.demo_safe).length, color: seriesColor(0) },
      { label: "Test safe", value: rows.filter((m) => m.test_safe).length, color: seriesColor(1) },
      { label: "Offline fallback", value: rows.filter((m) => m.offline_fallback_available).length, color: seriesColor(2) },
      { label: "Deterministic default demo", value: rows.filter((m) => m.default_demo_deterministic).length, color: seriesColor(3) },
      { label: "External provider possible", value: rows.filter((m) => m.external_provider_required).length, color: "var(--warn)" },
    ];
  }, [r]);

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
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Data Mode Registry &amp; API Reliability Center</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This workspace uses the backend static reliability-metadata API. Start the QuantLab API and reopen it.
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
              Data Mode Registry &amp; API Reliability Center
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              See which modules are fully static or local, which may reach the optional external
              providers (disabled by default, never relied on in tests), which offline fixtures
              back the default demos, and how missing data is handled — so demos stay
              deterministic.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static reliability metadata
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative reliability metadata. Data-mode registry, offline fixtures, and API reliability diagnostics are educational and not investment, trading, legal, tax, compliance, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Controls ─────────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Scope &amp; report controls</p>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Category filter">
          <button type="button" onClick={() => selectCategory("all")} aria-pressed={category === "all"}
            className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
            style={{
              background: category === "all" ? "var(--accent-softer)" : "var(--glass)",
              border: `1px solid ${category === "all" ? "var(--accent-line)" : "var(--line)"}`,
              color: category === "all" ? "var(--accent-text)" : "var(--text-mut)",
            }}>All categories</button>
          {sample?.categories.map((c) => (
            <button key={c.category} type="button" onClick={() => selectCategory(c.category)} aria-pressed={category === c.category}
              className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
              style={{
                background: category === c.category ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${category === c.category ? "var(--accent-line)" : "var(--line)"}`,
                color: category === c.category ? "var(--accent-text)" : "var(--text-mut)",
              }}>{c.category_label}</button>
          ))}
        </div>
        <div className="mt-3">
          <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
            Modules in scope (click to include/exclude; at least one stays)
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {categoryModules.map((m) => {
              const on = moduleSelected(m.module_id);
              return (
                <button key={m.module_id} type="button" onClick={() => toggleModule(m.module_id)} aria-pressed={on}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-opacity"
                  style={{
                    background: on ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${on ? "var(--accent-line)" : "var(--line)"}`,
                    color: on ? "var(--accent-text)" : "var(--text-mut)",
                    opacity: on ? 1 : 0.55,
                  }}>{m.module_name}</button>
              );
            })}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
            <input type="checkbox" checked={includeExternal} onChange={(e) => setIncludeExternal(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
            Include external providers
          </label>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
            <input type="checkbox" checked={includeFixtures} onChange={(e) => setIncludeFixtures(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
            Include static fixtures
          </label>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
            <input type="checkbox" checked={includeTestSafety} onChange={(e) => setIncludeTestSafety(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
            Include test safety
          </label>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Report sections">
            {sample?.sections.map((s) => {
              const on = sections.includes(s.section_id);
              return (
                <button key={s.section_id} type="button" onClick={() => toggleSection(s.section_id)} aria-pressed={on}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                  style={{
                    background: on ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${on ? "var(--accent-line)" : "var(--line)"}`,
                    color: on ? "var(--accent-text)" : "var(--text-mut)",
                  }}>{s.section_title}</button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Reliability summary ──────────────────────────────────────────── */}
      {r && summary && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Reliability summary</p>
            <span className="rounded-full px-3 py-1 text-[12px] font-semibold uppercase tracking-wide"
              style={{
                background: summary.reliability_score >= 75 ? "var(--accent-softer)" : "var(--warn-soft)",
                border: "1px solid var(--line)",
                color: summary.reliability_score >= 90 ? "var(--emerald)" : summary.reliability_score >= 75 ? "var(--accent-text)" : "var(--warn)",
              }}>
              {BUCKET_LABELS[summary.reliability_bucket] ?? summary.reliability_bucket}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Modules in scope" value={String(summary.module_count)} />
            <MetricCard label="Demo-safe rate" value={pct(summary.demo_safe_rate)} tone="positive" />
            <MetricCard label="Test-safe rate" value={pct(summary.test_safe_rate)} tone="positive" />
            <MetricCard label="Fallback coverage" value={pct(summary.fallback_coverage)} />
            <MetricCard label="External exposure" value={pct(summary.external_provider_exposure)} tone={summary.external_provider_exposure > 0.25 ? "warn" : "default"} />
            <MetricCard label="Reliability score" value={`${num(summary.reliability_score, 1)}/100`} tone={summary.reliability_score >= 90 ? "positive" : summary.reliability_score >= 75 ? "accent" : "warn"} />
          </div>
          <div className="mt-3">
            <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
              <span>Reliability gauge</span>
              <span className="mono">{num(summary.reliability_score, 1)}/100</span>
            </div>
            <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div className="h-full rounded-full"
                style={{
                  width: `${Math.min(Math.max(summary.reliability_score, 0), 100)}%`,
                  background: summary.reliability_score >= 90 ? "var(--emerald)" : summary.reliability_score >= 75 ? "var(--accent)" : "var(--warn)",
                }} />
            </div>
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {summary.drivers.map((d) => <li key={d}>{d}</li>)}
          </ul>
        </div>
      )}

      {/* ── Charts ───────────────────────────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4">
            <p className="section-title mb-2">Data-mode distribution</p>
            <ScenarioBarChart data={modeChart} format={(v) => `${v.toFixed(0)} module(s)`} height={190} />
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Provider usage (scoped modules)</p>
            <ScenarioBarChart data={providerChart} format={(v) => `${v.toFixed(0)} module(s)`} height={190} />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Amber bars are optional external providers — disabled by default, never relied on in tests.
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Safety &amp; fallback coverage</p>
            <ScenarioBarChart data={safetyChart} format={(v) => `${v.toFixed(0)} / ${r.module_modes.length}`} height={190} />
          </div>
        </div>
      )}

      {/* ── Module data-mode table ───────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Module data modes</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Module</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Data mode</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Demo safe</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Test safe</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">External</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Fallback</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Failure behavior</th>
                </tr>
              </thead>
              <tbody>
                {r.module_modes.map((m) => (
                  <tr key={m.module_id} style={{ borderTop: "1px solid var(--line)" }} title={m.limitations[0]}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{m.module_name}</td>
                    <td className="px-2 py-1.5 text-[11px] font-semibold" style={{ color: MODE_TONE[m.data_mode] }}>{DATA_MODE_LABELS[m.data_mode]}</td>
                    {[m.demo_safe, m.test_safe, m.external_provider_required, m.offline_fallback_available].map((flag, i) => {
                      const isExternalCol = i === 2;
                      const v = isExternalCol
                        ? (flag ? { text: "possible", color: "var(--warn)" } : { text: "no", color: "var(--text-faint)" })
                        : yesNo(flag);
                      return (
                        <td key={i} className="mono px-2 py-1.5 text-center text-[11px]" style={{ color: v.color }}>{v.text}</td>
                      );
                    })}
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{m.failure_behavior}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hover a row for its headline limitation. Flags are hand-maintained static annotations
            fact-checked against the code when written — not runtime checks.
          </p>
        </div>
      )}

      {/* ── Test-safety matrix ───────────────────────────────────────────── */}
      {r && r.test_safety_matrix.length > 0 && (
        <div className="card p-4">
          <p className="section-title mb-2">Test-safety matrix</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {r.test_safety_matrix.map((row) => (
              <div key={row.module_id} className="flex items-start gap-2.5 rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <span className="mono mt-0.5 flex-shrink-0 text-sm font-bold" style={{ color: row.test_safe ? "var(--emerald)" : "var(--risk)" }}>
                  {row.test_safe ? "✓" : "✗"}
                </span>
                <div className="min-w-0">
                  <p className="text-sm" style={{ color: "var(--text-hi)" }}>
                    {row.module_name}
                    {row.external_provider_required && (
                      <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--warn)" }}>optional provider</span>
                    )}
                  </p>
                  <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>{row.notes}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Provider registry ────────────────────────────────────────────── */}
      {r && r.providers.length > 0 && (
        <div className="card p-4">
          <p className="section-title mb-2">Provider registry</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Provider</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Type</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Network</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">API key</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">In tests</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">On failure</th>
                </tr>
              </thead>
              <tbody>
                {r.providers.map((p) => (
                  <tr key={p.provider_id} style={{ borderTop: "1px solid var(--line)" }} title={p.limitations[0]}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>
                      {p.provider_name}
                      {p.is_external && (
                        <span className="ml-1.5 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", color: "var(--warn)" }}>external</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{p.provider_type.replace("_", " ")}</td>
                    {[p.requires_network, p.requires_api_key, p.allowed_in_tests].map((flag, i) => {
                      const v = i === 2 ? (flag ? yesNo(true) : { text: "never", color: "var(--warn)" }) : yesNo(flag);
                      return <td key={i} className="mono px-2 py-1.5 text-center text-[11px]" style={{ color: v.color }}>{v.text}</td>;
                    })}
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{FAILURE_MODE_LABELS[p.default_failure_mode]} — {p.user_message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Offline fixture registry ─────────────────────────────────────── */}
      {r && r.offline_fixtures.length > 0 && (
        <div className="card p-4">
          <p className="section-title mb-2">Offline fixture registry</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Fixture</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Type</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Records</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Range</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Used by</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Deterministic</th>
                </tr>
              </thead>
              <tbody>
                {r.offline_fixtures.map((f) => (
                  <tr key={f.fixture_id} style={{ borderTop: "1px solid var(--line)" }} title={`${f.description} ${f.limitations[0]}`}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{f.fixture_name}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{FIXTURE_TYPE_LABELS[f.fixture_type]}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{f.observation_count}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{f.date_range_label}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{f.used_by_modules.join(", ")}</td>
                    <td className="mono px-2 py-1.5 text-center text-[11px]" style={{ color: "var(--emerald)" }}>{f.deterministic && f.test_safe ? "✓✓" : "✓"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            ✓✓ = deterministic and test-safe. Hover a row for the fixture description and limitation.
          </p>
        </div>
      )}

      {/* ── Generated report ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Generated reliability report (Markdown)</p>
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
            {r.generated_report.markdown}
          </pre>
        ) : (
          <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>Awaiting analysis…</p>
        )}
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          A deterministic educational reliability summary — not an SLA, uptime measurement, audit,
          or data governance record.
        </p>
      </div>

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={RELIABILITY_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Hand-maintained static registry fact-checked against the code when written — not telemetry, and it can drift until manually re-reviewed.</li>
          <li>Optional external providers (yfinance, FRED, delayed quotes) are disabled by default, fail closed, and are never relied on in tests; their availability is never guaranteed.</li>
          <li>This panel never calls any provider it describes — it serves static metadata only.</li>
          <li>Educational only — not investment, trading, legal, tax, compliance, or risk-management advice, and not a production data governance system.</li>
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
