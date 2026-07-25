"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type AssetResultRow,
  type AttributionRow,
  type ConstraintResultRow,
  type EpisodeRow,
  type RiskResultRow,
  type RunFull,
  type SensitivityRow,
  SCENARIO_TYPE_LABELS,
  fmtPct,
  getAssetResults,
  getAttribution,
  getConstraintResults,
  getEpisodes,
  getRiskResults,
  getRun,
  getSensitivity,
  markBaseline,
  shortFp,
} from "@/lib/portfolioStress";
import { notifyBackendOffline, toast } from "@/lib/toast";
import ErrorState from "@/components/ui/ErrorState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { CopyValue } from "@/components/ExperimentRegistryShared";
import { CompletenessPill, IntegrityPill, StatusPill } from "@/components/PortfolioStressShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenPortfolio?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
  onOpenRegime?: () => void;
  onOpenCost?: () => void;
}

interface Children {
  assets: AssetResultRow[];
  risk: RiskResultRow[];
  constraints: ConstraintResultRow[];
  episodes: EpisodeRow[];
  attribution: AttributionRow[];
  sensitivity: SensitivityRow[];
}

export default function PortfolioStressDetail({
  run, onBack, onRefresh, onOpenPortfolio, onOpenDataset, onOpenExperiment,
  onOpenRegime, onOpenCost,
}: Props) {
  const [children, setChildren] = useState<Children | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getAssetResults(run.id), getRiskResults(run.id),
      getConstraintResults(run.id), getEpisodes(run.id),
      getAttribution(run.id), getSensitivity(run.id),
    ])
      .then(([a, r, c, e, at, s]) => {
        if (cancelled) return;
        setChildren({ assets: a.items, risk: r.items, constraints: c.items,
                      episodes: e.items, attribution: at.items,
                      sensitivity: s.items });
      })
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [run.id]);

  async function handleBaseline() {
    setMarking(true);
    try {
      const updated = await markBaseline(run.id);
      onRefresh(updated);
      toast.success("Marked as baseline", "This run is now its scope’s comparison reference.");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Couldn’t mark baseline", cls.message);
      try {
        onRefresh(await getRun(run.id));
      } catch {
        /* keep the stale view */
      }
    } finally {
      setMarking(false);
    }
  }

  const rec = run.reconciliation;
  const scenario = (run.configuration?.scenario ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-4" data-testid="portfolio-stress-detail">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" onClick={onBack}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
          ← Back to runs
        </button>
        <div className="flex flex-wrap items-center gap-2">
          {onOpenPortfolio && (
            <button type="button" onClick={onOpenPortfolio}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Portfolio lab →
            </button>
          )}
          {onOpenCost && run.cost_diagnostic_run_id && (
            <button type="button" onClick={onOpenCost}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Cost lab →
            </button>
          )}
          {onOpenRegime && run.regime_run_id && (
            <button type="button" onClick={onOpenRegime}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Regime lab →
            </button>
          )}
          {onOpenDataset && run.dataset_version_id && (
            <button type="button" onClick={onOpenDataset}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Dataset lineage →
            </button>
          )}
          {onOpenExperiment && run.experiment_id && (
            <button type="button" onClick={onOpenExperiment}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Experiment →
            </button>
          )}
          {run.status === "completed" && !run.is_baseline && (
            <button type="button" onClick={handleBaseline} disabled={marking}
              className="rounded-md border border-indigo-200 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
              {marking ? "Marking…" : "★ Mark baseline"}
            </button>
          )}
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-slate-900">{run.name}</h2>
            {run.description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{run.description}</p>}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusPill status={run.status} />
              <IntegrityPill status={run.integrity_status} />
              <CompletenessPill status={run.completeness_status} />
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {SCENARIO_TYPE_LABELS[run.scenario_type] ?? run.scenario_type}
              </span>
              {run.is_baseline && (
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">★ baseline</span>
              )}
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-slate-500">
            <dt>Portfolio run</dt>
            <dd className="font-medium text-slate-700">{run.portfolio_run_name ?? `#${run.portfolio_run_id}`}</dd>
            <dt>Rebalance</dt>
            <dd className="font-mono">{run.portfolio_rebalance_id ?? "—"}</dd>
            <dt>Scenario fp</dt>
            <dd><CopyValue value={run.scenario_fingerprint} display={shortFp(run.scenario_fingerprint)} /></dd>
            <dt>Config fp</dt>
            <dd><CopyValue value={run.configuration_fingerprint} display={shortFp(run.configuration_fingerprint)} /></dd>
            <dt>Result fp</dt>
            <dd>{run.result_fingerprint ? <CopyValue value={run.result_fingerprint} display={shortFp(run.result_fingerprint)} /> : "—"}</dd>
            <dt>Weights fp</dt>
            <dd>{run.baseline_weight_fingerprint ? <CopyValue value={run.baseline_weight_fingerprint} display={shortFp(run.baseline_weight_fingerprint)} /> : "—"}</dd>
          </dl>
        </div>
        {run.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">{run.error_message}</div>
        )}
        {run.warnings.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800" data-testid="stress-warnings">
            {run.warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
          </div>
        )}
      </div>

      {rec && (
        <div className="card p-4" data-testid="stress-reconciliation">
          <h3 className="text-sm font-semibold text-slate-700">Scenario reconciliation</h3>
          <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="Direct shock return" value={fmtPct(rec.direct_shock_return, 3)} />
            <Metric label="Stressed cost return" value={rec.stressed_cost_return === null ? "—" : fmtPct(rec.stressed_cost_return, 3)} />
            <Metric label="Net scenario return"
              value={rec.net_scenario_return === null ? "— (withheld)" : fmtPct(rec.net_scenario_return, 3)} emphasis />
            <Metric label="Scenario P&L" value={rec.scenario_pnl === null ? "— (no notional configured)" : rec.scenario_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
          </div>
          {rec.net_basis_note && (
            <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              {rec.net_basis_note}
            </p>
          )}
          {rec.cost_basis_note && (
            <p className="mt-2 text-xs text-slate-400">{rec.cost_basis_note}</p>
          )}
          {rec.stressed_cost_state && rec.stressed_cost_state !== "not_configured"
            && rec.stressed_cost_state !== "available" && (
            <p className="mt-2 text-xs text-amber-700">
              Stressed cost leg unavailable: {rec.stressed_cost_reason ?? "no applicable component"}
            </p>
          )}
          <p className="mt-2 text-xs text-slate-400">{rec.risk_effect_note}</p>
        </div>
      )}

      {error ? (
        <ErrorState title="Couldn’t load run details" message={classifyApiError(error).message} onRetry={() => window.location.reload()} />
      ) : !children ? (
        <SkeletonTable rows={6} cols={6} caption="Loading stress results…" />
      ) : (
        <>
          <ContributionSection assets={children.assets} drifted={run.drifted} />
          <RiskSection run={run} rows={children.risk} />
          {children.constraints.length > 0 && (
            <ConstraintSection rows={children.constraints} />
          )}
          {run.cost_stress && <CostSection run={run} />}
          <DrawdownSection run={run} episodes={children.episodes} attribution={children.attribution} />
          {children.sensitivity.length > 0 && (
            <SensitivitySection rows={children.sensitivity} />
          )}
          <ScenarioSection scenario={scenario} run={run} />
        </>
      )}
    </div>
  );
}

