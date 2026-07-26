"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type RunFull,
  type RunSample,
  type SplitRecord,
  METHOD_LABELS,
  fmtTs,
  getRun,
  listRunSamples,
  listRunSplits,
  markRunBaseline,
} from "@/lib/modelValidation";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, JsonBlock, KeyValueTable } from "@/components/ExperimentRegistryShared";
import ModelValidationTimeline from "@/components/ModelValidationTimeline";

interface Props {
  run: RunFull;
  onBack: () => void;
  onChanged: (run: RunFull) => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
}

export default function ModelValidationDetail({ run, onBack, onChanged, onOpenDataset, onOpenExperiment }: Props) {
  const [splits, setSplits] = useState<SplitRecord[]>([]);
  const [samples, setSamples] = useState<RunSample[]>([]);
  const [selectedSplit, setSelectedSplit] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listRunSplits(run.id), listRunSamples(run.id)])
      .then(([sp, sa]) => {
        if (cancelled) return;
        setSplits(sp);
        setSamples(sa);
        setSelectedSplit(0);
      })
      .catch((err) => !cancelled && setError(classifyApiError(err).message));
    return () => {
      cancelled = true;
    };
  }, [run.id]);

  async function handleBaseline() {
    setBusy(true);
    try {
      const updated = await markRunBaseline(run.id);
      toast.success("Marked baseline", `"${run.name}" is the scope baseline.`);
      onChanged(updated);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Baseline rejected", cls.message);
    } finally {
      setBusy(false);
    }
  }

  const leak = run.leakage_summary as Record<string, number | boolean>;
  const split = splits[selectedSplit];
  const canBaseline =
    run.status === "completed" && run.leakage_clean === true && !run.is_baseline;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Back to runs
        </button>
        {canBaseline && (
          <button
            type="button"
            disabled={busy}
            onClick={handleBaseline}
            className="rounded-md border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
          >
            ★ Mark as baseline
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Identity */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-900">{run.name}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {METHOD_LABELS[run.method] ?? run.method} · {run.sample_count} samples ·{" "}
              {run.split_count} splits
            </p>
            {run.description && (
              <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <LeakagePill clean={run.leakage_clean} invalid={run.invalid_split_count} />
            {run.is_baseline && (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                ★ Baseline
              </span>
            )}
          </div>
        </div>
        {run.method === "standard_kfold" && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800">
            ⚠ Standard K-fold is a reference method: with overlapping label intervals it leaks
            information between training and test — the leakage audit below reports the overlaps.
          </div>
        )}
        {run.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">
            <span className="font-semibold">
              {run.status === "failed" ? "Execution failed:" : "Note:"}
            </span>{" "}
            {run.error_message}
          </div>
        )}
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Row label="Created" value={fmtTs(run.created_at)} />
          <Row label="Completed" value={fmtTs(run.completed_at)} />
          <Row label="Duration" value={run.duration_ms !== null ? `${run.duration_ms} ms` : "—"} />
          <Row label="Seed" value={run.random_seed === null ? "—" : String(run.random_seed)} />
        </dl>
        <dl className="mt-3 space-y-2 text-sm">
          <FpRow label="Configuration fingerprint" value={run.configuration_fingerprint} />
          <FpRow label="Result fingerprint" value={run.result_fingerprint} />
        </dl>
      </div>

      {/* Leakage audit */}
      <DetailSection title="Leakage audit">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Stat label="Splits" value={String(leak.total_splits ?? run.split_count)} />
          <Stat label="Valid" value={String(leak.valid_splits ?? run.valid_split_count)} />
          <Stat label="Invalid" value={String(leak.invalid_splits ?? run.invalid_split_count)} warn={Number(leak.invalid_splits ?? 0) > 0} />
          <Stat label="Purged" value={String(leak.total_purged ?? "—")} />
          <Stat label="Embargoed" value={String(leak.total_embargoed ?? "—")} />
          <Stat label="Remaining overlap" value={String(leak.total_remaining_overlap ?? "—")} warn={Number(leak.total_remaining_overlap ?? 0) > 0} />
        </div>
        <p className="mt-2 text-xs text-slate-400">
          A split is valid only when zero training intervals overlap the test intervals after
          purge + embargo. Purged and embargoed samples are counted separately. This audit checks
          the represented intervals only — it is not proof of model quality or profitability.
        </p>
      </DetailSection>

      {/* Linked records */}
      {(run.dataset_version_id || run.experiment_id) && (
        <DetailSection title="Linked records">
          <div className="grid gap-3 md:grid-cols-2">
            {run.dataset_version_id && (
              <div className="rounded-lg border border-slate-100 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-slate-800">
                    {run.dataset_name} · {run.dataset_version_label}
                  </span>
                  {onOpenDataset && (
                    <button
                      type="button"
                      onClick={onOpenDataset}
                      className="rounded-md border border-blue-200 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
                    >
                      Open in Dataset Lineage
                    </button>
                  )}
                </div>
                <dl className="mt-2 space-y-1 text-xs text-slate-500">
                  <div>Manifest fp: <CopyValue value={run.dataset_manifest_fingerprint} display={run.dataset_manifest_fingerprint?.slice(0, 12)} /></div>
                  <div>Provenance: {run.dataset_provenance_status ?? "unknown"} · Quality: {run.dataset_quality_status ?? "unknown"}</div>
                </dl>
                {run.dataset_invalidated && (
                  <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                    ⚠ This dataset version has been invalidated in the Dataset Lineage registry —
                    the recorded identity is preserved, but review before reuse.
                  </p>
                )}
              </div>
            )}
            {run.experiment_id && (
              <div className="rounded-lg border border-slate-100 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-slate-800">
                    {run.experiment_name ?? `Experiment #${run.experiment_id}`}
                  </span>
                  {onOpenExperiment && (
                    <button
                      type="button"
                      onClick={onOpenExperiment}
                      className="rounded-md border border-blue-200 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
                    >
                      Open in Experiment Registry
                    </button>
                  )}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  Recorded in the Experiment Registry (module: model_validation).
                </p>
              </div>
            )}
          </div>
        </DetailSection>
      )}

      {/* Aggregate metrics */}
      <DetailSection title="Aggregate metrics (across valid folds)">
        {Object.keys(run.aggregate_metrics).length === 0 ? (
          <p className="text-sm text-slate-400">No metrics recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2 text-left">Metric</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean</th>
                  <th scope="col" className="px-3 py-2 text-right">Median</th>
                  <th scope="col" className="px-3 py-2 text-right">Std</th>
                  <th scope="col" className="px-3 py-2 text-right">Min</th>
                  <th scope="col" className="px-3 py-2 text-right">Max</th>
                  <th scope="col" className="px-3 py-2 text-right">Valid folds</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(run.aggregate_metrics)
                  .filter(([, v]) => v.valid_folds > 0)
                  .map(([name, v]) => (
                    <tr key={name} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-medium text-slate-700">{name}</td>
                      {(["mean", "median", "std", "min", "max"] as const).map((k) => (
                        <td key={k} className="px-3 py-1.5 text-right font-mono text-xs">
                          {v[k] ?? "—"}
                        </td>
                      ))}
                      <td className="px-3 py-1.5 text-right font-mono text-xs">{v.valid_folds}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">
          Neutral statistics only — undefined metrics are omitted per fold with a recorded reason;
          nothing here ranks or recommends a model.
        </p>
      </DetailSection>

      {/* Splits */}
      {splits.length > 0 && (
        <DetailSection title={`Splits (${splits.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-2 text-left">Split</th>
                  <th scope="col" className="px-2 py-2 text-right">Train</th>
                  <th scope="col" className="px-2 py-2 text-right">Test</th>
                  <th scope="col" className="px-2 py-2 text-right">Purged</th>
                  <th scope="col" className="px-2 py-2 text-right">Embargoed</th>
                  <th scope="col" className="px-2 py-2 text-right">Remaining overlap</th>
                  <th scope="col" className="px-2 py-2 text-left">Status</th>
                  <th scope="col" className="px-2 py-2 text-left">Fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {splits.map((s, i) => (
                  <tr
                    key={s.id}
                    className={`border-b border-slate-50 last:border-0 ${i === selectedSplit ? "bg-blue-50/40" : ""}`}
                  >
                    <td className="px-2 py-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedSplit(i)}
                        className="font-medium text-blue-700 hover:underline"
                      >
                        {s.split_label}
                      </button>
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{s.train_ids.length}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{s.test_ids.length}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{s.purged_ids.length}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{s.embargoed_ids.length}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">
                      {s.diagnostics.remaining_overlap_count ?? 0}
                    </td>
                    <td className="px-2 py-1.5">
                      {s.status === "valid" ? (
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">valid</span>
                      ) : (
                        <span className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">invalid</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5">
                      <CopyValue value={s.split_fingerprint} display={s.split_fingerprint.slice(0, 12)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DetailSection>
      )}

      {/* Timeline for the selected split */}
      {split && samples.length > 0 && (
        <DetailSection title={`Split timeline — ${split.split_label}`}>
          <ModelValidationTimeline samples={samples} split={split} />
        </DetailSection>
      )}

      {/* Configuration + raw */}
      <DetailSection
        title="Configuration"
        action={
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {showRaw ? "Hide raw JSON" : "Raw JSON"}
          </button>
        }
      >
        <KeyValueTable data={run.configuration} empty="Default configuration." />
        {showRaw && <div className="mt-3"><JsonBlock value={{ ...run, samples: undefined }} /></div>}
      </DetailSection>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="truncate text-slate-800" title={value}>{value}</dd>
    </div>
  );
}

function FpRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 overflow-hidden"><CopyValue value={value} className="max-w-full" /></dd>
    </div>
  );
}

function Stat({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className={`rounded-lg border p-2.5 ${warn ? "border-red-200 bg-red-50/50" : "border-slate-100"}`}>
      <div className={`text-lg font-bold ${warn ? "text-red-700" : "text-slate-900"}`}>{value}</div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
    pending: "border-slate-200 bg-slate-50 text-slate-600",
    failed: "border-red-200 bg-red-50 text-red-700",
    invalidated: "border-amber-200 bg-amber-50 text-amber-700",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.pending}`}>
      {status}
    </span>
  );
}

export function LeakagePill({ clean, invalid }: { clean: boolean | null; invalid: number }) {
  if (clean === null) {
    return (
      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
        leakage: unknown
      </span>
    );
  }
  return clean ? (
    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
      leakage-clean
    </span>
  ) : (
    <span className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
      leakage: {invalid} invalid split{invalid === 1 ? "" : "s"}
    </span>
  );
}
