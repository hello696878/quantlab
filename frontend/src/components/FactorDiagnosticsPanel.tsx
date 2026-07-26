"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type LabSummary,
  type RunComparison,
  type RunFilters,
  type RunFull,
  type RunSummary,
  INTEGRITY_LABELS,
  MODE_LABELS,
  RANK_LABELS,
  TIMING_LABELS,
  compareRuns,
  exportRuns,
  fmtNum,
  fmtSci,
  getLabSummary,
  getRun,
  listRuns,
  seedDemo,
  shortFp,
} from "@/lib/factorDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import FactorDiagnosticsDetail from "@/components/FactorDiagnosticsDetail";
import {
  CompletenessPill,
  IntegrityPill,
  RankPill,
  ReconciliationPill,
  StatusPill,
} from "@/components/FactorDiagnosticsShared";

type Mode = "list" | "detail" | "compare";
type Selected = { id: number; name: string };

const PAGE_SIZE = 25; // the 20 documented demo cases fit on one page
const STATUSES = ["pending", "running", "completed", "failed", "invalidated"];
const INTEGRITY_OPTIONS = [
  "verified_from_validation_split", "verified_causal_lag",
  "verified_trailing_estimation", "supplied_descriptive",
  "contemporaneous_descriptive", "full_sample_descriptive", "unknown",
  "invalid",
];
const MODE_OPTIONS = ["time_series_regression", "supplied_exposure_aggregation"];
const TIMING_OPTIONS = ["lagged_causal", "contemporaneous",
                        "full_sample_descriptive", "future_looking_invalid"];
const RANK_OPTIONS = ["full_rank", "rank_deficient_descriptive"];

const DISCLAIMER =
  "Local-first factor research diagnostics: measured sensitivities of ONE explicitly declared return series to SUPPLIED factor and macro observations, under a stated transformation, unit, lag and availability rule, with strict timestamp alignment (nothing is resampled, forward-filled or interpolated), honest rank and availability states, exact contribution reconciliation, trailing rolling estimates that a later observation can never rewrite, and held-out evaluation that never refits on held-out data. Nothing here proves causality, proves alpha, proves manager skill, predicts future returns, recommends a factor exposure, a macro trade or a portfolio, executes trades, certifies a factor model, or constitutes investment advice. No market or macroeconomic data is ever downloaded.";

