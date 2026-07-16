"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type LabSummary,
  type RunFilters,
  type RunFull,
  type RunListResponse,
  type RunSummary,
  METHOD_LABELS,
  exportRuns,
  getRun,
  listRuns,
  seedDemoValidation,
  shortFp,
} from "@/lib/modelValidation";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { CopyValue } from "@/components/ExperimentRegistryShared";
import ModelValidationDetail, { LeakagePill, StatusPill } from "@/components/ModelValidationDetail";
import ModelValidationCompare from "@/components/ModelValidationCompare";

type Mode = "list" | "detail" | "compare";
type Selected = { id: number; name: string };

const PAGE_SIZE = 15;
const METHOD_OPTIONS = ["standard_kfold", "walk_forward", "purged_kfold", "cpcv"];
const STATUS_OPTIONS = ["pending", "completed", "failed", "invalidated"];

const DISCLAIMER =
  "Local-first model-validation lab for time-dependent research: samples carry information intervals [prediction → evaluation]; purged K-fold and CPCV remove training samples whose intervals overlap the test window, and a from-scratch leakage audit verifies every split. Ordinary shuffled K-fold is included as a reference only — it leaks with overlapping labels. Methodology and audit only: nothing here proves profitability, recommends a model, or constitutes investment, trading, or risk advice.";

interface Props {
  onNav?: (view: string) => void;
}

