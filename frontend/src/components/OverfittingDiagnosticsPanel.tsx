"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type CompareEntry,
  type LabSummary,
  type RunComparison,
  type RunFilters,
  type RunFull,
  type RunSummary,
  compareRuns,
  exportRuns,
  getLabSummary,
  getRun,
  listRuns,
  seedDemo,
  shortFp,
} from "@/lib/overfittingDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { CopyValue } from "@/components/ExperimentRegistryShared";
import OverfittingDiagnosticsDetail, { StatusPill } from "@/components/OverfittingDiagnosticsDetail";

type Mode = "list" | "detail" | "compare";
type Selected = { id: number; name: string };

const PAGE_SIZE = 15;
const METRICS = ["sharpe_like", "mean_return", "median_return"];
const STATUSES = ["pending", "completed", "failed", "invalidated"];

const DISCLAIMER =
  "Local-first selection-bias diagnostics: when many strategy candidates are tried and the in-sample winner is reported, that selection itself inflates apparent performance. This lab estimates the Probability of Backtest Overfitting via CSCV (how often the in-sample-selected candidate lands in the bottom half out of sample), deflates the highest observed Sharpe for the number of effectively independent trials (PSR/DSR under explicit assumptions), and applies Bonferroni/Holm/Benjamini–Hochberg corrections to declared p-values. Every number is a research statistic under stated assumptions — never proof of profitability, robustness, or safety; no candidate is selected, recommended, or allocated capital, and nothing here is investment advice.";