function Metric({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div>
      <div className={`font-mono ${emphasis ? "text-lg font-bold text-slate-900" : "text-base font-semibold text-slate-800"}`}>{value}</div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

function ContributionSection({ assets, drifted }: { assets: AssetResultRow[]; drifted: RunFull["drifted"] }) {
  const contributions = assets.filter((a) => a.contribution !== null);
  const maxAbs = Math.max(1e-12, ...contributions.map((a) => Math.abs(a.contribution as number)));
  const sorted = [...assets].sort((a, b) => (a.contribution ?? 0) - (b.contribution ?? 0));
  return (
    <div className="card p-4" data-testid="stress-contributions">
      <h3 className="text-sm font-semibold text-slate-700">Scenario contribution attribution</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        contribution_i = weight_i × shock_i (static linear approximation on the fixed stored book); measured under this scenario, not causal.
      </p>
      {assets.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="contribution-waterfall">
          {sorted.map((a) => {
            const c = a.contribution;
            if (c === null) {
              return (
                <div key={a.asset_id} className="flex items-center gap-2 text-xs">
                  <span className="w-24 truncate font-mono text-slate-600">{a.asset_id}</span>
                  <span className="text-slate-400">unavailable (no shock under the missing-shock policy)</span>
                </div>
              );
            }
            const width = (Math.abs(c) / maxAbs) * 50;
            return (
              <div key={a.asset_id} className="flex items-center gap-2 text-xs">
                <span className="w-24 truncate font-mono text-slate-600">{a.asset_id}</span>
                <div className="relative h-4 flex-1">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-slate-200" />
                  <div
                    className={`absolute inset-y-0 rounded-sm ${c < 0 ? "bg-red-400" : "bg-emerald-400"}`}
                    style={c < 0
                      ? { right: "50%", width: `${width}%` }
                      : { left: "50%", width: `${width}%` }}
                  />
                </div>
                <span className="w-20 text-right font-mono text-slate-700">{fmtPct(c, 3)}</span>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Asset</th>
              <th scope="col" className="px-3 py-2">Group</th>
              <th scope="col" className="px-3 py-2 text-right">Weight</th>
              <th scope="col" className="px-3 py-2 text-right">Shock</th>
              <th scope="col" className="px-3 py-2">Source</th>
              <th scope="col" className="px-3 py-2 text-right">Contribution</th>
              <th scope="col" className="px-3 py-2 text-right">|share|</th>
              <th scope="col" className="px-3 py-2 text-right">Drifted weight</th>
              <th scope="col" className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.asset_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{a.asset_id}</td>
                <td className="px-3 py-1.5">{a.group ?? "—"}</td>
                <td className="px-3 py-1.5 text-right">{a.weight === null ? "—" : a.weight.toFixed(4)}</td>
                <td className="px-3 py-1.5 text-right">{a.shock === null ? "—" : fmtPct(a.shock, 2)}</td>
                <td className="px-3 py-1.5">{a.shock_source?.replace(/_/g, " ") ?? "—"}</td>
                <td className="px-3 py-1.5 text-right">{a.contribution === null ? "—" : fmtPct(a.contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{a.abs_share === null ? "—" : fmtPct(a.abs_share, 1)}</td>
                <td className="px-3 py-1.5 text-right">{a.drifted_weight === null ? "—" : a.drifted_weight.toFixed(4)}</td>
                <td className="px-3 py-1.5">{a.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {drifted && !drifted.available && drifted.reason && (
        <p className="mt-2 text-xs text-amber-700">Drifted weights unavailable: {drifted.reason}</p>
      )}
      {drifted && drifted.available && drifted.cash_weight !== null && drifted.cash_weight > 0 && (
        <p className="mt-2 text-xs text-slate-500">Cash weight after drift: {fmtPct(drifted.cash_weight, 2)} (carried unshocked; no automatic rebalancing).</p>
      )}
    </div>
  );
}

function RiskSection({ run, rows }: { run: RunFull; rows: RiskResultRow[] }) {
  const rs = run.risk_summary;
  const cs = run.covariance_stress;
  const maxPcr = Math.max(1e-12, ...rows.flatMap((r) =>
    [Math.abs(r.baseline_pcr ?? 0), Math.abs(r.stressed_pcr ?? 0)]));
  return (
    <div className="card p-4" data-testid="stress-risk">
      <h3 className="text-sm font-semibold text-slate-700">Baseline vs stressed risk</h3>
      {rs && rs.available !== false ? (
        <>
          <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="Baseline volatility" value={rs.baseline_volatility === null ? "—" : rs.baseline_volatility.toFixed(6)} />
            <Metric label="Stressed volatility" value={rs.stressed_volatility === null ? "—" : rs.stressed_volatility.toFixed(6)} emphasis />
            <Metric label="Volatility change" value={rs.volatility_change === null ? "—" : rs.volatility_change.toFixed(6)} />
            <Metric label="Risk identities" value={`base ${rs.baseline_identity_ok === null ? "—" : rs.baseline_identity_ok ? "ok" : "off"} · stressed ${rs.stressed_identity_ok === null ? "—" : rs.stressed_identity_ok ? "ok" : "off"}`} />
          </div>
          <p className="mt-2 text-xs text-slate-400">{rs.note}</p>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500" data-testid="risk-unavailable-reason">
          Risk recomputation unavailable for this run
          {rs?.reason ? `: ${rs.reason}` : " (no usable stored baseline covariance for the selected rebalance)"}.
          {rs?.note ? ` ${rs.note}.` : ""}
        </p>
      )}
      {rs && rs.available !== false && rs.stressed_note && (
        <p className="mt-2 text-xs text-amber-700">Stressed contributions: {rs.stressed_note}</p>
      )}
      {cs && !cs.available && cs.reason && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800" data-testid="cov-stress-unavailable">
          Stressed covariance unavailable: {cs.reason}
        </div>
      )}
      {cs && cs.available && cs.repair?.repaired && (
        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800"
          data-testid="cov-stress-repaired">
          <p>
            The requested stressed covariance was not positive semidefinite and was repaired
            under the explicit {cs.repair.policy} policy (original and repaired eigenvalues recorded).
            The values below describe the <strong>repaired</strong> matrix actually used for risk.
          </p>
          {cs.requested_correlation && cs.stressed_correlation && (
            <p className="mt-1">
              Example off-diagonal correlation: requested{" "}
              <span className="font-mono">{cs.requested_correlation[0]?.[1]?.toFixed(4) ?? "—"}</span>{" "}
              → effective{" "}
              <span className="font-mono">{cs.stressed_correlation[0]?.[1]?.toFixed(4) ?? "—"}</span>.
            </p>
          )}
        </div>
      )}
      {rows.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[860px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-3 py-2">Asset</th>
                <th scope="col" className="px-3 py-2">PCR baseline vs stressed</th>
                <th scope="col" className="px-3 py-2 text-right">Baseline PCR</th>
                <th scope="col" className="px-3 py-2 text-right">Stressed PCR</th>
                <th scope="col" className="px-3 py-2 text-right">Δ PCR</th>
                <th scope="col" className="px-3 py-2 text-right">Rank Δ</th>
                <th scope="col" className="px-3 py-2">State</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.asset_id} className="border-b border-slate-50 last:border-0">
                  <td className="px-3 py-1.5 font-mono">{r.asset_id}</td>
                  <td className="w-64 px-3 py-1.5">
                    <div className="space-y-0.5">
                      <div className="h-2 rounded-sm bg-slate-100">
                        <div className="h-2 rounded-sm bg-slate-400" style={{ width: `${(Math.abs(r.baseline_pcr ?? 0) / maxPcr) * 100}%` }} />
                      </div>
                      <div className="h-2 rounded-sm bg-slate-100">
                        <div className="h-2 rounded-sm bg-rose-400" style={{ width: `${(Math.abs(r.stressed_pcr ?? 0) / maxPcr) * 100}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">{r.baseline_pcr === null ? "—" : fmtPct(r.baseline_pcr, 2)}</td>
                  <td className="px-3 py-1.5 text-right font-mono">{r.stressed_pcr === null ? "—" : fmtPct(r.stressed_pcr, 2)}</td>
                  <td className="px-3 py-1.5 text-right font-mono">{r.pcr_change === null ? "—" : fmtPct(r.pcr_change, 2)}</td>
                  <td className="px-3 py-1.5 text-right font-mono">{r.rank_change === null ? "—" : r.rank_change > 0 ? `+${r.rank_change}` : String(r.rank_change)}</td>
                  <td className="px-3 py-1.5">{r.state.replace(/_/g, " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ConstraintSection({ rows }: { rows: ConstraintResultRow[] }) {
  return (
    <div className="card p-4" data-testid="stress-constraints">
      <h3 className="text-sm font-semibold text-slate-700">Constraint checks under the scenario</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        The stored portfolio constraints re-checked on the original and post-shock drifted books. Breaches are reported only — nothing is rebalanced automatically.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[640px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Book</th>
              <th scope="col" className="px-3 py-2">Constraint</th>
              <th scope="col" className="px-3 py-2">Detail</th>
              <th scope="col" className="px-3 py-2 text-right">Amount</th>
              <th scope="col" className="px-3 py-2">Asset</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.book}-${r.constraint}-${r.asset_id ?? ""}-${i}`}
                className="border-b border-slate-50 last:border-0">
                <td className="px-3 py-1.5 font-medium">{r.book}</td>
                <td className="px-3 py-1.5 font-mono">{r.constraint}</td>
                <td className="px-3 py-1.5">{r.detail}</td>
                <td className="px-3 py-1.5 text-right font-mono">{r.amount === null ? "—" : r.amount.toFixed(6)}</td>
                <td className="px-3 py-1.5 font-mono">{r.asset_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostSection({ run }: { run: RunFull }) {
  const cb = run.cost_stress;
  if (!cb) return null;
  const legs: { label: string; estimate: NonNullable<typeof cb.base> | null; fp: string | null }[] = [
    { label: "Base model", estimate: cb.base, fp: cb.base_model_fingerprint },
    { label: "Stressed copy", estimate: cb.stressed, fp: cb.stressed_model_fingerprint },
  ];
  return (
    <div className="card p-4" data-testid="stress-cost">
      <h3 className="text-sm font-semibold text-slate-700">Liquidity and cost stress</h3>
      <p className="mt-0.5 text-xs text-slate-400">{cb.reference_note} (reference turnover {fmtPct(cb.reference_turnover, 1)}). The linked Phase 55 model is copied — never modified.</p>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        {legs.map(({ label, estimate, fp }) => (
          <div key={label} className="rounded-lg border border-slate-100 p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
              {fp && <CopyValue value={fp} display={shortFp(fp)} />}
            </div>
            {estimate ? (
              <>
                <div className="mt-1 font-mono text-lg font-bold text-slate-900">
                  {estimate.total_cost_return === null ? "—" : fmtPct(estimate.total_cost_return, 4)}
                </div>
                {estimate.status !== "available" && estimate.reason && (
                  <p className="mt-1 text-xs text-amber-700">
                    Unavailable: {estimate.reason}
                  </p>
                )}
                {estimate.components && (
                  <dl className="mt-1 grid grid-cols-2 gap-x-4 text-xs text-slate-500">
                    {Object.entries(estimate.components).map(([name, v]) => (
                      <div key={name} className="flex justify-between"
                        title={v === null ? estimate.component_reasons?.[name] : undefined}>
                        <dt>{name}</dt>
                        <dd className="font-mono">{v === null ? "unavailable" : fmtPct(v, 4)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                {estimate.completeness && estimate.completeness !== "complete" && (
                  <p className="mt-1 text-xs text-amber-700">Completeness: {estimate.completeness}</p>
                )}
                {estimate.component_reasons && Object.keys(estimate.component_reasons).length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-[11px] text-slate-500">
                    {Object.entries(estimate.component_reasons).map(([name, why]) => (
                      <li key={name}>{name}: {why}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <p className="mt-1 text-sm text-slate-500">Not configured for this scenario.</p>
            )}
          </div>
        ))}
      </div>
      {cb.participation && (
        <div className="mt-3 rounded-lg border border-slate-100 p-3 text-sm" data-testid="stress-participation">
          {cb.participation.participation === null ? (
            <p className="text-slate-500">Participation unavailable: {cb.participation.reason}</p>
          ) : (
            <p className={cb.participation.above_threshold ? "text-amber-800" : "text-slate-600"}>
              Participation {fmtPct(cb.participation.participation, 1)} of stressed ADV
              {typeof cb.participation.threshold === "number" && ` (threshold ${fmtPct(cb.participation.threshold, 0)})`}
              {cb.participation.above_threshold ? " — above the explicit threshold; the impact assumption’s validity is questionable at this size." : ""}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DrawdownSection({ run, episodes, attribution }: {
  run: RunFull; episodes: EpisodeRow[]; attribution: AttributionRow[];
}) {
  const dd = run.drawdown;
  if (!dd) return null;
  const series = dd.series;
  let svg: JSX.Element | null = null;
  if (series && series.drawdowns.length > 1) {
    const w = 720;
    const h = 120;
    const n = series.drawdowns.length;
    const min = Math.min(...series.drawdowns, -1e-9);
    const points = series.drawdowns
      .map((v, i) => `${((i / (n - 1)) * w).toFixed(1)},${((v / min) * (h - 10)).toFixed(1)}`)
      .join(" ");
    svg = (
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 w-full" role="img"
        aria-label="Drawdown series (0 at the top; deeper drawdowns lower)" data-testid="drawdown-chart">
        <line x1="0" y1="0" x2={w} y2="0" stroke="#cbd5e1" strokeWidth="1" />
        <polyline points={points} fill="none" stroke="#ef4444" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <div className="card p-4" data-testid="stress-drawdown">
      <h3 className="text-sm font-semibold text-slate-700">Historical drawdown of the stored book</h3>
      {dd.available ? (
        <>
          <p className="mt-0.5 text-xs text-slate-400">
            {dd.convention}. Max drawdown {fmtPct(dd.max_drawdown, 2)} · {dd.episode_count} episode{dd.episode_count === 1 ? "" : "s"}
            {dd.episodes_truncated
              ? ` (the deepest ${episodes.length} are listed below — the count above is the true total)`
              : ""}.
          </p>
          {svg}
          {episodes.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[720px] text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">#</th>
                    <th scope="col" className="px-3 py-2">Peak</th>
                    <th scope="col" className="px-3 py-2">Trough</th>
                    <th scope="col" className="px-3 py-2">Recovery</th>
                    <th scope="col" className="px-3 py-2 text-right">Depth</th>
                    <th scope="col" className="px-3 py-2 text-right">Duration</th>
                    <th scope="col" className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {episodes.map((e) => (
                    <tr key={e.episode_id} className="border-b border-slate-50 font-mono last:border-0">
                      <td className="px-3 py-1.5">{e.episode_id}</td>
                      <td className="px-3 py-1.5">
                        {e.peak_is_initial_capital
                          ? `initial capital (before ${e.peak_timestamp.slice(0, 10)})`
                          : e.peak_timestamp.slice(0, 10)}
                      </td>
                      <td className="px-3 py-1.5">{e.trough_timestamp.slice(0, 10)}</td>
                      <td className="px-3 py-1.5">{e.recovery_timestamp ? e.recovery_timestamp.slice(0, 10) : "unrecovered"}</td>
                      <td className="px-3 py-1.5 text-right">{fmtPct(e.depth, 2)}</td>
                      <td className="px-3 py-1.5 text-right">{e.duration}</td>
                      <td className="px-3 py-1.5">{e.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {dd.attribution && attribution.length > 0 && (
            <div className="mt-3" data-testid="stress-attribution">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Deepest episode attribution (episode {dd.attribution.episode_id})
              </h4>
              <p className="mt-0.5 text-xs text-slate-400">{dd.attribution.weight_policy}. {dd.attribution.reconciliation_note}</p>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[560px] text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                      <th scope="col" className="px-3 py-2">Asset</th>
                      <th scope="col" className="px-3 py-2">Group</th>
                      <th scope="col" className="px-3 py-2 text-right">Contribution</th>
                      <th scope="col" className="px-3 py-2 text-right">Avg weight</th>
                      <th scope="col" className="px-3 py-2 text-right">|share|</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attribution.map((r) => (
                      <tr key={r.asset_id} className="border-b border-slate-50 font-mono last:border-0">
                        <td className="px-3 py-1.5">{r.asset_id}</td>
                        <td className="px-3 py-1.5">{r.group ?? "—"}</td>
                        <td className="px-3 py-1.5 text-right">{r.contribution === null ? "—" : fmtPct(r.contribution, 3)}</td>
                        <td className="px-3 py-1.5 text-right">{r.average_weight === null ? "—" : r.average_weight.toFixed(4)}</td>
                        <td className="px-3 py-1.5 text-right">{r.abs_share === null ? "—" : fmtPct(r.abs_share, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Interval contribution sum: {fmtPct(dd.attribution.portfolio_contribution_sum, 3)} · groups: {Object.entries(dd.attribution.group_contributions).map(([g, v]) => `${g} ${fmtPct(v, 3)}`).join(" · ")}
              </p>
            </div>
          )}
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Drawdown analysis unavailable: {dd.reason}</p>
      )}
    </div>
  );
}

function SensitivitySection({ rows }: { rows: SensitivityRow[] }) {
  return (
    <div className="card p-4" data-testid="stress-sensitivity">
      <h3 className="text-sm font-semibold text-slate-700">Sensitivity probes (one-at-a-time)</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Bounded deterministic probes around the same stored book — each row is an independent explicit scenario, not an optimization.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Dimension</th>
              <th scope="col" className="px-3 py-2 text-right">Value</th>
              <th scope="col" className="px-3 py-2 text-right">Scenario return</th>
              <th scope="col" className="px-3 py-2 text-right">Stressed vol</th>
              <th scope="col" className="px-3 py-2 text-right">Cost return</th>
              <th scope="col" className="px-3 py-2">Completeness</th>
              <th scope="col" className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.fingerprint} className={`border-b border-slate-50 font-mono last:border-0 ${r.is_base ? "bg-slate-50/60" : ""}`}>
                <td className="px-3 py-1.5">{r.is_base ? "base scenario" : r.dimension.replace(/_/g, " ")}</td>
                <td className="px-3 py-1.5 text-right">{r.value === null ? "—" : r.value}</td>
                <td className="px-3 py-1.5 text-right">{r.scenario_return === null ? "—" : fmtPct(r.scenario_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{r.stressed_volatility === null ? "—" : r.stressed_volatility.toFixed(6)}</td>
                <td className="px-3 py-1.5 text-right">{r.cost_return === null ? "—" : fmtPct(r.cost_return, 4)}</td>
                <td className="px-3 py-1.5">{r.completeness ?? "—"}</td>
                <td className="px-3 py-1.5">{r.status}{r.reason ? ` (${r.reason})` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScenarioSection({ scenario, run }: { scenario: Record<string, unknown>; run: RunFull }) {
  const order = run.configuration?.execution_order as string[] | undefined;
  return (
    <div className="card p-4" data-testid="stress-scenario-definition">
      <h3 className="text-sm font-semibold text-slate-700">Scenario definition (stored verbatim)</h3>
      {order && (
        <p className="mt-1 text-xs text-slate-500">
          Documented execution order: {order.map((s) => s.replace(/_/g, " ")).join(" → ")}.
        </p>
      )}
      <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        {JSON.stringify(scenario, null, 2)}
      </pre>
      <p className="mt-2 text-xs text-slate-400">
        Units: return = decimal, percent = value/100, bps = value/10000. Precedence: asset shock → group shock → global shock → missing-shock policy. Factor shocks are deferred in v1 (no estimated exposure system exists). Absolute price shocks are unsupported (stored universes carry returns, not reference prices).
      </p>
    </div>
  );
}
