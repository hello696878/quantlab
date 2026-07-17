"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type CalibrationBin,
  type ObservationRow,
  type RunFull,
  type ThresholdPolicy,
  type ThresholdRow,
  OOF_LABELS,
  createPolicy,
  getCalibration,
  listObservations,
  listPolicies,
  markPolicyBaseline,
} from "@/lib/metaLabeling";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, KeyValueTable } from "@/components/ExperimentRegistryShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
}

export default function MetaLabelingDetail({ run, onBack, onOpenValidation, onOpenDataset, onOpenExperiment }: Props) {
  const [bins, setBins] = useState<Record<string, CalibrationBin[]>>({});
  const [policies, setPolicies] = useState<ThresholdPolicy[]>([]);
  const [obs, setObs] = useState<{ items: ObservationRow[]; total: number; page: number; total_pages: number } | null>(null);
  const [obsPage, setObsPage] = useState(1);
  const [selectedThreshold, setSelectedThreshold] = useState<number>(0.5);
  const [busy, setBusy] = useState(false);

  const rows: ThresholdRow[] = useMemo(
    () => run.threshold_analysis?.thresholds ?? [],
    [run.threshold_analysis],
  );
  const selectedRow = useMemo(() => {
    if (!rows.length) return null;
    return rows.reduce((best, r) =>
      Math.abs(r.threshold - selectedThreshold) < Math.abs(best.threshold - selectedThreshold) ? r : best,
    );
  }, [rows, selectedThreshold]);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getCalibration(run.id).then((c) => !cancelled && setBins(c.bins)).catch(() => {});
      listPolicies(run.id).then((p) => !cancelled && setPolicies(p)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status]);

  useEffect(() => {
    let cancelled = false;
    listObservations(run.id, obsPage).then((o) => !cancelled && setObs(o)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [run.id, obsPage]);

  async function savePolicy() {
    setBusy(true);
    try {
      await createPolicy(run.id, { threshold: selectedThreshold });
      toast.success("Threshold policy saved", `Research record at threshold ${selectedThreshold}.`);
      setPolicies(await listPolicies(run.id));
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Policy rejected", cls.message);
    } finally {
      setBusy(false);
    }
  }

  async function baseline(policyId: number) {
    setBusy(true);
    try {
      await markPolicyBaseline(policyId);
      toast.success("Baseline marked", "Previous baseline in this run was unmarked.");
      setPolicies(await listPolicies(run.id));
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Baseline rejected", cls.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
        ← Back to runs
      </button>

      {/* Identity */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-900">{run.name}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              Calibration: {run.calibration_method} · {run.observation_count} observations ·{" "}
              {run.positive_count} positive / {run.labeled_count} labeled
              {run.abstained_count > 0 ? ` · ${run.abstained_count} abstained (side 0)` : ""}
            </p>
            {run.description && <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <OofPill status={run.oof_status} />
          </div>
        </div>
        {run.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">
            <span className="font-semibold">{run.status === "failed" ? "Execution failed:" : "Note:"}</span>{" "}
            {run.error_message}
          </div>
        )}
        {run.oof_status === "not_out_of_fold" && run.status === "completed" && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800">
            ⚠ The calibrator was fitted on all observations — these metrics are not out-of-fold.
          </div>
        )}
        <dl className="mt-3 space-y-2 text-sm">
          <FpRow label="Configuration fingerprint" value={run.configuration_fingerprint} />
          <FpRow label="Result fingerprint" value={run.result_fingerprint} />
        </dl>
      </div>

      {/* Linked records */}
      {(run.validation_run_id || run.dataset_version_id || run.experiment_id) && (
        <DetailSection title="Linked records">
          <div className="grid gap-3 md:grid-cols-3">
            {run.validation_run_id && (
              <LinkCard
                title={`Validation run #${run.validation_run_id}`}
                lines={[
                  `Method: ${run.validation_method ?? "—"}`,
                  `Leakage-clean: ${run.validation_leakage_clean === true ? "yes" : run.validation_leakage_clean === false ? "no" : "—"}`,
                ]}
                fp={run.validation_config_fp}
                action={onOpenValidation}
                actionLabel="Open in Model Validation Lab"
              />
            )}
            {run.dataset_version_id && (
              <LinkCard
                title={`${run.dataset_name ?? "dataset"} · ${run.dataset_version_label ?? ""}`}
                lines={[
                  `Provenance: ${run.dataset_provenance_status ?? "unknown"} · Quality: ${run.dataset_quality_status ?? "unknown"}`,
                ]}
                fp={run.dataset_manifest_fingerprint}
                warning={run.dataset_invalidated ? "⚠ This dataset version has been invalidated — review before reuse." : undefined}
                action={onOpenDataset}
                actionLabel="Open in Dataset Lineage"
              />
            )}
            {run.experiment_id && (
              <LinkCard
                title={run.experiment_name ?? `Experiment #${run.experiment_id}`}
                lines={["Recorded in the Experiment Registry (module: meta_labeling)."]}
                action={onOpenExperiment}
                actionLabel="Open in Experiment Registry"
              />
            )}
          </div>
        </DetailSection>
      )}

      {run.status === "completed" && (
        <>
          {/* Raw vs calibrated metrics */}
          <DetailSection title="Probability metrics (raw vs calibrated)">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2 text-left">Metric</th>
                    <th scope="col" className="px-3 py-2 text-right">Raw</th>
                    <th scope="col" className="px-3 py-2 text-right">Calibrated</th>
                  </tr>
                </thead>
                <tbody>
                  {["brier", "log_loss", "roc_auc", "pr_auc"].map((m) => (
                    <MetricRow key={m} name={m}
                      raw={run.raw_metrics?.metrics?.[m] ?? null}
                      cal={run.calibrated_metrics?.metrics?.[m] ?? null}
                      rawReason={run.raw_metrics?.reasons?.[m]}
                    />
                  ))}
                  <MetricRow name="ECE" raw={run.raw_metrics?.ece ?? null} cal={run.calibrated_metrics?.ece ?? null} />
                  <MetricRow name="MCE" raw={run.raw_metrics?.mce ?? null} cal={run.calibrated_metrics?.mce ?? null} />
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Neutral probability-quality statistics — a lower Brier score or ECE describes probability
              reliability under this dataset, not profitability, and no model is recommended.
            </p>
          </DetailSection>

          {/* Reliability chart */}
          <DetailSection title="Reliability (calibration curve)">
            <ReliabilityChart raw={bins.raw ?? []} calibrated={bins.calibrated ?? []} />
          </DetailSection>

          {/* Threshold analysis */}
          <DetailSection title="Decision-threshold analysis">
            <ThresholdChart rows={rows} selected={selectedRow} onSelect={(t) => setSelectedThreshold(t)} />
            {selectedRow && (
              <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
                <Stat label="Threshold" value={String(selectedRow.threshold)} />
                <Stat label="Coverage" value={fmt(selectedRow.coverage)} />
                <Stat label="Accepted" value={String(selectedRow.accepted)} />
                <Stat label="Precision" value={fmt(selectedRow.precision)} />
                <Stat label="Recall" value={fmt(selectedRow.recall)} />
                <Stat label="F1" value={fmt(selectedRow.f1)} />
                <Stat label="FP / FN" value={`${selectedRow.false_positives} / ${selectedRow.false_negatives}`} />
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" onClick={savePolicy} disabled={busy || !selectedRow}
                className="rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50">
                Save threshold policy at {selectedRow?.threshold ?? "—"}
              </button>
              <span className="text-xs text-slate-400">
                A saved policy is a research record of your own selection — the lab never recommends a threshold.
              </span>
            </div>
          </DetailSection>

          {/* Policies */}
          <DetailSection title={`Threshold policies (${policies.length})`}>
            {policies.length === 0 ? (
              <p className="text-sm text-slate-400">No saved policies for this run.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <th scope="col" className="px-2 py-2 text-left">Name</th>
                      <th scope="col" className="px-2 py-2 text-right">Threshold</th>
                      <th scope="col" className="px-2 py-2 text-left">Abstention</th>
                      <th scope="col" className="px-2 py-2 text-right">Coverage</th>
                      <th scope="col" className="px-2 py-2 text-right">Precision</th>
                      <th scope="col" className="px-2 py-2 text-right">Recall</th>
                      <th scope="col" className="px-2 py-2 text-center">Baseline</th>
                    </tr>
                  </thead>
                  <tbody>
                    {policies.map((p) => (
                      <tr key={p.id} className="border-b border-slate-50 last:border-0">
                        <td className="max-w-[220px] truncate px-2 py-1.5 font-medium text-slate-700" title={p.name}>{p.name}</td>
                        <td className="px-2 py-1.5 text-right font-mono text-xs">{p.threshold}</td>
                        <td className="px-2 py-1.5 text-xs text-slate-500">
                          {p.abstention ? `(${p.abstention.lower}, ${p.abstention.upper})` : "—"}
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(p.observed_coverage)}</td>
                        <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(p.observed_precision)}</td>
                        <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(p.observed_recall)}</td>
                        <td className="px-2 py-1.5 text-center">
                          {p.is_baseline ? (
                            <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">★</span>
                          ) : (
                            <button type="button" disabled={busy} onClick={() => baseline(p.id)}
                              className="rounded-md border border-slate-200 px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-50 disabled:opacity-50">
                              mark
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </DetailSection>
        </>
      )}

      {/* Observations */}
      {obs && obs.total > 0 && (
        <DetailSection title={`Observations (${obs.total})`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-2 text-left">Sample</th>
                  <th scope="col" className="px-2 py-2 text-right">Side</th>
                  <th scope="col" className="px-2 py-2 text-right">Raw p</th>
                  <th scope="col" className="px-2 py-2 text-right">Calibrated p</th>
                  <th scope="col" className="px-2 py-2 text-right">Outcome</th>
                  <th scope="col" className="px-2 py-2 text-right">Meta-label</th>
                  <th scope="col" className="px-2 py-2 text-left">Split</th>
                </tr>
              </thead>
              <tbody>
                {obs.items.map((o) => (
                  <tr key={o.sample_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1.5 font-mono text-xs">{o.sample_id}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{o.primary_side}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(o.raw_probability)}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(o.calibrated_probability)}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">{fmt(o.realized_outcome)}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs">
                      {o.abstained ? "abstained" : o.meta_label ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 text-xs text-slate-500">{o.split_label ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
            <span>page {obs.page} of {obs.total_pages}</span>
            <div className="flex gap-2">
              <button type="button" disabled={obs.page <= 1} onClick={() => setObsPage((p) => p - 1)}
                className="rounded-md border border-slate-200 px-2.5 py-1 disabled:opacity-40">← Prev</button>
              <button type="button" disabled={obs.page >= obs.total_pages} onClick={() => setObsPage((p) => p + 1)}
                className="rounded-md border border-slate-200 px-2.5 py-1 disabled:opacity-40">Next →</button>
            </div>
          </div>
        </DetailSection>
      )}

      <DetailSection title="Label policy & configuration">
        <div className="grid gap-4 md:grid-cols-2">
          <KeyValueTable data={run.label_policy} empty="—" />
          <KeyValueTable data={run.configuration} empty="—" />
        </div>
      </DetailSection>
    </div>
  );
}

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function MetricRow({ name, raw, cal, rawReason }: { name: string; raw: number | null; cal: number | null; rawReason?: string }) {
  return (
    <tr className="border-b border-slate-50 last:border-0">
      <td className="px-3 py-1.5 font-medium text-slate-700">
        {name}
        {raw === null && rawReason && <span className="ml-1.5 text-[10px] text-slate-400">({rawReason})</span>}
      </td>
      <td className="px-3 py-1.5 text-right font-mono text-xs">{raw === null ? "unavailable" : fmt(raw)}</td>
      <td className="px-3 py-1.5 text-right font-mono text-xs">{cal === null ? "unavailable" : fmt(cal)}</td>
    </tr>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 p-2.5">
      <div className="text-lg font-bold text-slate-900">{value}</div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
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

function LinkCard({ title, lines, fp, warning, action, actionLabel }: {
  title: string; lines: string[]; fp?: string | null; warning?: string;
  action?: () => void; actionLabel?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-100 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-slate-800">{title}</span>
        {action && (
          <button type="button" onClick={action}
            className="rounded-md border border-blue-200 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50">
            {actionLabel}
          </button>
        )}
      </div>
      {lines.map((l, i) => <p key={i} className="mt-1 text-xs text-slate-500">{l}</p>)}
      {fp && <div className="mt-1 text-xs"><CopyValue value={fp} display={fp.slice(0, 12)} /></div>}
      {warning && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">{warning}</p>
      )}
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
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.pending}`}>{status}</span>;
}

export function OofPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified_from_validation_run: "border-emerald-200 bg-emerald-50 text-emerald-700",
    declared_out_of_fold: "border-blue-200 bg-blue-50 text-blue-700",
    not_out_of_fold: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {OOF_LABELS[status] ?? status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Reliability chart (SVG; diagonal + raw + calibrated; pattern + shape coded)
// ---------------------------------------------------------------------------

const CW = 420;
const CH = 300;
const PAD = 36;

function ReliabilityChart({ raw, calibrated }: { raw: CalibrationBin[]; calibrated: CalibrationBin[] }) {
  const x = (p: number) => PAD + p * (CW - PAD * 2);
  const y = (p: number) => CH - PAD - p * (CH - PAD * 2);
  const path = (bins: CalibrationBin[]) =>
    bins
      .filter((b) => b.mean_probability !== null && b.observed_frequency !== null)
      .map((b, i) => `${i === 0 ? "M" : "L"} ${x(b.mean_probability!)} ${y(b.observed_frequency!)}`)
      .join(" ");
  const filledRaw = raw.filter((b) => b.sample_count > 0);
  const filledCal = calibrated.filter((b) => b.sample_count > 0);
  const small = [...filledRaw, ...filledCal].some((b) => b.sample_count < 5);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-slate-400" style={{ borderTop: "2px dashed #94a3b8", height: 0 }} /> Perfect calibration</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2 w-2 rounded-full" style={{ background: "#f59e0b" }} /> Raw (circles)</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2 w-2" style={{ background: "#34d399" }} /> Calibrated (squares)</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg width={CW} height={CH} role="img"
          aria-label={`Reliability chart: ${filledRaw.length} raw and ${filledCal.length} calibrated non-empty bins; the bin table below lists exact values.`}>
          <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="#94a3b8" strokeDasharray="5 4" strokeWidth={1.5} />
          <line x1={PAD} y1={CH - PAD} x2={CW - PAD} y2={CH - PAD} stroke="#475569" />
          <line x1={PAD} y1={PAD} x2={PAD} y2={CH - PAD} stroke="#475569" />
          <text x={CW / 2} y={CH - 8} fontSize={10} textAnchor="middle" fill="#94a3b8">Mean predicted probability</text>
          <text x={12} y={CH / 2} fontSize={10} textAnchor="middle" fill="#94a3b8" transform={`rotate(-90 12 ${CH / 2})`}>Observed frequency</text>
          <path d={path(filledRaw)} fill="none" stroke="#f59e0b" strokeWidth={1.5} />
          <path d={path(filledCal)} fill="none" stroke="#34d399" strokeWidth={1.5} />
          {filledRaw.map((b) => (
            <circle key={`r${b.bin_index}`} cx={x(b.mean_probability!)} cy={y(b.observed_frequency!)} r={4} fill="#f59e0b">
              <title>{`raw bin ${b.bin_index}: n=${b.sample_count}, p̄=${b.mean_probability}, freq=${b.observed_frequency}`}</title>
            </circle>
          ))}
          {filledCal.map((b) => (
            <rect key={`c${b.bin_index}`} x={x(b.mean_probability!) - 3.5} y={y(b.observed_frequency!) - 3.5} width={7} height={7} fill="#34d399">
              <title>{`calibrated bin ${b.bin_index}: n=${b.sample_count}, p̄=${b.mean_probability}, freq=${b.observed_frequency}`}</title>
            </rect>
          ))}
        </svg>
      </div>
      {small && (
        <p className="text-xs text-amber-600">Some bins hold fewer than 5 samples — treat those points with caution.</p>
      )}
      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-500">Bin table (accessible alternative)</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[560px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-2 py-1">Bin</th><th scope="col" className="px-2 py-1">Range</th>
                <th scope="col" className="px-2 py-1 text-right">Raw n / p̄ / freq</th>
                <th scope="col" className="px-2 py-1 text-right">Calibrated n / p̄ / freq</th>
              </tr>
            </thead>
            <tbody>
              {raw.map((rb, i) => {
                const cb = calibrated[i];
                return (
                  <tr key={rb.bin_index} className="border-b border-slate-50 last:border-0 font-mono">
                    <td className="px-2 py-1">{rb.bin_index}</td>
                    <td className="px-2 py-1">{fmt(rb.lower_bound)}–{fmt(rb.upper_bound)}</td>
                    <td className="px-2 py-1 text-right">{rb.sample_count} / {fmt(rb.mean_probability)} / {fmt(rb.observed_frequency)}</td>
                    <td className="px-2 py-1 text-right">{cb ? `${cb.sample_count} / ${fmt(cb.mean_probability)} / ${fmt(cb.observed_frequency)}` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
      <p className="text-xs text-slate-400">
        Closeness to the diagonal describes probability reliability only — it does not prove profitability.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Threshold chart (SVG; coverage/precision/recall/F1 vs threshold)
// ---------------------------------------------------------------------------

const SERIES: { key: keyof ThresholdRow; label: string; color: string; dash?: string }[] = [
  { key: "coverage", label: "Coverage", color: "#60a5fa" },
  { key: "precision", label: "Precision", color: "#34d399", dash: "6 3" },
  { key: "recall", label: "Recall", color: "#f59e0b", dash: "2 3" },
  { key: "f1", label: "F1", color: "#c084fc", dash: "8 3 2 3" },
];

function ThresholdChart({ rows, selected, onSelect }: {
  rows: ThresholdRow[]; selected: ThresholdRow | null; onSelect: (t: number) => void;
}) {
  if (!rows.length) return <p className="text-sm text-slate-400">No threshold analysis recorded.</p>;
  const x = (t: number) => PAD + t * (CW - PAD * 2);
  const y = (v: number) => CH - PAD - v * (CH - PAD * 2);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
        {SERIES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <svg width={22} height={6}><line x1={0} y1={3} x2={22} y2={3} stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} /></svg>
            {s.label}
          </span>
        ))}
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg width={CW} height={CH} role="img"
          aria-label={`Threshold analysis across ${rows.length} thresholds; exact values are in the threshold table.`}
          onClick={(e) => {
            const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
            const t = Math.min(1, Math.max(0, (e.clientX - rect.left - PAD) / (CW - PAD * 2)));
            onSelect(Math.round(t * 20) / 20);
          }}
          style={{ cursor: "pointer" }}>
          <line x1={PAD} y1={CH - PAD} x2={CW - PAD} y2={CH - PAD} stroke="#475569" />
          <line x1={PAD} y1={PAD} x2={PAD} y2={CH - PAD} stroke="#475569" />
          <text x={CW / 2} y={CH - 8} fontSize={10} textAnchor="middle" fill="#94a3b8">Decision threshold (accept when p ≥ t)</text>
          {selected && (
            <line x1={x(selected.threshold)} y1={PAD} x2={x(selected.threshold)} y2={CH - PAD}
              stroke="#e2e8f0" strokeWidth={2} />
          )}
          {SERIES.map((s) => (
            <path key={s.key} fill="none" stroke={s.color} strokeWidth={1.8} strokeDasharray={s.dash}
              d={rows.filter((r) => r[s.key] !== null)
                .map((r, i) => `${i === 0 ? "M" : "L"} ${x(r.threshold)} ${y(r[s.key] as number)}`).join(" ")} />
          ))}
        </svg>
      </div>
      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-500">Threshold table (accessible alternative)</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-2 py-1">t</th><th scope="col" className="px-2 py-1 text-right">accepted</th>
                <th scope="col" className="px-2 py-1 text-right">coverage</th><th scope="col" className="px-2 py-1 text-right">precision</th>
                <th scope="col" className="px-2 py-1 text-right">recall</th><th scope="col" className="px-2 py-1 text-right">F1</th>
                <th scope="col" className="px-2 py-1 text-right">FP</th><th scope="col" className="px-2 py-1 text-right">FN</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.threshold}
                  className={`cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 ${selected?.threshold === r.threshold ? "bg-blue-50/50" : ""}`}
                  onClick={() => onSelect(r.threshold)}>
                  <td className="px-2 py-1">{r.threshold}</td>
                  <td className="px-2 py-1 text-right">{r.accepted}</td>
                  <td className="px-2 py-1 text-right">{fmt(r.coverage)}</td>
                  <td className="px-2 py-1 text-right">{r.precision === null ? "unavailable" : fmt(r.precision)}</td>
                  <td className="px-2 py-1 text-right">{r.recall === null ? "unavailable" : fmt(r.recall)}</td>
                  <td className="px-2 py-1 text-right">{r.f1 === null ? "unavailable" : fmt(r.f1)}</td>
                  <td className="px-2 py-1 text-right">{r.false_positives}</td>
                  <td className="px-2 py-1 text-right">{r.false_negatives}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
