"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type Aggregates,
  type Breakeven,
  type CapacityRow,
  type ObservationRow,
  type RegimeBlock,
  type RunFull,
  type SensitivityRow,
  COMPLETENESS_LABELS,
  INTEGRITY_LABELS,
  getCapacity,
  getObservations,
  getSensitivity,
  markBaseline,
} from "@/lib/costDiagnostics";
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
  onOpenRegime?: () => void;
}

const COMPONENTS = ["commission", "spread", "slippage", "impact"] as const;
const COMPONENT_LABELS: Record<string, string> = {
  commission: "Commission",
  spread: "Spread cost",
  slippage: "Slippage",
  impact: "Market impact",
};

export default function CostDiagnosticsDetail({
  run, onBack, onRefresh, onOpenValidation, onOpenDataset, onOpenExperiment,
  onOpenOverfitting, onOpenRegime,
}: Props) {
  const [observations, setObservations] =
    useState<{ items: ObservationRow[]; total: number; page: number; total_pages: number } | null>(null);
  const [obsPage, setObsPage] = useState(1);
  const [sensitivity, setSensitivity] = useState<SensitivityRow[]>([]);
  const [capacity, setCapacity] = useState<CapacityRow[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getObservations(run.id, { page: obsPage, page_size: 12 })
        .then((r) => !cancelled && setObservations(r)).catch(() => {});
      getSensitivity(run.id).then((r) => !cancelled && setSensitivity(r.items)).catch(() => {});
      getCapacity(run.id).then((r) => !cancelled && setCapacity(r.items)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status, obsPage]);

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

  const unit = valueUnit(run);

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
              {run.observation_type === "trade" ? "Trade-level" : "Period-level"} ·{" "}
              {run.observation_count} observation{run.observation_count === 1 ? "" : "s"} ·{" "}
              {run.candidate_count} candidate{run.candidate_count === 1 ? "" : "s"}
              {run.currency ? ` · results in ${run.currency}` : " · results in return fractions"} ·{" "}
              {run.unavailable_input_count} with missing cost inputs ·{" "}
              {run.participation_warning_count} participation warning{run.participation_warning_count === 1 ? "" : "s"}
            </p>
            {run.description && <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <IntegrityPill status={run.integrity_status} />
            <CompletenessPill status={run.completeness_status} />
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
          <FpRow label="Observation-universe fingerprint" value={run.universe_fingerprint} />
          <FpRow label="Cost-model fingerprint" value={run.cost_model_fingerprint} />
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
              A baseline is a comparison reference within its scope — never a sizing or execution recommendation.
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
        || run.overfitting_run_id || run.regime_run_id) && (
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
                  "Cost evaluation never changes its split memberships.",
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
                  "Stored PBO values are never reused or rewritten for net returns.",
                ]}
                fp={run.overfitting_universe_fp}
                action={onOpenOverfitting} actionLabel="Open in Overfitting Diagnostics"
              />
            )}
            {run.regime_run_id && (
              <LinkCard
                title={run.regime_run_name ?? `Regime run #${run.regime_run_id}`}
                lines={[
                  `Definition: ${run.regime_definition_id ?? "—"} · Integrity: ${run.regime_run_integrity ? (INTEGRITY_LABELS[run.regime_run_integrity] ?? run.regime_run_integrity) : "—"}`,
                  "Stored assignments are joined by timestamp — never recomputed.",
                ]}
                action={onOpenRegime} actionLabel="Open in Regime Diagnostics"
              />
            )}
            {run.experiment_id && (
              <LinkCard
                title={run.experiment_name ?? `Experiment #${run.experiment_id}`}
                lines={["Recorded in the Experiment Registry (module: transaction_cost_diagnostics)."]}
                action={onOpenExperiment} actionLabel="Open in Experiment Registry"
              />
            )}
          </div>
        </DetailSection>
      )}

      {run.status === "completed" && run.aggregates && (
        <>
          <DetailSection title="Gross-to-net waterfall">
            <Waterfall aggregates={run.aggregates} unit={unit} />
          </DetailSection>

          <DetailSection title="Cost composition">
            <Composition aggregates={run.aggregates} unit={unit} />
          </DetailSection>

          <DetailSection title="Aggregate diagnostics">
            <AggregatesView aggregates={run.aggregates} unit={unit} run={run} />
          </DetailSection>

          {run.breakeven && (
            <DetailSection title="Break-even diagnostics">
              <BreakevenView breakeven={run.breakeven} unit={unit} />
            </DetailSection>
          )}

          <DetailSection title="Per-observation reconciliation">
            <ObservationsTable
              data={observations} unit={unit}
              onPage={(p) => setObsPage(p)}
            />
          </DetailSection>

          {sensitivity.length > 0 && (
            <DetailSection title={`Cost-sensitivity scenarios (${sensitivity.length})`}>
              <SensitivityTable rows={sensitivity} unit={unit} />
            </DetailSection>
          )}

          {capacity.length > 0 && (
            <DetailSection title="Capacity scaling (estimated under configured assumptions)">
              <CapacityView rows={capacity} unit={unit} />
            </DetailSection>
          )}

          {run.regimes && (
            <DetailSection title="Costs by stored regime assignment">
              <RegimesView block={run.regimes} unit={unit} />
            </DetailSection>
          )}
        </>
      )}

      <DetailSection title="Configuration">
        <KeyValueTable data={run.configuration} empty="—" />
      </DetailSection>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Formatting — explicit units everywhere
