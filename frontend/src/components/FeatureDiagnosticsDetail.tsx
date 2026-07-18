"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type CorrelationGroup,
  type DriftRow,
  type FeatureResult,
  type RunFull,
  type SplitResultRow,
  INTEGRITY_LABELS,
  getCorrelations,
  getDrift,
  getFeatures,
  getSplits,
  markBaseline,
} from "@/lib/featureDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, KeyValueTable } from "@/components/ExperimentRegistryShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
  onOpenMetaLabeling?: () => void;
}

export default function FeatureDiagnosticsDetail({
  run, onBack, onRefresh, onOpenValidation, onOpenDataset, onOpenExperiment, onOpenMetaLabeling,
}: Props) {
  const [features, setFeatures] = useState<FeatureResult[]>([]);
  const [splitRows, setSplitRows] = useState<SplitResultRow[]>([]);
  const [groups, setGroups] = useState<CorrelationGroup[]>([]);
  const [drift, setDrift] = useState<DriftRow[]>([]);
  const [topN, setTopN] = useState(10);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getFeatures(run.id).then((r) => !cancelled && setFeatures(r.items)).catch(() => {});
      getSplits(run.id).then((r) => !cancelled && setSplitRows(r.items)).catch(() => {});
      getCorrelations(run.id).then((r) => !cancelled && setGroups(r.groups)).catch(() => {});
      getDrift(run.id).then((r) => !cancelled && setDrift(r.items)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status]);

  async function handleBaseline() {
    setBusy(true);
    try {
      const updated = await markBaseline(run.id);
      toast.success("Baseline marked", "Any previous baseline in the same scope was unmarked.");
      onRefresh(updated);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Baseline rejected", cls.message);
    } finally {
      setBusy(false);
    }
  }

  const distributionDrift = drift.filter((d) => d.kind === "distribution");
  const importanceDrift = drift.filter((d) => d.kind === "importance");

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
              Method: {run.method} · Model: {run.model_type} · Metric: {run.metric} ({run.metric_direction.replace(/_/g, " ")}) ·{" "}
              {run.sample_count} samples · {run.feature_count} features · {run.valid_split_count}/{run.split_count} valid splits
            </p>
            {run.description && <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <IntegrityPill status={run.integrity_status} />
            {run.is_baseline && (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">★ baseline</span>
            )}
          </div>
        </div>
        {run.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">
            <span className="font-semibold">{run.status === "failed" ? "Execution failed:" : "Note:"}</span>{" "}
            {run.error_message}
          </div>
        )}
        {run.integrity_status === "not_held_out" && run.status === "completed" && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800">
            ⚠ Importance here is training-data derived or evaluated in-sample — it is not held-out
            performance degradation.
          </div>
        )}
        <dl className="mt-3 space-y-2 text-sm">
          <FpRow label="Configuration fingerprint" value={run.configuration_fingerprint} />
          <FpRow label="Result fingerprint" value={run.result_fingerprint} />
          {run.baseline_fingerprint && <FpRow label="Baseline fingerprint" value={run.baseline_fingerprint} />}
        </dl>
        {run.status === "completed" && !run.is_baseline && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" onClick={handleBaseline} disabled={busy}
              className="rounded-md border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
              {busy ? "Marking…" : "Mark as scope baseline"}
            </button>
            <span className="text-xs text-slate-400">
              A baseline is a comparison reference within its scope — it is never a recommendation.
            </span>
          </div>
        )}
      </div>

      {/* Warnings */}
      {run.warnings.length > 0 && (
        <DetailSection title={`Warnings (${run.warnings.length})`}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700">
            {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </DetailSection>
      )}

      {/* Linked records */}
      {(run.validation_run_id || run.dataset_version_id || run.experiment_id || run.meta_label_run_id) && (
        <DetailSection title="Linked records">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
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
                lines={["Recorded in the Experiment Registry (module: feature_diagnostics)."]}
                action={onOpenExperiment}
                actionLabel="Open in Experiment Registry"
              />
            )}
            {run.meta_label_run_id && (
              <LinkCard
                title={run.meta_label_run_name ?? `Meta-label run #${run.meta_label_run_id}`}
                lines={[
                  `OOF: ${run.meta_label_oof_status ?? "—"} · Calibration: ${run.meta_label_calibration_method ?? "—"}`,
                ]}
                fp={run.meta_label_result_fp}
                action={onOpenMetaLabeling}
                actionLabel="Open in Meta-Labeling Lab"
              />
            )}
          </div>
        </DetailSection>
      )}

      {run.status === "completed" && (
        <>
          <DetailSection title="Feature importance (aggregate across splits)">
            <ImportanceChart features={features} topN={topN} onTopN={setTopN}
              method={run.method} metric={run.metric} />
          </DetailSection>

          <DetailSection title="Rank stability across splits">
            <StabilityView run={run} splitRows={splitRows} features={features} />
          </DetailSection>

          <DetailSection title={`Correlated feature groups (${groups.length})`}>
            <CorrelationView groups={groups} />
          </DetailSection>

          <DetailSection title="Feature distribution drift">
            <DriftView rows={distributionDrift} context={run.drift_context} kind="distribution" />
          </DetailSection>

          <DetailSection title="Importance drift (earlier vs later splits)">
            <DriftView rows={importanceDrift} context={run.drift_context} kind="importance"
              importanceMeta={run.importance_drift} />
          </DetailSection>

          {(run.references.coefficients || run.references.native_impurity) && (
            <DetailSection title="Model references (training-data derived — caveated)">
              <ReferencesView references={run.references} />
            </DetailSection>
          )}

          <DetailSection title={`Split-level results (${run.splits.length} splits)`}>
            <SplitTable run={run} rows={splitRows} />
          </DetailSection>
        </>
      )}

      <DetailSection title="Configuration">
        <KeyValueTable data={run.configuration} empty="—" />
      </DetailSection>
    </div>
  );
}

