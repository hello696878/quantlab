"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type CoefficientRow,
  type ObservationRow,
  type PeriodRow,
  type RegimeRow,
  type RollingRow,
  type RunFull,
  type SensitivityRow,
  INTEGRITY_LABELS,
  MODE_LABELS,
  TIMING_LABELS,
  fmtNum,
  fmtP,
  fmtPct,
  fmtSci,
  getCoefficients,
  getObservations,
  getPeriods,
  getRegimes,
  getRolling,
  getSensitivity,
  getRun,
  markBaseline,
  shortFp,
} from "@/lib/factorDiagnostics";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import {
  CompletenessPill,
  IntegrityPill,
  RankPill,
  ReconciliationPill,
  StatusPill,
} from "@/components/FactorDiagnosticsShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onRefresh: (run: RunFull) => void;
  onOpenAttribution?: () => void;
  onOpenStress?: () => void;
  onOpenRegime?: () => void;
  onOpenValidation?: () => void;
  onOpenDataset?: () => void;
  onOpenExperiment?: () => void;
}

const MAX_PERIOD_ROWS = 40;
const MAX_OBSERVATION_ROWS = 30;

export default function FactorDiagnosticsDetail(props: Props) {
  const { run, onBack, onRefresh } = props;
  const [coefficients, setCoefficients] = useState<CoefficientRow[] | null>(null);
  const [periods, setPeriods] = useState<PeriodRow[] | null>(null);
  const [rolling, setRolling] = useState<RollingRow[] | null>(null);
  const [regimes, setRegimes] = useState<RegimeRow[] | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityRow[] | null>(null);
  const [observations, setObservations] = useState<ObservationRow[] | null>(null);
  const [rareThreshold, setRareThreshold] = useState<number>(10);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getCoefficients(run.id), getPeriods(run.id), getRolling(run.id),
      getRegimes(run.id), getSensitivity(run.id), getObservations(run.id),
    ])
      .then(([c, p, r, g, s, o]) => {
        if (cancelled) return;
        setCoefficients(c.items);
        setPeriods(p.items);
        setRolling(r.items);
        setRegimes(g.items);
        setRareThreshold(g.rare_threshold);
        setSensitivity(s.items);
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

  const factorIds = useMemo(() => run.factors.map((f) => f.factor_id), [run.factors]);
  const units = useMemo(
    () => Object.fromEntries(run.factors.map((f) => [f.factor_id, f.transformed_unit])),
    [run.factors],
  );

  return (
    <div className="space-y-4" data-testid="factor-diagnostics-detail">
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
        {props.onOpenAttribution && run.attribution_linkage && (
          <button type="button" onClick={props.onOpenAttribution}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Portfolio Attribution →
          </button>
        )}
        {props.onOpenRegime && run.regime_run_name && (
          <button type="button" onClick={props.onOpenRegime}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Regime Diagnostics →
          </button>
        )}
        {props.onOpenValidation && run.validation_run_name && (
          <button type="button" onClick={props.onOpenValidation}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Model Validation →
          </button>
        )}
        {props.onOpenStress && run.stress_run_name && (
          <button type="button" onClick={props.onOpenStress}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Open Portfolio Stress →
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
            <RankPill status={run.rank_status} />
            {run.is_baseline && (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                ★ baseline
              </span>
            )}
          </div>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
          <Field label="Target" value={`${run.target_id} · ${run.target_type.replace(/_/g, " ")}`} />
          <Field label="Target source" value={run.target_source.replace(/_/g, " ")} />
          <Field label="Analysis mode" value={MODE_LABELS[run.analysis_mode] ?? run.analysis_mode} />
          <Field label="Estimator" value={`${run.regression_method.toUpperCase()} · intercept ${run.intercept_policy}d`} />
          <Field label="Timing" value={TIMING_LABELS[run.timing_policy] ?? run.timing_policy} />
          <Field label="Vintage policy" value={run.vintage_policy.replace(/_/g, " ")} />
          <Field label="Return convention" value={`${run.return_convention} · ${run.return_frequency} · ${run.currency}`} />
          <Field label="Window" value={`${run.observation_start ?? "—"} → ${run.observation_end ?? "—"}`} />
          <Field label="Observations used" value={`${run.observation_count} (${run.excluded_period_count} excluded)`} />
          <Field label="Degrees of freedom" value={run.degrees_of_freedom ?? "unavailable"} />
        </dl>
        {run.error_message && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-800">
            Execution failed: {run.error_message}
          </p>
        )}
      </div>

      {run.warnings.length > 0 && (
        <div className="card p-4" data-testid="factor-warnings">
          <h3 className="text-sm font-semibold text-slate-700">Warnings ({run.warnings.length})</h3>
          <ul className="mt-2 space-y-1.5 text-sm text-amber-800">
            {run.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        </div>
      )}

      {/* ---------------- factor definitions ---------------- */}
      <div className="card overflow-hidden" data-testid="factor-definitions">
        <SectionHeader title="Factor definitions"
          note="Every factor states its unit, transformation formula, lag and availability rule. Nothing is inferred from a factor's name." />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-3 py-2">Factor</th>
                <th scope="col" className="px-3 py-2">Category</th>
                <th scope="col" className="px-3 py-2">Source unit</th>
                <th scope="col" className="px-3 py-2">Transformation</th>
                <th scope="col" className="px-3 py-2">Transformed unit</th>
                <th scope="col" className="px-3 py-2 text-right">Lag (periods)</th>
                <th scope="col" className="px-3 py-2">Availability</th>
                <th scope="col" className="px-3 py-2">Missing</th>
                <th scope="col" className="px-3 py-2">Winsorisation</th>
                <th scope="col" className="px-3 py-2">Definition fp</th>
              </tr>
            </thead>
            <tbody>
              {run.factors.map((f) => (
                <tr key={f.factor_id} className="border-b border-slate-50 last:border-0">
                  <td className="px-3 py-1.5 font-medium text-slate-700" title={f.description}>{f.factor_id}</td>
                  <td className="px-3 py-1.5">{f.category.replace(/_/g, " ")}</td>
                  <td className="px-3 py-1.5 font-mono">{f.unit}</td>
                  <td className="px-3 py-1.5 font-mono">{f.transformation}</td>
                  <td className="px-3 py-1.5 font-mono">{f.transformed_unit}</td>
                  <td className="px-3 py-1.5 text-right font-mono">{f.lag}</td>
                  <td className="px-3 py-1.5">{f.availability_policy.replace(/_/g, " ")}</td>
                  <td className="px-3 py-1.5">{f.missing_policy}</td>
                  <td className="px-3 py-1.5">{f.winsorisation_policy}</td>
                  <td className="px-3 py-1.5 font-mono text-[11px] text-slate-500">{shortFp(f.definition_fingerprint)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ---------------- coefficients ---------------- */}
      <div className="card overflow-hidden" data-testid="factor-coefficients">
        <SectionHeader title="Factor exposures"
          note={run.fit?.standard_error_assumptions ??
                "Standard errors are unavailable for this estimator."} />
        {!coefficients ? (
          <SkeletonTable rows={3} cols={6} caption="Loading coefficients…" />
        ) : (
          <>
            <CoefficientChart rows={coefficients} />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1180px] text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Factor</th>
                    <th scope="col" className="px-3 py-2">Exposure state</th>
                    <th scope="col" className="px-3 py-2 text-right">Coefficient</th>
                    <th scope="col" className="px-3 py-2">Unit</th>
                    <th scope="col" className="px-3 py-2 text-right">Std. error</th>
                    <th scope="col" className="px-3 py-2 text-right">t</th>
                    <th scope="col" className="px-3 py-2 text-right">p (raw)</th>
                    <th scope="col" className="px-3 py-2 text-right">p (Holm)</th>
                    <th scope="col" className="px-3 py-2 text-right">p (BH)</th>
                    <th scope="col" className="px-3 py-2 text-right">95% CI</th>
                    <th scope="col" className="px-3 py-2 text-right">VIF</th>
                    <th scope="col" className="px-3 py-2 text-right">Contribution Σ</th>
                    <th scope="col" className="px-3 py-2">Warning</th>
                  </tr>
                </thead>
                <tbody>
                  {run.intercept !== null && run.intercept !== undefined && (
                    <tr className="border-b border-slate-50 bg-slate-50/60">
                      <td className="px-3 py-1.5 font-medium text-slate-700">intercept</td>
                      <td className="px-3 py-1.5">model constant</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtSci(run.intercept)}</td>
                      <td className="px-3 py-1.5 font-mono">target return per period</td>
                      <td className="px-3 py-1.5 text-right" colSpan={9}>
                        the mean return this specification did not explain over this sample — not alpha
                      </td>
                    </tr>
                  )}
                  {coefficients.map((row) => (
                    <tr key={row.factor_id} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                      <td className="px-3 py-1.5">{row.exposure_state}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.coefficient)}</td>
                      <td className="px-3 py-1.5 font-mono text-[11px]">{row.coefficient_unit ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtSci(row.standard_error)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.t_statistic, 3)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtP(row.p_value)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtP(row.p_holm)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtP(row.p_bh)}</td>
                      <td className="px-3 py-1.5 text-right font-mono text-[11px]">
                        {row.confidence_lower === null || row.confidence_upper === null
                          ? "unavailable"
                          : `[${fmtNum(row.confidence_lower, 4)}, ${fmtNum(row.confidence_upper, 4)}]`}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {row.vif === null ? "unavailable" : fmtNum(row.vif, 2)}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtSci(row.contribution_sum)}</td>
                      <td className="px-3 py-1.5 text-amber-700">{row.warning ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {run.fit?.standard_error_note && (
              <p className="px-4 py-2 text-xs text-slate-500">{run.fit.standard_error_note}</p>
            )}
            {run.multiple_testing && (
              <p className="px-4 pb-3 text-xs text-slate-500">
                Multiple-testing family: {run.multiple_testing.family} · methods{" "}
                {run.multiple_testing.methods.join(", ")} · alpha {run.multiple_testing.alpha} ·{" "}
                {run.multiple_testing.hypotheses} hypothesis(es). Raw p-values are preserved; an adjusted
                p-value is still not evidence of causality.
              </p>
            )}
          </>
        )}
      </div>

      {/* ---------------- reconciliation ---------------- */}
      {run.summary && (
        <div className="card p-4" data-testid="factor-reconciliation">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-700">Return decomposition and reconciliation</h3>
            <ReconciliationPill status={run.summary.reconciliation_state} />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-3 lg:grid-cols-6">
            <Field label="Measured Σ (return)" value={fmtPct(run.summary.measured_return_sum, 4)} />
            <Field label="Intercept Σ (return)" value={fmtPct(run.summary.intercept_contribution_sum, 4)} />
            <Field label="Modelled Σ (return)" value={fmtPct(run.summary.modelled_return_sum, 4)} />
            <Field label="Residual Σ (return)" value={fmtPct(run.summary.residual_sum, 4)} />
            <Field label="Difference" value={fmtSci(run.summary.reconciliation_difference, 3)} />
            <Field label="Periods decomposed" value={`${run.summary.periods_decomposed} (${run.summary.periods_unavailable} unavailable)`} />
          </dl>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  <th scope="col" className="px-3 py-2 text-right">Contribution Σ (return)</th>
                </tr>
              </thead>
              <tbody>
                {factorIds.map((id) => (
                  <tr key={id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{id}</td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      {fmtPct(run.summary?.factor_contribution_sums?.[id] ?? null, 4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">{run.summary.convention}</p>
        </div>
      )}

      {/* ---------------- per-period rows ---------------- */}
      <div className="card overflow-hidden" data-testid="factor-periods">
        <SectionHeader title="Per-period decomposition"
          note="measured = intercept + Σ (exposure × factor value) + residual, checked every period against the estimator's own residual." />
        {!periods ? (
          <SkeletonTable rows={5} cols={6} caption="Loading periods…" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Period start</th>
                  <th scope="col" className="px-3 py-2">Known at</th>
                  <th scope="col" className="px-3 py-2 text-right">Measured</th>
                  <th scope="col" className="px-3 py-2 text-right">Intercept</th>
                  {factorIds.map((id) => (
                    <th key={id} scope="col" className="px-3 py-2 text-right">{id}</th>
                  ))}
                  <th scope="col" className="px-3 py-2 text-right">Modelled</th>
                  <th scope="col" className="px-3 py-2 text-right">Residual</th>
                  <th scope="col" className="px-3 py-2 text-right">Δ</th>
                  <th scope="col" className="px-3 py-2">State</th>
                  {periods.some((p) => p.membership) && (
                    <th scope="col" className="px-3 py-2">Split</th>
                  )}
                  {periods.some((p) => p.regime_label) && (
                    <th scope="col" className="px-3 py-2">Regime</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {periods.slice(0, MAX_PERIOD_ROWS).map((row) => (
                  <tr key={row.period_index} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-mono">{row.period_start.slice(0, 10)}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px] text-slate-500">
                      {(row.information_available_at ?? "—").slice(0, 10)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.measured_return, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.intercept_contribution, 4)}</td>
                    {factorIds.map((id) => (
                      <td key={id} className="px-3 py-1.5 text-right font-mono">
                        {fmtPct(row.factor_contributions?.[id] ?? null, 4)}
                      </td>
                    ))}
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.modelled_return, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.residual, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-[11px]">
                      {fmtSci(row.reconciliation_difference, 2)}
                    </td>
                    <td className="px-3 py-1.5">{row.reconciliation_state}</td>
                    {periods.some((p) => p.membership) && (
                      <td className="px-3 py-1.5">{row.membership ?? "—"}</td>
                    )}
                    {periods.some((p) => p.regime_label) && (
                      <td className="px-3 py-1.5">{row.regime_label ?? "—"}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {periods.length > MAX_PERIOD_ROWS && (
              <p className="px-4 py-2 text-xs text-slate-500">
                Showing the first {MAX_PERIOD_ROWS} of {periods.length} periods — the full series is in the
                JSON export.
              </p>
            )}
          </div>
        )}
      </div>

      {/* ---------------- multicollinearity ---------------- */}
      {run.multicollinearity && (
        <div className="card overflow-hidden" data-testid="factor-correlation">
          <SectionHeader title="Design conditioning and factor correlation"
            note={run.multicollinearity.note} />
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 px-4 py-3 text-xs md:grid-cols-4">
            <Field label="Rank" value={`${run.multicollinearity.rank ?? "—"} of ${run.multicollinearity.expected_rank}`} />
            <Field label="Condition number" value={fmtSci(run.multicollinearity.condition_number, 3)} />
            <Field label="Condition state" value={run.multicollinearity.condition_state} />
            <Field label="Singular values"
              value={run.multicollinearity.singular_values.map((v) => fmtSci(v, 2)).join(", ") || "—"} />
          </dl>
          <div className="overflow-x-auto px-4 pb-4">
            <table className="w-full min-w-[420px] text-xs">
              <caption className="pb-2 text-left text-[11px] text-slate-500">
                Pearson correlation over the estimation sample (table alternative to the heatmap;
                identical values, no colour-only meaning)
              </caption>
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  {run.multicollinearity.correlation.factor_ids.map((id) => (
                    <th key={id} scope="col" className="px-3 py-2 text-right">{id}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {run.multicollinearity.correlation.rows.map((row) => (
                  <tr key={row.factor_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                    {row.values.map((v, i) => (
                      <td key={i} className="px-3 py-1.5 text-right font-mono"
                        style={v === null ? undefined : {
                          backgroundColor: `rgba(${v >= 0 ? "37,99,235" : "220,38,38"},${Math.min(Math.abs(v), 1) * 0.18})`,
                        }}>
                        {v === null ? "unavailable" : v.toFixed(4)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {run.multicollinearity.constant_columns.length > 0 && (
            <p className="px-4 text-xs text-amber-700">
              Constant column(s): {run.multicollinearity.constant_columns.join(", ")} — no cross-period
              information, and nothing was dropped automatically.
            </p>
          )}
          {run.multicollinearity.duplicate_columns.length > 0 && (
            <p className="px-4 text-xs text-amber-700">
              Duplicate column(s):{" "}
              {run.multicollinearity.duplicate_columns
                .map((d) => `${d.factor_a} = ${d.factor_b}`)
                .join(", ")}
            </p>
          )}
          <p className="px-4 pb-3 pt-2 text-xs text-slate-500">{run.multicollinearity.condition_note}</p>
        </div>
      )}

      {/* ---------------- residual diagnostics ---------------- */}
      {run.residual_diagnostics && periods && (
        <div className="card p-4" data-testid="factor-residuals">
          <h3 className="text-sm font-semibold text-slate-700">Residual diagnostics</h3>
          <p className="mt-0.5 text-xs text-slate-500">{run.residual_diagnostics.note}</p>
          <ResidualChart periods={periods} />
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Mean" value={fmtSci(run.residual_diagnostics.mean, 3)} />
            <Field label="Std. deviation" value={fmtSci(run.residual_diagnostics.std, 3)} />
            <Field label="Skewness" value={fmtNum(run.residual_diagnostics.skewness, 4)} />
            <Field label="Excess kurtosis" value={fmtNum(run.residual_diagnostics.excess_kurtosis, 4)} />
            <Field label="Lag-1 autocorrelation" value={fmtNum(run.residual_diagnostics.lag1_autocorrelation, 4)} />
            <Field label="Concentration (HHI)" value={fmtNum(run.residual_diagnostics.concentration, 4)} />
            <Field label="Effective periods" value={fmtNum(run.residual_diagnostics.effective_periods, 2)} />
            <Field label="Cumulative drawdown" value={fmtSci(run.residual_diagnostics.cumulative_drawdown, 3)} />
          </dl>
          <p className="mt-2 text-[11px] text-slate-400">
            {run.residual_diagnostics.skewness_convention} · {run.residual_diagnostics.kurtosis_convention} ·{" "}
            {run.residual_diagnostics.drawdown_convention}
          </p>
          {run.residual_diagnostics.small_sample_note && (
            <p className="mt-1 text-xs text-amber-700">{run.residual_diagnostics.small_sample_note}</p>
          )}
          {run.residual_diagnostics.largest_absolute.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[420px] text-xs">
                <caption className="pb-1 text-left text-[11px] text-slate-500">Largest absolute residuals</caption>
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Period</th>
                    <th scope="col" className="px-3 py-2 text-right">Residual (return)</th>
                  </tr>
                </thead>
                <tbody>
                  {run.residual_diagnostics.largest_absolute.map((row, i) => (
                    <tr key={i} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5 font-mono">{(row.period_start ?? "—").slice(0, 10)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.residual, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---------------- rolling + stability ---------------- */}
      {rolling && rolling.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-rolling">
          <SectionHeader title={`Trailing rolling exposures (${rolling.length} windows)`}
            note={run.rolling_summary?.convention ??
                  "trailing windows only; a window never reads an observation after its own end index"} />
          <RollingChart rows={rolling} factorIds={factorIds} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Window</th>
                  <th scope="col" className="px-3 py-2">Decision at</th>
                  <th scope="col" className="px-3 py-2">Effective from</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  {factorIds.map((id) => (
                    <th key={id} scope="col" className="px-3 py-2 text-right">{id}</th>
                  ))}
                  <th scope="col" className="px-3 py-2 text-right">R²</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {rolling.map((row) => (
                  <tr key={row.window_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-mono">
                      {row.window_start.slice(0, 10)} → {row.window_end.slice(0, 10)}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-[11px]">{(row.decision_timestamp ?? "—").slice(0, 10)}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px]">{(row.effective_timestamp ?? "— (governs nothing yet)").slice(0, 10)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{row.observations}</td>
                    {factorIds.map((id) => (
                      <td key={id} className="px-3 py-1.5 text-right font-mono">
                        {row.coefficients?.[id] === undefined ? "unavailable" : fmtNum(row.coefficients[id], 4)}
                      </td>
                    ))}
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.r_squared, 4)}</td>
                    <td className="px-3 py-1.5">{row.status.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {run.stability.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-stability">
          <SectionHeader title="Exposure stability across windows"
            note="Sample counts are visible; no factor is classified stable or unstable, and nothing here is an investment classification." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  <th scope="col" className="px-3 py-2 text-right">Windows</th>
                  <th scope="col" className="px-3 py-2 text-right">Availability</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean</th>
                  <th scope="col" className="px-3 py-2 text-right">Median</th>
                  <th scope="col" className="px-3 py-2 text-right">Std. dev</th>
                  <th scope="col" className="px-3 py-2 text-right">Min</th>
                  <th scope="col" className="px-3 py-2 text-right">Max</th>
                  <th scope="col" className="px-3 py-2 text-right">Sign changes</th>
                  <th scope="col" className="px-3 py-2 text-right">Max jump</th>
                </tr>
              </thead>
              <tbody>
                {run.stability.map((row) => (
                  <tr key={row.factor_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{row.windows_available}/{row.windows_total}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.availability_rate, 1)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.mean, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.median, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.std, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.minimum, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.maximum, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{row.sign_changes ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.max_absolute_change, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-4 pb-3 text-xs text-slate-500">{run.stability[0]?.note}</p>
        </div>
      )}

      {/* ---------------- benchmark comparison ---------------- */}
      {run.exposure_comparison.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-benchmark">
          <SectionHeader title="Portfolio versus benchmark exposure"
            note="The same specification is fitted to the linked run's explicitly declared benchmark series. active = portfolio − benchmark." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  <th scope="col" className="px-3 py-2 text-right">Portfolio exposure</th>
                  <th scope="col" className="px-3 py-2 text-right">Benchmark exposure</th>
                  <th scope="col" className="px-3 py-2 text-right">Active exposure</th>
                  <th scope="col" className="px-3 py-2 text-right">Portfolio contribution</th>
                  <th scope="col" className="px-3 py-2 text-right">Benchmark contribution</th>
                  <th scope="col" className="px-3 py-2 text-right">Active contribution</th>
                </tr>
              </thead>
              <tbody>
                {run.exposure_comparison.map((row) => (
                  <tr key={row.factor_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.portfolio_exposure)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.benchmark_exposure)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.active_exposure)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.portfolio_contribution, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.benchmark_contribution, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.active_contribution, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-4 pb-3 text-xs text-slate-500">{run.exposure_comparison[0]?.note}</p>
        </div>
      )}

      {/* ---------------- regimes ---------------- */}
      {regimes && regimes.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-regimes">
          <SectionHeader title="Exposures by stored regime"
            note={`Regimes come from stored Phase 54 assignments and are never recomputed. Fewer than ${rareThreshold} observations withholds the conditional fit. Differences between regimes are measurements, not structural or causal claims.`} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Regime</th>
                  <th scope="col" className="px-3 py-2 text-right">Observations</th>
                  {factorIds.map((id) => (
                    <th key={id} scope="col" className="px-3 py-2 text-right">{id}</th>
                  ))}
                  <th scope="col" className="px-3 py-2 text-right">R²</th>
                  <th scope="col" className="px-3 py-2 text-right">Measured Σ</th>
                  <th scope="col" className="px-3 py-2 text-right">Residual Σ</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {regimes.map((row) => (
                  <tr key={row.regime_label} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {row.regime_label}
                      {row.rare && <span className="ml-1 text-[10px] uppercase text-amber-600">rare</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">{row.observations}</td>
                    {factorIds.map((id) => (
                      <td key={id} className="px-3 py-1.5 text-right font-mono">
                        {row.coefficients?.[id] === undefined ? "withheld" : fmtNum(row.coefficients[id], 4)}
                      </td>
                    ))}
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.r_squared, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.measured_return_sum, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.residual_sum, 4)}</td>
                    <td className="px-3 py-1.5" title={row.reason ?? undefined}>{row.status.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- stress linkage ---------------- */}
      {run.stress_linkage && (
        <div className="card overflow-hidden" data-testid="factor-stress">
          <SectionHeader title="Exposure-implied factor shock"
            note={run.stress_linkage.formula} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  <th scope="col" className="px-3 py-2 text-right">Supplied shock (factor unit)</th>
                  <th scope="col" className="px-3 py-2 text-right">Measured exposure</th>
                  <th scope="col" className="px-3 py-2 text-right">Implied contribution (return)</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {run.stress_linkage.rows.map((row) => (
                  <tr key={row.factor_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.shock, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.exposure)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(row.contribution, 4)}</td>
                    <td className="px-3 py-1.5">{row.state.replace(/_/g, " ")}</td>
                  </tr>
                ))}
                <tr className="bg-slate-50/60">
                  <td className="px-3 py-1.5 font-semibold text-slate-700">total</td>
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5 text-right font-mono font-semibold">
                    {fmtPct(run.stress_linkage.total_contribution, 4)}
                  </td>
                  <td className="px-3 py-1.5" />
                </tr>
              </tbody>
            </table>
          </div>
          <p className="px-4 py-2 text-xs text-slate-500">{run.stress_linkage.residual_note}</p>
          <p className="px-4 pb-3 text-xs text-slate-500">{run.stress_linkage.comparability_warning}</p>
        </div>
      )}

      {/* ---------------- attribution linkage ---------------- */}
      {run.attribution_linkage && (
        <div className="card p-4" data-testid="factor-attribution">
          <h3 className="text-sm font-semibold text-slate-700">Performance-attribution linkage</h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Attribution run" value={run.attribution_linkage.attribution_run_name ?? "—"} />
            <Field label="Series" value={run.attribution_linkage.column.replace(/_/g, " ")} />
            <Field label="Measured Σ" value={fmtPct(run.attribution_linkage.measured_return_sum, 4)} />
            <Field label="Factor-model Σ" value={fmtPct(run.attribution_linkage.modelled_return_sum, 4)} />
            <Field label="Residual Σ" value={fmtPct(run.attribution_linkage.residual_sum, 4)} />
            <Field label="Difference" value={fmtSci(run.attribution_linkage.reconciliation_difference, 3)} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">{run.attribution_linkage.note}</p>
          <p className="mt-1 text-xs text-slate-500">{run.attribution_linkage.cost_note}</p>
        </div>
      )}

      {/* ---------------- held-out ---------------- */}
      {run.held_out && (
        <div className="card p-4" data-testid="factor-heldout">
          <h3 className="text-sm font-semibold text-slate-700">Held-out evaluation</h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Split" value={run.held_out.split_label ?? "—"} />
            <Field label="Leakage clean" value={String(run.held_out.leakage_clean)} />
            <Field label="Training obs." value={run.held_out.training_observations} />
            <Field label="Held-out obs." value={run.held_out.held_out_observations} />
            <Field label="Purged obs." value={run.held_out.purged_observations} />
            <Field label="Embargoed obs." value={run.held_out.embargoed_observations} />
            <Field label="Training R²" value={fmtNum(run.held_out.training_r_squared, 6)} />
            <Field label="Held-out R²" value={fmtNum(run.held_out.r_squared, 6)} />
            <Field label="Training RMSE" value={fmtSci(run.held_out.training_rmse, 3)} />
            <Field label="Held-out RMSE" value={fmtSci(run.held_out.rmse, 3)} />
            <Field label="Held-out correlation" value={fmtNum(run.held_out.correlation, 4)} />
            <Field label="Held-out residual σ" value={fmtSci(run.held_out.residual_std, 3)} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">{run.held_out.r_squared_formula}</p>
          <p className="mt-1 text-xs text-slate-500">{run.held_out.note}</p>
          {run.held_out.reason && <p className="mt-1 text-xs text-amber-700">{run.held_out.reason}</p>}
        </div>
      )}

      {/* ---------------- sensitivity ---------------- */}
      {sensitivity && sensitivity.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-sensitivity">
          <SectionHeader title={`Sensitivity scenarios (${sensitivity.length})`}
            note="One stated assumption changes per scenario. No scenario is labelled best, optimal or recommended, and no hyper-parameter is selected automatically." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Scenario</th>
                  <th scope="col" className="px-3 py-2">What changed</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  {factorIds.map((id) => (
                    <th key={id} scope="col" className="px-3 py-2 text-right">{id}</th>
                  ))}
                  <th scope="col" className="px-3 py-2 text-right">R²</th>
                  <th scope="col" className="px-3 py-2 text-right">RMSE</th>
                  <th scope="col" className="px-3 py-2 text-right">Cond.</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {sensitivity.map((row) => (
                  <tr key={row.scenario_index}
                    className={`border-b border-slate-50 last:border-0 ${row.is_base ? "bg-slate-50/60" : ""}`}>
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {row.label}
                      {row.is_base && <span className="ml-1 text-[10px] uppercase text-slate-500">base</span>}
                    </td>
                    <td className="px-3 py-1.5">{row.description}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{row.observations ?? "—"}</td>
                    {factorIds.map((id) => (
                      <td key={id} className="px-3 py-1.5 text-right font-mono">
                        {row.coefficients?.[id] === undefined ? "not in scenario" : fmtNum(row.coefficients[id], 4)}
                      </td>
                    ))}
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.r_squared, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtSci(row.root_mean_squared_error, 2)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtSci(row.condition_number, 2)}</td>
                    <td className="px-3 py-1.5" title={row.reason ?? undefined}>
                      {row.status}{row.regression_method === "ridge" ? " · ridge" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- observations ---------------- */}
      {observations && observations.length > 0 && (
        <div className="card overflow-hidden" data-testid="factor-observations">
          <SectionHeader title="Aligned factor observations"
            note="Which observation fed each period, when it referred to, and when it could have been known." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Factor</th>
                  <th scope="col" className="px-3 py-2">Observation</th>
                  <th scope="col" className="px-3 py-2">Refers to</th>
                  <th scope="col" className="px-3 py-2">Knowable at</th>
                  <th scope="col" className="px-3 py-2">Used for period</th>
                  <th scope="col" className="px-3 py-2 text-right">Transformed value</th>
                  <th scope="col" className="px-3 py-2">Unit</th>
                  <th scope="col" className="px-3 py-2">Vintage</th>
                </tr>
              </thead>
              <tbody>
                {observations.slice(0, MAX_OBSERVATION_ROWS).map((row, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{row.factor_id}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px]">{row.observation_id}</td>
                    <td className="px-3 py-1.5 font-mono">{row.source_timestamp.slice(0, 10)}</td>
                    <td className="px-3 py-1.5 font-mono">{(row.knowable_at ?? "—").slice(0, 10)}</td>
                    <td className="px-3 py-1.5 font-mono">{row.effective_timestamp.slice(0, 10)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(row.transformed_value)}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px]">{units[row.factor_id] ?? row.unit}</td>
                    <td className="px-3 py-1.5">{row.vintage_state.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {observations.length > MAX_OBSERVATION_ROWS && (
              <p className="px-4 py-2 text-xs text-slate-500">
                Showing {MAX_OBSERVATION_ROWS} of {observations.length} aligned observations — the rest are in
                the JSON export.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ---------------- policy + fingerprints ---------------- */}
      <div className="card p-4" data-testid="factor-policy">
        <h3 className="text-sm font-semibold text-slate-700">Stored policy and identity</h3>
        <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-3">
          <Field label="Integrity" value={INTEGRITY_LABELS[run.integrity_status] ?? run.integrity_status} />
          <Field label="Rank policy" value={run.rank_policy} />
          <Field label="Reconciliation" value={run.reconciliation_status ?? "unavailable"} />
          <Field label="Target fp" value={shortFp(run.target_fingerprint)} mono />
          <Field label="Observation fp" value={shortFp(run.observation_fingerprint)} mono />
          <Field label="Model policy fp" value={shortFp(run.model_policy_fingerprint)} mono />
          <Field label="Configuration fp" value={shortFp(run.configuration_fingerprint)} mono />
          <Field label="Result fp" value={shortFp(run.result_fingerprint)} mono />
          <Field label="Dataset" value={
            (run.dataset_identity?.dataset_name as string | undefined) ?? "— (none linked)"} />
        </dl>
        {run.deferred && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs text-slate-600">
            <p className="font-semibold">Deferred in v1 (stated reasons, nothing silently approximated)</p>
            <ul className="mt-1 space-y-1">
              {Object.entries((run.deferred.analysis_modes ?? {}) as Record<string, string>).map(([k, v]) => (
                <li key={k}>• {k.replace(/_/g, " ")}: {v}</li>
              ))}
              {typeof run.deferred.robust_standard_errors === "string" && (
                <li>• robust standard errors: {run.deferred.robust_standard_errors}</li>
              )}
              {typeof run.deferred.winsorisation === "string" && (
                <li>• winsorisation: {run.deferred.winsorisation}</li>
              )}
            </ul>
          </div>
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

function CoefficientChart({ rows }: { rows: CoefficientRow[] }) {
  const values = rows.map((r) => r.coefficient ?? 0);
  const max = Math.max(1e-12, ...values.map((v) => Math.abs(v)));
  const width = 640;
  const rowHeight = 26;
  const height = Math.max(rowHeight, rows.length * rowHeight);
  const mid = width / 2;
  return (
    <div className="overflow-x-auto px-4 pt-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
        aria-label="Factor coefficients (bars left of centre are negative)"
        data-testid="coefficient-chart">
        <line x1={mid} y1="0" x2={mid} y2={height} stroke="#cbd5e1" strokeWidth="1" />
        {rows.map((row, i) => {
          const value = row.coefficient ?? 0;
          const w = (Math.abs(value) / max) * (mid - 60);
          return (
            <g key={row.factor_id}>
              <rect x={value >= 0 ? mid : mid - w} y={i * rowHeight + 6}
                width={Math.max(w, 1)} height={rowHeight - 12}
                fill={value >= 0 ? "#2563eb" : "#dc2626"} opacity="0.75" />
              <text x={4} y={i * rowHeight + rowHeight / 2 + 4} fontSize="11" fill="#475569">
                {row.factor_id}
              </text>
              <text x={width - 4} y={i * rowHeight + rowHeight / 2 + 4} fontSize="11" fill="#475569"
                textAnchor="end">
                {fmtNum(row.coefficient, 4)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function RollingChart({ rows, factorIds }: { rows: RollingRow[]; factorIds: string[] }) {
  const usable = rows.filter((r) => r.status === "estimated");
  if (usable.length < 2) return null;
  const width = 720;
  const height = 160;
  const palette = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626"];
  const all = factorIds.flatMap((id) =>
    usable.map((r) => r.coefficients?.[id]).filter((v): v is number => typeof v === "number"));
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const x = (i: number) => (i / Math.max(1, usable.length - 1)) * (width - 40) + 30;
  const y = (v: number) => height - 20 - ((v - min) / span) * (height - 40);
  return (
    <div className="overflow-x-auto px-4 pt-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
        aria-label="Rolling coefficient by window (table below carries the same values)"
        data-testid="rolling-chart">
        <line x1="30" y1={height - 20} x2={width - 10} y2={height - 20} stroke="#cbd5e1" strokeWidth="1" />
        {factorIds.map((id, k) => {
          const points = usable
            .map((r, i) => {
              const v = r.coefficients?.[id];
              return typeof v === "number" ? `${x(i)},${y(v)}` : null;
            })
            .filter(Boolean)
            .join(" ");
          return points ? (
            <polyline key={id} points={points} fill="none"
              stroke={palette[k % palette.length]} strokeWidth="1.5" />
          ) : null;
        })}
        <text x="4" y="12" fontSize="10" fill="#64748b">{max.toFixed(3)}</text>
        <text x="4" y={height - 24} fontSize="10" fill="#64748b">{min.toFixed(3)}</text>
      </svg>
    </div>
  );
}

function ResidualChart({ periods }: { periods: PeriodRow[] }) {
  const values = periods
    .map((p) => p.residual)
    .filter((v): v is number => typeof v === "number");
  if (values.length < 2) return null;
  const width = 720;
  const height = 120;
  const max = Math.max(1e-12, ...values.map((v) => Math.abs(v)));
  const mid = height / 2;
  const barWidth = Math.max(1, (width - 20) / values.length - 1);
  return (
    <div className="mt-3 overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
        aria-label="Residual by period (bars below the centre line are negative)"
        data-testid="residual-chart">
        <line x1="10" y1={mid} x2={width - 10} y2={mid} stroke="#cbd5e1" strokeWidth="1" />
        {values.map((v, i) => {
          const h = (Math.abs(v) / max) * (mid - 8);
          return (
            <rect key={i} x={10 + i * (barWidth + 1)} y={v >= 0 ? mid - h : mid}
              width={barWidth} height={Math.max(h, 0.5)}
              fill={v >= 0 ? "#2563eb" : "#dc2626"} opacity="0.7" />
          );
        })}
      </svg>
    </div>
  );
}
