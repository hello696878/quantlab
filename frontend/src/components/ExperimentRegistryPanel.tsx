"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type ExperimentFilters,
  type ExperimentFull,
  type ExperimentListResponse,
  type ExperimentSummary,
  type RegistrySummary,
  exportExperiments,
  getExperiment,
  getRegistrySummary,
  listExperiments,
  metricPreview,
  seedDemoRegistry,
  shortFingerprint,
  formatDuration,
  formatTimestamp,
} from "@/lib/experimentRegistry";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import {
  BaselineBadge,
  CopyValue,
  ReproBadge,
  StatusBadge,
} from "@/components/ExperimentRegistryShared";
import ExperimentRegistryDetail from "@/components/ExperimentRegistryDetail";
import ExperimentRegistryCompare from "@/components/ExperimentRegistryCompare";

type Mode = "list" | "detail" | "compare";
type Selected = { id: number; name: string };

const STATUS_OPTIONS = ["pending", "running", "completed", "failed", "invalidated"];
const REPRO_OPTIONS = [
  "unknown",
  "reproducible",
  "partially_reproducible",
  "not_reproducible",
];
const PAGE_SIZE = 15;

const DISCLAIMER =
  "Local-first, single-user registry stored in SQLite. Fingerprints and the reproducibility check are integrity aids — not a scientific-reproducibility claim, an audit trail, or investment advice.";