// ---------------------------------------------------------------------------

type Unit = { kind: "money"; currency: string } | { kind: "return" };

function valueUnit(run: RunFull): Unit {
  return run.observation_type === "trade"
    ? { kind: "money", currency: run.currency ?? "USD" }
    : { kind: "return" };
}

function fmtValue(v: number | null | undefined, unit: Unit): string {
  if (v === null || v === undefined) return "unavailable";
  if (unit.kind === "money") {
    return `${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${unit.currency}`;
  }
  return `${(v * 100).toFixed(4)}% of capital`;
}

function fmtShare(v: number | null | undefined, dp = 1): string {
  if (v === null || v === undefined) return "unavailable";
  return `${(v * 100).toFixed(dp)}%`;
}

function fmtNum(v: number | null | undefined, dp = 4): string {
  if (v === null || v === undefined) return "unavailable";
  return v.toFixed(dp);
}

export function IntegrityPill({ status }: { status: string }) {
  const label = INTEGRITY_LABELS[status] ?? status;
  const cls =
    status === "supplied_realized" || status === "verified_causal_input"
      || status === "verified_from_dataset_lineage"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "declared"
        ? "border-sky-200 bg-sky-50 text-sky-700"
        : status === "full_sample_descriptive"
          ? "border-amber-200 bg-amber-50 text-amber-700"
          : status === "invalid"
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-slate-200 bg-slate-50 text-slate-500";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

export function CompletenessPill({ status }: { status: string }) {
  const label = COMPLETENESS_LABELS[status] ?? status;
  const cls =
    status === "complete"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "partial"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : status === "gross_only"
          ? "border-slate-300 bg-slate-100 text-slate-600"
          : "border-red-200 bg-red-50 text-red-700";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const cls =
    status === "completed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "failed" || status === "invalidated"
        ? "border-red-200 bg-red-50 text-red-700"
        : "border-slate-200 bg-slate-50 text-slate-500";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

function FpRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <dt className="w-56 shrink-0 text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="min-w-0">
        {value ? <CopyValue value={value} display={`${value.slice(0, 20)}…`} /> : <span className="text-slate-400">—</span>}
      </dd>
    </div>
  );
}

