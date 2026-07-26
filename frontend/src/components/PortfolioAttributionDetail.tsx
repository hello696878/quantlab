"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type AssetRow,
  type BenchmarkBlock,
  type BrinsonRow,
  type DrawdownRow,
  type GroupRow,
  type PeriodRow,
  type RegimeRow,
  type RunFull,
  LINKING_LABELS,
  METHOD_LABELS,
  VARIANT_LABELS,
  fmtNum,
  fmtPct,
  getAssets,
  getBenchmark,
  getBrinson,
  getDrawdowns,
  getGroups,
  getPeriods,
  getRegimes,
  getRun,
  markBaseline,
  shortFp,
} from "@/lib/portfolioAttribution";
import { notifyBackendOffline, toast } from "@/lib/toast";
import ErrorState from "@/components/ui/ErrorState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { CopyValue } from "@/components/ExperimentRegistryShared";
import {
  CompletenessPill,
  IntegrityPill,
  ReconciliationPill,
  StatusPill,
} from "@/components/PortfolioAttributionShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenPortfolio?: () => void;
  onOpenStress?: () => void;
  onOpenCost?: () => void;
  onOpenRegime?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
}

interface Children {
  benchmark: BenchmarkBlock | null;
  periods: PeriodRow[];
  assets: AssetRow[];
  groups: GroupRow[];
  brinson: BrinsonRow[];
  regimes: RegimeRow[];
  regimeNote: string | null;
  drawdowns: DrawdownRow[];
}