export default function ExperimentRegistryPanel() {
  const [mode, setMode] = useState<Mode>("list");

  // list state
  const [summary, setSummary] = useState<RegistrySummary | null>(null);
  const [list, setList] = useState<ExperimentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filters, setFilters] = useState<ExperimentFilters>({});
  const [seeding, setSeeding] = useState(false);
  const [exporting, setExporting] = useState(false);

  // detail + compare state
  const [detail, setDetail] = useState<ExperimentFull | null>(null);
  const [selected, setSelected] = useState<Selected[]>([]);
  const [comparePair, setComparePair] = useState<{ a: Selected; b: Selected } | null>(null);

  const listParams = useMemo(
    () => ({ ...filters, sort_by: sortBy, sort_dir: sortDir, page, page_size: PAGE_SIZE }),
    [filters, sortBy, sortDir, page],
  );

  const reload = useCallback(() => setRetryTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([listExperiments(listParams), getRegistrySummary()])
      .then(([listResp, summaryResp]) => {
        if (cancelled) return;
        setList(listResp);
        setSummary(summaryResp);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        if (classifyApiError(err).backendUnavailable) {
          notifyBackendOffline({ onRetry: reload });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [listParams, retryTick, reload]);

  function updateFilter(key: keyof ExperimentFilters, value: string | boolean | undefined) {
    setPage(1);
    setFilters((prev) => {
      const next = { ...prev };
      if (value === undefined || value === "" || value === false) delete next[key];
      else (next as Record<string, unknown>)[key] = value;
      return next;
    });
  }

  function resetFilters() {
    setPage(1);
    setFilters({});
  }

  async function openDetail(id: number) {
    try {
      const exp = await getExperiment(id);
      setDetail(exp);
      setMode("detail");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t open experiment", cls.message);
    }
  }

  function toggleSelect(row: ExperimentSummary) {
    setSelected((prev) => {
      const exists = prev.find((s) => s.id === row.id);
      if (exists) return prev.filter((s) => s.id !== row.id);
      if (prev.length >= 2) return [prev[1], { id: row.id, name: row.name }];
      return [...prev, { id: row.id, name: row.name }];
    });
  }

  function startCompare() {
    if (selected.length === 2) {
      setComparePair({ a: selected[0], b: selected[1] });
      setMode("compare");
    }
  }

  function compareFromDetail(id: number) {
    const name = detail?.name ?? `#${id}`;
    setSelected([{ id, name }]);
    setDetail(null);
    setMode("list");
    toast.info("Select the second experiment", `Pick another row to compare with "${name}".`);
  }

  async function handleSeedDemo() {
    setSeeding(true);
    try {
      const res = await seedDemoRegistry();
      toast.success(
        "Demo registry loaded",
        res.created > 0
          ? `${res.created} deterministic demo records added.`
          : "Demo records already present — nothing duplicated.",
      );
      reload();
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t load demo records", cls.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const payload = await exportExperiments(filters);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `quantlab-experiment-registry-${stamp}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export ready", `${payload.count} experiment(s) exported as JSON.`);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Export failed", cls.message);
    } finally {
      setExporting(false);
    }
  }

  // ── Detail / compare modes ────────────────────────────────────────────────

  if (mode === "detail" && detail) {
    return (
      <ExperimentRegistryDetail
        experiment={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onChanged={(updated) => {
          if (updated) setDetail(updated);
          else {
            setMode("list");
            setDetail(null);
          }
          reload();
        }}
        onCompareWith={compareFromDetail}
      />
    );
  }

  if (mode === "compare" && comparePair) {
    return (
      <ExperimentRegistryCompare
        aId={comparePair.a.id}
        bId={comparePair.b.id}
        aLabel={comparePair.a.name}
        bLabel={comparePair.b.name}
        onBack={() => {
          setMode("list");
          setComparePair(null);
          setSelected([]);
        }}
      />
    );
  }

  // ── List mode ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Intro + actions */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Local-first
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                SQLite · no accounts
              </span>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-slate-500">{DISCLAIMER}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={reload}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              ↻ Refresh
            </button>
            <button
              type="button"
              onClick={handleSeedDemo}
              disabled={seeding}
              className="rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
            >
              {seeding ? "Loading…" : "Load demo registry"}
            </button>
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              {exporting ? "Exporting…" : "Export JSON"}
            </button>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <SummaryCard label="Total" value={summary.total} />
          <SummaryCard label="Completed" value={summary.by_status.completed ?? 0} />
          <SummaryCard label="Failed" value={summary.by_status.failed ?? 0} />
          <SummaryCard label="Reproducible" value={summary.by_reproducibility.reproducible ?? 0} />
          <SummaryCard label="Baselines" value={summary.baselines} />
          <SummaryCard label="Modules" value={summary.modules_represented} />
        </div>
      )}

      {/* Filter bar */}
      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <FilterSelect
            label="Module"
            value={filters.module ?? ""}
            options={summary?.modules ?? []}
            onChange={(v) => updateFilter("module", v)}
          />
          <FilterSelect
            label="Type"
            value={filters.experiment_type ?? ""}
            options={summary?.experiment_types ?? []}
            onChange={(v) => updateFilter("experiment_type", v)}
          />
          <FilterSelect
            label="Status"
            value={filters.status ?? ""}
            options={STATUS_OPTIONS}
            onChange={(v) => updateFilter("status", v)}
          />
          <FilterSelect
            label="Reproducibility"
            value={filters.reproducibility_status ?? ""}
            options={REPRO_OPTIONS}
            onChange={(v) => updateFilter("reproducibility_status", v)}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor="reg-search" className="text-xs font-medium text-slate-500">
              Search
            </label>
            <input
              id="reg-search"
              type="text"
              value={filters.query ?? ""}
              onChange={(e) => updateFilter("query", e.target.value)}
              placeholder="name or description"
              className="w-48 rounded-md border border-slate-200 px-2 py-1.5 text-sm"
            />
          </div>
          <label className="flex items-center gap-1.5 pb-1.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={filters.baseline === true}
              onChange={(e) => updateFilter("baseline", e.target.checked ? true : undefined)}
            />
            Baselines only
          </label>
          <button
            type="button"
            onClick={resetFilters}
            className="ml-auto rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Reset filters
          </button>
        </div>
      </div>

      {/* Compare bar */}
      {selected.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm">
          <span className="text-blue-800">
            {selected.length === 1
              ? `Selected "${selected[0].name}" — pick one more to compare.`
              : `Selected: ${selected.map((s) => `"${s.name}"`).join(" vs ")}`}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={startCompare}
              disabled={selected.length !== 2}
              className="rounded-md border border-blue-300 bg-white px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
            >
              Compare selected
            </button>
            <button
              type="button"
              onClick={() => setSelected([])}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500 hover:bg-white"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Table / states */}
      {loading ? (
        <SkeletonTable rows={6} cols={7} caption="Loading experiments…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState
            title="Couldn’t load the registry"
            message={classifyApiError(error).message}
            onRetry={reload}
          />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No experiments recorded yet"
          description="Load the deterministic demo registry to explore the dashboard, or record runs from your modules via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo registry", onClick: handleSeedDemo }]}
        />
      ) : (
        <ExperimentTable
          rows={list.items}
          selectedIds={selected.map((s) => s.id)}
          onToggle={toggleSelect}
          onView={openDetail}
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={(col) => {
            setPage(1);
            if (col === sortBy) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
            else {
              setSortBy(col);
              setSortDir("desc");
            }
          }}
          page={list.page}
          totalPages={list.total_pages}
          total={list.total}
          onPage={setPage}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="card px-3 py-2.5">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const id = `filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-slate-500">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-200 px-2 py-1.5 text-sm"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

const SORT_COLUMNS: Record<string, boolean> = {
  name: true,
  module: true,
  experiment_type: true,
  status: true,
  created_at: true,
  duration_ms: true,
};

function ExperimentTable({
  rows,
  selectedIds,
  onToggle,
  onView,
  sortBy,
  sortDir,
  onSort,
  page,
  totalPages,
  total,
  onPage,
}: {
  rows: ExperimentSummary[];
  selectedIds: number[];
  onToggle: (row: ExperimentSummary) => void;
  onView: (id: number) => void;
  sortBy: string;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
  page: number;
  totalPages: number;
  total: number;
  onPage: (page: number) => void;
}) {
  function Th({ col, label, className = "" }: { col?: string; label: string; className?: string }) {
    const sortable = col && SORT_COLUMNS[col];
    return (
      <th scope="col" className={`px-3 py-3 ${className}`}>
        {sortable ? (
          <button
            type="button"
            onClick={() => onSort(col!)}
            className="inline-flex items-center gap-1 font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700"
          >
            {label}
            {sortBy === col && <span>{sortDir === "asc" ? "▲" : "▼"}</span>}
          </button>
        ) : (
          <span className="font-semibold uppercase tracking-wide text-slate-500">{label}</span>
        )}
      </th>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-xs">
              <th scope="col" className="px-3 py-3 text-center">Cmp</th>
              <Th col="name" label="Name" className="text-left" />
              <Th col="module" label="Module" className="text-left" />
              <Th col="status" label="Status" className="text-left" />
              <th scope="col" className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Reproducibility
              </th>
              <th scope="col" className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Metric
              </th>
              <Th col="duration_ms" label="Duration" className="text-left" />
              <th scope="col" className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Config fp
              </th>
              <Th col="created_at" label="Created" className="text-left" />
              <th scope="col" className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                Baseline
              </th>
              <th scope="col" className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-slate-50 transition-colors hover:bg-slate-50">
                <td className="px-3 py-3 text-center">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(row.id)}
                    onChange={() => onToggle(row)}
                    aria-label={`Select ${row.name} for comparison`}
                  />
                </td>
                <td className="max-w-[220px] px-3 py-3">
                  <button
                    type="button"
                    onClick={() => onView(row.id)}
                    className="truncate text-left font-medium text-slate-800 hover:text-blue-700"
                  >
                    {row.name}
                  </button>
                  {row.tags.length > 0 && (
                    <div className="mt-0.5 truncate text-[11px] text-slate-400">{row.tags.join(", ")}</div>
                  )}
                </td>
                <td className="px-3 py-3 text-slate-600">
                  <div className="truncate">{row.module}</div>
                  <div className="truncate text-[11px] text-slate-400">{row.experiment_type}</div>
                </td>
                <td className="px-3 py-3"><StatusBadge status={row.status} /></td>
                <td className="px-3 py-3"><ReproBadge status={row.reproducibility_status} /></td>
                <td className="max-w-[160px] truncate px-3 py-3 font-mono text-xs text-slate-600">
                  {metricPreview(row.metrics)}
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">
                  {formatDuration(row.duration_ms)}
                </td>
                <td className="px-3 py-3">
                  <CopyValue value={row.configuration_fingerprint} display={shortFingerprint(row.configuration_fingerprint)} />
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-400">
                  {formatTimestamp(row.created_at).slice(0, 16)}
                </td>
                <td className="px-3 py-3 text-center"><BaselineBadge active={row.is_baseline} /></td>
                <td className="px-3 py-3 text-center">
                  <button
                    type="button"
                    onClick={() => onView(row.id)}
                    className="rounded-md border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-50 px-4 py-2 text-xs text-slate-500">
        <span>
          {total} experiment{total === 1 ? "" : "s"} · page {page} of {totalPages}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onPage(page - 1)}
            disabled={page <= 1}
            className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            ← Prev
          </button>
          <button
            type="button"
            onClick={() => onPage(page + 1)}
            disabled={page >= totalPages}
            className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
