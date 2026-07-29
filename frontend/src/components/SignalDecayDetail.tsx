"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type BootstrapRow,
  type BucketRow,
  type HorizonRow,
  type ObservationRow,
  type RegimeRow,
  type RunFull,
  type TurnoverRow,
  INTEGRITY_LABELS,
  fmtNum,
  fmtP,
  fmtPct,
  getBootstrap,
  getBuckets,
  getHorizons,
  getObservations,
  getRegimes,
  getRun,
  getTurnover,
  markBaseline,
  shortFp,
} from "@/lib/signalDecay";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import {
  CompletenessPill,
  IntegrityPill,
  OverlapPill,
  StatusPill,
} from "@/components/SignalDecayShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenValidation?: () => void;
  onOpenRegime?: () => void;
  onOpenCost?: () => void;
  onOpenFactor?: () => void;
  onOpenMetaLabel?: () => void;
}

const MAX_TURNOVER_ROWS = 25;
const MAX_OBSERVATION_ROWS = 25;

export default function SignalDecayDetail(props: Props) {
  const { run, onBack, onRefresh } = props;
  const [horizons, setHorizons] = useState<HorizonRow[] | null>(null);
  const [buckets, setBuckets] = useState<BucketRow[] | null>(null);
  const [turnover, setTurnover] = useState<TurnoverRow[] | null>(null);
  const [regimes, setRegimes] = useState<RegimeRow[] | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapRow[] | null>(null);
  const [observations, setObservations] = useState<ObservationRow[] | null>(null);
  const [rareThreshold, setRareThreshold] = useState<number>(10);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getHorizons(run.id), getBuckets(run.id), getTurnover(run.id),
      getRegimes(run.id), getBootstrap(run.id), getObservations(run.id),
    ])
      .then(([h, b, t, g, bo, o]) => {
        if (cancelled) return;
        setHorizons(h.items);
        setBuckets(b.items);
        setTurnover(t.items);
        setRegimes(g.items);
        setRareThreshold(g.rare_threshold);
        setBootstrap(bo.items);
        setObservations(o.items);
      })
      .catch((err) => {
        if (cancelled) return;
        const cls = classifyApiError(err);
        if (cls.backendUnavailable) notifyBackendOffline();
        else toast.error("Couldn’t load run details", cls.message);
      });
    return () => {
      cancelled = true;
    };
  }, [run.id]);

  async function handleBaseline() {
    setMarking(true);
    try {
      await markBaseline(run.id);
      onRefresh(await getRun(run.id));
      toast.success("Baseline marked", "Comparison reference only — nothing is recommended.");
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Baseline rejected", cls.message);
    } finally {
      setMarking(false);
    }
  }

  const rawRows = useMemo(
    () => (horizons ?? []).filter(
      (r) => r.outcome_scope === "raw" && r.selection === "overlapping"),
    [horizons],
  );
  const firstLag = rawRows.length ? Math.min(...rawRows.map((r) => r.entry_lag)) : 0;
  const decayRows = rawRows.filter((r) => r.entry_lag === firstLag);
  const lagRows = rawRows.filter(() => true);
  const nonOverlapRows = (horizons ?? []).filter(
    (r) => r.selection === "non_overlapping");
  const residualRows = (horizons ?? []).filter(
    (r) => r.outcome_scope === "factor_residual");
  const signalUnit = String((run.signal as Record<string, unknown>)?.unit ?? "score");
  const horizonUnit = String((run.horizon_policy as Record<string, unknown>)?.unit ?? "observations");

  return (
    <div className="space-y-4" data-testid="signal-decay-detail">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={onBack}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
          ← Back to runs
        </button>
        {run.status === "completed" && !run.is_baseline && (
          <button type="button" onClick={handleBaseline} disabled={marking}
            className="rounded-md border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
            {marking ? "Marking…" : "Mark as comparison baseline"}
          </button>
        )}
        {props.onOpenValidation && run.validation_identity && (
          <button type="button" onClick={props.onOpenValidation}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Model Validation →
          </button>
        )}
        {props.onOpenRegime && run.regime_identity && (
          <button type="button" onClick={props.onOpenRegime}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Regime Diagnostics →
          </button>
        )}
        {props.onOpenCost && run.cost_identity && (
          <button type="button" onClick={props.onOpenCost}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Cost Diagnostics →
          </button>
        )}
        {props.onOpenFactor && run.factor_identity && (
          <button type="button" onClick={props.onOpenFactor}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Factor Diagnostics →
          </button>
        )}
        {props.onOpenMetaLabel && run.meta_label_identity && (
          <button type="button" onClick={props.onOpenMetaLabel}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Meta-Labeling →
          </button>
        )}
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-slate-900">{run.name}</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">{run.description}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <IntegrityPill status={run.integrity_status} />
            <CompletenessPill status={run.completeness_status} />
            <OverlapPill status={run.overlap_status} />
            {run.is_baseline && (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                ★ baseline
              </span>
            )}
          </div>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
          <Field label="Signal" value={`${run.signal_id} · ${run.signal_type.replace(/_/g, " ")} · unit ${signalUnit}`} />
          <Field label="Direction" value={String((run.signal as Record<string, unknown>)?.direction ?? "—").replace(/_/g, " ")} />
          <Field label="Tie policy" value={String((run.signal as Record<string, unknown>)?.tie_policy ?? "—")} />
          <Field label="Outcome" value={`${run.outcome_id} · ${run.outcome_target_type.replace(/_/g, " ")}`} />
          <Field label="Horizon unit" value={horizonUnit} />
          <Field label="Window" value={`${run.observation_start ?? "—"} → ${run.observation_end ?? "—"}`} />
          <Field label="Entities × observations" value={`${run.entity_count} × ${run.observation_count}`} />
          <Field label="Horizons × lags" value={`${run.horizon_count} × ${run.lag_count}`} />
        </dl>
        {run.error_message && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-800">
            Execution failed: {run.error_message}
          </p>
        )}
      </div>

      {run.warnings.length > 0 && (
        <div className="card p-4" data-testid="signal-warnings">
          <h3 className="text-sm font-semibold text-slate-700">Warnings ({run.warnings.length})</h3>
          <ul className="mt-2 space-y-1.5 text-sm text-amber-800">
            {run.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        </div>
      )}

      {/* ---------------- decay curve ---------------- */}
      <div className="card overflow-hidden" data-testid="signal-decay-curve">
        <SectionHeader title="Decay curve — per-horizon diagnostics"
          note={`Statistics by forecast horizon (${horizonUnit}) at entry lag ${firstLag}. Every row shows its sample count and overlap state; no horizon is called optimal.`} />
        {!horizons ? (
          <SkeletonTable rows={4} cols={8} caption="Loading horizons…" />
        ) : (
          <>
            <DecayChart rows={decayRows} />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Horizon ({horizonUnit})</th>
                    <th scope="col" className="px-3 py-2 text-right">Lag</th>
                    <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                    <th scope="col" className="px-3 py-2 text-right">Pearson</th>
                    <th scope="col" className="px-3 py-2 text-right">Rank IC (Spearman)</th>
                    <th scope="col" className="px-3 py-2 text-right">p (raw)</th>
                    <th scope="col" className="px-3 py-2 text-right">p (adjusted)</th>
                    <th scope="col" className="px-3 py-2 text-right">Top−bottom (return)</th>
                    <th scope="col" className="px-3 py-2 text-right">Cost-adjusted</th>
                    <th scope="col" className="px-3 py-2 text-right">Overlap ratio</th>
                    <th scope="col" className="px-3 py-2">Overlap</th>
                    <th scope="col" className="px-3 py-2">State</th>
                  </tr>
                </thead>
                <tbody>
                  {lagRows.map((r, i) => (
                    <tr key={i} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-mono">{r.horizon}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{r.entry_lag}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{r.observations}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(r.pearson)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(r.spearman)}</td>
                      <td className="px-3 py-1.5 text-right font-mono" title={r.p_value_note ?? undefined}>
                        {fmtP(r.spearman_p_value)}{r.p_value_note ? " ⚠" : ""}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtP(r.spearman_p_adjusted)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(r.top_minus_bottom)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(r.cost_adjusted_spread)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(r.overlap_ratio, 0)}</td>
                      <td className="px-3 py-1.5"><OverlapPill status={r.overlap_state} /></td>
                      <td className="px-3 py-1.5" title={r.reason ?? undefined}>{r.state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rawRows.some((r) => r.p_value_note) && (
              <p className="px-4 py-2 text-xs text-amber-700">
                ⚠ {rawRows.find((r) => r.p_value_note)?.p_value_note}
              </p>
            )}
          </>
        )}
      </div>

      {/* ---------------- decay summaries ---------------- */}
      {run.decay.length > 0 && (
        <div className="card p-4" data-testid="signal-decay-summary">
          <h3 className="text-sm font-semibold text-slate-700">Decay summaries</h3>
          {run.decay.map((d, i) => (
            <div key={i} className="mt-2 rounded-lg border border-slate-100 p-2.5 text-xs">
              <p className="font-semibold text-slate-700">{d.statistic}</p>
              <dl className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 md:grid-cols-4">
                <Field label="Horizons available" value={d.horizons_available} />
                <Field label="First sign change" value={d.first_sign_change_horizon ?? "none observed"} />
                <Field label="First below threshold"
                  value={d.absolute_threshold === null ? "no threshold configured"
                    : d.first_below_threshold_horizon ?? "never"} />
                <Field label="Largest |statistic| at horizon" value={`${fmtNum(d.max_absolute_statistic)} @ ${d.max_absolute_horizon ?? "—"}`} />
                <Field label="Half-life"
                  value={d.exponential_fit?.half_life !== null && d.exponential_fit?.half_life !== undefined
                    ? `${fmtNum(d.exponential_fit.half_life, 2)} ${d.exponential_fit.half_life_unit}`
                    : `unavailable — ${d.exponential_fit?.reason ?? "no fit"}`} />
              </dl>
              <p className="mt-1 text-slate-500">{d.note}</p>
              {d.exponential_fit && (
                <p className="mt-1 text-slate-400">{d.exponential_fit.convention}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ---------------- non-overlapping selection ---------------- */}
      {nonOverlapRows.length > 0 && (
        <div className="card overflow-hidden" data-testid="signal-non-overlap">
          <SectionHeader title="Deterministic non-overlapping selection"
            note="Earliest pair first, then the next pair whose entry is at or after the previous exit — a documented deterministic rule, not a sampling choice." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Horizon</th>
                  <th scope="col" className="px-3 py-2 text-right">Lag</th>
                  <th scope="col" className="px-3 py-2 text-right">Selected obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                  <th scope="col" className="px-3 py-2 text-right">p</th>
                  <th scope="col" className="px-3 py-2 text-right">Top−bottom</th>
                  <th scope="col" className="px-3 py-2">Overlap</th>
                </tr>
              </thead>
              <tbody>
                {nonOverlapRows.map((r, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-mono">{r.horizon}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{r.entry_lag}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{r.observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(r.spearman)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtP(r.spearman_p_value)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(r.top_minus_bottom)}</td>
                    <td className="px-3 py-1.5"><OverlapPill status={r.overlap_state} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- buckets ---------------- */}
      {buckets && buckets.length > 0 && (
        <div className="card overflow-hidden" data-testid="signal-buckets">
          <SectionHeader title="Bucket outcomes"
            note="Equal-count rank buckets over the configured score orientation; bucket 1 is the lowest configured score. Boundaries and counts are visible, empty buckets stay visible, and monotone means do not prove predictability." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Horizon</th>
                  <th scope="col" className="px-3 py-2 text-right">Lag</th>
                  <th scope="col" className="px-3 py-2">Scope</th>
                  <th scope="col" className="px-3 py-2 text-right">Bucket</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Score min ({signalUnit})</th>
                  <th scope="col" className="px-3 py-2 text-right">Score max ({signalUnit})</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean outcome</th>
                  <th scope="col" className="px-3 py-2 text-right">Median</th>
                  <th scope="col" className="px-3 py-2 text-right">Positive rate</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {buckets.map((b, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-mono">{b.horizon}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{b.entry_lag}</td>
                    <td className="px-3 py-1.5">{b.outcome_scope.replace(/_/g, " ")}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{b.bucket}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{b.observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(b.score_minimum)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(b.score_maximum)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(b.mean_outcome)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(b.median_outcome)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(b.positive_rate, 1)}</td>
                    <td className="px-3 py-1.5" title={b.reason ?? undefined}>{b.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- turnover ---------------- */}
      {turnover && turnover.length > 0 && (
        <div className="card overflow-hidden" data-testid="signal-turnover">
          <SectionHeader title="Reference turnover timeline"
            note={run.turnover_summary?.initial_policy_note ?? "Equal-weight top-bucket reference; one-way turnover = 0.5 × Σ|w_t − w_t−1|."} />
          {run.turnover_summary && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 px-4 py-3 text-xs md:grid-cols-5">
              <Field label="Rebalances" value={run.turnover_summary.rebalance_count} />
              <Field label="Mean one-way turnover" value={fmtPct(run.turnover_summary.mean_one_way_turnover, 1)} />
              <Field label="Max one-way turnover" value={fmtPct(run.turnover_summary.max_one_way_turnover, 1)} />
              <Field label="Mean Jaccard (top)" value={fmtNum(run.turnover_summary.mean_jaccard_top, 3)} />
              <Field label="Avg holding duration"
                value={run.turnover_summary.average_holding_duration === null ? "—"
                  : `${fmtNum(run.turnover_summary.average_holding_duration, 1)} ${run.turnover_summary.holding_duration_unit}`} />
            </dl>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Rebalance</th>
                  <th scope="col" className="px-3 py-2 text-right">Universe</th>
                  <th scope="col" className="px-3 py-2 text-right">Top entries</th>
                  <th scope="col" className="px-3 py-2 text-right">Top exits</th>
                  <th scope="col" className="px-3 py-2 text-right">Bottom entries</th>
                  <th scope="col" className="px-3 py-2 text-right">Bottom exits</th>
                  <th scope="col" className="px-3 py-2 text-right">Jaccard (top)</th>
                  <th scope="col" className="px-3 py-2 text-right">One-way turnover</th>
                  <th scope="col" className="px-3 py-2 text-right">Cost (reference ccy)</th>
                  <th scope="col" className="px-3 py-2">Cost state</th>
                </tr>
              </thead>
              <tbody>
                {turnover.slice(0, MAX_TURNOVER_ROWS).map((t, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-mono">{t.timestamp.slice(0, 10)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{t.universe_size}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{t.top_entries}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{t.top_exits}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{t.bottom_entries}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{t.bottom_exits}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(t.jaccard_top, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      {t.one_way_turnover === null ? "unavailable (no prior)" : fmtPct(t.one_way_turnover, 1)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(t.cost, 2)}</td>
                    <td className="px-3 py-1.5">{t.cost_state ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {turnover.length > MAX_TURNOVER_ROWS && (
              <p className="px-4 py-2 text-xs text-slate-500">
                Showing {MAX_TURNOVER_ROWS} of {turnover.length} rebalances — the rest are in the JSON export.
              </p>
            )}
          </div>
          {run.holding_overlap && (
            <div className="border-t border-slate-100 px-4 py-3 text-xs" data-testid="signal-holding-overlap">
              <p className="font-semibold text-slate-700">Holding-period overlap</p>
              <dl className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 md:grid-cols-4">
                <Field label="Max concurrent cohorts" value={run.holding_overlap.max_concurrent_cohorts ?? "—"} />
                <Field label="Avg concurrent cohorts" value={fmtNum(run.holding_overlap.average_concurrent_cohorts, 2)} />
                <Field label="Gross exposure (overlapping)" value={fmtNum(run.holding_overlap.gross_exposure_overlapping, 1)} />
                <Field label="Normalisation" value={run.holding_overlap.cohort_normalisation.replace(/_/g, " ")} />
              </dl>
              {run.holding_overlap.gross_exposure_note && (
                <p className="mt-1 text-slate-500">{run.holding_overlap.gross_exposure_note}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ---------------- cost ---------------- */}
      {run.cost && (
        <div className="card p-4" data-testid="signal-cost">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-700">Cost-adjusted reference (linked Phase 55 model)</h3>
            <CompletenessPill status={run.cost.completeness} />
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Reference notional" value={run.cost.reference_notional.toLocaleString()} />
            <Field label="Computable per-side bps" value={fmtNum(run.cost.per_side_bps_computable, 2)} />
            <Field label="Total cost (reference ccy)" value={fmtNum(run.cost.total_cost, 2)} />
            <Field label="Total cost return" value={fmtPct(run.cost.total_cost_return)} />
            <Field label="Costed rebalances" value={`${run.cost.costed_rebalances} (${run.cost.skipped_rebalances} skipped)`} />
            <Field label="Model fp" value={shortFp(run.cost.model_fingerprint)} mono />
          </dl>
          {run.cost.components.map((c) => (
            <p key={c.component} className="mt-1 text-xs text-slate-500">
              {c.component}: {c.model ?? "none"} — {c.state === "available"
                ? `${fmtNum(c.per_side_bps, 2)} bps per side${c.note ? ` (${c.note})` : ""}`
                : `unavailable — ${c.reason}`}
            </p>
          ))}
          <p className="mt-2 text-xs text-slate-400">{run.cost.convention}</p>
          {run.cost.spread_adjustment_convention && (
            <p className="mt-1 text-xs text-slate-400">{run.cost.spread_adjustment_convention}</p>
          )}
        </div>
      )}

      {/* ---------------- regimes ---------------- */}
      {regimes && regimes.length > 0 && (
        <div className="card overflow-hidden" data-testid="signal-regimes">
          <SectionHeader title="Diagnostics by stored regime"
            note={`Regimes come from stored Phase 54 assignments and are never recomputed. Fewer than ${rareThreshold} observations withholds the statistics. Differences between regimes are measurements, never permanent properties.`} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Regime</th>
                  <th scope="col" className="px-3 py-2">Horizon</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Pearson</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                  <th scope="col" className="px-3 py-2 text-right">Top−bottom</th>
                  <th scope="col" className="px-3 py-2 text-right">Overlap ratio</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {regimes.map((g, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {g.regime_label}
                      {g.rare && <span className="ml-1 text-[10px] uppercase text-amber-600">rare</span>}
                    </td>
                    <td className="px-3 py-1.5 font-mono">{g.horizon}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{g.observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(g.pearson)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(g.spearman)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(g.top_minus_bottom)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(g.overlap_ratio, 0)}</td>
                    <td className="px-3 py-1.5" title={g.reason ?? undefined}>{g.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- held-out ---------------- */}
      {run.held_out && (
        <div className="card p-4" data-testid="signal-heldout">
          <h3 className="text-sm font-semibold text-slate-700">Training versus held-out (linked validation split)</h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Split" value={run.held_out.split_label} />
            <Field label="Leakage clean" value={String(run.held_out.leakage_clean)} />
            <Field label="Training obs." value={run.held_out.training_observations} />
            <Field label="Held-out obs." value={run.held_out.held_out_observations} />
            <Field label="Purged obs." value={run.held_out.purged_observations} />
            <Field label="Embargoed obs." value={run.held_out.embargoed_observations} />
          </dl>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[640px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Scope</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Pearson</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                  <th scope="col" className="px-3 py-2 text-right">Top−bottom</th>
                </tr>
              </thead>
              <tbody>
                {(["training", "held_out", "full_sample"] as const).map((scope) => {
                  const block = run.held_out?.[scope] as Record<string, unknown> | undefined;
                  return (
                    <tr key={scope} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-medium text-slate-700">{scope.replace(/_/g, " ")}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{String(block?.observations ?? "—")}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(block?.pearson as number | null)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(block?.spearman as number | null)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(block?.top_minus_bottom as number | null)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">{run.held_out.note}</p>
        </div>
      )}

      {/* ---------------- factor residual ---------------- */}
      {run.factor_residual && (
        <div className="card p-4" data-testid="signal-factor-residual">
          <h3 className="text-sm font-semibold text-slate-700">Raw versus factor-residualised outcomes</h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Factor run" value={run.factor_residual.factor_run_name ?? "—"} />
            <Field label="State" value={run.factor_residual.state} />
            <Field label="Unmatched pairs" value={run.factor_residual.unmatched_pairs} />
            <Field label="Factor result fp" value={shortFp(run.factor_residual.result_fingerprint)} mono />
          </dl>
          {residualRows.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[560px] text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Scope</th>
                    <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                    <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                    <th scope="col" className="px-3 py-2 text-right">Top−bottom</th>
                  </tr>
                </thead>
                <tbody>
                  {[...decayRows.filter((r) => residualRows.some(
                    (x) => String(x.horizon) === String(r.horizon))),
                    ...residualRows].map((r, i) => (
                    <tr key={i} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5">{r.outcome_scope.replace(/_/g, " ")} · h{r.horizon}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{r.observations}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(r.spearman)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(r.top_minus_bottom)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-slate-500">{run.factor_residual.convention}</p>
          {run.factor_residual.reason && (
            <p className="mt-1 text-xs text-amber-700">{run.factor_residual.reason}</p>
          )}
        </div>
      )}

      {/* ---------------- bootstrap + multiple testing ---------------- */}
      {bootstrap && bootstrap.length > 0 && (
        <div className="card p-4" data-testid="signal-bootstrap">
          <h3 className="text-sm font-semibold text-slate-700">Bootstrap quantiles (seeded, deterministic)</h3>
          {bootstrap.map((b, i) => (
            <div key={i} className="mt-2 text-xs">
              <p className="font-medium text-slate-700">
                h{b.horizon} lag {b.entry_lag} · {b.statistic} · {b.method} · seed {b.seed} ·{" "}
                {b.valid_resamples}/{b.resamples} resamples
              </p>
              {b.state === "available" ? (
                <p className="font-mono text-slate-600">
                  observed {fmtNum(b.observed)} · {Object.entries(b.quantiles)
                    .map(([q, v]) => `q${q}=${fmtNum(v)}`).join(" · ")}
                </p>
              ) : (
                <p className="text-slate-500">unavailable — {b.reason}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {run.multiple_testing && (
        <div className="card p-4" data-testid="signal-multiple-testing">
          <h3 className="text-sm font-semibold text-slate-700">Multiple testing (Phase 53 corrections, reused)</h3>
          <p className="mt-1 text-xs text-slate-500">
            Family: {run.multiple_testing.family} · methods {run.multiple_testing.methods.join(", ")} ·
            alpha {run.multiple_testing.alpha} · {run.multiple_testing.hypotheses} hypothesis(es).
          </p>
          <p className="mt-1 text-xs text-slate-500">{run.multiple_testing.note}</p>
        </div>
      )}

      {/* ---------------- observations ---------------- */}
      {observations && observations.length > 0 && (
        <div className="card overflow-hidden" data-testid="signal-observations">
          <SectionHeader title="Stored signal observations"
            note="When each signal referred to and when it was available. An assumed availability (same_timestamp policy) is marked." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Entity</th>
                  <th scope="col" className="px-3 py-2">Timestamp</th>
                  <th scope="col" className="px-3 py-2">Available at</th>
                  <th scope="col" className="px-3 py-2 text-right">Value ({signalUnit})</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank</th>
                </tr>
              </thead>
              <tbody>
                {observations.slice(0, MAX_OBSERVATION_ROWS).map((o, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{o.entity_id}</td>
                    <td className="px-3 py-1.5 font-mono">{o.source_timestamp.slice(0, 10)}</td>
                    <td className="px-3 py-1.5 font-mono">
                      {o.available_at.slice(0, 10)}{o.availability_assumed ? " (assumed)" : ""}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(o.raw_value)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{o.rank_value === null ? "—" : fmtNum(o.rank_value, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {observations.length > MAX_OBSERVATION_ROWS && (
              <p className="px-4 py-2 text-xs text-slate-500">
                Showing {MAX_OBSERVATION_ROWS} of {observations.length} observations — the rest are in the JSON export.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ---------------- policy + fingerprints ---------------- */}
      <div className="card p-4" data-testid="signal-policy">
        <h3 className="text-sm font-semibold text-slate-700">Stored policy and identity</h3>
        <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-3">
          <Field label="Integrity" value={INTEGRITY_LABELS[run.integrity_status] ?? run.integrity_status} />
          <Field label="Overlap policy" value={String((run.horizon_policy as Record<string, unknown>)?.overlap_policy ?? "—")} />
          <Field label="Interval convention" value={String((run.horizon_policy as Record<string, unknown>)?.interval_convention ?? "—")} />
          <Field label="Signal fp" value={shortFp(run.signal_fingerprint)} mono />
          <Field label="Outcome fp" value={shortFp(run.outcome_fingerprint)} mono />
          <Field label="Universe fp" value={shortFp(run.universe_fingerprint)} mono />
          <Field label="Horizon fp" value={shortFp(run.horizon_fingerprint)} mono />
          <Field label="Analysis fp" value={shortFp(run.analysis_fingerprint)} mono />
          <Field label="Result fp" value={shortFp(run.result_fingerprint)} mono />
          <Field label="Dataset" value={
            (run.dataset_identity?.dataset_name as string | undefined) ?? "— (none linked)"} />
        </dl>
        {run.signal_diagnostics && (
          <p className="mt-2 text-xs text-slate-500">{run.signal_diagnostics.note}</p>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`text-slate-700 ${mono ? "font-mono text-[11px]" : ""}`}>{String(value ?? "—")}</dd>
    </div>
  );
}

function SectionHeader({ title, note }: { title: string; note: string }) {
  return (
    <div className="border-b border-slate-100 bg-slate-50 px-4 py-2">
      <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      <p className="mt-0.5 text-xs text-slate-500">{note}</p>
    </div>
  );
}

function DecayChart({ rows }: { rows: HorizonRow[] }) {
  const usable = rows.filter((r) => typeof r.horizon === "number"
    && r.spearman !== null);
  if (usable.length < 2) return null;
  const width = 720;
  const height = 150;
  const values = usable.map((r) => r.spearman as number);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;
  const x = (i: number) => (i / Math.max(1, usable.length - 1)) * (width - 60) + 40;
  const y = (v: number) => height - 24 - ((v - min) / span) * (height - 44);
  const points = usable.map((r, i) => `${x(i)},${y(r.spearman as number)}`).join(" ");
  return (
    <div className="overflow-x-auto px-4 pt-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
        aria-label="Rank IC by horizon (the table below carries the same values)"
        data-testid="decay-chart">
        <line x1="40" y1={y(0)} x2={width - 20} y2={y(0)} stroke="#cbd5e1" strokeWidth="1" />
        <polyline points={points} fill="none" stroke="#2563eb" strokeWidth="1.5" />
        {usable.map((r, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(r.spearman as number)} r="3" fill="#2563eb" />
            <text x={x(i)} y={height - 6} fontSize="10" fill="#64748b" textAnchor="middle">
              h{r.horizon}
            </text>
          </g>
        ))}
        <text x="4" y="14" fontSize="10" fill="#64748b">{max.toFixed(2)}</text>
        <text x="4" y={height - 26} fontSize="10" fill="#64748b">{min.toFixed(2)}</text>
      </svg>
    </div>
  );
}