function fmt(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined) return "—";
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
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

export function IntegrityPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified_held_out: "border-emerald-200 bg-emerald-50 text-emerald-700",
    declared_held_out: "border-blue-200 bg-blue-50 text-blue-700",
    not_held_out: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {INTEGRITY_LABELS[status] ?? status}
    </span>
  );
}

export function StabilityPill({ classification }: { classification: string }) {
  const styles: Record<string, string> = {
    stable: "border-emerald-200 bg-emerald-50 text-emerald-700",
    moderately_stable: "border-blue-200 bg-blue-50 text-blue-700",
    unstable: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[classification] ?? styles.unknown}`}>
      {classification.replace(/_/g, " ")}
    </span>
  );
}

export function DriftPill({ classification }: { classification: string }) {
  const styles: Record<string, string> = {
    none: "border-slate-200 bg-slate-50 text-slate-500",
    low: "border-blue-200 bg-blue-50 text-blue-700",
    moderate: "border-amber-200 bg-amber-50 text-amber-700",
    high: "border-red-200 bg-red-50 text-red-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-400",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[classification] ?? styles.unknown}`}>
      {classification}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Importance chart (horizontal SVG bars + spread whiskers + zero line)
// ---------------------------------------------------------------------------

const BAR_H = 22;
const CHART_W = 560;
const LABEL_W = 130;
const PAD_R = 16;