export default function PortfolioAttributionDetail({
  run, onBack, onRefresh, onOpenPortfolio, onOpenStress, onOpenCost,
  onOpenRegime, onOpenDataset, onOpenExperiment,
}: Props) {
  const [children, setChildren] = useState<Children | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getBenchmark(run.id), getPeriods(run.id), getAssets(run.id),
      getGroups(run.id), getBrinson(run.id), getRegimes(run.id),
      getDrawdowns(run.id),
    ])
      .then(([b, p, a, g, br, rg, dd]) => {
        if (cancelled) return;
        setChildren({
          benchmark: b.benchmark, periods: p.items, assets: a.items,
          groups: g.items, brinson: br.items, regimes: rg.items,
          regimeNote: rg.note, drawdowns: dd.items,
        });
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

  const summary = run.summary;

  return (
    <div className="space-y-4" data-testid="portfolio-attribution-detail">
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
          {onOpenCost && run.cost_run_name && (
            <button type="button" onClick={onOpenCost}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Cost lab →
            </button>
          )}
          {onOpenRegime && run.regime_run_name && (
            <button type="button" onClick={onOpenRegime}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Regime lab →
            </button>
          )}
          {onOpenStress && run.stress_run_name && (
            <button type="button" onClick={onOpenStress}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              Stress lab →
            </button>
          )}
          {onOpenDataset && run.dataset_name && (
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
              <ReconciliationPill status={run.reconciliation_status} />
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {METHOD_LABELS[run.attribution_method] ?? run.attribution_method}
                {run.brinson_variant ? ` · ${VARIANT_LABELS[run.brinson_variant] ?? run.brinson_variant}` : ""}
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {LINKING_LABELS[run.linking_method] ?? run.linking_method}
              </span>
              {run.is_baseline && (
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">★ baseline</span>
              )}
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-slate-500">
            <dt>Portfolio run</dt>
            <dd className="font-medium text-slate-700">{run.portfolio_run_name ?? `#${run.portfolio_run_id}`}</dd>
            <dt>Benchmark</dt>
            <dd className="font-medium text-slate-700">{run.benchmark_name ?? "— none configured"}</dd>
            <dt>Window</dt>
            <dd className="font-mono">{run.observation_start?.slice(0, 10)} → {run.observation_end?.slice(0, 10)}</dd>
            <dt>Periods · assets · groups</dt>
            <dd className="font-mono">{run.period_count} · {run.asset_count} · {run.group_count}</dd>
            <dt>Observation fp</dt>
            <dd><CopyValue value={run.observation_fingerprint} display={shortFp(run.observation_fingerprint)} /></dd>
            <dt>Policy fp</dt>
            <dd><CopyValue value={run.policy_fingerprint} display={shortFp(run.policy_fingerprint)} /></dd>
            <dt>Config fp</dt>
            <dd><CopyValue value={run.configuration_fingerprint} display={shortFp(run.configuration_fingerprint)} /></dd>
            <dt>Result fp</dt>
            <dd>{run.result_fingerprint ? <CopyValue value={run.result_fingerprint} display={shortFp(run.result_fingerprint)} /> : "—"}</dd>
          </dl>
        </div>
        {run.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">{run.error_message}</div>
        )}
        {run.warnings.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-800" data-testid="attribution-warnings">
            {run.warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
          </div>
        )}
        <p className="mt-3 text-xs text-slate-400">
          Weights are beginning-of-period ({run.weight_timing_policy.replace(/_/g, " ")}), returns are {run.return_convention}, frequency {run.return_frequency}.
          {" "}Measured contributions under this convention — not evidence of alpha, manager skill, or a preferred portfolio.
        </p>
      </div>

      <ReconciliationSection run={run} />

      {error ? (
        <ErrorState title="Couldn’t load attribution details" message={classifyApiError(error).message} onRetry={() => window.location.reload()} />
      ) : !children ? (
        <SkeletonTable rows={6} cols={6} caption="Loading attribution results…" />
      ) : (
        <>
          {children.benchmark && <BenchmarkSection benchmark={children.benchmark} run={run} />}
          <AssetSection rows={children.assets} run={run} />
          <GroupSection rows={children.groups} assets={children.assets} />
          {children.brinson.length > 0 && (
            <BrinsonSection rows={children.brinson} run={run} />
          )}
          {run.linking && <LinkingSection run={run} />}
          {run.cost && <CostSection run={run} />}
          {run.active_risk && <ActiveRiskSection run={run} />}
          <TimelineSection periods={children.periods} />
          {children.regimes.length > 0 && (
            <RegimeSection rows={children.regimes} note={children.regimeNote} />
          )}
          {children.drawdowns.length > 0 && (
            <DrawdownSection rows={children.drawdowns} />
          )}
          <PolicySection run={run} />
        </>
      )}
    </div>
  );
}

function Metric({ label, value, emphasis, unit }: {
  label: string; value: string; emphasis?: boolean; unit?: string;
}) {
  return (
    <div>
      <div className={`font-mono ${emphasis ? "text-lg font-bold text-slate-900" : "text-base font-semibold text-slate-800"}`}>
        {value}{unit ? <span className="ml-1 text-xs font-normal text-slate-400">{unit}</span> : null}
      </div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

function ReconciliationSection({ run }: { run: RunFull }) {
  const s = run.summary;
  return (
    <div className="card p-4" data-testid="attribution-reconciliation">
      <h3 className="text-sm font-semibold text-slate-700">Return reconciliation</h3>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Portfolio market return" value={fmtPct(run.portfolio_market_return, 3)} />
        <Metric label="Transaction costs" value={run.total_cost_return === null ? "— (none linked)" : fmtPct(run.total_cost_return, 4)} />
        <Metric label="Portfolio net return" value={run.portfolio_net_return === null ? "— (no cost leg)" : fmtPct(run.portfolio_net_return, 3)} />
        <Metric label="Benchmark return" value={run.benchmark_return === null ? "— (no benchmark)" : fmtPct(run.benchmark_return, 3)} />
        <Metric label="Active return" value={run.active_return === null ? "— (no benchmark)" : fmtPct(run.active_return, 3)} emphasis />
      </div>
      {s && (
        <div className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-2">
          <p>
            Asset contributions sum to <span className="font-mono">{fmtPct(s.asset_contribution_sum, 4)}</span>{" "}
            versus the portfolio market return <span className="font-mono">{fmtPct(s.portfolio_market_return_arithmetic, 4)}</span> —{" "}
            <span className={s.contribution_reconciled ? "text-emerald-700" : "text-amber-700"}>
              {s.contribution_reconciled ? "reconciled" : "residual"}
            </span>{" "}(tolerance {s.tolerance}).
          </p>
          <p>
            Group totals sum to <span className="font-mono">{fmtPct(s.group_contribution_sum, 4)}</span> —{" "}
            <span className={s.group_reconciled ? "text-emerald-700" : "text-amber-700"}>
              {s.group_reconciled ? "match the asset totals" : "differ from the asset totals"}
            </span>.
          </p>
          {s.time_weighted_return?.available && (
            <p data-testid="attribution-twr">
              Time-weighted return (compounded): <span className="font-mono">{fmtPct(s.time_weighted_return.value, 3)}</span>.{" "}
              {s.time_weighted_return.convention}
            </p>
          )}
          {s.benchmark_time_weighted_return?.available && (
            <p>
              Benchmark time-weighted return: <span className="font-mono">{fmtPct(s.benchmark_time_weighted_return.value, 3)}</span>.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function BenchmarkSection({ benchmark, run }: { benchmark: BenchmarkBlock; run: RunFull }) {
  const definition = benchmark.definition as {
    asset_ids?: string[]; base_weights?: number[];
    portfolio_only_assets?: string[]; benchmark_only_assets?: string[];
  };
  return (
    <div className="card p-4" data-testid="attribution-benchmark">
      <h3 className="text-sm font-semibold text-slate-700">Benchmark definition</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Declared explicitly — a benchmark is never selected automatically and never falls back to an implicit equal-weight book.
      </p>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Name" value={benchmark.name} />
        <Metric label="Kind" value={benchmark.kind.replace(/_/g, " ")} />
        <Metric label="Source" value={benchmark.source.replace(/_/g, " ")} />
        <Metric label="Weight sum" value={fmtNum(benchmark.weight_sum, 4)} />
      </div>
      {benchmark.weight_sum !== null && Math.abs(benchmark.weight_sum - 1) > 1e-9 && (
        <p className="mt-2 text-xs text-amber-700">
          The declared weights sum to {fmtNum(benchmark.weight_sum, 4)}, not 1 — they are used as declared and never renormalized.
        </p>
      )}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[420px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Asset</th>
              <th scope="col" className="px-3 py-2 text-right">Declared weight</th>
            </tr>
          </thead>
          <tbody>
            {(definition.asset_ids ?? []).map((aid, i) => (
              <tr key={aid} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{aid}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct((definition.base_weights ?? [])[i], 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(definition.portfolio_only_assets?.length || definition.benchmark_only_assets?.length) ? (
        <p className="mt-2 text-xs text-slate-500">
          {definition.portfolio_only_assets?.length ? `Portfolio-only: ${definition.portfolio_only_assets.join(", ")}. ` : ""}
          {definition.benchmark_only_assets?.length ? `Benchmark-only: ${definition.benchmark_only_assets.join(", ")}.` : ""}
        </p>
      ) : null}
    </div>
  );
}

function AssetSection({ rows, run }: { rows: AssetRow[]; run: RunFull }) {
  const maxAbs = Math.max(1e-12, ...rows.map((r) => Math.abs(r.arithmetic_contribution ?? 0)));
  const sorted = [...rows].sort((a, b) => (a.arithmetic_contribution ?? 0) - (b.arithmetic_contribution ?? 0));
  return (
    <div className="card p-4" data-testid="attribution-assets">
      <h3 className="text-sm font-semibold text-slate-700">Asset contributions</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        contribution_i = beginning-of-period weight × asset return, summed over periods. Measured under this convention — no asset “caused” the result.
      </p>
      <div className="mt-3 space-y-1" data-testid="asset-contribution-chart">
        {sorted.map((r) => {
          const c = r.arithmetic_contribution ?? 0;
          const width = (Math.abs(c) / maxAbs) * 50;
          return (
            <div key={r.asset_id} className="flex items-center gap-2 text-xs">
              <span className="w-24 truncate font-mono text-slate-600">{r.asset_id}</span>
              <div className="relative h-4 flex-1">
                <div className="absolute inset-y-0 left-1/2 w-px bg-slate-200" />
                <div className={`absolute inset-y-0 rounded-sm ${c < 0 ? "bg-red-400" : "bg-emerald-400"}`}
                  style={c < 0 ? { right: "50%", width: `${width}%` } : { left: "50%", width: `${width}%` }} />
              </div>
              <span className="w-20 text-right font-mono text-slate-700">{fmtPct(c, 3)}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[820px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Asset</th>
              <th scope="col" className="px-3 py-2">Group</th>
              <th scope="col" className="px-3 py-2 text-right">Avg weight</th>
              <th scope="col" className="px-3 py-2 text-right">Arithmetic contrib.</th>
              <th scope="col" className="px-3 py-2 text-right">Positive</th>
              <th scope="col" className="px-3 py-2 text-right">Negative</th>
              <th scope="col" className="px-3 py-2 text-right">|share|</th>
              <th scope="col" className="px-3 py-2 text-right">Periods</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.asset_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{r.asset_id}</td>
                <td className="px-3 py-1.5">{r.group_id ?? "—"}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.average_weight, 2)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.arithmetic_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.positive_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.negative_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.absolute_share, 1)}</td>
                <td className="px-3 py-1.5 text-right">{r.observation_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {run.concentration && (
        <p className="mt-2 text-xs text-slate-500" data-testid="attribution-concentration">
          Absolute-contribution concentration: Herfindahl {fmtNum(run.concentration.herfindahl, 4)},
          effective contributors {fmtNum(run.concentration.effective_contributors, 2)},
          largest share {fmtPct(run.concentration.largest_absolute_share, 1)}. {run.concentration.note}
        </p>
      )}
    </div>
  );
}

function GroupSection({ rows, assets }: { rows: GroupRow[]; assets: AssetRow[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="card p-4" data-testid="attribution-groups">
      <h3 className="text-sm font-semibold text-slate-700">Group contributions</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Explicit stored group labels — never inferred from asset names. Each asset belongs to exactly one group, so group totals sum to the asset totals with no double counting.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[680px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Group</th>
              <th scope="col" className="px-3 py-2 text-right">Assets</th>
              <th scope="col" className="px-3 py-2 text-right">Arithmetic contrib.</th>
              <th scope="col" className="px-3 py-2 text-right">Positive</th>
              <th scope="col" className="px-3 py-2 text-right">Negative</th>
              <th scope="col" className="px-3 py-2 text-right">|share|</th>
              <th scope="col" className="px-3 py-2 text-center">Assets</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.group_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{r.group_id}</td>
                <td className="px-3 py-1.5 text-right">{r.asset_count}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.arithmetic_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.positive_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.negative_contribution, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.absolute_share, 1)}</td>
                <td className="px-3 py-1.5 text-center">
                  <button type="button"
                    onClick={() => setOpen(open === r.group_id ? null : r.group_id)}
                    className="rounded border border-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50">
                    {open === r.group_id ? "Hide" : "Show"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="mt-2 rounded-lg border border-slate-100 p-3" data-testid="group-drilldown">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {open} constituents
          </p>
          <ul className="mt-1 space-y-0.5 text-xs">
            {assets.filter((a) => a.group_id === open).map((a) => (
              <li key={a.asset_id} className="flex justify-between font-mono">
                <span>{a.asset_id}</span>
                <span>{fmtPct(a.arithmetic_contribution, 3)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function BrinsonSection({ rows, run }: { rows: BrinsonRow[]; run: RunFull }) {
  const total = rows.reduce((acc, r) => acc + (r.total_effect ?? 0), 0);
  const maxAbs = Math.max(1e-12, ...rows.flatMap((r) =>
    [Math.abs(r.allocation_effect ?? 0), Math.abs(r.selection_effect ?? 0),
     Math.abs(r.interaction_effect ?? 0)]));
  const residual = (run.active_return ?? 0) - total;
  return (
    <div className="card p-4" data-testid="attribution-brinson">
      <h3 className="text-sm font-semibold text-slate-700">
        Brinson effects ({VARIANT_LABELS[run.brinson_variant ?? ""] ?? run.brinson_variant})
      </h3>
      <p className="mt-0.5 text-xs text-slate-400">
        {run.brinson_variant === "brinson_hood_beebower"
          ? "allocation_g = (Wp−Wb) × Rb_g; selection_g = Wb × (Rp−Rb); interaction_g = (Wp−Wb) × (Rp−Rb)"
          : "allocation_g = (Wp−Wb) × (Rb_g − Rb_total); selection_g = Wb × (Rp−Rb); interaction_g = (Wp−Wb) × (Rp−Rb)"}
        {" "}— an arithmetic decomposition of a measured difference, not evidence of skill.
      </p>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Allocation" value={fmtPct(rows.reduce((a, r) => a + (r.allocation_effect ?? 0), 0), 3)} />
        <Metric label="Selection" value={fmtPct(rows.reduce((a, r) => a + (r.selection_effect ?? 0), 0), 3)} />
        <Metric label="Interaction" value={fmtPct(rows.reduce((a, r) => a + (r.interaction_effect ?? 0), 0), 3)} />
        <Metric label="Residual" value={fmtPct(residual, 4)} />
        <Metric label="Total active return" value={fmtPct(run.active_return, 3)} emphasis />
      </div>
      <div className="mt-3 space-y-2" data-testid="brinson-chart">
        {rows.map((r) => (
          <div key={r.group_id} className="text-xs">
            <div className="flex items-center justify-between">
              <span className="font-mono text-slate-600">{r.group_id}</span>
              <span className="text-slate-400">{r.presence?.replace(/_/g, " ")}</span>
            </div>
            <div className="mt-0.5 flex gap-1">
              {([["allocation", r.allocation_effect, "bg-sky-400"],
                 ["selection", r.selection_effect, "bg-violet-400"],
                 ["interaction", r.interaction_effect, "bg-amber-400"]] as const).map(
                ([label, value, color]) => (
                  <div key={label} className="flex-1">
                    <div className="h-2 rounded-sm bg-slate-100">
                      <div className={`h-2 rounded-sm ${color}`}
                        style={{ width: `${(Math.abs(value ?? 0) / maxAbs) * 100}%` }} />
                    </div>
                    <div className="mt-0.5 flex justify-between text-[10px] text-slate-500">
                      <span>{label}</span>
                      <span className="font-mono">{value === null ? "unavailable" : fmtPct(value, 3)}</span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[900px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Group</th>
              <th scope="col" className="px-3 py-2">Presence</th>
              <th scope="col" className="px-3 py-2 text-right">Avg Wp</th>
              <th scope="col" className="px-3 py-2 text-right">Avg Wb</th>
              <th scope="col" className="px-3 py-2 text-right">Allocation</th>
              <th scope="col" className="px-3 py-2 text-right">Selection</th>
              <th scope="col" className="px-3 py-2 text-right">Interaction</th>
              <th scope="col" className="px-3 py-2 text-right">Total</th>
              <th scope="col" className="px-3 py-2 text-right">Unavailable periods</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.group_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{r.group_id}</td>
                <td className="px-3 py-1.5">{r.presence?.replace(/_/g, " ") ?? "—"}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.average_portfolio_weight, 2)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.average_benchmark_weight, 2)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.allocation_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.selection_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.interaction_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.total_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{r.unavailable_periods}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500" data-testid="brinson-residual">
        Residual = active return − (allocation + selection + interaction) = <span className="font-mono">{fmtPct(residual, 4)}</span>.
        It is reported verbatim and never redistributed into the three effects.
      </p>
    </div>
  );
}

function LinkingSection({ run }: { run: RunFull }) {
  const l = run.linking;
  if (!l) return null;
  return (
    <div className="card p-4" data-testid="attribution-linking">
      <h3 className="text-sm font-semibold text-slate-700">
        Multi-period linking ({LINKING_LABELS[l.method] ?? l.method})
      </h3>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Arithmetic active (summed)" value={fmtPct(l.arithmetic_active_return, 3)} />
        <Metric label="Geometric active (compounded)" value={fmtPct(l.geometric_active_return, 3)} />
        <Metric label="Arithmetic − geometric gap" value={fmtPct(l.arithmetic_vs_geometric_gap, 4)} />
        <Metric label="Linking residual" value={l.linking_residual === null ? "— (withheld)" : fmtPct(l.linking_residual, 6)} />
      </div>
      <p className="mt-2 text-xs text-slate-400">{l.arithmetic_caveat}</p>
      {l.available === false && l.reason && (
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          Linked effects withheld: {l.reason}
        </p>
      )}
      {l.linked_effects && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-3 py-2">Effect</th>
                <th scope="col" className="px-3 py-2 text-right">Arithmetic</th>
                <th scope="col" className="px-3 py-2 text-right">Linked ({l.method})</th>
              </tr>
            </thead>
            <tbody>
              {["allocation_effect", "selection_effect", "interaction_effect"].map((k) => (
                <tr key={k} className="border-b border-slate-50 font-mono last:border-0">
                  <td className="px-3 py-1.5">{k.replace(/_effect$/, "")}</td>
                  <td className="px-3 py-1.5 text-right">{fmtPct(l.arithmetic_effects?.[k], 3)}</td>
                  <td className="px-3 py-1.5 text-right">{fmtPct(l.linked_effects?.[k], 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {l.carino_note && <p className="mt-2 text-xs text-slate-400">{l.carino_note}</p>}
      {l.closure_note && <p className="mt-1 text-xs text-slate-400">{l.closure_note}</p>}
    </div>
  );
}

function CostSection({ run }: { run: RunFull }) {
  const c = run.cost;
  if (!c) return null;
  return (
    <div className="card p-4" data-testid="attribution-cost">
      <h3 className="text-sm font-semibold text-slate-700">Transaction-cost attribution</h3>
      <p className="mt-0.5 text-xs text-slate-400">{c.source_note}</p>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Gross (costed periods)" value={fmtPct(c.gross_market_return_costed_periods, 3)} />
        <Metric label="Total cost" value={fmtPct(c.total_cost_return, 4)} />
        <Metric label="Net (costed periods)" value={fmtPct(c.net_return_costed_periods, 3)} emphasis />
        <Metric label="Costed / traded periods" value={`${c.costed_period_count} / ${c.traded_period_count}`} />
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[420px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Component</th>
              <th scope="col" className="px-3 py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(c.component_totals).map(([name, value]) => (
              <tr key={name} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{name}</td>
                <td className="px-3 py-1.5 text-right">{value === null ? "unavailable" : fmtPct(value, 4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">{c.basis_note}</p>
      <p className="mt-1 text-xs text-slate-400">{c.stress_note}</p>
      {c.completeness !== "complete" && (
        <p className="mt-1 text-xs text-amber-700">Cost completeness: {c.completeness} ({c.unavailable_period_count} period(s) without an estimate).</p>
      )}
    </div>
  );
}

function ActiveRiskSection({ run }: { run: RunFull }) {
  const r = run.active_risk;
  if (!r) return null;
  const dd = run.summary?.active_drawdown;
  return (
    <div className="card p-4" data-testid="attribution-active-risk">
      <h3 className="text-sm font-semibold text-slate-700">Active-risk diagnostics</h3>
      <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Mean active return" value={fmtPct(r.mean_active_return, 4)} unit="per period" />
        <Metric label="Tracking error" value={fmtPct(r.tracking_error, 4)} unit="per period" />
        <Metric label="Annualized TE" value={r.annualized_tracking_error === null ? "— (unavailable)" : fmtPct(r.annualized_tracking_error, 3)} />
        <Metric label="Information ratio" value={r.information_ratio === null ? "— (unavailable)" : fmtNum(r.information_ratio, 4)} emphasis />
        <Metric label="Hit rate" value={fmtPct(r.hit_rate, 1)} />
      </div>
      <p className="mt-2 text-xs text-slate-400">{r.std_convention}. {r.annualization_note}</p>
      {r.information_ratio === null && r.information_ratio_reason && (
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800" data-testid="ir-unavailable">
          Information ratio unavailable: {r.information_ratio_reason}
        </p>
      )}
      {dd?.available && (
        <p className="mt-2 text-xs text-slate-500">
          Maximum active drawdown: <span className="font-mono">{fmtPct(dd.max_active_drawdown, 3)}</span>. {dd.convention}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-400">{r.note}</p>
    </div>
  );
}

function TimelineSection({ periods }: { periods: PeriodRow[] }) {
  if (!periods.length) return null;
  const w = 720;
  const h = 120;
  const values = periods.flatMap((p) =>
    [p.portfolio_market_return ?? 0, p.benchmark_return ?? 0]);
  const max = Math.max(1e-9, ...values.map(Math.abs));
  const line = (key: "portfolio_market_return" | "benchmark_return" | "active_return") =>
    periods.map((p, i) => {
      const v = p[key] ?? 0;
      const x = periods.length > 1 ? (i / (periods.length - 1)) * w : 0;
      const y = h / 2 - (v / max) * (h / 2 - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  return (
    <div className="card p-4" data-testid="attribution-timeline">
      <h3 className="text-sm font-semibold text-slate-700">Active-return timeline</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Portfolio (slate), benchmark (sky) and active (rose) returns per period, all in return units. The table below carries the same values.
      </p>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 w-full" role="img"
        aria-label="Per-period portfolio, benchmark and active returns">
        <line x1="0" y1={h / 2} x2={w} y2={h / 2} stroke="#cbd5e1" strokeWidth="1" />
        <polyline points={line("portfolio_market_return")} fill="none" stroke="#475569" strokeWidth="1.5" />
        <polyline points={line("benchmark_return")} fill="none" stroke="#0ea5e9" strokeWidth="1.5" />
        <polyline points={line("active_return")} fill="none" stroke="#f43f5e" strokeWidth="1.5" />
      </svg>
      <div className="mt-3 max-h-72 overflow-auto">
        <table className="w-full min-w-[880px] text-xs">
          <thead className="sticky top-0 bg-white">
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Period start</th>
              <th scope="col" className="px-3 py-2 text-right">Portfolio</th>
              <th scope="col" className="px-3 py-2 text-right">Cost</th>
              <th scope="col" className="px-3 py-2 text-right">Net</th>
              <th scope="col" className="px-3 py-2 text-right">Benchmark</th>
              <th scope="col" className="px-3 py-2 text-right">Active</th>
              <th scope="col" className="px-3 py-2 text-right">Allocation</th>
              <th scope="col" className="px-3 py-2 text-right">Selection</th>
              <th scope="col" className="px-3 py-2 text-right">Interaction</th>
              <th scope="col" className="px-3 py-2 text-right">Residual</th>
              <th scope="col" className="px-3 py-2">Recon.</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.period_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{p.period_start.slice(0, 10)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.portfolio_market_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{p.transaction_cost_return === null ? (p.cost_state ?? "—") : fmtPct(p.transaction_cost_return, 4)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.portfolio_net_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.benchmark_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.active_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.allocation_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.selection_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.interaction_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(p.residual, 5)}</td>
                <td className="px-3 py-1.5">{p.reconciliation_state ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RegimeSection({ rows, note }: { rows: RegimeRow[]; note: string | null }) {
  return (
    <div className="card p-4" data-testid="attribution-regimes">
      <h3 className="text-sm font-semibold text-slate-700">Attribution by stored regime</h3>
      {note && <p className="mt-0.5 text-xs text-slate-400">{note}</p>}
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[900px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">Regime</th>
              <th scope="col" className="px-3 py-2 text-right">Periods</th>
              <th scope="col" className="px-3 py-2 text-right">Portfolio</th>
              <th scope="col" className="px-3 py-2 text-right">Benchmark</th>
              <th scope="col" className="px-3 py-2 text-right">Active</th>
              <th scope="col" className="px-3 py-2 text-right">Cost</th>
              <th scope="col" className="px-3 py-2 text-right">Allocation</th>
              <th scope="col" className="px-3 py-2 text-right">Selection</th>
              <th scope="col" className="px-3 py-2 text-right">Interaction</th>
              <th scope="col" className="px-3 py-2 text-right">Tracking err.</th>
              <th scope="col" className="px-3 py-2">Completeness</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.regime_label} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">
                  {r.regime_label}
                  {r.rare_regime_warning && <span className="ml-1 text-[10px] text-amber-600">rare</span>}
                </td>
                <td className="px-3 py-1.5 text-right">{r.observation_count}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.portfolio_market_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.benchmark_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.active_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.cost_return, 4)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.allocation_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.selection_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.interaction_effect, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.tracking_error, 4)}</td>
                <td className="px-3 py-1.5">{r.completeness ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DrawdownSection({ rows }: { rows: DrawdownRow[] }) {
  return (
    <div className="card p-4" data-testid="attribution-drawdowns">
      <h3 className="text-sm font-semibold text-slate-700">Attribution over stored drawdown episodes</h3>
      <p className="mt-0.5 text-xs text-slate-400">
        Episode intervals are reused exactly from the linked stress run (read-only). Attribution describes what was measured over the interval — it never explains why the drawdown occurred.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[860px] text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-3 py-2">#</th>
              <th scope="col" className="px-3 py-2">Peak</th>
              <th scope="col" className="px-3 py-2">Trough</th>
              <th scope="col" className="px-3 py-2 text-right">Periods</th>
              <th scope="col" className="px-3 py-2 text-right">Portfolio</th>
              <th scope="col" className="px-3 py-2 text-right">Benchmark</th>
              <th scope="col" className="px-3 py-2 text-right">Active</th>
              <th scope="col" className="px-3 py-2 text-right">Cost</th>
              <th scope="col" className="px-3 py-2 text-right">Residual</th>
              <th scope="col" className="px-3 py-2">Recon.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.episode_id} className="border-b border-slate-50 font-mono last:border-0">
                <td className="px-3 py-1.5">{r.episode_id}</td>
                <td className="px-3 py-1.5">{r.peak_timestamp?.slice(0, 10) ?? "—"}</td>
                <td className="px-3 py-1.5">{r.trough_timestamp?.slice(0, 10) ?? "—"}</td>
                <td className="px-3 py-1.5 text-right">{r.period_count}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.portfolio_market_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.benchmark_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.active_return, 3)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.cost_return, 4)}</td>
                <td className="px-3 py-1.5 text-right">{fmtPct(r.residual, 5)}</td>
                <td className="px-3 py-1.5">{r.reconciliation_state ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PolicySection({ run }: { run: RunFull }) {
  const order = run.configuration?.execution_order as string[] | undefined;
  return (
    <div className="card p-4" data-testid="attribution-policy">
      <h3 className="text-sm font-semibold text-slate-700">Attribution policy (stored verbatim)</h3>
      {order && (
        <p className="mt-1 text-xs text-slate-500">
          Documented execution order: {order.map((s) => s.replace(/_/g, " ")).join(" → ")}.
        </p>
      )}
      <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        {JSON.stringify(run.configuration?.policy ?? {}, null, 2)}
      </pre>
      <p className="mt-2 text-xs text-slate-400">
        {String(run.configuration?.factor_attribution ?? "")}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        {String(run.configuration?.scope_note ?? "")}
      </p>
    </div>
  );
}
