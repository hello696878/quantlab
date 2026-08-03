"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type LabSummary,
  type RunComparison,
  type RunFilters,
  type RunFull,
  type RunSummary,
  ALIGNMENT_LABELS,
  INTEGRITY_LABELS,
  MODE_LABELS,
  compareRuns,
  exportRuns,
  fmtNum,
  fmtPct,
  getLabSummary,
  getRun,
  listRuns,
  seedDemo,
  shortFp,
} from "@/lib/signalEnsemble";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import SignalEnsembleDetail from "@/components/SignalEnsembleDetail";
import {
  CompletenessPill,
  IntegrityPill,
  StatusPill,
} from "@/components/SignalEnsembleShared";

type Mode = "list" | "detail" | "compare";
type Selected = { id: number; name: string };

const PAGE_SIZE = 30; // the 24 documented demo cases fit on one page
const STATUSES = ["pending", "running", "completed", "failed", "invalidated"];
const INTEGRITY_OPTIONS = [
  "verified_from_validation_split", "verified_point_in_time",
  "verified_trailing_transformation", "supplied_descriptive",
  "contemporaneous_descriptive", "full_sample_descriptive", "unknown",
  "invalid",
];
const MODE_OPTIONS = ["equal_weight", "user_weights", "rank_average",
                      "majority_sign"];
const ALIGNMENT_OPTIONS = ["strict_intersection", "pairwise_complete"];

const DISCLAIMER =
  "Local-first signal-ensemble diagnostics: descriptive similarity, redundancy and EXPLICIT user-configured combination references over stored signals aligned on exact (entity, timestamp) keys. Missing observations are disclosed and never filled, pairwise sample counts sit on every row, matrix-level numbers (rank, condition number, eigenvalue concentration, effective signal count) describe one correlation matrix and never the true number of independent signals, combined scores reconcile exactly with their component contributions, and gross versus cost-adjusted references stay separate. Nothing here selects a signal, derives or optimises a weight, picks a threshold, horizon or lag, proves independence, diversification, predictability or alpha, executes anything, or constitutes investment advice.";