export default function OverfittingDiagnosticsPanel({ onNav }: { onNav?: (view: string) => void }) {
  const [mode, setMode] = useState<Mode>("list");
  const [summary, setSummary] = useState<LabSummary | null>(null);
  const [list, setList] = useState<{ items: RunSummary[]; total: number; page: number; total_pages: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<RunFilters>({});
  const [seeding, setSeeding] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [detail, setDetail] = useState<RunFull | null>(null);
  const [selected, setSelected] = useState<Selected[]>([]);
  const [pair, setPair] = useState<{ a: Selected; b: Selected } | null>(null);

  const params = useMemo(() => ({ ...filters, page, page_size: PAGE_SIZE }), [filters, page]);
  const reload = useCallback(() => setRetryTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([listRuns(params), getLabSummary()])
      .then(([l, s]) => {
        if (cancelled) return;
        setList(l);
        setSummary(s);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        if (classifyApiError(err).backendUnavailable) notifyBackendOffline({ onRetry: reload });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [params, retryTick, reload]);

  function updateFilter(key: keyof RunFilters, value: string | undefined) {
    setPage(1);
    setFilters((prev) => {
      const next = { ...prev };
      if (!value) delete next[key];
      else next[key] = value;
      return next;
    });
  }

  async function openDetail(id: number) {
    try {
      setDetail(await getRun(id));
      setMode("detail");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t open run", cls.message);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      const res = await seedDemo();
      toast.success(
        "Demo loaded",
        res.created_runs > 0
          ? `${res.created_runs} diagnostic runs created.`
          : "Demo runs already present — nothing duplicated.",
      );
      reload();
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t load demo", cls.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const payload = await exportRuns(filters);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quantlab-overfitting-diagnostics-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export ready", `${(payload.runs as unknown[]).length} run(s) exported as JSON.`);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Export failed", cls.message);
    } finally {
      setExporting(false);
    }
  }

  if (mode === "detail" && detail) {
    return (
      <OverfittingDiagnosticsDetail
        run={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onRefresh={(updated) => setDetail(updated)}
        onOpenValidation={onNav ? () => onNav("modelvalidation") : undefined}
        onOpenDataset={onNav ? () => onNav("datasetlineage") : undefined}
        onOpenExperiment={onNav ? () => onNav("experimentregistry") : undefined}
        onOpenFeatureDiagnostics={onNav ? () => onNav("featurediagnostics") : undefined}
      />
    );
  }

  if (mode === "compare" && pair) {
    return (
      <OverfittingCompare
        pair={pair}
        onBack={() => {
          setMode("list");
          setPair(null);
          setSelected([]);
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Local-first</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">Selection-bias diagnostics · SQLite · no cloud</span>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-slate-500">{DISCLAIMER}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={reload}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">↻ Refresh</button>
            <button type="button" onClick={handleSeed} disabled={seeding}
              className="rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50">
              {seeding ? "Loading…" : "Load demo runs"}
            </button>
            <button type="button" onClick={handleExport} disabled={exporting}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50">
              {exporting ? "Exporting…" : "Export JSON"}
            </button>
          </div>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Card label="Diagnostic runs" value={summary.runs} />
          <Card label="Completed" value={summary.completed} />
          <Card label="Candidates" value={summary.candidates} />
          <Card label="Valid CSCV splits" value={summary.valid_splits} />
          <Card label="Adjusted below α" value={summary.adjusted_below_threshold} />
          <Card label="Baselines" value={summary.baselines} />
        </div>
      )}

      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <Select label="Metric" value={filters.metric ?? ""} options={METRICS}
            onChange={(v) => updateFilter("metric", v)} />
          <Select label="Status" value={filters.status ?? ""} options={STATUSES}
            onChange={(v) => updateFilter("status", v)} />
          <div className="flex flex-col gap-1">
            <label htmlFor="od-search" className="text-xs font-medium text-slate-500">Search</label>
            <input id="od-search" type="text" value={filters.query ?? ""}
              onChange={(e) => updateFilter("query", e.target.value)}
              placeholder="name or description" className="ql-input w-48 px-2 py-1.5 text-sm" />
          </div>
          <button type="button" onClick={() => { setPage(1); setFilters({}); }}
            className="ml-auto rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Reset filters
          </button>
        </div>
      </div>

      {selected.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm">
          <span className="text-blue-800">
            {selected.length === 1
              ? `Selected "${selected[0].name}" — pick one more to compare.`
              : `Selected: ${selected.map((s) => `"${s.name}"`).join(" vs ")}`}
          </span>
          <div className="flex items-center gap-2">
            <button type="button" disabled={selected.length !== 2}
              onClick={() => { setPair({ a: selected[0], b: selected[1] }); setMode("compare"); }}
              className="rounded-md border border-blue-300 bg-white px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50">
              Compare selected
            </button>
            <button type="button" onClick={() => setSelected([])}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500 hover:bg-white">Clear</button>
          </div>
        </div>
      )}

      {loading ? (
        <SkeletonTable rows={6} cols={8} caption="Loading diagnostic runs…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState title="Couldn’t load the lab" message={classifyApiError(error).message} onRetry={reload} />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No overfitting-diagnostic runs yet"
          description="Load the deterministic demo to explore PBO, Sharpe deflation and multiple-testing corrections — or create runs via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo runs", onClick: handleSeed }]}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1240px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-3 text-center">Cmp</th>
                  <th scope="col" className="px-3 py-3 text-left">Name</th>
                  <th scope="col" className="px-3 py-3 text-right">Candidates</th>
                  <th scope="col" className="px-3 py-3 text-right">Obs</th>
                  <th scope="col" className="px-3 py-3 text-left">Metric</th>
                  <th scope="col" className="px-3 py-3 text-right">Blocks</th>
                  <th scope="col" className="px-3 py-3 text-right">Valid splits</th>
                  <th scope="col" className="px-3 py-3 text-right">PBO</th>
                  <th scope="col" className="px-3 py-3 text-right">PSR</th>
                  <th scope="col" className="px-3 py-3 text-right">DSR</th>
                  <th scope="col" className="px-3 py-3 text-left">Status</th>
                  <th scope="col" className="px-3 py-3 text-left">Config fp</th>
                  <th scope="col" className="px-3 py-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((row) => (
                  <tr key={row.id} className="border-b border-slate-50 transition-colors hover:bg-slate-50">
                    <td className="px-3 py-3 text-center">
                      <input type="checkbox" checked={selected.some((s) => s.id === row.id)}
                        onChange={() => setSelected((prev) => {
                          const exists = prev.find((s) => s.id === row.id);
                          if (exists) return prev.filter((s) => s.id !== row.id);
                          if (prev.length >= 2) return [prev[1], { id: row.id, name: row.name }];
                          return [...prev, { id: row.id, name: row.name }];
                        })}
                        aria-label={`Select ${row.name} for comparison`} />
                    </td>
                    <td className="max-w-[260px] px-3 py-3">
                      <button type="button" onClick={() => openDetail(row.id)} title={row.name}
                        className="block max-w-full truncate text-left font-medium text-slate-800 hover:text-blue-700">
                        {row.name}
                      </button>
                      {row.is_baseline && <span className="text-[10px] font-medium text-indigo-600">★ baseline</span>}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.candidate_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.observation_count}</td>
                    <td className="px-3 py-3 text-xs text-slate-600">{row.metric}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.block_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.valid_split_count}/{row.combination_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.pbo_estimate === null ? "—" : row.pbo_estimate.toFixed(3)}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.psr === null ? "—" : row.psr.toFixed(3)}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.dsr === null ? "—" : row.dsr.toFixed(3)}</td>
                    <td className="px-3 py-3"><StatusPill status={row.status} /></td>
                    <td className="px-3 py-3"><CopyValue value={row.configuration_fingerprint} display={shortFp(row.configuration_fingerprint)} /></td>
                    <td className="px-3 py-3 text-center">
                      <button type="button" onClick={() => openDetail(row.id)}
                        className="rounded-md border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-50 px-4 py-2 text-xs text-slate-500">
            <span>{list.total} run{list.total === 1 ? "" : "s"} · page {list.page} of {list.total_pages}</span>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => setPage((p) => p - 1)} disabled={list.page <= 1}
                className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">← Prev</button>
              <button type="button" onClick={() => setPage((p) => p + 1)} disabled={list.page >= list.total_pages}
                className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">Next →</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Card({ label, value }: { label: string; value: number }) {
  return (
    <div className="card px-3 py-2.5">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  const id = `od-filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-slate-500">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="ql-input min-w-[7rem] px-2 py-1.5 text-sm">
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compare view (neutral, with comparability warnings)
// ---------------------------------------------------------------------------

const GROUP_LABELS: Record<string, string> = {
  identity: "Identity",
  diagnostics: "Diagnostics",
};

function OverfittingCompare({ pair, onBack }: { pair: { a: Selected; b: Selected }; onBack: () => void }) {
  const [data, setData] = useState<RunComparison | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    compareRuns(pair.a.id, pair.b.id)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [pair]);

  const cell = (v: unknown) =>
    v === null || v === undefined ? "—" : typeof v === "boolean" ? String(v) : typeof v === "object" ? JSON.stringify(v) : String(v);
  const num = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : Number.isInteger(v) ? String(v) : v.toFixed(4);

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
        ← Back to runs
      </button>
      <div className="card p-4">
        <h2 className="text-lg font-bold text-slate-900">Compare diagnostic runs</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          A · #{pair.a.id} “{pair.a.name}” vs B · #{pair.b.id} “{pair.b.name}”
        </p>
        {data && data.comparability_warnings.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800">
            {data.comparability_warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
          </div>
        )}
        {data && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {Object.entries(data.fingerprint_match).map(([name, match]) => (
              <span key={name} className={`rounded-full border px-2 py-0.5 font-medium ${match ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-500"}`}>
                {name} fp: {match ? "match" : "differs"}
              </span>
            ))}
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">
          Differences are reported neutrally — neither run is labelled better, safer, or recommended.
        </p>
      </div>
      {error ? (
        <ErrorState title="Couldn’t compare" message={classifyApiError(error).message} onRetry={() => window.location.reload()} />
      ) : !data ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        <>
          {Object.entries(GROUP_LABELS).map(([key, label]) => {
            const entries: CompareEntry[] = data.groups[key] ?? [];
            if (!entries.length) return null;
            return (
              <div key={key} className="card overflow-hidden">
                <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">{label}</div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th scope="col" className="px-4 py-2 text-left">Field</th>
                        <th scope="col" className="px-4 py-2 text-left">A</th>
                        <th scope="col" className="px-4 py-2 text-left">B</th>
                        <th scope="col" className="px-4 py-2 text-left">Δ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((e) => (
                        <tr key={e.field} className={`border-b border-slate-50 last:border-0 ${e.kind !== "same" ? "bg-amber-50/40" : ""}`}>
                          <td className="px-4 py-2 font-medium text-slate-700">
                            {e.field}
                            {e.kind !== "same" && <span className="ml-1.5 text-[10px] uppercase text-amber-600">{e.kind.replace(/_/g, " ")}</span>}
                          </td>
                          <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.a)}>{cell(e.a)}</td>
                          <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.b)}>{cell(e.b)}</td>
                          <td className="px-4 py-2 text-xs text-slate-500">{e.note || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
          {data.selection.length > 0 && (
            <div className="card overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
                Selection frequencies ({data.selection.length} candidates)
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                      <th scope="col" className="px-3 py-2">Candidate</th>
                      <th scope="col" className="px-3 py-2">Availability</th>
                      <th scope="col" className="px-3 py-2 text-right">A sel. freq</th>
                      <th scope="col" className="px-3 py-2 text-right">B sel. freq</th>
                      <th scope="col" className="px-3 py-2 text-right">A mean OOS rank</th>
                      <th scope="col" className="px-3 py-2 text-right">B mean OOS rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.selection.map((s) => (
                      <tr key={s.candidate_id} className="border-b border-slate-50 font-mono last:border-0">
                        <td className="px-3 py-1.5">{s.candidate_id}</td>
                        <td className="px-3 py-1.5">{s.availability.replace(/_/g, " ")}</td>
                        <td className="px-3 py-1.5 text-right">{num(s.a_selection_frequency)}</td>
                        <td className="px-3 py-1.5 text-right">{num(s.b_selection_frequency)}</td>
                        <td className="px-3 py-1.5 text-right">{num(s.a_mean_oos_rank)}</td>
                        <td className="px-3 py-1.5 text-right">{num(s.b_mean_oos_rank)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