function LinkCard({ title, lines, fp, warning, action, actionLabel }: {
  title: string; lines: string[]; fp?: string | null; warning?: string;
  action?: () => void; actionLabel?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="truncate text-sm font-semibold text-slate-800" title={title}>{title}</div>
      {lines.map((l, i) => <p key={i} className="mt-1 text-xs text-slate-500">{l}</p>)}
      {fp && <p className="mt-1 truncate font-mono text-[10px] text-slate-400" title={fp}>{fp}</p>}
      {warning && <p className="mt-1 text-xs font-medium text-amber-700">{warning}</p>}
      {action && (
        <button type="button" onClick={action}
          className="mt-2 rounded-md border border-blue-200 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">
          {actionLabel}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Waterfall + composition
// ---------------------------------------------------------------------------

function Waterfall({ aggregates, unit }: { aggregates: Aggregates; unit: Unit }) {
  const rows: { label: string; value: number | null; kind: "gross" | "cost" | "net" }[] = [
    { label: "Gross result", value: aggregates.gross_total, kind: "gross" },
    ...COMPONENTS.map((c) => ({
      label: COMPONENT_LABELS[c],
      value: aggregates.component_totals[c],
      kind: "cost" as const,
    })),
    { label: "Net result", value: aggregates.net_total, kind: "net" },
  ];
  const maxAbs = Math.max(
    1e-12,
    ...rows.map((r) => (r.value === null ? 0 : Math.abs(r.value))),
  );
  return (
    <div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const width = r.value === null ? 0 : Math.min(100, (Math.abs(r.value) / maxAbs) * 100);
          const barCls =
            r.kind === "gross" ? "bg-slate-400"
              : r.kind === "net"
                ? (r.value !== null && r.value < 0 ? "bg-red-400" : "bg-emerald-500")
                : "bg-amber-400";
          return (
            <div key={r.label} className="flex items-center gap-2 text-sm">
              <span className="w-32 shrink-0 text-xs font-medium text-slate-600">{r.label}</span>
              <div className="h-4 min-w-0 flex-1 rounded bg-slate-100" role="presentation">
                {r.value !== null && (
                  <div className={`h-4 rounded ${barCls}`} style={{ width: `${width}%` }} />
                )}
              </div>
              <span className="w-44 shrink-0 text-right font-mono text-xs text-slate-700">
                {r.kind === "cost" && r.value !== null ? "− " : ""}{fmtValue(r.value, unit)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Net equals gross minus the sum of available components; an unavailable component is
        excluded and disclosed — it is never treated as zero.
      </p>
    </div>
  );
}

function Composition({ aggregates, unit }: { aggregates: Aggregates; unit: Unit }) {
  const total = aggregates.total_cost;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th scope="col" className="px-3 py-2">Component</th>
            <th scope="col" className="px-3 py-2 text-right">Estimated cost</th>
            <th scope="col" className="px-3 py-2 text-right">Share of total cost</th>
            <th scope="col" className="px-3 py-2 text-right">Unavailable obs.</th>
          </tr>
        </thead>
        <tbody>
          {COMPONENTS.map((c) => {
            const v = aggregates.component_totals[c];
            const share = v !== null && total !== null && total !== 0 ? v / total : null;
            return (
              <tr key={c} className="border-b border-slate-50 last:border-0">
                <td className="px-3 py-2 font-medium text-slate-700">{COMPONENT_LABELS[c]}</td>
                <td className="px-3 py-2 text-right font-mono text-xs">{fmtValue(v, unit)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs">{fmtShare(share)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs">
                  {aggregates.component_unavailable_counts[c] ?? 0}
                </td>
              </tr>
            );
          })}
          <tr className="bg-slate-50 font-semibold">
            <td className="px-3 py-2 text-slate-800">Total estimated cost</td>
            <td className="px-3 py-2 text-right font-mono text-xs">{fmtValue(total, unit)}</td>
            <td className="px-3 py-2 text-right font-mono text-xs">{total !== null ? "100.0%" : "unavailable"}</td>
            <td className="px-3 py-2 text-right font-mono text-xs">{aggregates.unavailable_cost_count}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aggregates + break-even
// ---------------------------------------------------------------------------

function AggregatesView({ aggregates, unit, run }: { aggregates: Aggregates; unit: Unit; run: RunFull }) {
  const s = aggregates;
  const rows: [string, string][] = [
    ["Observations", String(s.observation_count)],
    ["Gross total", fmtValue(s.gross_total, unit)],
    ["Total estimated cost", fmtValue(s.total_cost, unit)],
    ["Net total", fmtValue(s.net_total, unit)],
    ["Cost / |gross|", fmtShare(s.cost_fraction_of_gross_magnitude, 2)],
    ["Cost / traded notional", s.cost_fraction_of_traded_notional === null
      ? "unavailable"
      : `${(s.cost_fraction_of_traded_notional * 10000).toFixed(2)} bps`],
    ["Traded notional", s.total_traded_notional === null
      ? "unavailable"
      : `${s.total_traded_notional.toLocaleString("en-US", { maximumFractionDigits: 0 })}${run.currency ? ` ${run.currency}` : ""} (${s.notional_observation_count} obs.)`],
    ["Turnover total", s.total_turnover === null
      ? "unavailable" : `${s.total_turnover.toFixed(4)} × capital (${s.turnover_observation_count} obs.)`],
    ["Gross mean / median", `${fmtValue(s.gross_stats.mean, unit)} / ${fmtValue(s.gross_stats.median, unit)}`],
    ["Net mean / median", `${fmtValue(s.net_stats.mean, unit)} / ${fmtValue(s.net_stats.median, unit)}`],
    ["Gross std (ddof=1)", fmtValue(s.gross_stats.std, unit)],
    ["Net std (ddof=1)", fmtValue(s.net_stats.std, unit)],
    ["Gross Sharpe-like (per obs., not annualized)", fmtNum(s.gross_stats.sharpe_like)],
    ["Net Sharpe-like (per obs., not annualized)", fmtNum(s.net_stats.sharpe_like)],
    ["Gross-positive rate", fmtShare(s.gross_stats.positive_rate)],
    ["Net-positive rate", fmtShare(s.net_stats.positive_rate)],
    ["Gross-positive becoming net-nonpositive", String(s.gross_positive_net_nonpositive_count)],
    ["Observations with unavailable costs", String(s.unavailable_cost_count)],
    ["Partial observations", String(s.partial_result_count)],
    ["Gross-only observations", String(s.gross_only_count)],
  ];
  return (
    <div>
      <div className="grid gap-x-8 gap-y-1 text-sm md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3 border-b border-slate-50 py-1">
            <span className="text-xs font-medium text-slate-500">{k}</span>
            <span className="text-right font-mono text-xs text-slate-800">{v}</span>
          </div>
        ))}
      </div>
      {(s.gross_candidate_matrix_fingerprint || s.net_candidate_matrix_fingerprint) && (
        <div className="mt-3 space-y-1 text-xs text-slate-500">
          <p>Gross candidate-matrix fingerprint: <span className="font-mono">{s.gross_candidate_matrix_fingerprint?.slice(0, 20)}…</span></p>
          <p>Cost-adjusted candidate-matrix fingerprint: <span className="font-mono">{s.net_candidate_matrix_fingerprint?.slice(0, 20)}…</span></p>
          {s.note && <p className="text-slate-400">{s.note}</p>}
        </div>
      )}
    </div>
  );
}

function BreakevenView({ breakeven, unit }: { breakeven: Breakeven; unit: Unit }) {
  if (breakeven.status !== "available") {
    return (
      <p className="text-sm text-slate-500">
        Break-even is unavailable: {breakeven.reason ?? "gross result is non-positive."}
      </p>
    );
  }
  const comps = breakeven.component_breakeven_multipliers ?? {};
  return (
    <div className="space-y-2 text-sm">
      <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
        <KV k="Aggregate break-even cost" v={breakeven.aggregate_breakeven_bps_of_notional == null
          ? `unavailable${breakeven.bps_reason ? ` (${breakeven.bps_reason})` : ""}`
          : `${breakeven.aggregate_breakeven_bps_of_notional.toFixed(2)} bps of traded notional`} />
        <KV k="Mean break-even cost per observation" v={fmtValue(breakeven.mean_breakeven_cost_per_observation, unit)} />
        <KV k="Maximum cost multiplier before net ≤ 0" v={breakeven.max_cost_multiplier == null ? "unavailable" : `${breakeven.max_cost_multiplier.toFixed(3)}×`} />
        <KV k="Break-even impact coefficient" v={breakeven.breakeven_impact_coefficient == null ? "unavailable" : breakeven.breakeven_impact_coefficient.toFixed(4)} />
        {COMPONENTS.map((c) => {
          const entry = comps[c];
          const text = !entry ? "no base cost"
            : entry.multiplier == null ? `unavailable (${entry.reason ?? "—"})`
              : `${entry.multiplier.toFixed(3)}× its base cost`;
          return <KV key={c} k={`${COMPONENT_LABELS[c]} break-even multiplier`} v={text} />;
        })}
      </div>
      <p className="text-xs text-slate-400">{breakeven.note}</p>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-50 py-1">
      <span className="text-xs font-medium text-slate-500">{k}</span>
      <span className="text-right font-mono text-xs text-slate-800">{v}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Observations
// ---------------------------------------------------------------------------

function ObservationsTable({ data, unit, onPage }: {
  data: { items: ObservationRow[]; total: number; page: number; total_pages: number } | null;
  unit: Unit;
  onPage: (p: number) => void;
}) {
  if (!data) return <p className="text-sm text-slate-500">Loading observations…</p>;
  if (!data.items.length) return <p className="text-sm text-slate-500">No observation results.</p>;
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Observation</th>
              <th scope="col" className="px-2 py-2">Candidate</th>
              <th scope="col" className="px-2 py-2 text-right">Gross</th>
              <th scope="col" className="px-2 py-2 text-right">Commission</th>
              <th scope="col" className="px-2 py-2 text-right">Spread</th>
              <th scope="col" className="px-2 py-2 text-right">Slippage</th>
              <th scope="col" className="px-2 py-2 text-right">Impact</th>
              <th scope="col" className="px-2 py-2 text-right">Total cost</th>
              <th scope="col" className="px-2 py-2 text-right">Net</th>
              <th scope="col" className="px-2 py-2">Completeness</th>
              <th scope="col" className="px-2 py-2 text-right">Participation</th>
              <th scope="col" className="px-2 py-2">Missing</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((o) => (
              <tr key={o.observation_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1.5" title={o.timestamp}>{o.observation_id}</td>
                <td className="px-2 py-1.5">{o.candidate_id}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.gross_value, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.commission_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.spread_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.slippage_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.impact_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.total_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(o.net_value, unit)}</td>
                <td className="px-2 py-1.5"><CompletenessPill status={o.completeness} /></td>
                <td className="px-2 py-1.5 text-right">
                  {o.participation === null ? "—" : fmtShare(o.participation, 2)}
                  {o.participation_status === "above_configured_threshold" && (
                    <span className="ml-1 text-amber-600" title="above the configured participation threshold">⚠</span>
                  )}
                </td>
                <td className="px-2 py-1.5 text-[10px] text-slate-500">
                  {o.unavailable_components.length ? o.unavailable_components.join(", ") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>{data.total} observation{data.total === 1 ? "" : "s"} · page {data.page} of {data.total_pages} · values in {unit.kind === "money" ? unit.currency : "return fractions"}</span>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => onPage(data.page - 1)} disabled={data.page <= 1}
            className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">← Prev</button>
          <button type="button" onClick={() => onPage(data.page + 1)} disabled={data.page >= data.total_pages}
            className="rounded-md border border-slate-200 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">Next →</button>
        </div>
      </div>
    </div>
  );
}

function cellValue(v: number | null, unit: Unit): string {
  if (v === null) return "—";
  if (unit.kind === "money") return v.toFixed(2);
  return `${(v * 100).toFixed(4)}%`;
}

// ---------------------------------------------------------------------------
// Sensitivity + capacity + regimes
// ---------------------------------------------------------------------------

function SensitivityTable({ rows, unit }: { rows: SensitivityRow[]; unit: Unit }) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Scenario</th>
              <th scope="col" className="px-2 py-2 text-right">Commission ×</th>
              <th scope="col" className="px-2 py-2 text-right">Spread ×</th>
              <th scope="col" className="px-2 py-2 text-right">Slippage ×</th>
              <th scope="col" className="px-2 py-2 text-right">Impact ×</th>
              <th scope="col" className="px-2 py-2 text-right">Total cost</th>
              <th scope="col" className="px-2 py-2 text-right">Net result</th>
              <th scope="col" className="px-2 py-2 text-right">Net-positive rate</th>
              <th scope="col" className="px-2 py-2 text-right">Gross+ → net≤0</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.scenario_index}
                className={`border-b border-slate-50 font-mono last:border-0 ${r.is_base ? "bg-sky-50/60" : ""}`}>
                <td className="px-2 py-1.5">
                  #{r.scenario_index}
                  {r.is_base && <span className="ml-1.5 rounded border border-sky-200 bg-sky-50 px-1 text-[10px] font-medium text-sky-700">base scenario</span>}
                </td>
                <td className="px-2 py-1.5 text-right">{r.commission_multiplier.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right">{r.spread_multiplier.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right">{r.slippage_multiplier.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right">{r.impact_multiplier.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.total_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.net_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{r.net_positive_rate === null ? "—" : fmtShare(r.net_positive_rate)}</td>
                <td className="px-2 py-1.5 text-right">{r.gross_positive_net_nonpositive_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        The base scenario is highlighted for reference only; scenarios are deterministic assumption
        variations — none is selected, preferred, or labelled anything beyond its multipliers.
        Realized (supplied) slippage is a historical fact and is never scaled by a multiplier.
      </p>
    </div>
  );
}

function CapacityView({ rows, unit }: { rows: CapacityRow[]; unit: Unit }) {
  const parts = rows.map((r) => r.max_participation ?? 0);
  const maxPart = Math.max(0.0001, ...parts);
  const W = 560;
  const H = 120;
  const x = (i: number) => 40 + (i * (W - 60)) / Math.max(1, rows.length - 1);
  const y = (p: number) => H - 18 - (p / maxPart) * (H - 40);
  const hasCurve = rows.some((r) => r.max_participation !== null);
  return (
    <div>
      {hasCurve && (
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[640px]" role="img"
            aria-label="Maximum participation by notional scale">
            <line x1="40" y1={H - 18} x2={W - 20} y2={H - 18} stroke="#cbd5e1" strokeWidth="1" />
            <polyline
              fill="none" stroke="#0ea5e9" strokeWidth="2"
              points={rows.map((r, i) => `${x(i)},${y(r.max_participation ?? 0)}`).join(" ")}
            />
            {rows.map((r, i) => (
              <g key={r.scale}>
                <circle cx={x(i)} cy={y(r.max_participation ?? 0)} r="3" fill="#0ea5e9" />
                <text x={x(i)} y={H - 5} textAnchor="middle" fontSize="9" fill="#64748b">{r.scale}×</text>
                <text x={x(i)} y={y(r.max_participation ?? 0) - 6} textAnchor="middle" fontSize="8" fill="#334155">
                  {r.max_participation === null ? "n/a" : `${((r.max_participation ?? 0) * 100).toFixed(1)}%`}
                </text>
              </g>
            ))}
            <text x="40" y="12" fontSize="9" fill="#64748b">max participation (% of configured volume denominator) by scale</text>
          </svg>
        </div>
      )}
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[980px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Scale</th>
              <th scope="col" className="px-2 py-2 text-right">Traded notional</th>
              <th scope="col" className="px-2 py-2 text-right">Mean part.</th>
              <th scope="col" className="px-2 py-2 text-right">Max part.</th>
              <th scope="col" className="px-2 py-2 text-right">Above threshold</th>
              <th scope="col" className="px-2 py-2 text-right">Commission</th>
              <th scope="col" className="px-2 py-2 text-right">Impact</th>
              <th scope="col" className="px-2 py-2 text-right">Total cost</th>
              <th scope="col" className="px-2 py-2 text-right">Net result</th>
              <th scope="col" className="px-2 py-2 text-right">Missing liquidity</th>
              <th scope="col" className="px-2 py-2 text-right">Excluded</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.scale} className={`border-b border-slate-50 font-mono last:border-0 ${r.is_base ? "bg-sky-50/60" : ""}`}>
                <td className="px-2 py-1.5">
                  {r.scale}×
                  {r.is_base && <span className="ml-1.5 rounded border border-sky-200 bg-sky-50 px-1 text-[10px] font-medium text-sky-700">base</span>}
                </td>
                <td className="px-2 py-1.5 text-right">{r.traded_notional === null ? "—" : r.traded_notional.toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                <td className="px-2 py-1.5 text-right">{r.mean_participation === null ? "—" : fmtShare(r.mean_participation, 2)}</td>
                <td className="px-2 py-1.5 text-right">{r.max_participation === null ? "—" : fmtShare(r.max_participation, 2)}</td>
                <td className="px-2 py-1.5 text-right">{r.above_threshold_count > 0
                  ? <span className="text-amber-600">{r.above_threshold_count} ⚠</span> : "0"}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.commission_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.impact_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.total_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.net_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{r.unavailable_liquidity_count}</td>
                <td className="px-2 py-1.5 text-right">{r.excluded_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Scaling multiplies observation size, never historical prices. Results are estimates under
        configured assumptions — no assumption is made that fills remain available at scale, and no
        scale is recommended or called executable capacity.
      </p>
    </div>
  );
}

function RegimesView({ block, unit }: { block: RegimeBlock; unit: Unit }) {
  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        Regime run “{block.regime_run_name}” · definition “{block.definition_id}” · {block.note}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Regime</th>
              <th scope="col" className="px-2 py-2 text-right">Observations</th>
              <th scope="col" className="px-2 py-2 text-right">Gross</th>
              <th scope="col" className="px-2 py-2 text-right">Total cost</th>
              <th scope="col" className="px-2 py-2 text-right">Net</th>
              <th scope="col" className="px-2 py-2 text-right">Spread</th>
              <th scope="col" className="px-2 py-2 text-right">Slippage</th>
              <th scope="col" className="px-2 py-2 text-right">Impact</th>
              <th scope="col" className="px-2 py-2 text-right">Mean part.</th>
              <th scope="col" className="px-2 py-2 text-right">Missing inputs</th>
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r) => (
              <tr key={r.regime_label} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1.5">
                  {r.regime_label}
                  {r.rare_regime_warning && (
                    <span className="ml-1.5 rounded border border-amber-200 bg-amber-50 px-1 text-[10px] font-medium text-amber-700">few obs.</span>
                  )}
                </td>
                <td className="px-2 py-1.5 text-right">{r.observation_count}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.gross_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.total_cost, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.net_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.spread_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.slippage_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{cellValue(r.impact_total, unit)}</td>
                <td className="px-2 py-1.5 text-right">{r.mean_participation === null ? "—" : fmtShare(r.mean_participation, 2)}</td>
                <td className="px-2 py-1.5 text-right">{r.incomplete_input_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Cost differences across regimes are measured under this configuration — no regime is
        cheapest, most profitable, or recommended.
      </p>
    </div>
  );
}
