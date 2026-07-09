"use client";

/**
 * Release Readiness, Smoke Test Matrix & QA Command Center v1 (Phase 36.0).
 *
 * A product-quality workflow layer over hand-maintained static QA metadata:
 * release readiness rates and score, the per-module smoke-test matrix, a
 * grouped manual regression checklist, the exact local verification commands
 * (listed with copy buttons — never executed here), a known-limitations
 * tracker, and a copyable Markdown/JSON release report.
 *
 * This page never runs tests or builds and never claims they were run — the
 * user runs the backend suite, typecheck, and production build locally.
 * Educational project-management aid only — not a compliance system, not
 * investment or trading advice.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import { ScenarioBarChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  DECISION_LABELS,
  PRIORITY_LABELS,
  QA_DATA_MODE_LABELS,
  STATUS_LABELS,
  analyzeQACommandCenter,
  fetchQACommandCenterSample,
  num,
  pct,
  type QaPriority,
  type QaSectionId,
  type QACommandCenterAnalysisResponse,
  type QACommandCenterRequest,
  type QACommandCenterSampleResponse,
  type ReleaseStatus,
} from "@/lib/qaCommandCenter";

const STATUS_TONE: Record<ReleaseStatus, string> = {
  ready: "var(--emerald)",
  needs_review: "var(--warn)",
  experimental: "var(--accent-text)",
  blocked: "var(--risk)",
};

const PRIORITY_ORDER: QaPriority[] = ["critical", "high", "medium", "low"];
const STATUS_ORDER: ReleaseStatus[] = ["ready", "needs_review", "experimental", "blocked"];

const QA_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Coverage rates",
    formulas: [
      { label: "Ready rate", latex: "R = \\frac{N_{\\mathrm{ready}}}{N_{\\mathrm{modules}}}" },
      { label: "Smoke coverage", latex: "S = \\frac{N_{\\mathrm{smoke}}}{N_{\\mathrm{modules}}}" },
      {
        label: "Test coverage proxy",
        latex: "T = \\frac{N_{\\mathrm{tested}}}{N_{\\mathrm{modules}}}",
        note: "Counts modules with test files — not proof that any test was run.",
      },
      { label: "Interactive coverage", latex: "I = \\frac{N_{\\mathrm{interactive}}}{N_{\\mathrm{modules}}}" },
      { label: "Chart coverage", latex: "C = \\frac{N_{\\mathrm{charts}}}{N_{\\mathrm{modules}}}" },
    ],
  },
  {
    title: "Release score",
    formulas: [
      {
        label: "Release score",
        latex: "Q = 100 \\left( 0.30R + 0.20S + 0.20T + 0.15I + 0.15C \\right)",
        note: "A documentation-coverage read over hand-maintained flags — not a certification.",
      },
    ],
  },
];

export default function QACommandCenterPanel() {
  const [sample, setSample] = useState<QACommandCenterSampleResponse | null>(null);
  const [category, setCategory] = useState<string>("all");
  const [statuses, setStatuses] = useState<ReleaseStatus[] | null>(null); // null = all
  const [priorities, setPriorities] = useState<QaPriority[] | null>(null); // null = all
  const [includeManual, setIncludeManual] = useState(true);
  const [includeBackend, setIncludeBackend] = useState(true);
  const [includeFrontend, setIncludeFrontend] = useState(true);
  const [includeLimitations, setIncludeLimitations] = useState(true);
  const [sections, setSections] = useState<QaSectionId[]>([]);
  const [result, setResult] = useState<QACommandCenterAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchQACommandCenterSample(ctrl.signal)
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

  function toggleIn<T extends string>(list: T[] | null, all: T[], value: T): T[] | null {
    const current = list === null ? all : list;
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : all.filter((v) => current.includes(v) || v === value);
    if (next.length === 0) return list; // keep at least one selected
    return next.length === all.length ? null : next;
  }

  function toggleSection(id: QaSectionId) {
    setSections((secs) =>
      secs.includes(id) ? (secs.length > 1 ? secs.filter((s) => s !== id) : secs) : [...secs, id],
    );
  }

  const request = useMemo<QACommandCenterRequest | null>(() => {
    if (!sample || sections.length === 0) return null;
    const orderedSections = sample.sections
      .map((s) => s.section_id)
      .filter((s) => sections.includes(s));
    return {
      selected_category: category === "all" ? null : category,
      selected_release_statuses: statuses,
      selected_priorities: priorities,
      include_manual_steps: includeManual,
      include_backend_checks: includeBackend,
      include_frontend_checks: includeFrontend,
      include_known_limitations: includeLimitations,
      report_sections: orderedSections,
    };
  }, [sample, category, statuses, priorities, includeManual, includeBackend, includeFrontend, includeLimitations, sections]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeQACommandCenter(request, ctrl.signal)
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
  const summary = r?.readiness_summary;

  const statusChart = useMemo(() => {
    if (!r) return [];
    const counts: Record<string, number> = {};
    r.qa_modules.forEach((m) => { counts[m.release_status] = (counts[m.release_status] ?? 0) + 1; });
    return STATUS_ORDER.filter((s) => (counts[s] ?? 0) > 0).map((s) => ({
      label: STATUS_LABELS[s],
      value: counts[s] ?? 0,
      color: STATUS_TONE[s],
    }));
  }, [r]);

  const capabilityChart = useMemo(() => {
    if (!r) return [];
    const rows = r.qa_modules;
    return [
      { label: "Backend endpoint", value: rows.filter((m) => m.has_backend_endpoint).length, color: seriesColor(0) },
      { label: "Charts", value: rows.filter((m) => m.has_charts).length, color: seriesColor(1) },
      { label: "Interactive controls", value: rows.filter((m) => m.has_interactive_controls).length, color: seriesColor(2) },
      { label: "Formula panel", value: rows.filter((m) => m.has_formula_panel).length, color: seriesColor(3) },
      { label: "Test files", value: rows.filter((m) => m.has_tests).length, color: seriesColor(4) },
    ];
  }, [r]);

  const priorityMatrix = useMemo(() => {
    if (!r) return [];
    return PRIORITY_ORDER.map((p) => ({
      priority: p,
      counts: STATUS_ORDER.map((s) => r.qa_modules.filter((m) => m.priority === p && m.release_status === s).length),
      total: r.qa_modules.filter((m) => m.priority === p).length,
    })).filter((row) => row.total > 0);
  }, [r]);

  async function copyText(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${what} copied ✓`);
    } catch {
      setCopyStatus("Copy failed — select the text instead");
    }
    window.setTimeout(() => setCopyStatus(null), 2500);
  }

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Release Readiness &amp; QA Command Center</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This workspace uses the backend static QA-metadata API. Start the QuantLab API and reopen it.
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
              Release Readiness &amp; QA Command Center
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Inspect release readiness, smoke-test coverage, manual regression steps, known
              limitations, and the exact local verification commands — then copy release notes.
              This page lists checks; it never runs them and never claims tests or builds were
              executed.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static QA metadata
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative QA metadata. Release readiness, smoke-test matrix, and QA command center outputs are educational project-management aids and not investment, trading, legal, tax, compliance, or risk-management advice."}
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
          <button type="button" onClick={() => setCategory("all")} aria-pressed={category === "all"}
            className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
            style={{
              background: category === "all" ? "var(--accent-softer)" : "var(--glass)",
              border: `1px solid ${category === "all" ? "var(--accent-line)" : "var(--line)"}`,
              color: category === "all" ? "var(--accent-text)" : "var(--text-mut)",
            }}>All categories</button>
          {sample?.categories.map((c) => (
            <button key={c.category} type="button" onClick={() => setCategory(c.category)} aria-pressed={category === c.category}
              className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
              style={{
                background: category === c.category ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${category === c.category ? "var(--accent-line)" : "var(--line)"}`,
                color: category === c.category ? "var(--accent-text)" : "var(--text-mut)",
              }}>{c.category_label}</button>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Release status filter</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {sample?.release_statuses.map((s) => {
                const on = statuses === null || statuses.includes(s);
                return (
                  <button key={s} type="button" onClick={() => setStatuses(toggleIn(statuses, sample.release_statuses, s))} aria-pressed={on}
                    className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                    style={{
                      background: on ? "var(--accent-softer)" : "var(--glass)",
                      border: `1px solid ${on ? "var(--accent-line)" : "var(--line)"}`,
                      color: on ? STATUS_TONE[s] : "var(--text-mut)",
                      opacity: on ? 1 : 0.55,
                    }}>{STATUS_LABELS[s]}</button>
                );
              })}
            </div>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Priority filter</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {sample?.priorities.map((p) => {
                const on = priorities === null || priorities.includes(p);
                return (
                  <button key={p} type="button" onClick={() => setPriorities(toggleIn(priorities, sample.priorities, p))} aria-pressed={on}
                    className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                    style={{
                      background: on ? "var(--accent-softer)" : "var(--glass)",
                      border: `1px solid ${on ? "var(--accent-line)" : "var(--line)"}`,
                      color: on ? "var(--accent-text)" : "var(--text-mut)",
                      opacity: on ? 1 : 0.55,
                    }}>{PRIORITY_LABELS[p]}</button>
                );
              })}
            </div>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
          {[
            { label: "Manual steps", value: includeManual, set: setIncludeManual },
            { label: "Backend checks", value: includeBackend, set: setIncludeBackend },
            { label: "Frontend checks", value: includeFrontend, set: setIncludeFrontend },
            { label: "Known limitations", value: includeLimitations, set: setIncludeLimitations },
          ].map((t) => (
            <label key={t.label} className="flex cursor-pointer items-center gap-1.5 text-xs" style={{ color: "var(--text-mut)" }}>
              <input type="checkbox" checked={t.value} onChange={(e) => t.set(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
              {t.label}
            </label>
          ))}
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

      {/* ── Readiness summary ────────────────────────────────────────────── */}
      {r && summary && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Readiness summary</p>
            <span className="rounded-full px-3 py-1 text-[12px] font-semibold uppercase tracking-wide"
              style={{
                background: summary.release_decision === "ready_for_demo" ? "var(--accent-softer)" : "var(--warn-soft)",
                border: "1px solid var(--line)",
                color: summary.release_decision === "ready_for_demo" ? "var(--emerald)" : summary.release_decision === "blocked" ? "var(--risk)" : "var(--warn)",
              }}>
              {DECISION_LABELS[summary.release_decision]}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCard label="Modules" value={String(summary.module_count)} />
            <MetricCard label="Ready rate" value={pct(summary.ready_rate)} tone="positive" />
            <MetricCard label="Smoke coverage" value={pct(summary.smoke_coverage)} />
            <MetricCard label="Test proxy" value={pct(summary.test_coverage)} />
            <MetricCard label="Interactive" value={pct(summary.interactive_coverage)} />
            <MetricCard label="Charts" value={pct(summary.chart_coverage)} />
            <MetricCard label="Release score" value={`${num(summary.release_score, 1)}/100`} tone={summary.release_score >= 85 ? "positive" : summary.release_score >= 70 ? "accent" : "warn"} />
          </div>
          <div className="mt-3">
            <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
              <span>Release score gauge (documentation coverage — not proof tests were run)</span>
              <span className="mono">{num(summary.release_score, 1)}/100</span>
            </div>
            <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div className="h-full rounded-full"
                style={{
                  width: `${Math.min(Math.max(summary.release_score, 0), 100)}%`,
                  background: summary.release_score >= 85 ? "var(--emerald)" : summary.release_score >= 70 ? "var(--accent)" : "var(--warn)",
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
            <p className="section-title mb-2">Release status distribution</p>
            <ScenarioBarChart ariaLabel="Module count by release status" data={statusChart} format={(v) => `${v.toFixed(0)} module(s)`} height={170} />
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Capability coverage</p>
            <ScenarioBarChart data={capabilityChart} format={(v) => `${v.toFixed(0)} / ${r.qa_modules.length}`} height={170} />
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Priority × status matrix</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Priority</th>
                    {STATUS_ORDER.map((s) => (
                      <th key={s} className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">{STATUS_LABELS[s]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {priorityMatrix.map((row) => (
                    <tr key={row.priority} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{PRIORITY_LABELS[row.priority]}</td>
                      {row.counts.map((count, i) => (
                        <td key={i} className="px-1 py-1">
                          <div className="mono rounded-md px-1 py-1 text-center text-[11px]"
                            style={{
                              background: count > 0 ? `rgba(var(--accent-rgb), ${(0.08 + 0.4 * Math.min(count / 8, 1)).toFixed(3)})` : "transparent",
                              color: count > 0 ? "var(--text-hi)" : "var(--text-faint)",
                            }}>
                            {count}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Smoke-test matrix ────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Smoke-test matrix</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Module</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Route</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Smoke steps</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Expected</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody>
                {r.smoke_test_matrix.map((row) => (
                  <tr key={row.module_id} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.module_name}</td>
                    <td className="mono px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{row.route}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{row.steps.join(" → ")}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>{row.expected_result}</td>
                    <td className="px-2 py-1.5 text-center text-[11px] font-semibold" style={{ color: STATUS_TONE[row.status_label] }}>
                      {STATUS_LABELS[row.status_label]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Regression checklist ─────────────────────────────────────────── */}
      {r && r.regression_checklist.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Manual regression checklist</p>
            <button type="button"
              onClick={() => copyText(
                r.regression_checklist.map((g) => `${g.category_label}\n${g.items.map((i) => `- [ ] ${i}`).join("\n")}`).join("\n\n"),
                "Checklist",
              )}
              className="rounded-md px-2.5 py-1 text-xs font-semibold"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
              📋 Copy checklist
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {r.regression_checklist.map((g) => (
              <div key={g.category} className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{g.category_label}</p>
                <ul className="mt-1 space-y-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                  {g.items.map((item) => <li key={item}>☐ {item}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Command checklist ────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Command checklist — run locally by the user</p>
          <div className="space-y-2">
            {[
              { label: "Backend tests", cmd: r.command_checklist.backend_test_command, show: includeBackend },
              { label: "Backend dev server", cmd: r.command_checklist.backend_run_command, show: includeBackend },
              { label: "Frontend typecheck", cmd: r.command_checklist.frontend_typecheck_command, show: includeFrontend },
              { label: "Production build (user only)", cmd: r.command_checklist.frontend_build_command_for_user, show: includeFrontend },
            ].filter((row) => row.show).map((row) => (
              <div key={row.label} className="flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <div className="min-w-0">
                  <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{row.label}</p>
                  <p className="mono text-[11.5px]" style={{ color: "var(--text-hi)" }}>{row.cmd}</p>
                </div>
                <button type="button" onClick={() => copyText(row.cmd, row.label)}
                  className="rounded-md px-2 py-1 text-[11px] font-semibold"
                  style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}>
                  Copy
                </button>
              </div>
            ))}
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {r.command_checklist.notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </div>
      )}

      {/* ── Known limitations tracker ────────────────────────────────────── */}
      {r && r.limitation_tracker.length > 0 && (
        <div className="card p-4">
          <p className="section-title mb-2">Known limitations tracker</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {r.limitation_tracker.map((row) => (
              <div key={row.module_id} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                  {row.module_name}
                  <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--warn)" }}>
                    {QA_DATA_MODE_LABELS[row.data_mode]}
                  </span>
                </p>
                <ul className="mt-1 space-y-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                  {row.limitations.map((l) => <li key={l}>• {l}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Generated release report ─────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Generated release report (Markdown)</p>
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
          A deterministic educational release summary — it lists verification commands but does
          not run them, and it never claims tests or builds were executed.
        </p>
      </div>

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={QA_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Hand-maintained static QA registry fact-checked against the code when written — not telemetry, and it can drift until manually re-reviewed.</li>
          <li>The release score is a documentation-coverage read — verification (backend suite, typecheck, production build) is the user&apos;s local step.</li>
          <li>Educational project-management aid only — not a production compliance or release-management system, and not investment or trading advice.</li>
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
