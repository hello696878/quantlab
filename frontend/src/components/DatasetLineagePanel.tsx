"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type DatasetFilters,
  type DatasetFull,
  type DatasetListResponse,
  type RegistrySummary,
  exportDatasets,
  getDataset,
  getDatasetSummary,
  listDatasets,
  seedDemoLineage,
  shortFp,
  SOURCE_TYPE_LABELS,
} from "@/lib/datasetRegistry";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { CopyValue } from "@/components/ExperimentRegistryShared";
import { ProvenanceBadge, QualityBadge } from "@/components/DatasetLineageShared";
import DatasetLineageDetail from "@/components/DatasetLineageDetail";
import DatasetLineageCompare from "@/components/DatasetLineageCompare";

type Mode = "list" | "detail" | "compare";

const PAGE_SIZE = 15;
const SOURCE_OPTIONS = [
  "deterministic_fixture",
  "local_file",
  "generated",
  "derived",
  "optional_provider",
  "manual",
  "unknown",
];
const QUALITY_OPTIONS = ["passed", "warning", "failed", "unknown"];
const PROVENANCE_OPTIONS = ["complete", "partial", "unknown", "invalidated"];

const DISCLAIMER =
  "Local-first dataset registry stored in SQLite. Provenance records are declared metadata plus deterministic fingerprints over that metadata — integrity aids only, not a regulatory audit trail, not tamper-proof, and not proof the data is correct. Storage locators are logical identifiers; absolute local paths are never stored or shown.";

