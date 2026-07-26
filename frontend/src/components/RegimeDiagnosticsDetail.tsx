"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type ConditionalRow,
  type DefinitionRow,
  type RunFull,
  INTEGRITY_LABELS,
  getConditionalResults,
  getDefinitions,
  markBaseline,
} from "@/lib/regimeDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, KeyValueTable } from "@/components/ExperimentRegistryShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
  onOpenOverfitting?: () => void;
  onOpenFeatureDiagnostics?: () => void;
}

export default function RegimeDiagnosticsDetail({
  run, onBack, onRefresh, onOpenValidation, onOpenDataset, onOpenExperiment,
  onOpenOverfitting, onOpenFeatureDiagnostics,
}: Props) {
  const [definitions, setDefinitions] = useState<DefinitionRow[]>([]);
  const [conditional, setConditional] = useState<ConditionalRow[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getDefinitions(run.id).then((r) => !cancelled && setDefinitions(r.items)).catch(() => {});
      getConditionalResults(run.id).then((r) => !cancelled && setConditional(r.items)).catch(() => {});
    } else {
      getDefinitions(run.id).then((r) => !cancelled && setDefinitions(r.items)).catch(() => {});
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

  const validDefinitions = definitions.filter((d) => d.status === "ok");

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
              {run.candidate_count} candidate{run.candidate_count === 1 ? "" : "s"} ·{" "}
              {run.period_count} {run.frequency} periods · {run.regime_definition_count} definitions ·{" "}
              {run.observed_regime_count} observed regimes · {run.invalid_definition_count} invalid ·{" "}
              {run.low_coverage_warning_count} low-coverage warning{run.low_coverage_warning_count === 1 ? "" : "s"}
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
        {run.integrity_status === "full_sample_descriptive" && run.status === "completed" && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800">
            ⚠ At least one regime definition fitted thresholds on the full sample — descriptive only,
            not leakage-safe, and never labelled verified.
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
              A baseline is a comparison reference within its scope — never a regime or strategy selection.
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
      {(run.validation_run_id || run.dataset_version_id || run.experiment_id
        || run.overfitting_run_id || run.feature_diagnostics_run_id) && (
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
                  "Training-only thresholds use its exact recorded memberships.",
                ]}
                fp={run.validation_config_fp}
                action={onOpenValidation} actionLabel="Open in Model Validation Lab"
              />
            )}
            {run.overfitting_run_id && (
              <LinkCard
                title={run.overfitting_name ?? `Overfitting run #${run.overfitting_run_id}`}
                lines={[
                  `PBO: ${run.overfitting_pbo === null ? "—" : run.overfitting_pbo?.toFixed(3)} · PSR: ${run.overfitting_psr === null ? "—" : run.overfitting_psr?.toFixed(3)} · DSR: ${run.overfitting_dsr === null ? "—" : run.overfitting_dsr?.toFixed(3)}`,
                ]}
                fp={run.overfitting_universe_fp}
                action={onOpenOverfitting} actionLabel="Open in Overfitting Diagnostics"
              />
            )}
            {run.feature_diagnostics_run_id && (
              <LinkCard
                title={run.feature_run_name ?? `Feature run #${run.feature_diagnostics_run_id}`}
                lines={[`Integrity: ${run.feature_run_integrity ?? "—"}`]}
                action={onOpenFeatureDiagnostics} actionLabel="Open in Feature Diagnostics"
              />
            )}
            {run.experiment_id && (
              <LinkCard
                title={run.experiment_name ?? `Experiment #${run.experiment_id}`}
                lines={["Recorded in the Experiment Registry (module: regime_diagnostics)."]}
                action={onOpenExperiment} actionLabel="Open in Experiment Registry"
              />
            )}
          </div>
        </DetailSection>
      )}

      {definitions.length > 0 && (
        <DetailSection title={`Regime definitions (${definitions.length})`}>
          <DefinitionsTable definitions={definitions} />
        </DetailSection>
      )}

      {run.status === "completed" && (
        <>
          <DetailSection title="Regime timeline (effective labels)">
            <RegimeTimeline definitions={validDefinitions} periodCount={run.period_count}
              timestamps={run.timestamps} />
          </DetailSection>

          <DetailSection title="Coverage">
            <CoverageView coverage={run.coverage} />
          </DetailSection>

          <DetailSection title="Conditional performance (candidate × regime)">
            <ConditionalView conditional={conditional} definitions={validDefinitions} />
          </DetailSection>

          <DetailSection title="Robustness across regimes">
            <RobustnessView robustness={run.robustness} />
          </DetailSection>

          <DetailSection title="Rank stability across regimes">
            <RankStabilityView rankStability={run.rank_stability} />
          </DetailSection>

          <DetailSection title="Concentration">
            <ConcentrationView concentration={run.concentration} />
          </DetailSection>

          <DetailSection title="Regime transitions">
            <TransitionsView definitions={validDefinitions} />
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
    ok: "border-emerald-200 bg-emerald-50 text-emerald-700",
    invalid: "border-red-200 bg-red-50 text-red-700",
  };
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.pending}`}>{status}</span>;
}

export function IntegrityPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified_from_validation_split: "border-emerald-200 bg-emerald-50 text-emerald-700",
    verified_causal_rule: "border-emerald-200 bg-emerald-50 text-emerald-700",
    declared: "border-blue-200 bg-blue-50 text-blue-700",
    full_sample_descriptive: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
    invalid: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {INTEGRITY_LABELS[status] ?? status}
    </span>
  );
}

function ClassificationPill({ classification }: { classification: string }) {
  const styles: Record<string, string> = {
    broadly_consistent: "border-emerald-200 bg-emerald-50 text-emerald-700",
    mixed: "border-blue-200 bg-blue-50 text-blue-700",
    concentrated: "border-amber-200 bg-amber-50 text-amber-700",
    unstable: "border-red-200 bg-red-50 text-red-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${styles[classification] ?? styles.unknown}`}>
      {classification.replace(/_/g, " ")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Definitions table
// ---------------------------------------------------------------------------

function DefinitionsTable({ definitions }: { definitions: DefinitionRow[] }) {
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Definition</th>
              <th scope="col" className="px-2 py-1">Dimension</th>
              <th scope="col" className="px-2 py-1">Feature</th>
              <th scope="col" className="px-2 py-1 text-right">Lookback</th>
              <th scope="col" className="px-2 py-1 text-right">Lag</th>
              <th scope="col" className="px-2 py-1">Threshold mode</th>
              <th scope="col" className="px-2 py-1">Thresholds</th>
              <th scope="col" className="px-2 py-1">Integrity</th>
              <th scope="col" className="px-2 py-1 text-right">Labels</th>
              <th scope="col" className="px-2 py-1 text-right">Unavailable</th>
            </tr>
          </thead>
          <tbody>
            {definitions.map((d) => (
              <tr key={d.definition_id} className="border-b border-slate-50 last:border-0">
                <td className="max-w-[160px] truncate px-2 py-1 font-mono" title={d.name}>{d.definition_id}</td>
                <td className="px-2 py-1">{d.dimension}</td>
                <td className="px-2 py-1 font-mono">{d.source_feature ?? "—"}</td>
                <td className="px-2 py-1 text-right font-mono">{d.lookback ?? "—"}</td>
                <td className="px-2 py-1 text-right font-mono">{d.lag ?? "—"}</td>
                <td className="px-2 py-1">{d.threshold_mode ?? "—"}</td>
                <td className="max-w-[200px] truncate px-2 py-1 font-mono"
                  title={d.thresholds_used ? JSON.stringify(d.thresholds_used) : undefined}>
                  {d.thresholds_used ? JSON.stringify((d.thresholds_used as { values?: unknown }).values ?? d.thresholds_used) : "—"}
                </td>
                <td className="px-2 py-1"><IntegrityPill status={d.integrity_status} /></td>
                <td className="px-2 py-1 text-right font-mono">{d.distinct_label_count}</td>
                <td className="px-2 py-1 text-right font-mono">{d.unavailable_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {definitions.flatMap((d) => d.warnings).length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-xs text-amber-700">
          {definitions.flatMap((d) => d.warnings).map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}
      <p className="text-xs text-slate-400">
        Every label is effective with its declared lag over trailing windows only — a regime never
        sees its own period’s end-of-period value, and centered windows do not exist here.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Regime timeline (per-definition colored strip + legend + table alternative)
// ---------------------------------------------------------------------------

const STRIP_W = 560;
const STRIP_H = 20;
const PALETTE = ["#60a5fa", "#f59e0b", "#34d399", "#c084fc", "#f87171", "#22d3ee",
                 "#facc15", "#a3e635", "#fb923c", "#e879f9", "#94a3b8", "#4ade80"];

function RegimeTimeline({ definitions, periodCount, timestamps }: {
  definitions: DefinitionRow[]; periodCount: number; timestamps: string[];
}) {
  if (!definitions.length) return <p className="text-sm text-slate-400">No valid definitions.</p>;
  return (
    <div className="space-y-4">
      {definitions.map((d) => {
        const labels = Array.from(new Set(d.assignments.filter((a): a is string => a !== null))).sort();
        const colorOf = (label: string) => PALETTE[labels.indexOf(label) % PALETTE.length];
        const segments: { label: string | null; start: number; length: number }[] = [];
        let current: string | null = d.assignments[0] ?? null;
        let start = 0;
        for (let i = 1; i <= d.assignments.length; i += 1) {
          const lb = i < d.assignments.length ? d.assignments[i] : "__end__";
          if (lb !== current) {
            segments.push({ label: current, start, length: i - start });
            current = lb as string | null;
            start = i;
          }
        }
        return (
          <div key={d.definition_id} className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
              <span className="font-mono font-semibold">{d.definition_id}</span>
              {labels.map((lb) => (
                <span key={lb} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: colorOf(lb) }} />
                  {lb}
                </span>
              ))}
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm border border-slate-300 bg-transparent" />
                unavailable
              </span>
            </div>
            <div className="overflow-x-auto rounded border border-slate-100">
              <svg width={STRIP_W} height={STRIP_H} role="img"
                aria-label={`Effective ${d.definition_id} regime labels over ${periodCount} periods from ${timestamps[0] ?? ""} to ${timestamps[timestamps.length - 1] ?? ""}; the interval table below lists exact durations.`}>
                {segments.map((seg, i) => (
                  <rect key={i}
                    x={(seg.start / periodCount) * STRIP_W}
                    y={0}
                    width={Math.max(1, (seg.length / periodCount) * STRIP_W)}
                    height={STRIP_H}
                    fill={seg.label === null ? "transparent" : colorOf(seg.label)}
                    stroke={seg.label === null ? "#cbd5e1" : "none"}
                    strokeDasharray={seg.label === null ? "2 2" : undefined}>
                    <title>{`${seg.label ?? "unavailable"}: periods ${seg.start}–${seg.start + seg.length - 1}`}</title>
                  </rect>
                ))}
              </svg>
            </div>
            {d.interval_summary?.per_label && (
              <details>
                <summary className="cursor-pointer text-xs font-medium text-slate-500">
                  Interval table for {d.definition_id} (accessible alternative)
                </summary>
                <div className="mt-1 overflow-x-auto">
                  <table className="w-full min-w-[420px] text-xs font-mono">
                    <thead>
                      <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                        <th scope="col" className="px-2 py-1">Label</th>
                        <th scope="col" className="px-2 py-1 text-right">Intervals</th>
                        <th scope="col" className="px-2 py-1 text-right">Mean duration</th>
                        <th scope="col" className="px-2 py-1 text-right">Max duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(d.interval_summary.per_label).map(([lb, s]) => (
                        <tr key={lb} className="border-b border-slate-50 last:border-0">
                          <td className="px-2 py-1">{lb}</td>
                          <td className="px-2 py-1 text-right">{s.intervals}</td>
                          <td className="px-2 py-1 text-right">{fmt(s.mean_duration, 1)}</td>
                          <td className="px-2 py-1 text-right">{s.max_duration}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Coverage + conditional + robustness + ranks + concentration + transitions
// ---------------------------------------------------------------------------

function CoverageView({ coverage }: { coverage: RunFull["coverage"] }) {
  const entries = Object.entries(coverage ?? {});
  if (!entries.length) return <p className="text-sm text-slate-400">No coverage recorded.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-xs">
        <thead>
          <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
            <th scope="col" className="px-2 py-1">Definition</th>
            <th scope="col" className="px-2 py-1">Regime</th>
            <th scope="col" className="px-2 py-1 text-right">Observations</th>
            <th scope="col" className="px-2 py-1 text-right">Share</th>
          </tr>
        </thead>
        <tbody>
          {entries.flatMap(([defId, block]) => [
            ...Object.entries(block.per_label).map(([lb, v]) => (
              <tr key={`${defId}|${lb}`} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{defId}</td>
                <td className="px-2 py-1">{lb}</td>
                <td className="px-2 py-1 text-right">{v.observations}</td>
                <td className="px-2 py-1 text-right">{fmt(v.share)}</td>
              </tr>
            )),
            <tr key={`${defId}|__un`} className="border-b border-slate-50 font-mono text-slate-400 last:border-0">
              <td className="px-2 py-1">{defId}</td>
              <td className="px-2 py-1">(unassigned)</td>
              <td className="px-2 py-1 text-right">{block.unassigned_periods}</td>
              <td className="px-2 py-1 text-right">—</td>
            </tr>,
          ])}
        </tbody>
      </table>
    </div>
  );
}

function ConditionalView({ conditional, definitions }: {
  conditional: ConditionalRow[]; definitions: DefinitionRow[];
}) {
  const [defId, setDefId] = useState<string>("");
  const active = defId || definitions[0]?.definition_id || "";
  const rows = useMemo(
    () => conditional.filter((r) => r.definition_id === active),
    [conditional, active],
  );
  if (!conditional.length) return <p className="text-sm text-slate-400">No conditional results.</p>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="rd-def-select" className="text-xs font-medium text-slate-500">Definition</label>
        <select id="rd-def-select" value={active} onChange={(e) => setDefId(e.target.value)}
          className="ql-input px-2 py-1 text-xs">
          {definitions.map((d) => (
            <option key={d.definition_id} value={d.definition_id}>{d.definition_id}</option>
          ))}
        </select>
        <span className="text-xs text-slate-400">
          Observation counts stay prominent — a statistic never outranks its sample size.
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Candidate</th>
              <th scope="col" className="px-2 py-1">Regime</th>
              <th scope="col" className="px-2 py-1 text-right">n</th>
              <th scope="col" className="px-2 py-1 text-right">Coverage</th>
              <th scope="col" className="px-2 py-1 text-right">Mean</th>
              <th scope="col" className="px-2 py-1 text-right">Median</th>
              <th scope="col" className="px-2 py-1 text-right">Std</th>
              <th scope="col" className="px-2 py-1 text-right">Pos rate</th>
              <th scope="col" className="px-2 py-1 text-right">Cumulative</th>
              <th scope="col" className="px-2 py-1 text-right">Sharpe-like</th>
              <th scope="col" className="px-2 py-1">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.candidate_id}|${r.regime_label}`}
                className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{r.candidate_id}</td>
                <td className="px-2 py-1">{r.regime_label}</td>
                <td className="px-2 py-1 text-right font-semibold">{r.observation_count}</td>
                <td className="px-2 py-1 text-right">{fmt(r.coverage)}</td>
                <td className="px-2 py-1 text-right">{r.mean === null ? "unavailable" : fmt(r.mean, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.median, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.std, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.positive_rate)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.cumulative, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.sharpe_like)}</td>
                <td className="px-2 py-1">
                  {r.status === "low_sample"
                    ? <span className="rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700" title={r.note ?? undefined}>low sample</span>
                    : r.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RobustnessView({ robustness }: { robustness: RunFull["robustness"] }) {
  if (!robustness.length) return <p className="text-sm text-slate-400">No robustness diagnostics.</p>;
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Candidate</th>
              <th scope="col" className="px-2 py-1">Definition</th>
              <th scope="col" className="px-2 py-1 text-right">Defined regimes</th>
              <th scope="col" className="px-2 py-1 text-right">Sign consistency</th>
              <th scope="col" className="px-2 py-1 text-right">Dispersion</th>
              <th scope="col" className="px-2 py-1 text-right">Lowest mean</th>
              <th scope="col" className="px-2 py-1 text-right">Highest mean</th>
              <th scope="col" className="px-2 py-1 text-right">Largest share</th>
              <th scope="col" className="px-2 py-1">Classification</th>
            </tr>
          </thead>
          <tbody>
            {robustness.map((r) => (
              <tr key={`${r.candidate_id}|${r.definition_id}`}
                className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{r.candidate_id}</td>
                <td className="px-2 py-1">{r.definition_id}</td>
                <td className="px-2 py-1 text-right">{r.defined_regimes}/{r.observed_regimes}</td>
                <td className="px-2 py-1 text-right">{fmt(r.sign_consistency)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.dispersion, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.lowest_regime_mean, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.highest_regime_mean, 6)}</td>
                <td className="px-2 py-1 text-right">{fmt(r.largest_regime_share)}</td>
                <td className="px-2 py-1"><ClassificationPill classification={r.classification} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        Classifications describe broader or narrower measured consistency under this configuration —
        they are never robustness proof, and no candidate or regime is recommended.
      </p>
    </div>
  );
}

function RankStabilityView({ rankStability }: { rankStability: RunFull["rank_stability"] }) {
  const entries = Object.entries(rankStability ?? {});
  if (!entries.length) return <p className="text-sm text-slate-400">No rank diagnostics.</p>;
  return (
    <div className="space-y-4">
      {entries.map(([defId, block]) => (
        <div key={defId} className="space-y-1.5">
          <p className="text-xs font-semibold text-slate-600">
            {defId}
            {block.status !== "ok" && (
              <span className="ml-2 font-normal text-slate-400">— {block.reason ?? "unavailable"}</span>
            )}
          </p>
          {block.status === "ok" && block.ranks && (
            <>
              <p className="text-xs text-slate-500">
                {block.rank_convention} · mean Spearman {fmt(block.mean_spearman)} ·
                top-{block.top_k} overlap {fmt(block.mean_top_k_overlap)}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                      <th scope="col" className="px-2 py-1">Candidate</th>
                      {block.labels!.map((lb) => (
                        <th key={lb} scope="col" className="px-2 py-1 text-right">{lb}</th>
                      ))}
                      <th scope="col" className="px-2 py-1 text-right">Rank σ</th>
                      <th scope="col" className="px-2 py-1 text-right">Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(block.per_candidate ?? []).map((pc) => (
                      <tr key={pc.candidate_id} className="border-b border-slate-50 last:border-0">
                        <td className="px-2 py-1">{pc.candidate_id}</td>
                        {block.labels!.map((lb) => (
                          <td key={lb} className="px-2 py-1 text-right">
                            {fmt(block.ranks![lb]?.[pc.candidate_id])}
                          </td>
                        ))}
                        <td className="px-2 py-1 text-right">{fmt(pc.rank_std)}</td>
                        <td className="px-2 py-1 text-right">{fmt(pc.rank_range)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      ))}
      <p className="text-xs text-slate-400">
        Rank changes across regimes are measured observations — no winner is identified.
      </p>
    </div>
  );
}

function ConcentrationView({ concentration }: { concentration: RunFull["concentration"] }) {
  if (!concentration.length) return <p className="text-sm text-slate-400">No concentration diagnostics.</p>;
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[840px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-1">Candidate</th>
              <th scope="col" className="px-2 py-1">Definition</th>
              <th scope="col" className="px-2 py-1 text-right">Obs HHI</th>
              <th scope="col" className="px-2 py-1 text-right">Effective regimes</th>
              <th scope="col" className="px-2 py-1 text-right">Entropy</th>
              <th scope="col" className="px-2 py-1 text-right">Largest |share|</th>
              <th scope="col" className="px-2 py-1 text-right">Top-2 |share|</th>
              <th scope="col" className="px-2 py-1 text-right">Largest signed</th>
            </tr>
          </thead>
          <tbody>
            {concentration.map((c) => (
              <tr key={`${c.candidate_id}|${c.definition_id}`}
                className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1">{c.candidate_id}</td>
                <td className="px-2 py-1">{c.definition_id}</td>
                <td className="px-2 py-1 text-right">{fmt(c.observation_hhi)}</td>
                <td className="px-2 py-1 text-right">{fmt(c.effective_regime_count, 2)}</td>
                <td className="px-2 py-1 text-right">{fmt(c.entropy)}</td>
                <td className="px-2 py-1 text-right">{fmt(c.largest_abs_share)}</td>
                <td className="px-2 py-1 text-right">{fmt(c.top2_abs_share)}</td>
                <td className="px-2 py-1 text-right">
                  {c.largest_signed_share === null
                    ? <span title={c.signed_share_note ?? undefined}>unavailable</span>
                    : fmt(c.largest_signed_share)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        Concentration is a measured distribution of observations and outcomes — never proof of
        overfitting on its own.
      </p>
    </div>
  );
}

function TransitionsView({ definitions }: { definitions: DefinitionRow[] }) {
  const withTransitions = definitions.filter(
    (d) => (d.transitions?.transition_count ?? 0) > 0);
  if (!withTransitions.length) {
    return <p className="text-sm text-slate-400">No regime transitions detected.</p>;
  }
  return (
    <div className="space-y-4">
      {withTransitions.map((d) => (
        <div key={d.definition_id} className="space-y-1.5">
          <p className="text-xs font-semibold text-slate-600">
            {d.definition_id} — {d.transitions.transition_count} transition{d.transitions.transition_count === 1 ? "" : "s"}
            {d.transitions.truncated && (
              <span className="ml-2 font-normal text-amber-600">{d.transitions.truncation_note}</span>
            )}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-2 py-1">Timestamp</th>
                  <th scope="col" className="px-2 py-1">From → To</th>
                  <th scope="col" className="px-2 py-1">Candidate</th>
                  <th scope="col" className="px-2 py-1 text-right">Pre mean (n)</th>
                  <th scope="col" className="px-2 py-1 text-right">Post mean (n)</th>
                  <th scope="col" className="px-2 py-1 text-right">Measured difference</th>
                  <th scope="col" className="px-2 py-1">Notes</th>
                </tr>
              </thead>
              <tbody>
                {(d.transitions.transitions ?? []).slice(0, 12).flatMap((t) =>
                  t.candidates.map((c) => (
                    <tr key={`${t.transition_index}|${c.candidate_id}`}
                      className="border-b border-slate-50 last:border-0">
                      <td className="px-2 py-1">{t.timestamp.slice(0, 10)}</td>
                      <td className="px-2 py-1">{t.previous_regime} → {t.next_regime}</td>
                      <td className="px-2 py-1">{c.candidate_id}</td>
                      <td className="px-2 py-1 text-right">{fmt(c.pre_mean, 6)} ({c.pre_count})</td>
                      <td className="px-2 py-1 text-right">{fmt(c.post_mean, 6)} ({c.post_count})</td>
                      <td className="px-2 py-1 text-right">{fmt(c.difference, 6)}</td>
                      <td className="px-2 py-1 text-slate-400">
                        {c.status === "small_sample" ? "small sample" : ""}
                        {t.overlapping_window ? " overlapping window" : ""}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
          {(d.transitions.transitions ?? []).length > 12 && (
            <p className="text-xs text-slate-400">
              Showing the first 12 of {(d.transitions.transitions ?? []).length} recorded transitions.
            </p>
          )}
        </div>
      ))}
      <p className="text-xs text-slate-400">
        Differences are measured before/after statistics under the chosen window — never causal claims,
        and no significance test exists in v1.
      </p>
    </div>
  );
}