function ImportanceChart({ features, topN, onTopN, method, metric }: {
  features: FeatureResult[]; topN: number; onTopN: (n: number) => void;
  method: string; metric: string;
}) {
  const defined = useMemo(
    () => features.filter((f) => f.mean_importance !== null),
    [features],
  );
  const shown = defined.slice(0, topN);
  if (!features.length) return <p className="text-sm text-slate-400">No aggregate results recorded.</p>;

  const values = shown.flatMap((f) => [
    f.mean_importance ?? 0, f.min_importance ?? 0, f.max_importance ?? 0,
  ]);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const span = hi - lo || 1;
  const x = (v: number) => LABEL_W + ((v - lo) / span) * (CHART_W - LABEL_W - PAD_R);
  const height = shown.length * (BAR_H + 6) + 30;
  const top = defined[0];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          {top
            ? `Highest measured importance under ${method}/${metric}: ${top.feature_name} (rank 1)`
            : "No feature has a defined importance."}
          {" — a descriptive ranking, not a quality or causality claim."}
        </span>
        <label className="flex items-center gap-1.5">
          Top&nbsp;N
          <select value={topN} onChange={(e) => onTopN(Number(e.target.value))}
            className="ql-input px-2 py-1 text-xs" aria-label="Top N features shown in chart">
            {[5, 10, 20, 32].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg width={CHART_W} height={height} role="img"
          aria-label={`Aggregate importance bars for ${shown.length} of ${features.length} features; the table below lists all exact values.`}>
          <line x1={x(0)} y1={8} x2={x(0)} y2={height - 22} stroke="#64748b" strokeWidth={1.5} />
          <text x={x(0)} y={height - 8} fontSize={10} textAnchor="middle" fill="#94a3b8">0</text>
          {shown.map((f, i) => {
            const yTop = 10 + i * (BAR_H + 6);
            const v = f.mean_importance ?? 0;
            const negative = v < 0;
            return (
              <g key={f.feature_name}>
                <text x={LABEL_W - 6} y={yTop + BAR_H / 2 + 3} fontSize={11} textAnchor="end" fill="#475569">
                  {f.feature_name.length > 16 ? `${f.feature_name.slice(0, 15)}…` : f.feature_name}
                </text>
                <rect
                  x={Math.min(x(0), x(v))}
                  y={yTop}
                  width={Math.max(1, Math.abs(x(v) - x(0)))}
                  height={BAR_H}
                  fill={negative ? "#f59e0b" : "#60a5fa"}
                  opacity={0.85}
                >
                  <title>{`${f.feature_name}: mean ${fmt(f.mean_importance, 6)} (rank ${fmt(f.rank)}), min ${fmt(f.min_importance, 6)}, max ${fmt(f.max_importance, 6)}${negative ? " — negative importance" : ""}`}</title>
                </rect>
                {f.min_importance !== null && f.max_importance !== null && f.min_importance !== f.max_importance && (
                  <line x1={x(f.min_importance)} y1={yTop + BAR_H / 2} x2={x(f.max_importance)} y2={yTop + BAR_H / 2}
                    stroke="#334155" strokeWidth={1.5} />
                )}
                <text x={x(Math.max(v, 0)) + 4} y={yTop + BAR_H / 2 + 3} fontSize={10} fill="#64748b">
                  {fmt(f.mean_importance, 4)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5" style={{ background: "#60a5fa" }} /> Positive importance (permutation worsened held-out score)</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5" style={{ background: "#f59e0b" }} /> Negative importance (shown honestly)</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-slate-600" /> Min–max spread across splits</span>
      </div>
      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-500">Full feature table (accessible alternative)</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-2 py-1">Rank</th>
                <th scope="col" className="px-2 py-1">Feature</th>
                <th scope="col" className="px-2 py-1 text-right">Mean</th>
                <th scope="col" className="px-2 py-1 text-right">Median</th>
                <th scope="col" className="px-2 py-1 text-right">Std</th>
                <th scope="col" className="px-2 py-1 text-right">Min</th>
                <th scope="col" className="px-2 py-1 text-right">Max</th>
                <th scope="col" className="px-2 py-1 text-right">Sign+ frac</th>
                <th scope="col" className="px-2 py-1">Stability</th>
                <th scope="col" className="px-2 py-1 text-right">Splits</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f) => (
                <tr key={f.feature_name} className="border-b border-slate-50 font-mono last:border-0">
                  <td className="px-2 py-1">{fmt(f.rank)}</td>
                  <td className="px-2 py-1">{f.feature_name}</td>
                  <td className="px-2 py-1 text-right">{f.mean_importance === null ? "unavailable" : fmt(f.mean_importance, 6)}</td>
                  <td className="px-2 py-1 text-right">{fmt(f.median_importance, 6)}</td>
                  <td className="px-2 py-1 text-right">{fmt(f.std_importance, 6)}</td>
                  <td className="px-2 py-1 text-right">{fmt(f.min_importance, 6)}</td>
                  <td className="px-2 py-1 text-right">{fmt(f.max_importance, 6)}</td>
                  <td className="px-2 py-1 text-right">{fmt(f.positive_split_fraction)}</td>
                  <td className="px-2 py-1"><StabilityPill classification={f.stability_classification} /></td>
                  <td className="px-2 py-1 text-right">{f.valid_split_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="text-xs text-slate-400">
        Positive importance means permuting the feature worsened the held-out metric under this run’s
        method — it is not causality, profitability, or a reason to keep or delete the feature.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stability view (rank matrix + pairwise summary)
// ---------------------------------------------------------------------------

function StabilityView({ run, splitRows, features }: {
  run: RunFull; splitRows: SplitResultRow[]; features: FeatureResult[];
}) {
  const summary = run.stability_summary ?? {};
  const splitIds = useMemo(
    () => Array.from(new Set(splitRows.map((r) => r.split_id))),
    [splitRows],
  );
  const rankOf = useMemo(() => {
    const map: Record<string, Record<string, number | null>> = {};
    for (const r of splitRows) {
      (map[r.feature_name] ??= {})[r.split_id] = r.rank;
    }
    return map;
  }, [splitRows]);

  if (!splitRows.length) return <p className="text-sm text-slate-400">No split-level results recorded.</p>;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Mean Spearman" value={fmt(summary.mean_spearman)} />
        <Stat label="Min Spearman" value={fmt(summary.min_spearman)} />
        <Stat label="Mean Kendall" value={fmt(summary.mean_kendall)} />
        <Stat label={`Top-${summary.top_k ?? "k"} overlap`} value={fmt(summary.mean_top_k_overlap)} />
      </div>
      {summary.truncated && summary.truncation_note && (
        <p className="text-xs text-amber-600">{summary.truncation_note}</p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-xs">
          <caption className="sr-only">Per-split rank of each feature (rank 1 = highest measured importance in that split)</caption>
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Feature</th>
              {splitIds.map((s) => <th key={s} scope="col" className="px-2 py-1 text-right">{s}</th>)}
              <th scope="col" className="px-2 py-1 text-right">Rank σ</th>
              <th scope="col" className="px-2 py-1">Stability</th>
            </tr>
          </thead>
          <tbody>
            {features.map((f) => (
              <tr key={f.feature_name} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{f.feature_name}</td>
                {splitIds.map((s) => {
                  const rank = rankOf[f.feature_name]?.[s];
                  return (
                    <td key={s} className="px-2 py-1 text-right">
                      {rank === null || rank === undefined ? "—" : fmt(rank)}
                    </td>
                  );
                })}
                <td className="px-2 py-1 text-right">{fmt(f.rank_std)}</td>
                <td className="px-2 py-1"><StabilityPill classification={f.stability_classification} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(summary.pairs?.length ?? 0) > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-slate-500">
            Pairwise split correlations ({summary.pairs!.length} pairs)
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[520px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Split A</th>
                  <th scope="col" className="px-2 py-1">Split B</th>
                  <th scope="col" className="px-2 py-1 text-right">Spearman</th>
                  <th scope="col" className="px-2 py-1 text-right">Kendall</th>
                  <th scope="col" className="px-2 py-1 text-right">Top-k overlap</th>
                </tr>
              </thead>
              <tbody>
                {summary.pairs!.map((p) => (
                  <tr key={`${p.split_a}|${p.split_b}`} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1">{p.split_a}</td>
                    <td className="px-2 py-1">{p.split_b}</td>
                    <td className="px-2 py-1 text-right">{p.spearman === null ? "unavailable" : fmt(p.spearman)}</td>
                    <td className="px-2 py-1 text-right">{p.kendall === null ? "unavailable" : fmt(p.kendall)}</td>
                    <td className="px-2 py-1 text-right">{fmt(p.top_k_overlap)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <p className="text-xs text-slate-400">
        Stability score formula: {summary.score_formula ?? "1 - min(1, rank_std / ((n_features - 1) / 2))"} —
        thresholds: stable ≥ {summary.thresholds?.stable ?? 0.75}, moderately stable ≥ {summary.thresholds?.moderately_stable ?? 0.5}.
        An unstable feature is a research observation, not automatically a bad feature.
      </p>
    </div>
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

// ---------------------------------------------------------------------------
// Correlation groups
// ---------------------------------------------------------------------------

function CorrelationView({ groups }: { groups: CorrelationGroup[] }) {
  if (!groups.length) {
    return <p className="text-sm text-slate-400">No feature pairs above the correlation threshold.</p>;
  }
  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.group_id} className="rounded-lg border border-slate-100 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium text-slate-800">
              {g.group_id} · {g.features.join(", ")}
            </span>
            <span className="text-xs text-slate-500">
              max |r| = {fmt(g.max_abs_correlation)} · combined mean importance {fmt(g.combined_mean_importance, 6)}
            </span>
          </div>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[480px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Feature A</th>
                  <th scope="col" className="px-2 py-1">Feature B</th>
                  <th scope="col" className="px-2 py-1 text-right">Correlation</th>
                  <th scope="col" className="px-2 py-1 text-right">Sign</th>
                </tr>
              </thead>
              <tbody>
                {g.pairs.map((p) => (
                  <tr key={`${p.feature_a}|${p.feature_b}`} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1">{p.feature_a}</td>
                    <td className="px-2 py-1">{p.feature_b}</td>
                    <td className="px-2 py-1 text-right">{fmt(p.correlation)}</td>
                    <td className="px-2 py-1 text-right">{p.sign > 0 ? "+" : "−"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      <p className="text-xs text-slate-400">
        Correlated features can split or mask importance between them — the group is shown so the
        combined view can be read; nothing is removed automatically, and correlation is not causation.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drift views
// ---------------------------------------------------------------------------

function DriftView({ rows, context, kind, importanceMeta }: {
  rows: DriftRow[]; context: RunFull["drift_context"]; kind: "distribution" | "importance";
  importanceMeta?: Record<string, unknown>;
}) {
  if (!rows.length) {
    return (
      <p className="text-sm text-slate-400">
        {kind === "importance" && importanceMeta?.reason
          ? String(importanceMeta.reason)
          : "No drift diagnostics recorded."}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {kind === "distribution" && context?.reference_label && (
        <p className="text-xs text-slate-500">
          Reference: <span className="font-medium">{context.reference_label}</span> ({context.reference_count} samples) ·
          Comparison: <span className="font-medium">{context.comparison_label}</span> ({context.comparison_count} samples)
        </p>
      )}
      {kind === "importance" && (
        <p className="text-xs text-slate-500">
          Earlier splits: {String((importanceMeta?.early_splits as string[] | undefined)?.join(", ") ?? "—")} ·
          Later splits: {String((importanceMeta?.late_splits as string[] | undefined)?.join(", ") ?? "—")}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Feature</th>
              <th scope="col" className="px-2 py-1">Classification</th>
              {kind === "distribution" ? (
                <>
                  <th scope="col" className="px-2 py-1 text-right">PSI</th>
                  <th scope="col" className="px-2 py-1 text-right">KS</th>
                  <th scope="col" className="px-2 py-1 text-right">Mean Δ</th>
                  <th scope="col" className="px-2 py-1 text-right">Std ratio</th>
                  <th scope="col" className="px-2 py-1 text-right">Out-of-range</th>
                </>
              ) : (
                <>
                  <th scope="col" className="px-2 py-1 text-right">Early mean</th>
                  <th scope="col" className="px-2 py-1 text-right">Late mean</th>
                  <th scope="col" className="px-2 py-1 text-right">Δ</th>
                  <th scope="col" className="px-2 py-1 text-right">Rank change</th>
                  <th scope="col" className="px-2 py-1">Direction</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = r.detail as Record<string, unknown>;
              return (
                <tr key={r.feature_name} className="border-b border-slate-50 font-mono last:border-0">
                  <td className="px-2 py-1">{r.feature_name}</td>
                  <td className="px-2 py-1"><DriftPill classification={r.classification} /></td>
                  {kind === "distribution" ? (
                    <>
                      <td className="px-2 py-1 text-right">{r.psi === null ? "unavailable" : fmt(r.psi)}</td>
                      <td className="px-2 py-1 text-right">{r.ks_statistic === null ? "unavailable" : fmt(r.ks_statistic)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.mean_difference as number | null)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.std_ratio as number | null)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.out_of_range_fraction as number | null)}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-2 py-1 text-right">{fmt(d.early_mean_importance as number | null, 6)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.late_mean_importance as number | null, 6)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.difference as number | null, 6)}</td>
                      <td className="px-2 py-1 text-right">{fmt(d.rank_change as number | null)}</td>
                      <td className="px-2 py-1">{String(d.direction ?? "—")}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        {kind === "distribution"
          ? "Drift classifications use documented PSI thresholds — drift describes a data change, it does not prove model failure and carries no financial interpretation."
          : "Importance drift compares the earlier and later halves of the valid splits — wording is descriptive (increased / decreased / sign changed), never a quality judgement."}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// References + split table
// ---------------------------------------------------------------------------

function ReferencesView({ references }: { references: RunFull["references"] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {references.coefficients && (
        <div>
          <h4 className="text-sm font-semibold text-slate-700">
            Standardized coefficients ({references.coefficients.fitted_splits} split fit{references.coefficients.fitted_splits === 1 ? "" : "s"})
          </h4>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[420px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Feature</th>
                  <th scope="col" className="px-2 py-1 text-right">Mean coef</th>
                  <th scope="col" className="px-2 py-1 text-right">Mean |coef|</th>
                  <th scope="col" className="px-2 py-1 text-right">Sign</th>
                </tr>
              </thead>
              <tbody>
                {references.coefficients.rows.map((r) => (
                  <tr key={r.feature_name} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1">{r.feature_name}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.mean_coefficient, 6)}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.mean_abs_coefficient, 6)}</td>
                    <td className="px-2 py-1 text-right">{r.sign > 0 ? "+" : r.sign < 0 ? "−" : "0"}{!r.sign_consistent && " (varies)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-2 list-disc pl-5 text-xs text-amber-700">
            {references.coefficients.caveats.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
      {references.native_impurity && (
        <div>
          <h4 className="text-sm font-semibold text-slate-700">
            Model-native impurity importance ({references.native_impurity.fitted_splits} split fit{references.native_impurity.fitted_splits === 1 ? "" : "s"})
          </h4>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[320px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Feature</th>
                  <th scope="col" className="px-2 py-1 text-right">Mean native importance</th>
                </tr>
              </thead>
              <tbody>
                {references.native_impurity.rows.map((r) => (
                  <tr key={r.feature_name} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1">{r.feature_name}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.mean_native_importance, 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-2 list-disc pl-5 text-xs text-amber-700">
            {references.native_impurity.caveats.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function SplitTable({ run, rows }: { run: RunFull; rows: SplitResultRow[] }) {
  if (!run.splits.length) return <p className="text-sm text-slate-400">No splits recorded.</p>;
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-xs">
          <caption className="sr-only">Split status and baseline scores</caption>
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Split</th>
              <th scope="col" className="px-2 py-1">Status</th>
              <th scope="col" className="px-2 py-1 text-right">Train n</th>
              <th scope="col" className="px-2 py-1 text-right">Eval n</th>
              <th scope="col" className="px-2 py-1 text-right">Baseline {run.metric}</th>
              <th scope="col" className="px-2 py-1">Fingerprint</th>
            </tr>
          </thead>
          <tbody>
            {run.splits.map((s) => (
              <tr key={s.split_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{s.split_id}</td>
                <td className="px-2 py-1">{s.status}{s.warning ? ` (${s.warning})` : ""}</td>
                <td className="px-2 py-1 text-right">{s.train_count ?? "—"}</td>
                <td className="px-2 py-1 text-right">{s.evaluated_count ?? "—"}</td>
                <td className="px-2 py-1 text-right">{fmt(s.baseline_score, 6)}</td>
                <td className="px-2 py-1">{s.split_fingerprint ? <CopyValue value={s.split_fingerprint} display={s.split_fingerprint.slice(0, 12)} /> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-slate-500">
            Per-split feature results ({rows.length} rows)
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Split</th>
                  <th scope="col" className="px-2 py-1">Feature</th>
                  <th scope="col" className="px-2 py-1 text-right">Mean imp</th>
                  <th scope="col" className="px-2 py-1 text-right">Std</th>
                  <th scope="col" className="px-2 py-1 text-right">Min</th>
                  <th scope="col" className="px-2 py-1 text-right">Max</th>
                  <th scope="col" className="px-2 py-1 text-right">+/− repeats</th>
                  <th scope="col" className="px-2 py-1 text-right">Rank</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.split_id}|${r.feature_name}`} className="border-b border-slate-50 last:border-0">
                    <td className="px-2 py-1">{r.split_id}</td>
                    <td className="px-2 py-1">{r.feature_name}</td>
                    <td className="px-2 py-1 text-right">{r.mean_importance === null ? "unavailable" : fmt(r.mean_importance, 6)}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.std_importance, 6)}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.min_importance, 6)}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.max_importance, 6)}</td>
                    <td className="px-2 py-1 text-right">{r.positive_repeats}/{r.negative_repeats}</td>
                    <td className="px-2 py-1 text-right">{fmt(r.rank)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