export default function DatasetLineagePanel() {
  const [mode, setMode] = useState<Mode>("list");
  const [summary, setSummary] = useState<RegistrySummary | null>(null);
  const [list, setList] = useState<DatasetListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<DatasetFilters>({});
  const [seeding, setSeeding] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [detail, setDetail] = useState<DatasetFull | null>(null);
  const [comparePair, setComparePair] = useState<{ a: number; b: number; label: string } | null>(null);

  const listParams = useMemo(
    () => ({ ...filters, page, page_size: PAGE_SIZE }),
    [filters, page],
  );
  const reload = useCallback(() => setRetryTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([listDatasets(listParams), getDatasetSummary()])
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

  function updateFilter(key: keyof DatasetFilters, value: string | boolean | undefined) {
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
      const ds = await getDataset(id);
      setDetail(ds);
      setMode("detail");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t open dataset", cls.message);
    }
  }

  async function handleSeedDemo() {
    setSeeding(true);
    try {
      const res = await seedDemoLineage();
      const created = res.created_datasets + res.created_versions + res.created_edges;
      toast.success(
        "Demo lineage loaded",
        created > 0
          ? `${res.created_datasets} datasets, ${res.created_versions} versions, ${res.created_edges} lineage edges added.`
          : "Demo lineage already present — nothing duplicated.",
      );
      reload();
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t load demo lineage", cls.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const payload = await exportDatasets(filters);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quantlab-dataset-lineage-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export ready", `${payload.datasets.length} dataset(s) exported as JSON.`);
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
      <DatasetLineageDetail
        dataset={detail}
        onBack={() => {
          setMode("list");
          setDetail(null);
          reload();
        }}
        onCompare={(a, b, label) => {
          setComparePair({ a, b, label });
          setMode("compare");
        }}
      />
    );
  }

  if (mode === "compare" && comparePair) {
    return (
      <DatasetLineageCompare
        aId={comparePair.a}
        bId={comparePair.b}
        contextLabel={comparePair.label}
        onBack={() => {
          setMode(detail ? "detail" : "list");
          setComparePair(null);
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Header card */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Local-first
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                SQLite · no cloud · no providers
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
              {seeding ? "Loading…" : "Load demo lineage"}
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
          <SummaryCard label="Datasets" value={summary.datasets} />
          <SummaryCard label="Versions" value={summary.versions} />
          <SummaryCard label="Derived" value={summary.derived_versions} />
          <SummaryCard label="Quality failures" value={summary.quality_failures} />
          <SummaryCard label="Unknown provenance" value={summary.unknown_provenance} />
          <SummaryCard label="Linked experiments" value={summary.linked_experiments} />
        </div>
      )}

      {/* Filter bar — ql-input keeps every control on the dark theme */}
      <div className="card p-3">
        <div className="flex flex-wrap items-end gap-2">
          <FilterSelect
            label="Source"
            value={filters.source_type ?? ""}
            options={SOURCE_OPTIONS}
            labels={SOURCE_TYPE_LABELS}
            onChange={(v) => updateFilter("source_type", v)}
          />
          <FilterSelect
            label="Domain"
            value={filters.domain ?? ""}
            options={summary?.domains ?? []}
            onChange={(v) => updateFilter("domain", v)}
          />
          <FilterSelect
            label="Format"
            value={filters.format ?? ""}
            options={summary?.formats ?? []}
            onChange={(v) => updateFilter("format", v)}
          />
          <FilterSelect
            label="Quality"
            value={filters.quality_status ?? ""}
            options={QUALITY_OPTIONS}
            onChange={(v) => updateFilter("quality_status", v)}
          />
          <FilterSelect
            label="Provenance"
            value={filters.provenance_status ?? ""}
            options={PROVENANCE_OPTIONS}
            onChange={(v) => updateFilter("provenance_status", v)}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor="ds-search" className="text-xs font-medium text-slate-500">
              Search
            </label>
            <input
              id="ds-search"
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
              checked={filters.demo === true}
              onChange={(e) => updateFilter("demo", e.target.checked ? true : undefined)}
            />
            Demo only
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

      {/* Table / states */}
      {loading ? (
        <SkeletonTable rows={6} cols={8} caption="Loading datasets…" />
      ) : error ? (
        classifyApiError(error).backendUnavailable ? (
          <OfflineState detail={classifyApiError(error).message} onRetry={reload} />
        ) : (
          <ErrorState
            title="Couldn’t load the dataset registry"
            message={classifyApiError(error).message}
            onRetry={reload}
          />
        )
      ) : !list || list.total === 0 ? (
        <EmptyState
          title="No datasets registered yet"
          description="Load the deterministic demo lineage to explore the dashboard, or register datasets and versions via the API."
          actions={[{ label: seeding ? "Loading…" : "Load demo lineage", onClick: handleSeedDemo }]}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            {/* min-width keeps columns readable; the card contains the scroll */}
            <table className="w-full min-w-[1160px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-3 text-left">Name</th>
                  <th scope="col" className="px-3 py-3 text-left">Source</th>
                  <th scope="col" className="px-3 py-3 text-left">Format</th>
                  <th scope="col" className="px-3 py-3 text-left">Freq</th>
                  <th scope="col" className="px-3 py-3 text-left">Date range</th>
                  <th scope="col" className="px-3 py-3 text-right">Rows</th>
                  <th scope="col" className="px-3 py-3 text-center">Versions</th>
                  <th scope="col" className="px-3 py-3 text-left">Quality</th>
                  <th scope="col" className="px-3 py-3 text-left">Provenance</th>
                  <th scope="col" className="px-3 py-3 text-left">Fingerprint</th>
                  <th scope="col" className="px-3 py-3 text-center">Experiments</th>
                  <th scope="col" className="px-3 py-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((row) => (
                  <tr key={row.id} className="border-b border-slate-50 transition-colors hover:bg-slate-50">
                    <td className="max-w-[240px] px-3 py-3">
                      <button
                        type="button"
                        onClick={() => openDetail(row.id)}
                        title={row.name}
                        className="block max-w-full truncate text-left font-medium text-slate-800 hover:text-blue-700"
                      >
                        {row.name}
                      </button>
                      <div className="truncate text-[11px] text-slate-400">
                        {row.domain} · {row.dataset_type}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-600">
                      {SOURCE_TYPE_LABELS[row.source_type] ?? row.source_type}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-600">{row.format}</td>
                    <td className="px-3 py-3 text-xs text-slate-600">{row.frequency ?? "—"}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">
                      {row.latest_date_range ?? "—"}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{row.latest_row_count ?? "—"}</td>
                    <td className="px-3 py-3 text-center text-xs">{row.version_count}</td>
                    <td className="px-3 py-3"><QualityBadge status={row.latest_quality_status} /></td>
                    <td className="px-3 py-3"><ProvenanceBadge status={row.provenance_status} /></td>
                    <td className="px-3 py-3">
                      <CopyValue
                        value={row.latest_manifest_fingerprint}
                        display={shortFp(row.latest_manifest_fingerprint)}
                      />
                    </td>
                    <td className="px-3 py-3 text-center text-xs">{row.linked_experiment_count}</td>
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
              {list.total} dataset{list.total === 1 ? "" : "s"} · page {list.page} of {list.total_pages}
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
  const id = `ds-filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
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