export default function FactorDiagnosticsPanel({ onNav }: { onNav?: (view: string) => void }) {
  const [mode, setMode] = useState<Mode>("list");
  const [summary, setSummary] = useState<LabSummary | null>(null);
  const [list, setList] = useState<{
    items: RunSummary[]; total: number; page: number; total_pages: number;
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
          ? `${res.created_count} factor-diagnostic runs created.`
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
      a.download = `quantlab-factor-diagnostics-${new Date().toISOString().slice(0, 10)}.json`;
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
      <FactorDiagnosticsDetail
        run={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onRefresh={(updated) => setDetail(updated)}
        onOpenAttribution={onNav ? () => onNav("portfolioattribution") : undefined}
        onOpenStress={onNav ? () => onNav("portfoliostress") : undefined}
        onOpenRegime={onNav ? () => onNav("regimediagnostics") : undefined}
        onOpenValidation={onNav ? () => onNav("modelvalidation") : undefined}
        onOpenDataset={onNav ? () => onNav("datasetlineage") : undefined}
        onOpenExperiment={onNav ? () => onNav("experimentregistry") : undefined}
      />
    );
  }

  if (mode === "compare" && pair) {
    return (
      <FactorCompare
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
    <div className="space-y-4" data-testid="factor-diagnostics-panel">
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Local-first</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                Supplied factors · explicit units &amp; lags · no causality claims · SQLite
              </span>
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
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7" data-testid="factor-summary-cards">
          <Card label="Runs" value={summary.runs} />
          <Card label="Completed" value={summary.completed} />
          <Card label="Factors" value={summary.factors} />
          <Card label="Observations" value={summary.observations} />
          <Card label="Verified timing" value={summary.verified_runs} />
          <Card label="Rank deficient" value={summary.rank_deficient_runs} />
          <Card label="Baselines" value={summary.baselines} />
        </div>
      )}

      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <Select label="Status" value={filters.status ?? ""} options={STATUSES}
            onChange={(v) => updateFilter("status", v)} />
          <Select label="Integrity" value={filters.integrity_status ?? ""}
            options={INTEGRITY_OPTIONS} labels={INTEGRITY_LABELS}
            onChange={(v) => updateFilter("integrity_status", v)} />
          <Select label="Mode" value={filters.analysis_mode ?? ""}
            options={MODE_OPTIONS} labels={MODE_LABELS}
            onChange={(v) => updateFilter("analysis_mode", v)} />
          <Select label="Timing" value={filters.timing_policy ?? ""}
            options={TIMING_OPTIONS} labels={TIMING_LABELS}
            onChange={(v) => updateFilter("timing_policy", v)} />
          <Select label="Rank" value={filters.rank_status ?? ""}
            options={RANK_OPTIONS} labels={RANK_LABELS}
            onChange={(v) => updateFilter("rank_status", v)} />
          <div className="flex flex-col gap-1">
            <label htmlFor="fdx-search" className="text-xs font-medium text-slate-500">Search</label>
            <input id="fdx-search" type="text" value={filters.query ?? ""}
              onChange={(e) => updateFilter("query", e.target.value)}
              placeholder="name, description or target" className="ql-input w-52 px-2 py-1.5 text-sm" />
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
        <SkeletonTable rows={6} cols={8} caption="Loading factor-diagnostic runs…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState title="Couldn’t load the lab" message={classifyApiError(error).message} onRetry={reload} />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No factor-diagnostic runs yet"
          description="Load the deterministic demo to explore hand-computable exact relationships, an intercept with a live residual, constant and duplicate factors, rank-deficient and near-collinear designs, lagged causal versus contemporaneous timing, a declared-invalid future-looking alignment, rolling exposure change, benchmark-relative exposure, stored-regime and stored-stress views, and a held-out validation split — or create runs via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo runs", onClick: handleSeed }]}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1500px] text-sm" data-testid="factor-runs-table">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-3 text-center">Cmp</th>
                  <th scope="col" className="px-3 py-3 text-left">Name</th>
                  <th scope="col" className="px-3 py-3 text-left">Target</th>
                  <th scope="col" className="px-3 py-3 text-left">Mode</th>
                  <th scope="col" className="px-3 py-3 text-left">Timing</th>
                  <th scope="col" className="px-3 py-3 text-right">Factors</th>
                  <th scope="col" className="px-3 py-3 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-3 text-right">R²</th>
                  <th scope="col" className="px-3 py-3 text-right">Residual σ</th>
                  <th scope="col" className="px-3 py-3 text-right">Cond. number</th>
                  <th scope="col" className="px-3 py-3 text-left">Rank</th>
                  <th scope="col" className="px-3 py-3 text-left">Integrity</th>
                  <th scope="col" className="px-3 py-3 text-left">Completeness</th>
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
                    <td className="max-w-[150px] truncate px-3 py-3 text-xs" title={row.target_type}>
                      {row.target_type.replace(/_/g, " ")}
                    </td>
                    <td className="px-3 py-3 text-xs">{MODE_LABELS[row.analysis_mode] ?? row.analysis_mode}</td>
                    <td className="px-3 py-3 text-xs">{TIMING_LABELS[row.timing_policy] ?? row.timing_policy}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.factor_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.observation_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{fmtNum(row.r_squared, 4)}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{fmtSci(row.residual_std)}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{fmtSci(row.condition_number, 2)}</td>
                    <td className="px-3 py-3"><RankPill status={row.rank_status} /></td>
                    <td className="px-3 py-3"><IntegrityPill status={row.integrity_status} /></td>
                    <td className="px-3 py-3"><CompletenessPill status={row.completeness_status} /></td>
                    <td className="px-3 py-3"><StatusPill status={row.status} /></td>
                    <td className="px-3 py-3 font-mono text-[11px] text-slate-500">{shortFp(row.configuration_fingerprint)}</td>
                    <td className="px-3 py-3 text-center">
                      <button type="button" onClick={() => openDetail(row.id)}
                        className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {list.total_pages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-sm">
              <span className="text-slate-500">Page {list.page} of {list.total_pages} · {list.total} run(s)</span>
              <div className="flex gap-2">
                <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-200 px-2 py-1 text-xs disabled:opacity-40">← Prev</button>
                <button type="button" disabled={page >= list.total_pages} onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-200 px-2 py-1 text-xs disabled:opacity-40">Next →</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Card({ label, value }: { label: string; value: number }) {
  return (
    <div className="card px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 font-mono text-lg font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function Select({ label, value, options, labels, onChange }: {
  label: string; value: string; options: string[];
  labels?: Record<string, string>; onChange: (v: string) => void;
}) {
  const id = `fdx-filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
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

function FactorCompare({ pair, onBack }: { pair: { a: Selected; b: Selected }; onBack: () => void }) {
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

  return (
    <div className="space-y-4" data-testid="factor-compare">
      <button type="button" onClick={onBack}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
        ← Back to runs
      </button>
      <div className="card p-4">
        <h2 className="text-lg font-bold text-slate-900">Compare factor-diagnostic runs</h2>
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
                {name.replace(/_/g, " ")} fp: {match ? "match" : "differs"}
              </span>
            ))}
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">
          {data?.note ?? "Differences are reported neutrally — no run is better, superior, preferred or recommended, and no factor set is endorsed."}
        </p>
      </div>
      {error ? (
        <ErrorState title="Couldn’t compare" message={classifyApiError(error).message} onRetry={() => window.location.reload()} />
      ) : !data ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        <>
          <div className="card overflow-hidden">
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
              Coefficients ({data.coefficients.length})
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-4 py-2 text-left">Factor</th>
                    <th scope="col" className="px-4 py-2 text-right">A</th>
                    <th scope="col" className="px-4 py-2 text-right">B</th>
                    <th scope="col" className="px-4 py-2 text-right">B − A</th>
                  </tr>
                </thead>
                <tbody>
                  {data.coefficients.map((row) => (
                    <tr key={row.factor_id} className="border-b border-slate-50 font-mono text-xs last:border-0">
                      <td className="px-4 py-1.5 font-sans font-medium text-slate-700">{row.factor_id}</td>
                      <td className="px-4 py-1.5 text-right">{row.a_present ? fmtNum(row.a_coefficient) : "absent"}</td>
                      <td className="px-4 py-1.5 text-right">{row.b_present ? fmtNum(row.b_coefficient) : "absent"}</td>
                      <td className="px-4 py-1.5 text-right">{fmtNum(row.difference)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card overflow-hidden">
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">Fit metrics</div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-4 py-2 text-left">Metric</th>
                    <th scope="col" className="px-4 py-2 text-right">A</th>
                    <th scope="col" className="px-4 py-2 text-right">B</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.metrics).map(([name, values]) => (
                    <tr key={name} className="border-b border-slate-50 last:border-0">
                      <td className="px-4 py-1.5 font-medium text-slate-700">{name.replace(/_/g, " ")}</td>
                      <td className="px-4 py-1.5 text-right font-mono text-xs">{fmtNum(values.a)}</td>
                      <td className="px-4 py-1.5 text-right font-mono text-xs">{fmtNum(values.b)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
