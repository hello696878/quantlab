"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type BudgetBlock,
  type ConcentrationBlock,
  type ContributionRow,
  type CovarianceBlock,
  type RebalanceRow,
  type RegimeBlock,
  type RunFull,
  type SensitivityRow,
  type WeightRow,
  INTEGRITY_LABELS,
  METHOD_LABELS,
  getRebalances,
  getRiskContributions,
  getSensitivity,
  getWeights,
  markBaseline,
} from "@/lib/portfolioDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { CopyValue, DetailSection, KeyValueTable } from "@/components/ExperimentRegistryShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
  onOpenRegime?: () => void;
  onOpenCost?: () => void;
  onOpenOverfitting?: () => void;
}

export default function PortfolioDiagnosticsDetail({
  run, onBack, onRefresh, onOpenValidation, onOpenDataset, onOpenExperiment,
  onOpenRegime, onOpenCost, onOpenOverfitting,
}: Props) {
  const [weights, setWeights] = useState<WeightRow[]>([]);
  const [contributions, setContributions] = useState<ContributionRow[]>([]);
  const [rebalances, setRebalances] = useState<RebalanceRow[]>([]);
  const [sensitivity, setSensitivity] = useState<SensitivityRow[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (run.status === "completed") {
      getWeights(run.id).then((r) => !cancelled && setWeights(r.items)).catch(() => {});
      getRiskContributions(run.id)
        .then((r) => !cancelled && setContributions(r.items)).catch(() => {});
      getRebalances(run.id)
        .then((r) => !cancelled && setRebalances(r.items)).catch(() => {});
      getSensitivity(run.id)
        .then((r) => !cancelled && setSensitivity(r.items)).catch(() => {});
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

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
        ← Back to runs
      </button>

      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-900">{run.name}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {METHOD_LABELS[run.method] ?? run.method} · {run.covariance_method} covariance ·{" "}
              {run.asset_count} assets · {run.observation_count} observations ·{" "}
              {run.rebalance_count} rebalance{run.rebalance_count === 1 ? "" : "s"} ·{" "}
              {run.constraint_violation_count} constraint violation{run.constraint_violation_count === 1 ? "" : "s"}
            </p>
            {run.description && <p className="mt-2 max-w-3xl text-sm text-slate-600">{run.description}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <IntegrityPill status={run.integrity_status} />
            <SolverPill status={run.solver_status} />
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
          <FpRow label="Constraint fingerprint" value={run.constraint_fingerprint} />
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
              A baseline is a comparison reference within its scope — never an allocation recommendation.
            </span>
          </div>
        )}
      </div>

      {run.warnings.length > 0 && (
        <DetailSection title={`Warnings (${run.warnings.length})`}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700">
            {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </DetailSection>
      )}

      {(run.validation_run_id || run.dataset_version_id || run.experiment_id
        || run.regime_run_id || run.cost_diagnostic_run_id
        || run.overfitting_run_id) && (
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
                  "Training-only estimation uses its exact recorded memberships.",
                ]}
                fp={run.validation_config_fp}
                action={onOpenValidation} actionLabel="Open in Model Validation Lab"
              />
            )}
            {run.regime_run_id && (
              <LinkCard
                title={run.regime_run_name ?? `Regime run #${run.regime_run_id}`}
                lines={[
                  `Definition: ${run.regime_definition_id ?? "—"}`,
                  "Stored assignments are joined by timestamp — never recomputed.",
                ]}
                action={onOpenRegime} actionLabel="Open in Regime Diagnostics"
              />
            )}
            {run.cost_diagnostic_run_id && (
              <LinkCard
                title={run.cost_run_name ?? `Cost run #${run.cost_diagnostic_run_id}`}
                lines={["Stored cost assumptions drive descriptive rebalance-cost estimates; Phase 55 records are never mutated."]}
                fp={run.cost_model_fingerprint}
                action={onOpenCost} actionLabel="Open in Cost & Capacity"
              />
            )}
            {run.overfitting_run_id && (
              <LinkCard
                title={run.overfitting_name ?? `Overfitting run #${run.overfitting_run_id}`}
                lines={[`PBO: ${run.overfitting_pbo === null ? "—" : run.overfitting_pbo?.toFixed(3)} · candidate PBO values are never overwritten.`]}
                fp={run.overfitting_universe_fp}
                action={onOpenOverfitting} actionLabel="Open in Overfitting Diagnostics"
              />
            )}
            {run.experiment_id && (
              <LinkCard
                title={run.experiment_name ?? `Experiment #${run.experiment_id}`}
                lines={["Recorded in the Experiment Registry (module: portfolio_diagnostics)."]}
                action={onOpenExperiment} actionLabel="Open in Experiment Registry"
              />
            )}
          </div>
        </DetailSection>
      )}

      {run.status === "completed" && (
        <>
          {weights.length > 0 && (
            <DetailSection title="Weight allocation">
              <WeightsView rows={weights} />
            </DetailSection>
          )}
          {run.risk && contributions.length > 0 && (
            <DetailSection title="Risk contributions (target vs measured)">
              <ContributionsView rows={contributions} risk={run.risk}
                budget={run.budget} />
            </DetailSection>
          )}
          {run.concentration && (
            <DetailSection title="Concentration & diversification">
              <ConcentrationView c={run.concentration} />
            </DetailSection>
          )}
          {run.covariance && (
            <DetailSection title="Covariance & correlation">
              <CovarianceView cov={run.covariance}
                assetIds={run.universe.assets.map((a) => a.asset_id)} />
            </DetailSection>
          )}
          {rebalances.length > 0 && (
            <DetailSection title={`Rebalances & turnover (${rebalances.length})`}>
              <RebalancesView rows={rebalances} />
            </DetailSection>
          )}
          {sensitivity.length > 0 && (
            <DetailSection title={`Sensitivity scenarios (${sensitivity.length})`}>
              <SensitivityView rows={sensitivity} />
            </DetailSection>
          )}
          {run.regimes && (
            <DetailSection title="Portfolio characteristics by stored regime">
              <RegimesView block={run.regimes} />
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

const fmt = (v: number | null | undefined, dp = 4): string =>
  v === null || v === undefined ? "unavailable" : v.toFixed(dp);
const pct = (v: number | null | undefined, dp = 2): string =>
  v === null || v === undefined ? "unavailable" : `${(v * 100).toFixed(dp)}%`;

export function IntegrityPill({ status }: { status: string }) {
  const label = INTEGRITY_LABELS[status] ?? status;
  const cls =
    status.startsWith("verified") ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "declared" ? "border-sky-200 bg-sky-50 text-sky-700"
        : status === "full_sample_descriptive" ? "border-amber-200 bg-amber-50 text-amber-700"
          : status === "invalid" ? "border-red-200 bg-red-50 text-red-700"
            : "border-slate-200 bg-slate-50 text-slate-500";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

export function SolverPill({ status }: { status: string | null }) {
  if (!status) return null;
  const cls =
    status === "converged" || status === "closed_form"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "failed" ? "border-red-200 bg-red-50 text-red-700"
        : "border-amber-200 bg-amber-50 text-amber-700";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>solver: {status.replace(/_/g, " ")}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const cls =
    status === "completed" ? "border-emerald-200 bg-emerald-50 text-emerald-700"
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

function WeightsView({ rows }: { rows: WeightRow[] }) {
  const maxAbs = Math.max(1e-9, ...rows.map((r) => Math.abs(r.weight ?? 0)));
  return (
    <div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const w = r.weight ?? 0;
          const width = Math.min(100, (Math.abs(w) / maxAbs) * 100);
          return (
            <div key={r.asset_id} className="flex items-center gap-2 text-sm">
              <span className="w-28 shrink-0 truncate font-mono text-xs text-slate-600" title={r.asset_id}>{r.asset_id}</span>
              <div className="h-4 min-w-0 flex-1 rounded bg-slate-100">
                <div className={`h-4 rounded ${w < 0 ? "bg-red-400" : "bg-sky-500"}`}
                  style={{ width: `${width}%` }} />
              </div>
              <span className="w-40 shrink-0 text-right font-mono text-xs text-slate-700">
                {pct(r.weight)} of portfolio
              </span>
              <span className="w-32 shrink-0 text-right text-[10px] text-slate-400">
                bounds [{fmt(r.lower_bound, 2)}, {fmt(r.upper_bound, 2)}]
              </span>
              <span className={`w-16 shrink-0 text-right text-[10px] font-medium ${r.constraint_status === "ok" ? "text-emerald-600" : "text-red-600"}`}>
                {r.constraint_status}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Signed weights as fractions of the portfolio (1.00 = 100%); negative weights render red.
        Raw pre-normalization weights are retained in the export.
      </p>
    </div>
  );
}

function ContributionsView({ rows, risk, budget }: {
  rows: ContributionRow[]; risk: { volatility: number; identity_ok: boolean | null };
  budget: BudgetBlock | null;
}) {
  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        Portfolio volatility (per period, not annualized): <span className="font-mono">{fmt(risk.volatility, 6)}</span> ·
        ΣCCR = volatility and ΣPCR = 1 {risk.identity_ok ? "reconcile within tolerance" : "— identity check unavailable"} ·
        {budget?.max_abs_deviation !== null && budget?.max_abs_deviation !== undefined
          ? ` max budget deviation ${fmt(budget.max_abs_deviation, 4)}`
          : " no risk budgets configured"}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Asset</th>
              <th scope="col" className="px-2 py-2 text-right">Weight</th>
              <th scope="col" className="px-2 py-2 text-right">Marginal (MCR)</th>
              <th scope="col" className="px-2 py-2 text-right">Component (CCR)</th>
              <th scope="col" className="px-2 py-2 text-right">Measured PCR</th>
              <th scope="col" className="px-2 py-2 text-right">Target budget</th>
              <th scope="col" className="px-2 py-2 text-right">Signed diff</th>
              <th scope="col" className="px-2 py-2">State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.asset_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-2 py-1.5">{r.asset_id}</td>
                <td className="px-2 py-1.5 text-right">{pct(r.weight)}</td>
                <td className="px-2 py-1.5 text-right">{fmt(r.mcr, 6)}</td>
                <td className="px-2 py-1.5 text-right">{fmt(r.ccr, 6)}</td>
                <td className={`px-2 py-1.5 text-right ${r.pcr !== null && r.pcr < 0 ? "text-red-600" : ""}`}>{pct(r.pcr)}</td>
                <td className="px-2 py-1.5 text-right">{pct(r.target_budget)}</td>
                <td className="px-2 py-1.5 text-right">{r.signed_difference === null ? "—" : pct(r.signed_difference)}</td>
                <td className="px-2 py-1.5 text-[10px]">{r.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Negative contributions in long-short portfolios stay visible — never forced to zero.
        Low deviation is a measured property, not a quality claim.
      </p>
    </div>
  );
}

function ConcentrationView({ c }: { c: ConcentrationBlock }) {
  const rows: [string, string][] = [
    ["Weight HHI (|w| shares)", fmt(c.weight_hhi)],
    ["Effective number of positions", fmt(c.effective_positions, 2)],
    ["Maximum |weight|", pct(c.max_abs_weight)],
    ["Top-3 |weight| share", pct(c.top3_abs_weight_share)],
    ["Risk-contribution HHI", fmt(c.risk_contribution_hhi)],
    ["Effective risk contributors", fmt(c.effective_risk_contributors, 2)],
    ["Average pairwise correlation", fmt(c.avg_pairwise_correlation)],
    ["Median pairwise correlation", fmt(c.median_pairwise_correlation)],
    ["Maximum pairwise correlation", fmt(c.max_pairwise_correlation)],
    ["Diversification ratio (Σ|w|σ / σₚ)", fmt(c.diversification_ratio)],
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
      <p className="mt-2 text-xs text-slate-400">
        Descriptive measurements under this configuration — a higher diversification ratio never
        guarantees diversification, risk reduction, or safety.
      </p>
    </div>
  );
}

function corrBg(v: number): string {
  const a = Math.min(1, Math.abs(v)) * 0.55;
  return v >= 0 ? `rgba(14, 165, 233, ${a})` : `rgba(239, 68, 68, ${a})`;
}

function CovarianceView({ cov, assetIds }: { cov: CovarianceBlock; assetIds: string[] }) {
  const report = cov.report;
  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        Estimation window indices [{cov.window[0]}, {cov.window[1]}] ·
        PSD: {String(report.psd)} · min eigenvalue: {report.min_eigenvalue === null || report.min_eigenvalue === undefined ? "—" : Number(report.min_eigenvalue).toExponential(2)} ·
        condition number: {report.condition_number === null || report.condition_number === undefined ? "undefined" : Number(report.condition_number).toExponential(2)} ·
        repair: {cov.repair.repaired ? `eigenvalue floor ${cov.repair.floor}` : `${cov.repair.policy} (not applied)`}
      </p>
      {(report.warnings ?? []).map((w, i) => (
        <p key={i} className="mb-1 text-xs font-medium text-amber-700">⚠ {w}</p>
      ))}
      {cov.correlation ? (
        <div className="overflow-x-auto">
          <table className="text-[10px]">
            <thead>
              <tr>
                <th className="px-1.5 py-1" />
                {assetIds.map((a) => (
                  <th key={a} scope="col" className="px-1.5 py-1 text-left font-mono">{a}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cov.correlation.map((row, i) => (
                <tr key={assetIds[i]}>
                  <th scope="row" className="px-1.5 py-1 text-left font-mono">{assetIds[i]}</th>
                  {row.map((v, j) => (
                    <td key={j} className="px-1.5 py-1 text-right font-mono"
                      style={{ backgroundColor: corrBg(v) }}>
                      {v.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          Correlation unavailable (a zero-variance asset leaves it undefined).
        </p>
      )}
      <p className="mt-2 text-xs text-slate-400">
        Correlation values are printed in every cell — shading is a reading aid, never the only
        signal. Covariance entries are per-period (never annualized).
      </p>
    </div>
  );
}

function RebalancesView({ rows }: { rows: RebalanceRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-xs">
        <thead>
          <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
            <th scope="col" className="px-2 py-2">#</th>
            <th scope="col" className="px-2 py-2">Decision timestamp</th>
            <th scope="col" className="px-2 py-2 text-right">Window</th>
            <th scope="col" className="px-2 py-2 text-right">One-way turnover</th>
            <th scope="col" className="px-2 py-2">Solver</th>
            <th scope="col" className="px-2 py-2 text-right">Violations</th>
            <th scope="col" className="px-2 py-2 text-right">Est. cost (return)</th>
            <th scope="col" className="px-2 py-2 text-right">Est. cost (notional)</th>
            <th scope="col" className="px-2 py-2">Cost completeness</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.rebalance_id} className="border-b border-slate-50 font-mono last:border-0">
              <td className="px-2 py-1.5">{r.rebalance_id}</td>
              <td className="px-2 py-1.5">{r.decision_timestamp.slice(0, 10)}</td>
              <td className="px-2 py-1.5 text-right">
                {r.window_start === null ? "—" : `[${r.window_start}, ${r.window_end}]`}
              </td>
              <td className="px-2 py-1.5 text-right">{r.turnover === null ? "unavailable" : pct(r.turnover)}</td>
              <td className="px-2 py-1.5">{r.solver_status ?? "—"}{r.status === "failed" && r.reason ? ` (${r.reason.slice(0, 40)}…)` : ""}</td>
              <td className="px-2 py-1.5 text-right">
                {r.constraint_violation_count > 0
                  ? <span className="text-red-600">{r.constraint_violation_count}</span> : "0"}
              </td>
              <td className="px-2 py-1.5 text-right">
                {r.cost?.total_cost_return === null || r.cost?.total_cost_return === undefined
                  ? "—" : pct(r.cost.total_cost_return, 4)}
              </td>
              <td className="px-2 py-1.5 text-right">
                {r.cost?.total_cost_notional === null || r.cost?.total_cost_notional === undefined
                  ? "—" : r.cost.total_cost_notional.toFixed(2)}
              </td>
              <td className="px-2 py-1.5 text-[10px]">{r.cost?.completeness ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-400">
        One-way turnover = 0.5 × Σ|Δw|. Cost estimates are descriptive research calculations from
        the linked Phase 55 cost model; unavailable components stay unavailable — never zero.
      </p>
    </div>
  );
}

function SensitivityView({ rows }: { rows: SensitivityRow[] }) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Scenario</th>
              <th scope="col" className="px-2 py-2 text-right">Value</th>
              <th scope="col" className="px-2 py-2 text-right">Volatility</th>
              <th scope="col" className="px-2 py-2 text-right">Effective positions</th>
              <th scope="col" className="px-2 py-2 text-right">Max budget dev.</th>
              <th scope="col" className="px-2 py-2 text-right">Turnover</th>
              <th scope="col" className="px-2 py-2">Solver</th>
              <th scope="col" className="px-2 py-2 text-right">Violations</th>
              <th scope="col" className="px-2 py-2 text-right">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.scenario_index}
                className={`border-b border-slate-50 font-mono last:border-0 ${r.is_base ? "bg-sky-50/60" : ""}`}>
                <td className="px-2 py-1.5">
                  {r.dimension.replace(/_/g, " ")}
                  {r.is_base && <span className="ml-1.5 rounded border border-sky-200 bg-sky-50 px-1 text-[10px] font-medium text-sky-700">base scenario</span>}
                </td>
                <td className="px-2 py-1.5 text-right">{r.value === null ? "—" : r.value}</td>
                <td className="px-2 py-1.5 text-right">{fmt(r.portfolio_volatility, 6)}</td>
                <td className="px-2 py-1.5 text-right">{fmt(r.effective_positions, 2)}</td>
                <td className="px-2 py-1.5 text-right">{r.max_budget_deviation === null ? "—" : fmt(r.max_budget_deviation, 4)}</td>
                <td className="px-2 py-1.5 text-right">{r.turnover === null ? "—" : pct(r.turnover)}</td>
                <td className="px-2 py-1.5">{r.solver_status ?? "—"}</td>
                <td className="px-2 py-1.5 text-right">{r.constraint_violation_count}</td>
                <td className="px-2 py-1.5 text-right">{r.cost_return === null ? "—" : pct(r.cost_return, 4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Deterministic one-at-a-time assumption variations. The base row shows the final
        rebalance's actual turnover; variation rows show the shift from the base book. The base
        scenario is highlighted for reference only — no scenario is selected, preferred, or
        labelled optimal.
      </p>
    </div>
  );
}

function RegimesView({ block }: { block: RegimeBlock }) {
  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        Regime run “{block.regime_run_name}” · definition “{block.definition_id}” · {block.note}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-2 py-2">Regime</th>
              <th scope="col" className="px-2 py-2 text-right">Observations</th>
              <th scope="col" className="px-2 py-2 text-right">Mean return</th>
              <th scope="col" className="px-2 py-2 text-right">Return std</th>
              <th scope="col" className="px-2 py-2 text-right">Cumulative</th>
              <th scope="col" className="px-2 py-2 text-right">Rebalances</th>
              <th scope="col" className="px-2 py-2 text-right">Mean turnover</th>
              <th scope="col" className="px-2 py-2">Cost completeness</th>
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
                <td className="px-2 py-1.5 text-right">{pct(r.mean_return, 4)}</td>
                <td className="px-2 py-1.5 text-right">{r.return_std === null ? "—" : pct(r.return_std, 4)}</td>
                <td className="px-2 py-1.5 text-right">{pct(r.cumulative_return)}</td>
                <td className="px-2 py-1.5 text-right">{r.rebalance_count}</td>
                <td className="px-2 py-1.5 text-right">{r.mean_turnover === null ? "—" : pct(r.mean_turnover)}</td>
                <td className="px-2 py-1.5 text-[10px]">{r.cost_completeness ? r.cost_completeness.join(", ") : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Differences across regimes are measured under this configuration — no regime is preferred
        or recommended.
      </p>
    </div>
  );
}