export default function SignalEnsemblePanel({ onNav }: { onNav?: (view: string) => void }) {
  const [mode, setMode] = useState<Mode>("list");
  const [summary, setSummary] = useState<LabSummary | null>(null);
  const [list, setList] = useState<{
    items: RunSummary[]; total: number; page: number; page_size: number;
  } | null>(null);
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
      else (next as Record<string, unknown>)[key] = value;
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
        res.created_count > 0
          ? `${res.created_count} signal-ensemble runs created.`
          : "Demo runs already present — nothing duplicated.",
      );
      reload();
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Demo load failed", cls.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const body = await exportRuns(filters);
      const blob = new Blob([JSON.stringify(body, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "signal-ensemble-export.json";
      anchor.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready",
        `${(body as { run_count?: number }).run_count ?? 0} run(s) exported.`);
    } catch (err) {
      toast.error("Export failed", classifyApiError(err).message);
    } finally {
      setExporting(false);
    }
  }

  function toggleSelect(run: RunSummary) {
    setSelected((prev) => {
      const exists = prev.find((s) => s.id === run.id);
      if (exists) return prev.filter((s) => s.id !== run.id);
      if (prev.length >= 2) return [prev[1], { id: run.id, name: run.name }];
      return [...prev, { id: run.id, name: run.name }];
    });
  }

  if (mode === "detail" && detail) {
    return (
      <SignalEnsembleDetail
        run={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onNav={onNav}
      />
    );
  }

  if (mode === "compare" && pair) {
    return (
      <SignalEnsembleCompare
        a={pair.a}
        b={pair.b}
        onBack={() => {
          setMode("list");
          setPair(null);
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-800">
                Signal Ensemble Lab
              </h2>
              <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                Local-first — no market data is ever downloaded
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              {DISCLAIMER}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={reload}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
              Refresh
            </button>
            <button type="button" onClick={handleSeed} disabled={seeding}
              className="rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50">
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
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6"
          data-testid="ensemble-summary-cards">
          {[
            { label: "Runs", value: String(summary.runs) },
            { label: "Completed", value: String(summary.completed) },
            { label: "Signals (all runs)", value: String(summary.signals) },
            { label: "Observations", value: String(summary.observations) },
            { label: "Pairwise rows", value: String(summary.pairwise_rows) },
            { label: "Baselines", value: String(summary.baselines) },
          ].map((card) => (
            <div key={card.label} className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                {card.label}
              </p>
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {card.value}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <Select label="Status" value={filters.status ?? ""} options={STATUSES}
            onChange={(v) => updateFilter("status", v)} />
          <Select label="Integrity" value={filters.integrity_status ?? ""}
            options={INTEGRITY_OPTIONS} labels={INTEGRITY_LABELS}
            onChange={(v) => updateFilter("integrity_status", v)} />
          <Select label="Mode" value={filters.combination_mode ?? ""}
            options={MODE_OPTIONS} labels={MODE_LABELS}
            onChange={(v) => updateFilter("combination_mode", v)} />
          <Select label="Alignment" value={filters.alignment_policy ?? ""}
            options={ALIGNMENT_OPTIONS} labels={ALIGNMENT_LABELS}
            onChange={(v) => updateFilter("alignment_policy", v)} />
          <div className="flex flex-col gap-1">
            <label htmlFor="senx-search" className="text-xs font-medium text-slate-500">Search</label>
            <input id="senx-search" type="text" value={filters.query ?? ""}
              onChange={(e) => updateFilter("query", e.target.value)}
              placeholder="name or description" className="ql-input w-52 px-2 py-1.5 text-sm" />
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
              className="rounded-md border border-blue-400 bg-[var(--bg-elev)] px-3 py-1 text-xs font-medium text-blue-200 hover:bg-[var(--glass)] disabled:opacity-50">
              Compare selected
            </button>
            <button type="button" onClick={() => setSelected([])}
              className="rounded-md border border-slate-500 px-3 py-1 text-xs font-medium text-slate-300 hover:bg-[var(--glass)]">Clear</button>
          </div>
        </div>
      )}

      {loading ? (
        <SkeletonTable rows={6} cols={8} caption="Loading signal-ensemble runs…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState title="Couldn’t load the lab" message={classifyApiError(error).message} onRetry={reload} />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No signal-ensemble runs yet"
          description="Load the deterministic demo to explore identical and inverse pairs, constants and heavy ties, strict-intersection versus pairwise-complete alignment, redundant and diverse trios with effective signal counts, equal-weight and user-weighted combinations with exact contribution reconciliation, missing-component policies, turnover that cancels or compounds, cost-linked references, regime and held-out views, a rank-deficient matrix and one eligible baseline — or create runs via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo runs", onClick: handleSeed }]}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1500px] text-sm" data-testid="ensemble-runs-table">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-3 text-center">Cmp</th>
                  <th scope="col" className="px-3 py-3 text-left">Name</th>
                  <th scope="col" className="px-3 py-3 text-left">Mode</th>
                  <th scope="col" className="px-3 py-3 text-left">Alignment</th>
                  <th scope="col" className="px-3 py-3 text-right">Signals</th>
                  <th scope="col" className="px-3 py-3 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-3 text-right">Strict keys</th>
                  <th scope="col" className="px-3 py-3 text-right">Coverage</th>
                  <th scope="col" className="px-3 py-3 text-right">Mean |ρ|</th>
                  <th scope="col" className="px-3 py-3 text-right">Effective count</th>
                  <th scope="col" className="px-3 py-3 text-left">Integrity</th>
                  <th scope="col" className="px-3 py-3 text-left">Completeness</th>
                  <th scope="col" className="px-3 py-3 text-left">Status</th>
                  <th scope="col" className="px-3 py-3 text-left">Config fp</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((run) => (
                  <tr key={run.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50">
                    <td className="px-3 py-2 text-center">
                      <input type="checkbox"
                        aria-label={`Select ${run.name} for comparison`}
                        checked={selected.some((s) => s.id === run.id)}
                        onChange={() => toggleSelect(run)} />
                    </td>
                    <td className="px-3 py-2">
                      <button type="button" onClick={() => openDetail(run.id)}
                        className="text-left font-medium text-blue-700 hover:underline">
                        {run.name}
                      </button>
                      {run.is_baseline && (
                        <span className="ml-1 text-[10px] font-semibold uppercase text-blue-500">★ baseline</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {MODE_LABELS[run.combination_mode] ?? run.combination_mode}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {ALIGNMENT_LABELS[run.alignment_policy] ?? run.alignment_policy}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{run.signal_count}</td>
                    <td className="px-3 py-2 text-right font-mono">{run.observation_count}</td>
                    <td className="px-3 py-2 text-right font-mono">{run.strict_intersection_count}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {run.combined_available_count !== null && run.strict_intersection_count
                        ? fmtPct(run.combined_available_count
                            / Math.max(1, run.observation_count / run.signal_count), 0)
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmtNum(run.mean_absolute_correlation, 3)}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmtNum(run.effective_signal_count, 2)}</td>
                    <td className="px-3 py-2"><IntegrityPill status={run.integrity_status} /></td>
                    <td className="px-3 py-2"><CompletenessPill status={run.completeness_status} /></td>
                    <td className="px-3 py-2"><StatusPill status={run.status} /></td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-500"
                      title={run.configuration_fingerprint ?? undefined}>
                      {shortFp(run.configuration_fingerprint)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {list.total > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-sm">
              <button type="button" disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-40">
                Previous
              </button>
              <span className="text-slate-500">
                Page {list.page} · {list.total} runs
              </span>
              <button type="button"
                disabled={page * PAGE_SIZE >= list.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-40">
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SignalEnsembleCompare({ a, b, onBack }: {
  a: Selected; b: Selected; onBack: () => void;
}) {
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    compareRuns(a.id, b.id)
      .then((c) => !cancelled && setComparison(c))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [a.id, b.id]);

  return (
    <div className="space-y-4" data-testid="ensemble-compare">
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-800">
            Run comparison — {a.name} vs {b.name}
          </h2>
          <button type="button" onClick={onBack}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
            ← Back to runs
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Differences are reported neutrally: no run is better and no winner
          is declared — nothing here selects an ensemble.
        </p>
      </div>
      {error ? (
        <ErrorState title="Comparison failed" message={classifyApiError(error).message} />
      ) : !comparison ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        <>
          {comparison.warnings.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-amber-700">
                Comparability warnings
              </h3>
              <ul className="mt-2 space-y-1 text-sm text-amber-800">
                {comparison.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
              </ul>
            </div>
          )}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Field</th>
                    <th scope="col" className="px-3 py-2">Run A</th>
                    <th scope="col" className="px-3 py-2">Run B</th>
                    <th scope="col" className="px-3 py-2">State</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.fields.map((f) => (
                    <tr key={f.field} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-medium text-slate-700">
                        {f.field.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-xs">{String(f.a ?? "—")}</td>
                      <td className="px-3 py-1.5 font-mono text-xs">{String(f.b ?? "—")}</td>
                      <td className="px-3 py-1.5">
                        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                          f.state === "same"
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : f.state === "changed"
                              ? "border-amber-300 bg-amber-50 text-amber-700"
                              : "border-slate-300 bg-slate-50 text-slate-600"
                        }`}>
                          {f.state.replace(/_/g, " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-slate-700">Metrics (side by side)</h3>
            <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
              {Object.entries(comparison.metrics).map(([metric, values]) => (
                <div key={metric}>
                  <dt className="font-medium uppercase tracking-wide text-slate-500">
                    {metric.replace(/_/g, " ")}
                  </dt>
                  <dd className="font-mono">
                    {fmtNum(values.a as number | null, 3)} vs {fmtNum(values.b as number | null, 3)}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-slate-500">{comparison.note}</p>
          </div>
        </>
      )}
    </div>
  );
}

function Select({ label, value, options, labels, onChange }: {
  label: string; value: string; options: string[];
  labels?: Record<string, string>; onChange: (v: string) => void;
}) {
  const id = `senx-filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-slate-500">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="ql-input min-w-[7rem] px-2 py-1.5 text-sm">
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{labels?.[o] ?? o}</option>)}
      </select>
    </div>
  );
}
