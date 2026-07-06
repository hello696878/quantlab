"use client";

/**
 * Research Workspace, Saved Presets & Experiment Journal v1 (Phase 33.0).
 *
 * A deterministic educational workflow layer: pick a saved research preset,
 * stage/unstage its sample experiment runs, write a workspace note, choose
 * report sections, and inspect a severity-ranked run comparison, module
 * coverage, a reproducibility checklist, a workflow timeline, and a
 * copy-friendly Markdown + JSON export.
 *
 * Optional browser-local drafts use localStorage only (client-side, no
 * accounts, no cloud, no server storage) — loaded after mount so SSR output
 * never depends on storage (no hydration mismatch) and every access is
 * guarded for unavailable storage. All analysis numbers come from the backend
 * static-sample API. Educational only — not investment, trading,
 * asset-allocation, or compliance advice; not production research records.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import { GroupedBarChart, ScenarioBarChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  analyzeResearchWorkspace,
  fetchResearchWorkspaceSample,
  num,
  pct,
  pctChange,
  signedNum,
  type ResearchWorkspaceAnalysisResponse,
  type ResearchWorkspaceSampleResponse,
  type RunComparisonRow,
  type WorkspaceAnalysisRequest,
  type WorkspaceSectionId,
} from "@/lib/researchWorkspace";

type ViewMode = "summary" | "comparison" | "journal" | "export";
type SortMode = "severity" | "name" | "module";

const VIEW_MODES: { id: ViewMode; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "comparison", label: "Comparison" },
  { id: "journal", label: "Journal" },
  { id: "export", label: "Export" },
];

const SORT_MODES: { id: SortMode; label: string }[] = [
  { id: "severity", label: "Severity ↓" },
  { id: "name", label: "Run name" },
  { id: "module", label: "Module" },
];

const CONFIDENCE_TONE: Record<string, string> = {
  low: "var(--warn)",
  medium: "var(--accent-text)",
  high: "var(--emerald)",
};

const TIMELINE_TONE: Record<string, { color: string; label: string }> = {
  complete: { color: "var(--emerald)", label: "complete" },
  in_progress: { color: "var(--warn)", label: "in progress" },
  planned: { color: "var(--text-faint)", label: "planned" },
};

function severityColor(v: number): string {
  return v >= 75 ? "var(--risk)" : v >= 55 ? "var(--warn)" : v >= 35 ? "var(--accent-text)" : "var(--emerald)";
}

const WORKSPACE_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Run comparison",
    formulas: [
      { label: "Run change", latex: "\\Delta x = x_{\\mathrm{stress}} - x_{\\mathrm{base}}" },
      {
        label: "Percentage change",
        latex: "\\Delta x_{\\%} = \\frac{x_{\\mathrm{stress}} - x_{\\mathrm{base}}}{|x_{\\mathrm{base}}| + \\epsilon}",
        note: "ε guards a zero baseline; the UI shows — when |x_base| ≈ 0.",
      },
    ],
  },
  {
    title: "Workspace scores",
    formulas: [
      { label: "Average severity", latex: "\\bar{S} = \\frac{1}{N} \\sum_{i=1}^{N} S_i" },
      { label: "Coverage score", latex: "C = \\frac{N_{\\mathrm{included\\ modules}}}{N_{\\mathrm{available\\ modules}}}" },
      {
        label: "Reproducibility score",
        latex: "R = \\frac{N_{\\mathrm{passed\\ checks}}}{N_{\\mathrm{total\\ checks}}}",
        note: "A documentation-completeness count, not verification that results reproduce.",
      },
    ],
  },
];

// --------------------------------------------------------------------------- //
// Browser-local drafts (localStorage only; guarded; never used during SSR)
// --------------------------------------------------------------------------- //
const DRAFTS_KEY = "quantlab.research_workspace.drafts.v1";

interface WorkspaceDraft {
  draft_id: string;
  name: string;
  saved_at: string;
  preset_id: string;
  included_run_ids: string[] | null;
  user_note: string;
  report_sections: WorkspaceSectionId[];
}

function readDrafts(): WorkspaceDraft[] {
  try {
    const raw = window.localStorage.getItem(DRAFTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (d): d is WorkspaceDraft =>
        typeof d?.draft_id === "string" && typeof d?.preset_id === "string" &&
        typeof d?.name === "string" && Array.isArray(d?.report_sections),
    );
  } catch {
    return [];
  }
}

function writeDrafts(drafts: WorkspaceDraft[]): boolean {
  try {
    window.localStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts));
    return true;
  } catch {
    return false;
  }
}

export default function ResearchWorkspacePanel() {
  const [sample, setSample] = useState<ResearchWorkspaceSampleResponse | null>(null);
  const [selectedId, setSelectedId] = useState("macro_stress_research_pack");
  const [includedRunIds, setIncludedRunIds] = useState<string[] | null>(null); // null = all
  const [userNote, setUserNote] = useState("");
  const [sections, setSections] = useState<WorkspaceSectionId[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("summary");
  const [sortMode, setSortMode] = useState<SortMode>("severity");
  const [result, setResult] = useState<ResearchWorkspaceAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<WorkspaceDraft[]>([]);
  const [storageOk, setStorageOk] = useState(true);
  const [draftStatus, setDraftStatus] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchResearchWorkspaceSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelectedId(s.default_request.selected_preset_id);
        setSections(s.default_request.report_sections);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  // Drafts load after mount only (client-side; SSR markup never depends on storage).
  useEffect(() => {
    try {
      window.localStorage.getItem(DRAFTS_KEY);
      setStorageOk(true);
      setDrafts(readDrafts());
    } catch {
      setStorageOk(false);
    }
  }, []);

  const preset = sample?.presets.find((p) => p.preset_id === selectedId) ?? null;
  const moduleLabel = useMemo(() => {
    const map: Record<string, string> = {};
    sample?.modules.forEach((m) => { map[m.module_id] = m.module_label; });
    return (id: string) => map[id] ?? id;
  }, [sample]);

  function runIncluded(runId: string): boolean {
    return includedRunIds === null || includedRunIds.includes(runId);
  }

  function selectPreset(id: string) {
    setSelectedId(id);
    setIncludedRunIds(null);
    setUserNote("");
  }

  function toggleRun(runId: string) {
    if (!preset) return;
    const all = preset.experiment_runs.map((r) => r.run_id);
    const current = includedRunIds === null ? all : includedRunIds;
    const next = current.includes(runId)
      ? current.filter((id) => id !== runId)
      : all.filter((id) => current.includes(id) || id === runId);
    if (next.length === 0) return; // keep at least one run staged
    setIncludedRunIds(next.length === all.length ? null : next);
  }

  function toggleSection(id: WorkspaceSectionId) {
    setSections((secs) =>
      secs.includes(id) ? (secs.length > 1 ? secs.filter((s) => s !== id) : secs) : [...secs, id],
    );
  }

  const request = useMemo<WorkspaceAnalysisRequest | null>(() => {
    if (!sample || !preset || sections.length === 0) return null;
    const orderedSections = sample.sections
      .map((s) => s.section_id)
      .filter((s) => sections.includes(s));
    return {
      selected_preset_id: preset.preset_id,
      included_run_ids: includedRunIds,
      user_note: userNote.trim() ? userNote.trim().slice(0, 2000) : null,
      report_sections: orderedSections,
    };
  }, [sample, preset, includedRunIds, userNote, sections]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeResearchWorkspace(request, ctrl.signal)
        .then((r) => {
          setResult(r);
          setAnalyzeError(null);
        })
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setAnalyzeError(e instanceof Error ? e.message : "Analysis failed.");
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey]);

  const r = result;

  const sortedRows = useMemo<RunComparisonRow[]>(() => {
    const rows = [...(r?.run_comparison ?? [])];
    if (sortMode === "name") rows.sort((a, b) => a.run_name.localeCompare(b.run_name));
    if (sortMode === "module") rows.sort((a, b) => a.module_id.localeCompare(b.module_id) || b.severity_score - a.severity_score);
    return rows; // backend order is already severity-descending
  }, [r, sortMode]);

  const coverageData = useMemo(() => {
    if (!sample || !r) return [];
    const counts: Record<string, number> = {};
    r.run_comparison.forEach((row) => { counts[row.module_id] = (counts[row.module_id] ?? 0) + 1; });
    return sample.modules.map((m) => ({
      label: m.module_label,
      value: counts[m.module_id] ?? 0,
      color: (counts[m.module_id] ?? 0) > 0 ? seriesColor(0) : "var(--line)",
    }));
  }, [sample, r]);

  async function copyText(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${what} copied ✓`);
    } catch {
      setCopyStatus("Copy failed — select the preview text instead");
    }
    window.setTimeout(() => setCopyStatus(null), 2500);
  }

  // ── Draft handlers (all storage access is inside try/catch helpers) ──────
  function saveDraft() {
    if (!preset) return;
    const draft: WorkspaceDraft = {
      draft_id: `draft_${Date.now().toString(36)}`,
      name: `${preset.preset_name} — draft ${drafts.length + 1}`,
      saved_at: new Date().toISOString(),
      preset_id: preset.preset_id,
      included_run_ids: includedRunIds,
      user_note: userNote,
      report_sections: sections,
    };
    const next = [...drafts, draft];
    if (writeDrafts(next)) {
      setDrafts(next);
      setDraftStatus("Draft saved to this browser ✓");
    } else {
      setDraftStatus("Local storage unavailable — draft not saved");
    }
    window.setTimeout(() => setDraftStatus(null), 2500);
  }

  function loadDraft(draft: WorkspaceDraft) {
    if (!sample) return;
    const target = sample.presets.find((p) => p.preset_id === draft.preset_id);
    if (!target) {
      setDraftStatus("Draft references an unknown preset — not loaded");
      window.setTimeout(() => setDraftStatus(null), 2500);
      return;
    }
    const validRuns = new Set(target.experiment_runs.map((x) => x.run_id));
    setSelectedId(draft.preset_id);
    setIncludedRunIds(
      draft.included_run_ids === null
        ? null
        : draft.included_run_ids.filter((id) => validRuns.has(id)),
    );
    setUserNote(draft.user_note ?? "");
    const validSections = new Set(sample.sections.map((s) => s.section_id));
    const secs = draft.report_sections.filter((s) => validSections.has(s));
    setSections(secs.length > 0 ? secs : sample.default_request.report_sections);
    setDraftStatus(`Loaded “${draft.name}”`);
    window.setTimeout(() => setDraftStatus(null), 2500);
  }

  function deleteDraft(draftId: string) {
    const next = drafts.filter((d) => d.draft_id !== draftId);
    if (writeDrafts(next)) setDrafts(next);
  }

  function deleteAllDrafts() {
    try {
      window.localStorage.removeItem(DRAFTS_KEY);
    } catch {
      // storage unavailable — clear the in-memory list anyway
    }
    setDrafts([]);
    setDraftStatus("All local drafts deleted");
    window.setTimeout(() => setDraftStatus(null), 2500);
  }

  function resetDemo() {
    if (!sample) return;
    selectPreset(sample.default_request.selected_preset_id);
    setSections(sample.default_request.report_sections);
    setViewMode("summary");
    setSortMode("severity");
  }

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Research Workspace &amp; Experiment Journal</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This workspace uses the backend static-sample analytics API. Start the QuantLab API and reopen it.
        </p>
      </div>
    );
  }

  const summary = r?.severity_summary;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              Research Workspace &amp; Experiment Journal
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Organize deterministic sample lab runs into saved research presets — stage runs,
              compare baseline vs stressed reads, write experiment notes, inspect reproducibility
              checks, and export copy-friendly Markdown or JSON summaries. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Research workspace, saved preset, experiment journal, and report export features are educational and not investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Preset selector + view mode ──────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Saved research presets</p>
          <div className="flex gap-1" role="group" aria-label="View mode">
            {VIEW_MODES.map((v) => (
              <button key={v.id} type="button" onClick={() => setViewMode(v.id)} aria-pressed={viewMode === v.id}
                className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
                style={{
                  background: viewMode === v.id ? "var(--accent-softer)" : "var(--glass)",
                  border: `1px solid ${viewMode === v.id ? "var(--accent-line)" : "var(--line)"}`,
                  color: viewMode === v.id ? "var(--accent-text)" : "var(--text-mut)",
                }}>{v.label}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {sample?.presets.map((p) => (
            <button key={p.preset_id} type="button" onClick={() => selectPreset(p.preset_id)} aria-pressed={selectedId === p.preset_id}
              className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
              style={{
                background: selectedId === p.preset_id ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selectedId === p.preset_id ? "var(--accent-line)" : "var(--line)"}`,
                color: selectedId === p.preset_id ? "var(--accent-text)" : "var(--text-mut)",
              }}>{p.preset_name}</button>
          ))}
        </div>
        {preset && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-mut)" }}>
            {preset.description}{" "}
            <span style={{ color: "var(--text-faint)" }}>
              Saved {preset.created_at.slice(0, 10)} (static sample timestamp) · tags: {preset.tags.join(", ")}
            </span>
          </p>
        )}
      </div>

      {/* ── Workspace summary ────────────────────────────────────────────── */}
      {r && summary && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Workspace summary</p>
            <span className="rounded-full px-3 py-1 text-[12px] font-semibold uppercase tracking-wide"
              style={{
                background: summary.workspace_regime === "severe_research_pack" || summary.workspace_regime === "incomplete_methodology" ? "var(--warn-soft)" : "var(--accent-softer)",
                border: "1px solid var(--line)",
                color: summary.workspace_regime === "severe_research_pack" ? "var(--risk)" : summary.workspace_regime === "incomplete_methodology" ? "var(--warn)" : "var(--accent-text)",
              }}>
              {summary.regime_label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Staged runs" value={`${r.run_comparison.length} / ${r.selected_preset.experiment_runs.length}`} />
            <MetricCard label="Avg severity" value={`${num(summary.average_severity, 1)}/100`} tone={summary.average_severity >= 70 ? "danger" : summary.average_severity >= 40 ? "warn" : "accent"} />
            <MetricCard label="Max severity" value={`${num(summary.max_severity, 1)}/100`} tone={summary.max_severity >= 75 ? "danger" : "default"} />
            <MetricCard label="Module coverage" value={pct(summary.coverage_score, 0)} />
            <MetricCard label="Reproducibility" value={pct(summary.reproducibility_score, 0)} tone={summary.reproducibility_score < 0.6 ? "warn" : "positive"} />
            <MetricCard label="Linked modules" value={String(r.selected_preset.linked_modules.length)} />
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {summary.drivers.map((d) => <li key={d}>{d}</li>)}
          </ul>
        </div>
      )}

      {/* ── Summary view: charts + timeline + checklist ──────────────────── */}
      {viewMode === "summary" && r && (
        <>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            <div className="card p-4">
              <p className="section-title mb-2">Run severity</p>
              <ScenarioBarChart
                data={r.run_comparison.map((row) => ({
                  label: row.run_name,
                  value: row.severity_score,
                  color: severityColor(row.severity_score),
                }))}
                format={(v) => `${v.toFixed(0)}/100`}
                height={210}
              />
            </div>
            <div className="card p-4">
              <p className="section-title mb-2">Baseline vs stressed (indexed)</p>
              <GroupedBarChart
                data={r.run_comparison
                  .filter((row) => Math.abs(row.baseline_value) >= 1e-9)
                  .map((row) => ({
                    label: row.run_name,
                    baseline: 100,
                    stressed: (row.stressed_value / row.baseline_value) * 100,
                  }))}
                series={[
                  { key: "baseline", label: "Baseline = 100", color: seriesColor(0) },
                  { key: "stressed", label: "Stressed (indexed)", color: seriesColor(4) },
                ]}
                format={(v) => v.toFixed(0)}
                height={210}
              />
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Each run indexed to its own baseline = 100 (units differ per metric); runs with a
                ~zero baseline are omitted here — see the comparison table.
              </p>
            </div>
            <div className="card p-4">
              <p className="section-title mb-2">Module coverage</p>
              <ScenarioBarChart
                data={coverageData}
                format={(v) => `${v.toFixed(0)} run(s)`}
                height={210}
              />
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Staged runs per module — coverage C = {summary ? pct(summary.coverage_score, 0) : "—"} of the 9 available modules.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <div className="card p-4">
              <p className="section-title mb-2">Research workflow timeline</p>
              <ol className="space-y-2.5">
                {r.workflow_timeline.map((step, i) => {
                  const tone = TIMELINE_TONE[step.status];
                  return (
                    <li key={step.step_id} className="flex items-start gap-3">
                      <span className="mono mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                        style={{ background: "var(--glass)", border: `1.5px solid ${tone.color}`, color: tone.color }}>
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                          {step.step_title}{" "}
                          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: tone.color }}>
                            · {tone.label}
                          </span>
                        </p>
                        <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>{step.step_description}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>
            <div className="card p-4">
              <p className="section-title mb-2">Methodology checklist</p>
              {summary && (
                <div className="mb-3">
                  <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
                    <span>Reproducibility R = passed / total</span>
                    <span className="mono">{pct(summary.reproducibility_score, 0)}</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                    <div className="h-full rounded-full" style={{ width: `${summary.reproducibility_score * 100}%`, background: summary.reproducibility_score < 0.6 ? "var(--warn)" : "var(--emerald)" }} />
                  </div>
                </div>
              )}
              <ul className="space-y-2">
                {r.methodology_checklist.map((item) => (
                  <li key={item.item_id} className="flex items-start gap-2.5">
                    <span className="mono mt-0.5 flex-shrink-0 text-sm font-bold" style={{ color: item.passed ? "var(--emerald)" : "var(--warn)" }} aria-label={item.passed ? "passed" : "not passed"}>
                      {item.passed ? "✓" : "✗"}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm" style={{ color: "var(--text-hi)" }}>{item.label}</p>
                      <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>{item.notes}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}

      {/* ── Comparison view ──────────────────────────────────────────────── */}
      {viewMode === "comparison" && r && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Run comparison</p>
            <div className="flex gap-1" role="group" aria-label="Sort runs">
              {SORT_MODES.map((s) => (
                <button key={s.id} type="button" onClick={() => setSortMode(s.id)} aria-pressed={sortMode === s.id}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                  style={{
                    background: sortMode === s.id ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${sortMode === s.id ? "var(--accent-line)" : "var(--line)"}`,
                    color: sortMode === s.id ? "var(--accent-text)" : "var(--text-mut)",
                  }}>{s.label}</button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Run</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Module</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Metric</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Baseline</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Stressed</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Δ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Δ%</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Severity</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.run_id} style={{ borderTop: "1px solid var(--line)" }} title={row.notes || row.scenario_name}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.run_name}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{moduleLabel(row.module_id)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{row.key_metric_name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(row.baseline_value, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(row.stressed_value, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: row.change >= 0 ? "var(--warn)" : "var(--accent-text)" }}>{signedNum(row.change, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pctChange(row.percent_change, row.baseline_value, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: severityColor(row.severity_score) }}>{row.severity_score.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Δ% is guarded with ε and shown as — when the baseline is ~zero. Hover a row for its
            sample note.
          </p>
        </div>
      )}

      {/* ── Journal view ─────────────────────────────────────────────────── */}
      {viewMode === "journal" && preset && (
        <>
          <div className="card p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="section-title">Experiment journal — staged runs</p>
              <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
                Click a card to stage/unstage a run (at least one stays staged).
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {preset.experiment_runs.map((run) => {
                const included = runIncluded(run.run_id);
                return (
                  <button key={run.run_id} type="button" onClick={() => toggleRun(run.run_id)} aria-pressed={included}
                    className="rounded-xl p-3 text-left transition-opacity"
                    style={{
                      background: "var(--glass)",
                      border: `1px solid ${included ? "var(--accent-line)" : "var(--line)"}`,
                      opacity: included ? 1 : 0.45,
                    }}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{run.run_name}</span>
                      <span className="mono text-sm font-semibold" style={{ color: severityColor(run.severity_score) }}>
                        {run.severity_score.toFixed(0)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                      {moduleLabel(run.module_id)} · “{run.scenario_name}”
                    </p>
                    <p className="mono mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>
                      {run.key_metric_name}: {num(run.baseline_value, 3)} → {num(run.stressed_value, 3)}
                    </p>
                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide" style={{ color: CONFIDENCE_TONE[run.confidence_label] }}>
                      confidence: {run.confidence_label} (illustrative)
                    </p>
                    {run.notes ? (
                      <p className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>{run.notes}</p>
                    ) : (
                      <p className="mt-1 text-[11px] italic" style={{ color: "var(--warn)" }}>No run note recorded.</p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Workspace note</p>
            <textarea
              value={userNote}
              onChange={(e) => setUserNote(e.target.value.slice(0, 2000))}
              rows={3}
              maxLength={2000}
              placeholder="Write a short research note for this workspace pass (stored only in this session unless you save a local draft)…"
              aria-label="Workspace note"
              className="ql-input w-full px-3 py-2 text-sm"
            />
            <p className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
              {userNote.length}/2000 characters — the note is included in the report overview and
              JSON export. Keep it non-sensitive; it is not stored on any server.
            </p>
          </div>
        </>
      )}

      {/* ── Export view: report builder + drafts ─────────────────────────── */}
      {viewMode === "export" && sample && (
        <>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            <div className="card p-4">
              <p className="section-title mb-2">Report sections</p>
              <div className="space-y-1.5">
                {sample.sections.map((s) => {
                  const included = sections.includes(s.section_id);
                  return (
                    <label key={s.section_id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                      style={{ background: included ? "var(--accent-softer)" : "var(--glass)", border: "1px solid var(--line)" }}>
                      <input type="checkbox" checked={included} onChange={() => toggleSection(s.section_id)} style={{ accentColor: "var(--accent)" }} />
                      <span style={{ color: included ? "var(--text-hi)" : "var(--text-mut)" }}>{s.section_title}</span>
                    </label>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                The methodology checklist flags a report without the Limitations section.
              </p>
            </div>
            <div className="card p-4 xl:col-span-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="section-title">Generated report preview (Markdown)</p>
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
                  {r.report_preview.markdown}
                </pre>
              ) : (
                <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>Awaiting analysis…</p>
              )}
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                A deterministic educational summary — not a production research record, not a
                compliance record, and not investment research.
              </p>
            </div>
          </div>

          <div className="card p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="section-title">Browser-local drafts (optional)</p>
              <div className="flex items-center gap-2">
                {draftStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{draftStatus}</span>}
                <button type="button" onClick={saveDraft} disabled={!storageOk || !preset}
                  className="rounded-md px-2.5 py-1 text-xs font-semibold"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)", opacity: storageOk ? 1 : 0.5 }}>
                  Save current workspace
                </button>
                <button type="button" onClick={resetDemo}
                  className="rounded-md px-2.5 py-1 text-xs font-semibold"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
                  Reset demo state
                </button>
                {drafts.length > 0 && (
                  <button type="button" onClick={deleteAllDrafts}
                    className="rounded-md px-2.5 py-1 text-xs font-semibold"
                    style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
                    Delete all drafts
                  </button>
                )}
              </div>
            </div>
            {!storageOk ? (
              <p className="text-xs" style={{ color: "var(--warn)" }}>
                Browser storage is unavailable (private mode or blocked) — drafts are disabled; everything else works normally.
              </p>
            ) : drafts.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-faint)" }}>
                No local drafts yet. Drafts capture the preset, staged runs, note, and report
                sections — stored only in this browser via localStorage (no accounts, no cloud, no
                server storage). Avoid storing sensitive information in notes.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {drafts.map((d) => (
                  <li key={d.draft_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2"
                    style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{d.name}</p>
                      <p className="text-[11px]" style={{ color: "var(--text-faint)" }}>
                        Saved {d.saved_at.slice(0, 16).replace("T", " ")} (local browser time) · this browser only
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => loadDraft(d)}
                        className="rounded-md px-2 py-1 text-[11px] font-semibold"
                        style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}>
                        Load
                      </button>
                      <button type="button" onClick={() => deleteDraft(d.draft_id)}
                        className="rounded-md px-2 py-1 text-[11px] font-semibold"
                        style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--warn)" }}>
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {/* ── Assumptions & limitations (always visible) ────────────────────── */}
      {preset && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Preset assumptions</p>
            <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              {preset.assumptions.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Preset limitations</p>
            <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              {preset.limitations.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={WORKSPACE_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Deterministic static sample presets and runs on fixed timestamps — hand-written numbers, not recorded lab outputs, no live data.</li>
          <li>Severity, coverage, and reproducibility scores are documented teaching formulas — not risk measurements or research-quality ratings.</li>
          <li>Local drafts (if used) live only in this browser&apos;s localStorage — no login, no cloud sync, no database, no server storage.</li>
          <li>Educational only — not investment, trading, asset-allocation, legal, tax, compliance, or risk-management advice, and not a production research-management system.</li>
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
