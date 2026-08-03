"use client";

import { useEffect, useMemo, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type BootstrapRow,
  type CombinedObservation,
  type ComponentRow,
  type HorizonRow,
  type PairwiseRow,
  type RegimeRow,
  type RunFull,
  type SensitivityRow,
  ALIGNMENT_LABELS,
  MODE_LABELS,
  fmtNum,
  fmtP,
  fmtPct,
  getBootstrap,
  getComponents,
  getHorizons,
  getPairwise,
  getRegimes,
  getRun,
  getSensitivity,
  markBaseline,
  shortFp,
} from "@/lib/signalEnsemble";
import { toast } from "@/lib/toast";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import {
  CompletenessPill,
  IntegrityPill,
  ReconciliationPill,
  StatusPill,
} from "@/components/SignalEnsembleShared";

interface Props {
  run: RunFull;
  onBack: () => void;
  onNav?: (view: string) => void;
}

export default function SignalEnsembleDetail({ run: initial, onBack, onNav }: Props) {
  const [run, setRun] = useState<RunFull>(initial);
  const [pairwise, setPairwise] = useState<PairwiseRow[] | null>(null);
  const [observations, setObservations] = useState<CombinedObservation[] | null>(null);
  const [components, setComponents] = useState<ComponentRow[] | null>(null);
  const [horizons, setHorizons] = useState<HorizonRow[] | null>(null);
  const [regimes, setRegimes] = useState<RegimeRow[] | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapRow[] | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityRow[] | null>(null);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getPairwise(run.id), getComponents(run.id), getHorizons(run.id),
      getRegimes(run.id), getBootstrap(run.id), getSensitivity(run.id),
    ])
      .then(([pw, comp, hor, reg, boot, sen]) => {
        if (cancelled) return;
        setPairwise(pw.items);
        setObservations(comp.observations);
        setComponents(comp.components);
        setHorizons(hor.items);
        setRegimes(reg.items);
        setBootstrap(boot.items);
        setSensitivity(sen.items);
      })
      .catch((err) => toast.error("Couldn’t load run details",
        classifyApiError(err).message));
    return () => {
      cancelled = true;
    };
  }, [run.id]);

  async function handleBaseline() {
    setMarking(true);
    try {
      const updated = await markBaseline(run.id);
      setRun(updated);
      toast.success("Baseline set",
        "This run is now the comparison reference for its exact scope.");
    } catch (err) {
      toast.error("Baseline rejected", classifyApiError(err).message);
    } finally {
      setMarking(false);
    }
  }

  const strictPairs = useMemo(
    () => (pairwise ?? []).filter(
      (p) => p.alignment_mode === "strict_intersection"),
    [pairwise]);
  const completePairs = useMemo(
    () => (pairwise ?? []).filter(
      (p) => p.alignment_mode === "pairwise_complete"),
    [pairwise]);
  const combinationRows = useMemo(
    () => (horizons ?? []).filter((h) => h.scope === "combination"),
    [horizons]);
  const componentRows = useMemo(
    () => (horizons ?? []).filter((h) => h.scope === "component"),
    [horizons]);

  return (
    <div className="space-y-4" data-testid="ensemble-detail">
      {/* ---------------- header ---------------- */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={onBack}
                className="rounded-md border border-slate-200 px-2.5 py-1 text-sm text-slate-600 hover:bg-slate-50">
                ← Back to runs
              </button>
              <h2 className="text-lg font-semibold text-slate-800">{run.name}</h2>
              <StatusPill status={run.status} />
              <IntegrityPill status={run.integrity_status} />
              <CompletenessPill status={run.completeness_status} />
              <ReconciliationPill state={run.reconciliation?.state} />
              {run.is_baseline && (
                <span className="rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                  ★ baseline
                </span>
              )}
            </div>
            {run.description && (
              <p className="mt-2 max-w-3xl text-xs leading-relaxed text-slate-500">
                {run.description}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={handleBaseline} disabled={marking}
              className="rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50">
              Mark as comparison baseline
            </button>
            {onNav && (
              <>
                <button type="button" onClick={() => onNav("signaldecay")}
                  className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                  Signal Decay Lab →
                </button>
                <button type="button" onClick={() => onNav("costdiagnostics")}
                  className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                  Cost Lab →
                </button>
                <button type="button" onClick={() => onNav("regimediagnostics")}
                  className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                  Regime Lab →
                </button>
              </>
            )}
          </div>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
          <Field label="Combination mode"
            value={MODE_LABELS[run.combination_mode] ?? run.combination_mode} />
          <Field label="Alignment"
            value={ALIGNMENT_LABELS[run.alignment_policy] ?? run.alignment_policy} />
          <Field label="Signals × entities"
            value={`${run.signal_count} × ${run.entity_count}`} />
          <Field label="Stored observations" value={run.observation_count} />
          <Field label="Strict-intersection keys"
            value={run.strict_intersection_count} />
          <Field label="Combined coverage"
            value={fmtPct(run.combination_coverage, 1)} />
          <Field label="Window"
            value={`${run.observation_start ?? "—"} → ${run.observation_end ?? "—"}`} />
          <Field label="Frequency" value={run.frequency} />
        </dl>
        {run.error_message && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-800">
            Execution failed: {run.error_message}
          </p>
        )}
      </div>

      {run.warnings.length > 0 && (
        <div className="card p-4" data-testid="ensemble-warnings">
          <h3 className="text-sm font-semibold text-slate-700">
            Warnings ({run.warnings.length})
          </h3>
          <ul className="mt-2 space-y-1.5 text-sm text-amber-800">
            {run.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        </div>
      )}

      {/* ---------------- signals + missingness ---------------- */}
      <div className="card overflow-hidden" data-testid="ensemble-missingness">
        <SectionHeader title="Signals, orientation and missingness"
          note="Missing observations are disclosed, never filled: no forward fill, no interpolation, no zero or mean imputation, no row-number alignment." />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-3 py-2">Signal</th>
                <th scope="col" className="px-3 py-2">Unit</th>
                <th scope="col" className="px-3 py-2">Direction</th>
                <th scope="col" className="px-3 py-2">Tie policy</th>
                <th scope="col" className="px-3 py-2">Orientation</th>
                <th scope="col" className="px-3 py-2">Normalisation</th>
                <th scope="col" className="px-3 py-2 text-right">Stored</th>
                <th scope="col" className="px-3 py-2 text-right">Null</th>
                <th scope="col" className="px-3 py-2 text-right">Absent</th>
                <th scope="col" className="px-3 py-2 text-right">Coverage</th>
                <th scope="col" className="px-3 py-2">Definition fp</th>
              </tr>
            </thead>
            <tbody>
              {run.definitions.map((d) => {
                const miss = run.missingness?.per_signal.find(
                  (s) => s.signal_id === d.signal_id);
                return (
                  <tr key={d.signal_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{d.signal_id}</td>
                    <td className="px-3 py-1.5">unit {String(d.definition.unit ?? "—")}</td>
                    <td className="px-3 py-1.5">{String(d.definition.direction ?? "—").replace(/_/g, " ")}</td>
                    <td className="px-3 py-1.5">{String(d.definition.tie_policy ?? "—")}</td>
                    <td className="px-3 py-1.5">{d.orientation.replace(/_/g, " ")}</td>
                    <td className="px-3 py-1.5">{String((d.normalisation as { mode?: string }).mode ?? "none")}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{d.stored_observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{miss?.stored_null ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{miss?.absent ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(d.coverage, 1)}</td>
                    <td className="px-3 py-1.5 font-mono text-slate-500"
                      title={d.definition_fingerprint}>{shortFp(d.definition_fingerprint)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {run.missingness && (
          <p className="px-4 py-2 text-xs text-slate-500">
            Union keys {run.missingness.union_keys} · strict intersection{" "}
            {run.missingness.strict_intersection_keys} (
            {fmtPct(run.missingness.strict_intersection_coverage, 1)} of the union).
          </p>
        )}
      </div>

      {/* ---------------- pairwise ---------------- */}
      <div className="card overflow-hidden" data-testid="ensemble-pairwise">
        <SectionHeader title="Pairwise similarity"
          note="Every row carries its own overlap count; constants and thin overlap stay unavailable with reasons, and no correlation threshold marks signals duplicates." />
        {!pairwise ? (
          <SkeletonTable rows={4} cols={8} caption="Loading pairwise rows…" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Pair</th>
                  <th scope="col" className="px-3 py-2">Alignment</th>
                  <th scope="col" className="px-3 py-2 text-right">Overlap</th>
                  <th scope="col" className="px-3 py-2 text-right">Pearson</th>
                  <th scope="col" className="px-3 py-2 text-right">Spearman</th>
                  <th scope="col" className="px-3 py-2 text-right">p (raw)</th>
                  <th scope="col" className="px-3 py-2 text-right">p (adjusted)</th>
                  <th scope="col" className="px-3 py-2 text-right">Sign agr.</th>
                  <th scope="col" className="px-3 py-2 text-right">Exact bucket agr.</th>
                  <th scope="col" className="px-3 py-2 text-right">Top Jaccard</th>
                  <th scope="col" className="px-3 py-2 text-right">Both-upper tails</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {(pairwise ?? []).map((p, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {p.signal_a} · {p.signal_b}
                    </td>
                    <td className="px-3 py-1.5">{ALIGNMENT_LABELS[p.alignment_mode] ?? p.alignment_mode}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{p.overlap_count}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(p.pearson)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(p.spearman)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtP(p.spearman_p)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtP(p.spearman_p_adjusted)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(p.sign_agreement_rate, 0)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      {fmtPct(p.agreement?.exact_agreement_rate, 0)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      {fmtNum(p.agreement?.top_bucket_jaccard, 2)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      {p.tails?.both_upper_count ?? "—"}
                    </td>
                    <td className="px-3 py-1.5" title={p.reason ?? undefined}>{p.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {completePairs.length > 0 && (
          <p className="px-4 py-2 text-xs text-amber-700">
            ⚠ pairwise-complete rows use pair-specific overlaps; matrix
            diagnostics below use only the strict intersection.
          </p>
        )}
      </div>

      {/* ---------------- matrix + diagnostics ---------------- */}
      {run.matrix && (
        <div className="card overflow-hidden" data-testid="ensemble-matrix">
          <SectionHeader title={`Similarity matrix (${run.matrix.method}, strict intersection)`}
            note={run.distance?.note ?? ""} />
          <div className="overflow-x-auto p-4">
            <table className="text-xs">
              <thead>
                <tr>
                  <th scope="col" className="px-2 py-1" />
                  {run.matrix.signal_ids.map((s) => (
                    <th key={s} scope="col" className="px-2 py-1 text-right font-semibold text-slate-500">{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {run.matrix.signal_ids.map((rowId, i) => (
                  <tr key={rowId}>
                    <th scope="row" className="px-2 py-1 text-left font-semibold text-slate-500">{rowId}</th>
                    {run.matrix!.signal_ids.map((colId, j) => {
                      const value = run.matrix!.cells[i][j];
                      return (
                        <td key={colId}
                          className={`px-2 py-1 text-right font-mono ${
                            value === null ? "text-amber-600" : "text-slate-700"}`}>
                          {value === null ? "unavailable" : value.toFixed(3)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {run.matrix.unavailable_cells.length > 0 && (
            <p className="px-4 pb-3 text-xs text-amber-700">
              ⚠ {run.matrix.unavailable_cells.length} cell(s) unavailable — matrix
              diagnostics are withheld rather than imputed.
            </p>
          )}
        </div>
      )}

      {run.matrix_diagnostics && (
        <div className="card p-4" data-testid="ensemble-diagnostics">
          <h3 className="text-sm font-semibold text-slate-700">
            Redundancy and matrix concentration (descriptive)
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Mean |correlation|"
              value={fmtNum(run.redundancy?.mean_absolute_correlation, 4)} />
            <Field label="Median |correlation|"
              value={fmtNum(run.redundancy?.median_absolute_correlation, 4)} />
            <Field label="Max |correlation|"
              value={fmtNum(run.redundancy?.max_absolute_correlation, 4)} />
            <Field label="Avg sign agreement"
              value={fmtPct(run.redundancy?.average_sign_agreement, 0)} />
            <Field label="Matrix rank"
              value={run.matrix_diagnostics.matrix_rank ?? "—"} />
            <Field label="Condition number"
              value={run.matrix_diagnostics.condition_number !== null
                ? fmtNum(run.matrix_diagnostics.condition_number, 2)
                : `unavailable — ${run.matrix_diagnostics.condition_number_note ?? "undefined"}`} />
            <Field label="Top eigenvalue share"
              value={fmtPct(run.matrix_diagnostics.eigenvalue_concentration_top, 1)} />
            <Field label="Effective signal count"
              value={run.matrix_diagnostics.effective_signal_count !== null
                ? fmtNum(run.matrix_diagnostics.effective_signal_count, 3)
                : `unavailable — ${run.matrix_diagnostics.reason ?? ""}`} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            {run.matrix_diagnostics.effective_signal_count_note}
          </p>
          <p className="mt-1 text-xs text-slate-500">{run.redundancy?.note}</p>
        </div>
      )}

      {/* ---------------- clustering ---------------- */}
      {run.clustering && (
        <div className="card p-4" data-testid="ensemble-clustering">
          <h3 className="text-sm font-semibold text-slate-700">
            Hierarchical clustering ({run.clustering.linkage} linkage,
            threshold {fmtNum(run.clustering.threshold, 2)})
          </h3>
          {run.clustering.state === "available" ? (
            <>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[420px] text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                      <th scope="col" className="px-3 py-2">Signal</th>
                      <th scope="col" className="px-3 py-2 text-right">Cluster</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(run.clustering.clusters ?? []).map((c) => (
                      <tr key={c.signal_id} className="border-b border-slate-50 last:border-0">
                        <td className="px-3 py-1.5 font-medium text-slate-700">{c.signal_id}</td>
                        <td className="px-3 py-1.5 text-right font-mono">{c.cluster}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {run.clustering.cluster_count} cluster(s) at the explicit
                threshold; leaf order {run.clustering.leaf_order?.join(" · ")}.
              </p>
            </>
          ) : (
            <p className="mt-2 text-xs text-amber-700">
              unavailable — {run.clustering.reason}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-500">{run.clustering.note}</p>
        </div>
      )}

      {/* ---------------- components ---------------- */}
      <div className="card overflow-hidden" data-testid="ensemble-components">
        <SectionHeader title="Combined observations and component contributions"
          note={run.reconciliation?.note ?? ""} />
        {!observations || !components ? (
          <SkeletonTable rows={4} cols={8} caption="Loading components…" />
        ) : (
          <>
            <div className="px-4 py-2 text-xs text-slate-500">
              {run.contribution_rows_stored} of {run.contribution_rows_total}{" "}
              contribution rows stored (deterministic sample; reconciliation
              verified over ALL observations) · reconciliation{" "}
              <ReconciliationPill state={run.reconciliation?.state} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <th scope="col" className="px-3 py-2">Entity</th>
                    <th scope="col" className="px-3 py-2">Timestamp</th>
                    <th scope="col" className="px-3 py-2">Signal</th>
                    <th scope="col" className="px-3 py-2 text-right">Raw</th>
                    <th scope="col" className="px-3 py-2 text-right">Oriented</th>
                    <th scope="col" className="px-3 py-2 text-right">Normalised</th>
                    <th scope="col" className="px-3 py-2 text-right">Configured w</th>
                    <th scope="col" className="px-3 py-2 text-right">Effective w</th>
                    <th scope="col" className="px-3 py-2 text-right">Contribution</th>
                    <th scope="col" className="px-3 py-2">Missing</th>
                  </tr>
                </thead>
                <tbody>
                  {components.slice(0, 24).map((c, i) => (
                    <tr key={i} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-1.5">{c.entity_id}</td>
                      <td className="px-3 py-1.5 font-mono">{c.timestamp.slice(0, 10)}</td>
                      <td className="px-3 py-1.5 font-medium text-slate-700">{c.signal_id}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.raw_value)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.oriented_value)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.normalised_value)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.configured_weight)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.effective_weight)}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{fmtNum(c.contribution)}</td>
                      <td className="px-3 py-1.5">{c.missing ? "missing" : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {observations.some((o) => o.state === "unavailable") && (
              <p className="px-4 py-2 text-xs text-amber-700">
                ⚠ {observations.filter((o) => o.state === "unavailable").length}{" "}
                combined observation(s) are unavailable under the configured
                missing-component policy (missing ids listed per row — never
                zero-imputed).
              </p>
            )}
          </>
        )}
      </div>

      {/* ---------------- horizons ---------------- */}
      {(combinationRows.length > 0 || componentRows.length > 0) && (
        <div className="card overflow-hidden" data-testid="ensemble-horizons">
          <SectionHeader title="Horizon × lag diagnostics — components and combination side by side"
            note="Neutral side-by-side measurements through the Phase 60 policies; no horizon, lag or ensemble is called better." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Subject</th>
                  <th scope="col" className="px-3 py-2">Scope</th>
                  <th scope="col" className="px-3 py-2 text-right">Horizon</th>
                  <th scope="col" className="px-3 py-2 text-right">Lag</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                  <th scope="col" className="px-3 py-2 text-right">p (raw)</th>
                  <th scope="col" className="px-3 py-2 text-right">Top−bottom</th>
                  <th scope="col" className="px-3 py-2 text-right">Cost-adjusted</th>
                  <th scope="col" className="px-3 py-2 text-right">Turnover</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {[...componentRows, ...combinationRows].map((h, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {h.subject_id ?? "combination"}
                    </td>
                    <td className="px-3 py-1.5">{h.outcome_scope === "factor_residual"
                      ? "factor residual" : h.scope}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{h.horizon}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{h.entry_lag}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{h.observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(h.spearman)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtP(h.spearman_p)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(h.top_minus_bottom, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(h.cost_adjusted_spread, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(h.mean_one_way_turnover, 3)}</td>
                    <td className="px-3 py-1.5" title={h.reason ?? undefined}>{h.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- leave one out ---------------- */}
      {run.leave_one_out.length > 0 && (
        <div className="card overflow-hidden" data-testid="ensemble-loo">
          <SectionHeader title="Full versus leave-one-signal-out (neutral)"
            note="Descriptive differences under the configured omission policy — never an exclusion recommendation, never a 'harmful signal' label." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Omitted signal</th>
                  <th scope="col" className="px-3 py-2 text-right">Coverage Δ</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean |ρ| Δ</th>
                  <th scope="col" className="px-3 py-2 text-right">Effective count Δ</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC Δ</th>
                  <th scope="col" className="px-3 py-2 text-right">Spread Δ</th>
                  <th scope="col" className="px-3 py-2 text-right">Turnover Δ</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {run.leave_one_out.map((l) => (
                  <tr key={l.omitted_signal_id} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">{l.omitted_signal_id}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.coverage_delta, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.mean_absolute_correlation_delta, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.effective_signal_count_delta, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.first_horizon_spearman_delta, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.first_horizon_spread_delta, 4)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(l.metrics.mean_one_way_turnover_delta, 3)}</td>
                    <td className="px-3 py-1.5" title={l.reason ?? undefined}>{l.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- turnover ---------------- */}
      {(run.turnover_summary || run.component_turnover) && (
        <div className="card p-4" data-testid="ensemble-turnover">
          <h3 className="text-sm font-semibold text-slate-700">
            Turnover — components versus combination
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            {Object.entries(run.component_turnover ?? {}).map(([signal, value]) => (
              <Field key={signal} label={`${signal} mean one-way turnover`}
                value={value === null ? "unavailable" : fmtNum(value, 3)} />
            ))}
            <Field label="Combination mean one-way turnover"
              value={fmtNum(run.turnover_summary?.mean_one_way_turnover as number | null, 3)} />
            <Field label="Combination mean top Jaccard"
              value={fmtNum(run.turnover_summary?.mean_jaccard_top as number | null, 3)} />
            <Field label="Rebalances"
              value={String(run.turnover_summary?.rebalance_count ?? "—")} />
            <Field label="Initial policy"
              value={String(run.turnover_summary?.initial_policy ?? "—")} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            {String(run.turnover_summary?.turnover_convention ?? "")} Combining
            can remove or CREATE turnover; neither direction makes a
            combination better.
          </p>
        </div>
      )}

      {/* ---------------- cost ---------------- */}
      {run.cost && (
        <div className="card p-4" data-testid="ensemble-cost">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-700">
              Cost-adjusted reference (linked Phase 55 model)
            </h3>
            <CompletenessPill status={String((run.cost as { completeness?: string }).completeness ?? "")} />
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Reference notional"
              value={Number((run.cost as { reference_notional?: number }).reference_notional ?? 0).toLocaleString()} />
            <Field label="Computable per-side bps"
              value={fmtNum((run.cost as { per_side_bps_computable?: number }).per_side_bps_computable, 2)} />
            <Field label="Total cost return"
              value={fmtPct((run.cost as { total_cost_return?: number }).total_cost_return, 4)} />
            <Field label="Costed rebalances"
              value={`${(run.cost as { costed_rebalances?: number }).costed_rebalances ?? "—"} (${(run.cost as { skipped_rebalances?: number }).skipped_rebalances ?? 0} skipped)`} />
          </dl>
          <p className="mt-2 text-xs text-slate-400">
            {String((run.cost as { convention?: string }).convention ?? "")}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {String((run.cost as { spread_adjustment_convention?: string }).spread_adjustment_convention ?? "")}
          </p>
        </div>
      )}

      {/* ---------------- regimes ---------------- */}
      {regimes && regimes.length > 0 && (
        <div className="card overflow-hidden" data-testid="ensemble-regimes">
          <SectionHeader title="Similarity by stored regime"
            note="Regimes come from stored Phase 54 assignments and are never recomputed; rare regimes withhold statistics, and differences between regimes are measurements — never permanent properties." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Regime</th>
                  <th scope="col" className="px-3 py-2 text-right">Obs.</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean |ρ|</th>
                  <th scope="col" className="px-3 py-2 text-right">Effective count</th>
                  <th scope="col" className="px-3 py-2 text-right">Combined IC</th>
                  <th scope="col" className="px-3 py-2 text-right">Coverage</th>
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
                    <td className="px-3 py-1.5 text-right font-mono">{g.observations}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(g.mean_absolute_correlation, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(g.effective_signal_count, 2)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(g.combined_spearman, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(g.coverage, 0)}</td>
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
        <div className="card p-4" data-testid="ensemble-heldout">
          <h3 className="text-sm font-semibold text-slate-700">
            Training versus held-out (linked validation split)
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Split" value={run.held_out.split_label} />
            <Field label="Leakage clean" value={String(run.held_out.leakage_clean)} />
            <Field label="Training obs." value={run.held_out.training_observations} />
            <Field label="Held-out obs." value={run.held_out.held_out_observations} />
            <Field label="Purged obs." value={run.held_out.purged_observations} />
            <Field label="Embargoed obs." value={run.held_out.embargoed_observations} />
            <Field label="Training rank IC" value={fmtNum(run.held_out.training.spearman)} />
            <Field label="Held-out rank IC" value={fmtNum(run.held_out.held_out.spearman)} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">{run.held_out.note}</p>
        </div>
      )}

      {/* ---------------- factor residual ---------------- */}
      {run.factor_residual && (
        <div className="card p-4" data-testid="ensemble-factor">
          <h3 className="text-sm font-semibold text-slate-700">
            Raw versus factor-residualised outcomes
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs md:grid-cols-4">
            <Field label="Factor run" value={run.factor_residual.factor_run_name ?? "—"} />
            <Field label="Matched pairs" value={run.factor_residual.matched_pairs} />
            <Field label="Unmatched pairs" value={run.factor_residual.unmatched_pairs} />
            <Field label="Signal-value residualisation"
              value={run.factor_residual.signal_value_residualisation.state} />
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            {run.factor_residual.signal_value_residualisation.reason}
          </p>
          <p className="mt-1 text-xs text-slate-500">{run.factor_residual.convention}</p>
        </div>
      )}

      {/* ---------------- bootstrap ---------------- */}
      {bootstrap && bootstrap.length > 0 && (
        <div className="card p-4" data-testid="ensemble-bootstrap">
          <h3 className="text-sm font-semibold text-slate-700">
            Bootstrap stability (seeded, descriptive)
          </h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Statistic</th>
                  <th scope="col" className="px-3 py-2">Method</th>
                  <th scope="col" className="px-3 py-2 text-right">Seed</th>
                  <th scope="col" className="px-3 py-2 text-right">Resamples</th>
                  <th scope="col" className="px-3 py-2 text-right">q2.5</th>
                  <th scope="col" className="px-3 py-2 text-right">Median</th>
                  <th scope="col" className="px-3 py-2 text-right">q97.5</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {bootstrap.map((b, i) => (
                  <tr key={i} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {b.statistic.replace(/_/g, " ")}
                    </td>
                    <td className="px-3 py-1.5">{b.method}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{b.seed}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{b.resamples}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(b.quantiles?.q025, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(b.quantiles?.q500, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(b.quantiles?.q975, 3)}</td>
                    <td className="px-3 py-1.5" title={b.reason ?? undefined}>{b.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Resampling quantiles over whole timestamp cross-sections —
            descriptive stability only, not a p-value and not scientific
            validation.
          </p>
        </div>
      )}

      {/* ---------------- sensitivity ---------------- */}
      {sensitivity && sensitivity.length > 0 && (
        <div className="card overflow-hidden" data-testid="ensemble-sensitivity">
          <SectionHeader title="Sensitivity scenarios (base exactly once)"
            note="Bounded deterministic what-ifs over declared settings; no configuration is preferred and no 'best ensemble' exists here." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-left font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2">Scenario</th>
                  <th scope="col" className="px-3 py-2 text-right">Coverage</th>
                  <th scope="col" className="px-3 py-2 text-right">Mean |ρ|</th>
                  <th scope="col" className="px-3 py-2 text-right">Effective count</th>
                  <th scope="col" className="px-3 py-2 text-right">Rank IC</th>
                  <th scope="col" className="px-3 py-2 text-right">Turnover</th>
                  <th scope="col" className="px-3 py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {sensitivity.map((s) => (
                  <tr key={s.scenario_index} className="border-b border-slate-50 last:border-0">
                    <td className="px-3 py-1.5 font-medium text-slate-700">
                      {s.label}
                      {s.is_base && <span className="ml-1 text-[10px] uppercase text-blue-500">base</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtPct(s.metrics.coverage as number | null, 0)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(s.metrics.mean_absolute_correlation as number | null, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(s.metrics.effective_signal_count as number | null, 2)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(s.metrics.first_horizon_spearman as number | null, 3)}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{fmtNum(s.metrics.mean_one_way_turnover as number | null, 3)}</td>
                    <td className="px-3 py-1.5" title={s.reason ?? undefined}>{s.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- policy / fingerprints ---------------- */}
      <div className="card p-4" data-testid="ensemble-policy">
        <h3 className="text-sm font-semibold text-slate-700">
          Policies and fingerprints
        </h3>
        <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-xs md:grid-cols-2">
          <Field label="Universe fp" value={shortFp(run.universe_fingerprint)} mono
            title={run.universe_fingerprint ?? undefined} />
          <Field label="Combination policy fp" value={shortFp(run.combination_fingerprint)} mono
            title={run.combination_fingerprint ?? undefined} />
          <Field label="Similarity policy fp" value={shortFp(run.similarity_fingerprint)} mono
            title={run.similarity_fingerprint ?? undefined} />
          <Field label="Analysis policy fp" value={shortFp(run.analysis_fingerprint)} mono
            title={run.analysis_fingerprint ?? undefined} />
          <Field label="Configuration fp" value={shortFp(run.configuration_fingerprint)} mono
            title={run.configuration_fingerprint ?? undefined} />
          <Field label="Result fp" value={shortFp(run.result_fingerprint)} mono
            title={run.result_fingerprint ?? undefined} />
        </dl>
        <p className="mt-2 text-xs text-slate-500">
          Content-addressed identity only — no database ids, timestamps,
          durations or paths enter a fingerprint, and non-finite values
          are rejected outright.
        </p>
      </div>
    </div>
  );
}

function SectionHeader({ title, note }: { title: string; note: string }) {
  return (
    <div className="border-b border-slate-100 px-4 py-3">
      <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </div>
  );
}

function Field({ label, value, mono, title }: {
  label: string; value: string | number | null | undefined;
  mono?: boolean; title?: string;
}) {
  return (
    <div title={title}>
      <dt className="font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={mono ? "font-mono" : undefined}>
        {value === null || value === undefined ? "—" : String(value)}
      </dd>
    </div>
  );
}