export default function ModelValidationPanel({ onNav }: Props) {
  const [mode, setMode] = useState<Mode>("list");
  const [summary, setSummary] = useState<LabSummary | null>(null);
  const [list, setList] = useState<RunListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<RunFilters>({});
  const [seeding, setSeeding] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [detail, setDetail] = useState<RunFull | null>(null);
  const [selected, setSelected] = useState<Selected[]>([]);
  const [comparePair, setComparePair] = useState<{ a: Selected; b: Selected } | null>(null);

  const listParams = useMemo(
    () => ({ ...filters, page, page_size: PAGE_SIZE }),
    [filters, page],
  );
  const reload = useCallback(() => setRetryTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([listRuns(listParams), getLabSummarySafe()])
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
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [listParams, retryTick, reload]);

  async function getLabSummarySafe(): Promise<LabSummary> {
    const { getLabSummary } = await import("@/lib/modelValidation");
    return getLabSummary();
  }

  function updateFilter(key: keyof RunFilters, value: string | boolean | undefined) {
    setPage(1);
    setFilters((prev) => {
      const next = { ...prev };
      if (value === undefined || value === "" || value === false) delete next[key];
      else (next as Record<string, unknown>)[key] = value;
      return next;
    });
  }

  async function openDetail(id: number) {
    try {
      const run = await getRun(id);
      setDetail(run);
      setMode("detail");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t open run", cls.message);
    }
  }

  function toggleSelect(row: RunSummary) {
    setSelected((prev) => {
      const exists = prev.find((s) => s.id === row.id);
      if (exists) return prev.filter((s) => s.id !== row.id);
      if (prev.length >= 2) return [prev[1], { id: row.id, name: row.name }];
      return [...prev, { id: row.id, name: row.name }];
    });
  }

  async function handleSeedDemo() {
    setSeeding(true);
    try {
      const res = await seedDemoValidation();
      toast.success(
        "Demo validation loaded",
        res.created_runs > 0
          ? `${res.created_runs} deterministic validation runs created and executed.`
          : "Demo runs already present — nothing duplicated.",
      );
      reload();
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t load demo validation", cls.message);
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
      a.download = `quantlab-model-validation-${new Date().toISOString().slice(0, 10)}.json`;
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
      <ModelValidationDetail
        run={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onChanged={(updated) => {
          setDetail(updated);
          reload();
        }}
        onOpenDataset={onNav ? () => onNav("datasetlineage") : undefined}
        onOpenExperiment={onNav ? () => onNav("experimentregistry") : undefined}
      />
    );
  }

  if (mode === "compare" && comparePair) {
    return (
      <ModelValidationCompare
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

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Local-first
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                Leakage prevention · SQLite · no cloud
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
              {seeding ? "Loading…" : "Load demo validation"}
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
          <SummaryCard label="Runs" value={summary.runs} />
          <SummaryCard label="Completed" value={summary.completed} />
          <SummaryCard label="Leakage-clean" value={summary.leakage_clean} />
          <SummaryCard label="Invalid splits" value={summary.invalid_splits} />
          <SummaryCard label="Baselines" value={summary.baselines} />
          <SummaryCard label="Linked datasets" value={summary.linked_datasets} />
        </div>
      )}

      {/* Filters — ql-input dark theme */}
      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <FilterSelect
            label="Method"
            value={filters.method ?? ""}
            options={METHOD_OPTIONS}
            labels={METHOD_LABELS}
            onChange={(v) => updateFilter("method", v)}
          />
          <FilterSelect
            label="Status"
            value={filters.status ?? ""}
            options={STATUS_OPTIONS}
            onChange={(v) => updateFilter("status", v)}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor="mv-search" className="text-xs font-medium text-slate-500">
              Search
            </label>
            <input
              id="mv-search"
              type="text"
              value={filters.query ?? ""}
              onChange={(e) => updateFilter("query", e.target.value)}
              placeholder="name or description"
              className="ql-input w-48 px-2 py-1.5 text-sm"
            />
          </div>
          <label className="flex items-center gap-1.5 pb-1.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={filters.leakage_clean === true}
              onChange={(e) => updateFilter("leakage_clean", e.target.checked ? true : undefined)}
            />
            Leakage-clean only
          </label>
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
            onClick={() => {
              setPage(1);
              setFilters({});
            }}
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
              onClick={() => {
                if (selected.length === 2) {
                  setComparePair({ a: selected[0], b: selected[1] });
                  setMode("compare");
                }
              }}
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
        <SkeletonTable rows={6} cols={8} caption="Loading validation runs…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState
            title="Couldn’t load the validation lab"
            message={classifyApiError(error).message}
            onRetry={reload}
          />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No validation runs yet"
          description="Load the deterministic demo validation to explore K-fold leakage, walk-forward, purged K-fold, embargo, and CPCV — or create runs via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo validation", onClick: handleSeedDemo }]}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-3 text-center">Cmp</th>
                  <th scope="col" className="px-3 py-3 text-left">Name</th>
                  <th scope="col" className="px-3 py-3 text-left">Method</th>
                  <th scope="col" className="px-3 py-3 text-left">Dataset</th>
                  <th scope="col" className="px-3 py-3 text-right">Samples</th>
                  <th scope="col" className="px-3 py-3 text-right">Splits</th>
                  <th scope="col" className="px-3 py-3 text-left">Leakage</th>
                  <th scope="col" className="px-3 py-3 text-left">Status</th>
                  <th scope="col" className="px-3 py-3 text-left">Metric</th>
                  <th scope="col" className="px-3 py-3 text-center">Baseline</th>
                  <th scope="col" className="px-3 py-3 text-left">Config fp</th>
                  <th scope="col" className="px-3 py-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((row) => (
                  <tr key={row.id} className="border-b border-slate-50 transition-colors hover:bg-slate-50">
                    <td className="px-3 py-3 text-center">
                      <input
                        type="checkbox"
                        checked={selected.some((s) => s.id === row.id)}
                        onChange={() => toggleSelect(row)}
                        aria-label={`Select ${row.name} for comparison`}
                      />
                    </td>
                    <td className="max-w-[260px] px-3 py-3">
                      <button
                        type="button"
                        onClick={() => openDetail(row.id)}
                        title={row.name}
                        className="block max-w-full truncate text-left font-medium text-slate-800 hover:text-blue-700"
                      >
                        {row.name}
                      </button>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-600">
                      {METHOD_LABELS[row.method] ?? row.method}
                    </td>
                    <td className="max-w-[160px] truncate px-3 py-3 text-xs text-slate-600" title={row.dataset_name ?? undefined}>
                      {row.dataset_name ? `${row.dataset_name} · ${row.dataset_version_label}` : "—"}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.sample_count}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">
                      {row.split_count}
                      {row.invalid_split_count > 0 && (
                        <span className="text-red-600"> ({row.invalid_split_count}✗)</span>
                      )}
                    </td>
                    <td className="px-3 py-3"><LeakagePill clean={row.leakage_clean} invalid={row.invalid_split_count} /></td>
                    <td className="px-3 py-3"><StatusPill status={row.status} /></td>
                    <td className="max-w-[150px] truncate px-3 py-3 font-mono text-xs text-slate-600">
                      {row.key_metric_preview ?? "—"}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {row.is_baseline ? (
                        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">★</span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <CopyValue value={row.configuration_fingerprint} display={shortFp(row.configuration_fingerprint)} />
                    </td>
                    <td className="px-3 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => openDetail(row.id)}
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
              {list.total} run{list.total === 1 ? "" : "s"} · page {list.page} of {list.total_pages}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => p - 1)}
                disabled={list.page <= 1}
                className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                ← Prev
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                disabled={list.page >= list.total_pages}
                className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

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
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  onChange: (value: string) => void;
}) {
  const id = `mv-filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-slate-500">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="ql-input min-w-[7rem] px-2 py-1.5 text-sm"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {labels?.[o] ?? o}
          </option>
        ))}
      </select>
    </div>
  );
}
