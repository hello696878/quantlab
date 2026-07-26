"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type CandidateRow,
  type MultipleTestingRow,
  type RunFull,
  type SelectionEntry,
  type SplitRow,
  getCandidates,
  getMultipleTesting,
  getSplits,
  markBaseline,
} from "@/lib/overfittingDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, KeyValueTable } from "@/components/ExperimentRegistryShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
  onOpenFeatureDiagnostics?: () => void;
}

export default function OverfittingDiagnosticsDetail({
  run, onBack, onRefresh, onOpenValidation, onOpenDataset, onOpenExperiment,
  onOpenFeatureDiagnostics,
}: Props) {
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [splits, setSplits] = useState<{ items: SplitRow[]; total: number; page: number; total_pages: number } | null>(null);
  const [splitPage, setSplitPage] = useState(1);
  const [mt, setMt] = useState<{ alpha: number | null; items: MultipleTestingRow[] } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getCandidates(run.id).then((r) => !cancelled && setCandidates(r.items)).catch(() => {});
      getMultipleTesting(run.id).then((r) => !cancelled && setMt(r)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status]);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getSplits(run.id, splitPage).then((r) => !cancelled && setSplits(r)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status, splitPage]);

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

  const agg = run.pbo_aggregate ?? {};
  const sd = run.sharpe_diagnostics ?? {};

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
              Metric: {run.metric} · {run.candidate_count} candidates · {run.observation_count} observations ·{" "}
              S = {run.block_count} blocks · {run.combination_count} CSCV combinations ·{" "}
              {run.valid_split_count} valid / {run.invalid_split_count} invalid splits
            </p>
            {run.description && <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            {run.pbo_estimate !== null && (
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600">
                PBO {fmt(run.pbo_estimate)}
              </span>
            )}
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
        <dl className="mt-3 space-y-2 text-sm">
          <FpRow label="Universe fingerprint" value={run.universe_fingerprint} />
          <FpRow label="Configuration fingerprint" value={run.configuration_fingerprint} />
          <FpRow label="Result fingerprint" value={run.result_fingerprint} />
        </dl>
        {run.status === "completed" && !run.is_baseline && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" onClick={handleBaseline} disabled={busy}
              className="rounded-md border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
              {busy ? "Marking…" : "Mark as scope baseline"}
            </button>
            <span className="text-xs text-slate-400">
              A baseline is a comparison reference within its scope — never a strategy selection.
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
      {(run.validation_run_id || run.dataset_version_id || run.experiment_id || run.feature_diagnostics_run_id) && (
        <DetailSection title="Linked records">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {run.dataset_version_id && (
              <LinkCard
                title={`${run.dataset_name ?? "dataset"} · ${run.dataset_version_label ?? ""}`}
                lines={[`Provenance: ${run.dataset_provenance_status ?? "unknown"} · Quality: ${run.dataset_quality_status ?? "unknown"}`]}
                fp={run.dataset_manifest_fingerprint}
                warning={run.dataset_invalidated ? "⚠ This dataset version has been invalidated — review before reuse." : undefined}
                action={onOpenDataset} actionLabel="Open in Dataset Lineage"
              />
            )}
            {run.validation_run_id && (
              <LinkCard
                title={`Validation run #${run.validation_run_id}`}
                lines={[
                  `Method: ${run.validation_method ?? "—"} · Leakage-clean: ${run.validation_leakage_clean === true ? "yes" : run.validation_leakage_clean === false ? "no" : "—"}`,
                  `Splits: ${run.validation_valid_splits ?? "—"} valid / ${run.validation_invalid_splits ?? "—"} invalid`,
                  "PBO complements — it never replaces — split-level validation.",
                ]}
                fp={run.validation_config_fp}
                action={onOpenValidation} actionLabel="Open in Model Validation Lab"
              />
            )}
            {run.experiment_id && (
              <LinkCard
                title={run.experiment_name ?? `Experiment #${run.experiment_id}`}
                lines={["Recorded in the Experiment Registry (module: overfitting_diagnostics)."]}
                action={onOpenExperiment} actionLabel="Open in Experiment Registry"
              />
            )}
            {run.feature_diagnostics_run_id && (
              <LinkCard
                title={run.feature_run_name ?? `Feature run #${run.feature_diagnostics_run_id}`}
                lines={[`Integrity: ${run.feature_run_integrity ?? "—"}`]}
                action={onOpenFeatureDiagnostics} actionLabel="Open in Feature Diagnostics"
              />
            )}
          </div>
        </DetailSection>
      )}

      {run.status === "completed" && (
        <>
          <DetailSection title="PBO — Probability of Backtest Overfitting">
            <PboSummary run={run} />
            <LambdaHistogram splits={splits?.items ?? []} totalValid={run.valid_split_count}
              pbo={run.pbo_estimate} invalid={run.invalid_split_count} />
          </DetailSection>

          <DetailSection title="Candidate selection frequency (in-sample)">
            <SelectionTable selection={agg.selection ?? []} />
          </DetailSection>

          <DetailSection title={`CSCV splits — IS vs OOS degradation (${splits?.total ?? 0})`}>
            <SplitTable splits={splits} onPage={setSplitPage} metric={run.metric} />
          </DetailSection>

          <DetailSection title="Sharpe diagnostics — PSR, DSR, MinTRL">
            <SharpeView sd={sd} />
          </DetailSection>

          <DetailSection title={`Multiple-testing corrections (alpha = ${mt?.alpha ?? "—"})`}>
            <MultipleTestingView mt={mt} />
          </DetailSection>

          <DetailSection title="Candidate dependence">
            <DependenceView run={run} />
          </DetailSection>

          <DetailSection title={`Candidates (${candidates.length})`}>
            <CandidateTable candidates={candidates} />
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

function prob(v: number | null | undefined): string {
  if (v === null || v === undefined) return "unavailable";
  return v.toFixed(4);
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

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-100 p-2.5" title={hint}>
      <div className="text-lg font-bold text-slate-900">{value}</div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PBO summary + lambda histogram
// ---------------------------------------------------------------------------

function PboSummary({ run }: { run: RunFull }) {
  const agg = run.pbo_aggregate ?? {};
  const ls = agg.lambda_stats ?? null;
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Estimated PBO" value={prob(run.pbo_estimate)} />
        <Stat label="Valid splits" value={String(agg.valid_split_count ?? "—")} />
        <Stat label="Invalid splits" value={String(agg.invalid_split_count ?? 0)} />
        <Stat label="λ mean" value={fmt(ls?.mean)} />
        <Stat label="λ median" value={fmt(ls?.median)} />
        <Stat label="OOS loss fraction" value={fmt(agg.oos_loss_fraction)} hint={agg.oos_loss_note} />
      </div>
      <p className="text-xs text-slate-500">{agg.pbo_note}</p>
      <p className="text-xs text-slate-400">
        Rank convention: {agg.rank_convention} · {agg.lambda_zero_policy}.
        IS↔OOS correlation (selected candidate): Pearson {fmt(agg.is_oos_correlation?.pearson)} ·
        Spearman {fmt(agg.is_oos_correlation?.spearman)}.
        Ties: {agg.tie_in_sample_count ?? 0} in-sample, {agg.tie_out_of_sample_count ?? 0} out-of-sample.
      </p>
    </div>
  );
}

const HW = 520;
const HH = 220;
const HPAD = 36;

function LambdaHistogram({ splits, totalValid, pbo, invalid }: {
  splits: SplitRow[]; totalValid: number; pbo: number | null; invalid: number;
}) {
  const lambdas = useMemo(
    () => splits.filter((s) => s.status === "valid" && s.lambda !== null)
      .map((s) => s.lambda as number),
    [splits],
  );
  if (!lambdas.length) return <p className="text-sm text-slate-400">No valid splits to draw.</p>;
  const lo = Math.min(...lambdas, 0);
  const hi = Math.max(...lambdas, 0);
  const span = hi - lo || 1;
  const nBins = Math.min(15, Math.max(5, Math.ceil(Math.sqrt(lambdas.length))));
  const bins = new Array(nBins).fill(0);
  for (const v of lambdas) {
    const k = Math.min(nBins - 1, Math.floor(((v - lo) / span) * nBins));
    bins[k] += 1;
  }
  const maxBin = Math.max(...bins);
  const x = (v: number) => HPAD + ((v - lo) / span) * (HW - HPAD * 2);
  const barW = (HW - HPAD * 2) / nBins;
  return (
    <div className="mt-3 space-y-2">
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg width={HW} height={HH} role="img"
          aria-label={`Lambda distribution over ${lambdas.length} valid splits shown (of ${totalValid}); the split table lists exact values.`}>
          <line x1={HPAD} y1={HH - HPAD} x2={HW - HPAD} y2={HH - HPAD} stroke="#475569" />
          {bins.map((count, k) => {
            const height = maxBin ? (count / maxBin) * (HH - HPAD * 2) : 0;
            const binLo = lo + (k / nBins) * span;
            return (
              <rect key={k} x={HPAD + k * barW + 1} y={HH - HPAD - height}
                width={Math.max(1, barW - 2)} height={height}
                fill={binLo + span / nBins <= 0 ? "#f59e0b" : (binLo >= 0 ? "#60a5fa" : "#94a3b8")}
                opacity={0.85}>
                <title>{`λ ∈ [${(binLo).toFixed(2)}, ${(binLo + span / nBins).toFixed(2)}): ${count} split(s)`}</title>
              </rect>
            );
          })}
          <line x1={x(0)} y1={HPAD / 2} x2={x(0)} y2={HH - HPAD} stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={x(0)} y={HPAD / 2 - 2} fontSize={10} textAnchor="middle" fill="#dc2626">λ = 0</text>
          <text x={HW / 2} y={HH - 8} fontSize={10} textAnchor="middle" fill="#94a3b8">
            logit λ of the selected candidate’s relative OOS rank
          </text>
        </svg>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5" style={{ background: "#f59e0b" }} /> λ &lt; 0 (selected candidate in the bottom OOS half)</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5" style={{ background: "#60a5fa" }} /> λ &gt; 0</span>
        <span>Fraction below zero (PBO): {prob(pbo)} · invalid splits excluded: {invalid}</span>
      </div>
      {lambdas.length < totalValid && (
        <p className="text-xs text-amber-600">
          ⚠ Histogram drawn from the {lambdas.length} valid split(s) on the loaded page, not all{" "}
          {totalValid} — it redraws as you page the split table below. The PBO shown above is
          always computed over all {totalValid} valid splits.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Selection frequency + split table
// ---------------------------------------------------------------------------

function SelectionTable({ selection }: { selection: SelectionEntry[] }) {
  if (!selection.length) return <p className="text-sm text-slate-400">No selection data.</p>;
  const sorted = [...selection].sort((a, b) => b.selection_frequency - a.selection_frequency);
  const top = sorted[0];
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        Highest measured selection frequency: <span className="font-mono">{top.candidate_id}</span>{" "}
        ({fmt(top.selection_frequency)}) — a descriptive statistic of this configuration, not a winner
        and not deployment suitability.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Candidate</th>
              <th scope="col" className="px-2 py-1 text-right">Selected</th>
              <th scope="col" className="px-2 py-1 text-right">Frequency</th>
              <th scope="col" className="px-2 py-1 text-right">Mean IS rank</th>
              <th scope="col" className="px-2 py-1 text-right">Mean OOS rank</th>
              <th scope="col" className="px-2 py-1 text-right">Median OOS rank (sel.)</th>
              <th scope="col" className="px-2 py-1 text-right">Mean degradation (sel.)</th>
              <th scope="col" className="px-2 py-1 text-right">Below-median OOS</th>
              <th scope="col" className="px-2 py-1 text-right">Negative OOS</th>
              <th scope="col" className="px-2 py-1 text-right">Mean λ (sel.)</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.candidate_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{e.candidate_id}</td>
                <td className="px-2 py-1 text-right">{e.selected_count}</td>
                <td className="px-2 py-1 text-right">{fmt(e.selection_frequency)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.mean_is_rank, 2)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.mean_oos_rank, 2)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.median_oos_rank_when_selected, 2)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.mean_degradation_when_selected, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.below_median_oos_fraction)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.negative_oos_fraction)}</td>
                <td className="px-2 py-1 text-right">{fmt(e.mean_lambda_when_selected)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SplitTable({ splits, onPage, metric }: {
  splits: { items: SplitRow[]; total: number; page: number; total_pages: number } | null;
  onPage: (p: number) => void; metric: string;
}) {
  if (!splits || !splits.items.length) return <p className="text-sm text-slate-400">No splits recorded.</p>;
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Split</th>
              <th scope="col" className="px-2 py-1">IS blocks</th>
              <th scope="col" className="px-2 py-1">Selected</th>
              <th scope="col" className="px-2 py-1 text-right">IS {metric}</th>
              <th scope="col" className="px-2 py-1 text-right">OOS {metric}</th>
              <th scope="col" className="px-2 py-1 text-right">OOS rank</th>
              <th scope="col" className="px-2 py-1 text-right">ω</th>
              <th scope="col" className="px-2 py-1 text-right">λ</th>
              <th scope="col" className="px-2 py-1 text-right">Degradation</th>
              <th scope="col" className="px-2 py-1">Tie</th>
              <th scope="col" className="px-2 py-1">Status</th>
            </tr>
          </thead>
          <tbody>
            {splits.items.map((s) => (
              <tr key={s.split_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{s.split_id}</td>
                <td className="px-2 py-1">{s.is_block_ids.join(",")}</td>
                <td className="px-2 py-1">{s.selected_candidate_id ?? "—"}</td>
                <td className="px-2 py-1 text-right">{fmt(s.is_metric, 6)}</td>
                <td className="px-2 py-1 text-right">{s.oos_metric === null ? "unavailable" : fmt(s.oos_metric, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(s.oos_rank, 2)}{s.oos_defined_count ? ` / ${s.oos_defined_count}` : ""}</td>
                <td className="px-2 py-1 text-right">{fmt(s.relative_rank)}</td>
                <td className="px-2 py-1 text-right">{fmt(s.lambda)}</td>
                <td className="px-2 py-1 text-right">{fmt(s.degradation, 6)}</td>
                <td className="px-2 py-1">{s.tie_in_sample ? "IS" : ""}{s.tie_out_of_sample ? " OOS" : ""}</td>
                <td className="px-2 py-1">{s.status}{s.warning ? ` (${s.warning})` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>page {splits.page} of {splits.total_pages}</span>
        <div className="flex gap-2">
          <button type="button" disabled={splits.page <= 1} onClick={() => onPage(splits.page - 1)}
            className="rounded-md border border-slate-200 px-2.5 py-1 disabled:opacity-40">← Prev</button>
          <button type="button" disabled={splits.page >= splits.total_pages} onClick={() => onPage(splits.page + 1)}
            className="rounded-md border border-slate-200 px-2.5 py-1 disabled:opacity-40">Next →</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sharpe diagnostics
// ---------------------------------------------------------------------------

function SharpeView({ sd }: { sd: RunFull["sharpe_diagnostics"] }) {
  if (!sd || sd.focus_candidate_id === undefined) {
    return <p className="text-sm text-slate-400">No Sharpe diagnostics recorded.</p>;
  }
  return (
    <div className="space-y-3">
      {sd.focus_note && <p className="text-xs text-slate-500">{sd.focus_note}</p>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Focus candidate" value={sd.focus_candidate_id ?? "unavailable"} />
        <Stat label="Observed Sharpe" value={fmt(sd.observed_sharpe)} hint={sd.sharpe_convention} />
        <Stat label="Observations" value={String(sd.observations ?? "—")} />
        <Stat label="Skewness" value={fmt(sd.skewness)} hint={sd.skew_convention} />
        <Stat label="Kurtosis (non-excess)" value={fmt(sd.kurtosis)} hint={sd.kurtosis_convention} />
        <Stat label="Benchmark SR*" value={fmt(sd.benchmark_sharpe)} />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="PSR" value={prob(sd.psr?.psr)} />
        <Stat label="Trials (raw)" value={String(sd.trials_raw ?? "—")} />
        <Stat label="Trials (effective)" value={fmt(sd.trials_effective, 2)} hint={`policy: ${sd.trial_policy?.mode ?? "—"}`} />
        <Stat label="E[max SR] benchmark" value={fmt(sd.dsr?.expected_max_sharpe)} />
        <Stat label="DSR" value={prob(sd.dsr?.dsr)} />
        <Stat label="MinTRL" value={sd.min_track_record?.min_track_record === null || sd.min_track_record?.min_track_record === undefined
          ? "unavailable"
          : `${fmt(sd.min_track_record.min_track_record, 1)} obs${sd.min_track_record.approx_years ? ` (≈${fmt(sd.min_track_record.approx_years, 2)}y)` : ""}`} />
      </div>
      {sd.small_sample_warning && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
          ⚠ {sd.small_sample_warning}
        </p>
      )}
      {(sd.psr?.note || sd.dsr?.note || sd.min_track_record?.note) && (
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500">
          {sd.psr?.note && <li>PSR: {sd.psr.note}</li>}
          {sd.dsr?.note && <li>DSR: {sd.dsr.note}</li>}
          {sd.min_track_record?.note && <li>MinTRL: {sd.min_track_record.note}</li>}
        </ul>
      )}
      <p className="text-xs text-slate-400">
        Assumptions on display: {sd.sharpe_convention}; skewness — {sd.skew_convention}; kurtosis —{" "}
        {sd.kurtosis_convention}; confidence {fmt(sd.confidence)}; cross-trial Sharpe variance{" "}
        {fmt(sd.sharpe_variance, 6)}. PSR and DSR are research statistics under these assumptions —
        neither is the probability of future profit, and DSR is not proof against overfitting.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multiple testing + dependence + candidates
// ---------------------------------------------------------------------------

function ThresholdPill({ state }: { state: string }) {
  const styles: Record<string, string> = {
    below_threshold: "border-blue-200 bg-blue-50 text-blue-700",
    above_threshold: "border-slate-200 bg-slate-50 text-slate-500",
    unavailable: "border-slate-200 bg-slate-50 text-slate-400",
  };
  return (
    <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${styles[state] ?? styles.unavailable}`}>
      {state.replace(/_/g, " ")}
    </span>
  );
}

function MultipleTestingView({ mt }: { mt: { alpha: number | null; items: MultipleTestingRow[] } | null }) {
  const items = mt?.items ?? [];
  const withP = items.filter((r) => r.raw_p_value !== null);
  if (!withP.length) {
    return <p className="text-sm text-slate-400">No candidate supplied a nominal p-value.</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        Bonferroni and Holm control the family-wise error rate (FWER); Benjamini–Hochberg controls the
        false discovery rate (FDR) under its stated assumptions — BH does not control FWER. States are
        neutral threshold positions at the configured alpha — nothing is accepted, validated, or
        rejected automatically. m = {withP.length} candidates supplied a p-value.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Candidate</th>
              <th scope="col" className="px-2 py-1">Provenance</th>
              <th scope="col" className="px-2 py-1 text-right">Nominal p</th>
              <th scope="col" className="px-2 py-1 text-right">Bonferroni</th>
              <th scope="col" className="px-2 py-1 text-right">Holm</th>
              <th scope="col" className="px-2 py-1 text-right">BH (q)</th>
              <th scope="col" className="px-2 py-1">Raw</th>
              <th scope="col" className="px-2 py-1">Holm state</th>
              <th scope="col" className="px-2 py-1">BH state</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.candidate_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{r.candidate_id}</td>
                <td className="px-2 py-1">{r.provenance_status}</td>
                <td className="px-2 py-1 text-right">{r.raw_p_value === null ? "unavailable" : fmt(r.raw_p_value)}</td>
                <td className="px-2 py-1 text-right">{r.bonferroni === null ? "unavailable" : fmt(r.bonferroni)}</td>
                <td className="px-2 py-1 text-right">{r.holm === null ? "unavailable" : fmt(r.holm)}</td>
                <td className="px-2 py-1 text-right">{r.bh === null ? "unavailable" : fmt(r.bh)}</td>
                <td className="px-2 py-1"><ThresholdPill state={r.state_raw} /></td>
                <td className="px-2 py-1"><ThresholdPill state={r.state_holm} /></td>
                <td className="px-2 py-1"><ThresholdPill state={r.state_bh} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        A supplied p-value is recorded as “declared” provenance — it is never independently verified
        by this lab.
      </p>
    </div>
  );
}

function DependenceView({ run }: { run: RunFull }) {
  const dep = run.dependence ?? {};
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Mean |ρ|" value={fmt(dep.mean_abs_correlation)} />
        <Stat label="Median |ρ|" value={fmt(dep.median_abs_correlation)} />
        <Stat label="Effective trials (approx.)" value={fmt(dep.effective_trials_estimate, 2)} hint={dep.effective_trials_note} />
        <Stat label="Constant candidates" value={String(dep.constant_candidates?.length ?? 0)} />
      </div>
      {dep.effective_trials_note && (
        <p className="text-xs text-slate-500">{dep.effective_trials_note}.</p>
      )}
      {(dep.high_correlation_pairs?.length ?? 0) > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-2 py-1">Candidate A</th>
                <th scope="col" className="px-2 py-1">Candidate B</th>
                <th scope="col" className="px-2 py-1 text-right">Correlation (|ρ| ≥ {fmt(dep.threshold)})</th>
              </tr>
            </thead>
            <tbody>
              {dep.high_correlation_pairs!.map((p) => (
                <tr key={`${p.candidate_a}|${p.candidate_b}`} className="border-b border-slate-50 last:border-0">
                  <td className="px-2 py-1">{p.candidate_a}</td>
                  <td className="px-2 py-1">{p.candidate_b}</td>
                  <td className="px-2 py-1 text-right">{fmt(p.correlation)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(dep.clusters?.length ?? 0) > 0 && (
        <p className="text-xs text-slate-500">
          Clusters: {dep.clusters!.map((c) => `${c.cluster_id} {${c.candidates.join(", ")}}`).join(" · ")}
          {" — "}nothing is collapsed or deleted automatically.
        </p>
      )}
      {dep.constant_note && <p className="text-xs text-amber-600">{dep.constant_note}.</p>}
      <p className="text-xs text-slate-400">
        Correlated trials weaken independence assumptions in DSR and multiple testing — the effective
        trial count is an approximation, never exact, and correlated trials are never treated as
        independent.
      </p>
    </div>
  );
}

function CandidateTable({ candidates }: { candidates: CandidateRow[] }) {
  if (!candidates.length) return <p className="text-sm text-slate-400">No candidates recorded.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[880px] text-xs">
        <thead>
          <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
            <th scope="col" className="px-2 py-1">Candidate</th>
            <th scope="col" className="px-2 py-1 text-right">Sharpe (per period)</th>
            <th scope="col" className="px-2 py-1 text-right">PSR</th>
            <th scope="col" className="px-2 py-1 text-right">Mean return</th>
            <th scope="col" className="px-2 py-1 text-right">Cumulative</th>
            <th scope="col" className="px-2 py-1 text-right">Skew</th>
            <th scope="col" className="px-2 py-1 text-right">Kurtosis</th>
            <th scope="col" className="px-2 py-1 text-right">Sel. freq</th>
            <th scope="col" className="px-2 py-1 text-right">Mean OOS rank</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.candidate_id} className="border-b border-slate-50 font-mono last:border-0">
              <td className="max-w-[180px] truncate px-2 py-1" title={c.name}>{c.candidate_id}</td>
              <td className="px-2 py-1 text-right">
                {c.raw_sharpe === null
                  ? <span title={c.sharpe_note ?? undefined}>unavailable</span>
                  : fmt(c.raw_sharpe)}
              </td>
              <td className="px-2 py-1 text-right">{c.psr === null ? "unavailable" : fmt(c.psr)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.mean_return, 6)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.cumulative_return)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.skewness)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.kurtosis)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.selection_frequency)}</td>
              <td className="px-2 py-1 text-right">{fmt(c.mean_oos_rank, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
