"use client";

import type { AdvancedScannerResult, ScannerExposure, ScannerValidationResponse } from "@/lib/scannerAdvanced";
import { downloadScannerValidation } from "@/lib/scannerAdvanced";

const number = (value: number | null, digits = 4) => value == null ? "Not available" : value.toFixed(digits);
const percent = (value: number | null) => value == null ? "Not available" : `${(value * 100).toFixed(2)}%`;

function Exposures({ value }: { value: ScannerExposure }) {
  return <div className="min-w-32 text-[11px]">
    <div>Net {number(value.net)} / gross {number(value.gross)}</div>
    <div>Beta {number(value.beta)}</div>
    {Object.entries(value.sectors).map(([sector, net]) => <div key={sector}>{sector}: {number(net)}</div>)}
  </div>;
}

export default function ScannerResearchResults({ advanced, validation }: {
  advanced?: AdvancedScannerResult | null; validation: ScannerValidationResponse | null;
}) {
  return <div className="min-w-0 space-y-5" data-testid="scanner-research-results">
    {advanced && <section className="space-y-3 border-t border-[var(--line)] pt-4">
      <h2 className="section-title">Neutralisation diagnostics</h2>
      <p className="text-xs text-slate-300">{advanced.support_policy}. Failed rebalance: {advanced.failed_rebalance}.</p>
      <p className="break-words text-xs text-slate-400">{advanced.exposure_provenance}; {advanced.factor_provenance}</p>
      <p className="text-xs text-slate-300">Later realized net volatility: {percent(advanced.realized_net_volatility)} per year, not the requested ex-ante target.</p>
      <p className="text-[11px] text-slate-400">Last {Math.min(12, advanced.diagnostics.length)} diagnostics of {advanced.total_rebalances}; public diagnostic cap 100.</p>
      <div className="overflow-x-auto">
        <table aria-label="Scanner neutralisation stages" className="w-full text-xs">
          <thead><tr>{["Decision / state", "Raw basket", "Residual basket", "Neutral", "Final", "Volatility reference", "Reconciliation"].map((h) => <th key={h} className="px-2 py-2 text-left font-medium text-slate-400">{h}</th>)}</tr></thead>
          <tbody>{advanced.diagnostics.slice(-12).map((row) => <tr key={row.date} className="border-t border-[var(--line)] align-top">
            <td className="min-w-44 px-2 py-2">{row.date}: {row.status}<div>{row.reason}</div><div>Eligible {row.eligible_count}; excluded {row.excluded.length}</div><div>Rank {row.rank ?? "unavailable"}/{row.columns ?? "?"}; support rank {row.support_rank ?? "unavailable"}</div>
              <details><summary>Excluded names</summary>{row.excluded.map((x) => <div key={x.asset_id}>{x.asset_id}: {x.reason}</div>)}</details></td>
            {[row.raw, row.transformed, row.neutral, row.final].map((value, i) => <td key={i} className="px-2 py-2"><Exposures value={value} /></td>)}
            <td className="min-w-40 px-2 py-2">Estimated {percent(row.volatility_estimate)}<div>Target {percent(row.volatility_target)}</div><div>Scale {number(row.volatility_scale)}</div><div>Achieved ex-ante {percent(row.achieved_ex_ante)}</div><div>Cap {row.cap_binding ? "binding" : "not binding"}</div></td>
            <td className="min-w-40 px-2 py-2">Outcome {row.outcome_date}<div>Turnover {number(row.turnover)}</div><div>Fee {percent(row.cost)}</div><div>Gross {percent(row.gross_return)} / net {percent(row.net_return)}</div><div>Constraint error {row.constraint_error.toExponential(2)}</div></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="overflow-x-auto"><table aria-label="Raw and transformed scanner scores" className="w-full max-w-2xl text-xs">
        <thead><tr>{["Asset", "Raw score", "Transformed score", "Final weight", "Declared sector", "Estimated / supplied beta"].map((h) => <th key={h} className="px-2 py-1 text-left text-slate-400">{h}</th>)}</tr></thead>
        <tbody>{advanced.latest_scores.slice(0, 20).map((r) => <tr key={r.asset_id} className="border-t border-[var(--line)]"><td className="p-2">{r.asset_id}</td><td>{number(r.raw_score)}</td><td>{number(r.transformed_score)}</td><td>{number(r.weight)}</td><td>{r.sector ?? "Not available"}</td><td>{number(r.beta ?? null)}</td></tr>)}</tbody>
      </table></div>
      {advanced.caveats.map((warning) => <p className="text-[11px] text-slate-400" key={warning}>{warning}</p>)}
    </section>}
    {validation && <section className="space-y-3 border-t border-[var(--line)] pt-4" data-testid="scanner-validation-results">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="section-title">Retrospective purged validation</h2>
        <button type="button" className="ql-input px-3 py-1.5 text-xs" onClick={() => downloadScannerValidation(validation)}>Download validation JSON</button></div>
      <p className="text-xs text-amber-300">Synthetic universe. No supervised fit, automatic winner, walk-forward claim or validated-alpha verdict.</p>
      <p className="text-xs text-slate-300">Declared family {validation.family.declared_count}; correction includes {validation.family.included_count}. Alpha {validation.family.alpha} (neutral threshold). Missing: {validation.family.missing_ids.join(", ") || "none"}. Invalid: {validation.family.invalid_ids.join(", ") || "none"}.</p>
      <p className="text-xs text-slate-400">{validation.family.provenance}</p>
      <div className="overflow-x-auto"><table aria-label="Scanner candidate corrections" className="w-full text-xs">
        <thead><tr>{["Candidate / availability", "Held-out mean net", "Raw p", "Bonferroni", "Holm", "BH", "Provenance"].map((h) => <th className="px-2 py-2 text-left text-slate-400" key={h}>{h}</th>)}</tr></thead>
        <tbody>{validation.candidates.map((c) => <tr key={c.candidate_id} className="border-t border-[var(--line)] align-top"><td className="max-w-80 p-2">{c.candidate_id}: {c.status}<div>{c.reason}</div></td><td>{percent(c.mean_test_net_return)}</td>
          {[c.correction.raw_p_value, c.correction.bonferroni, c.correction.holm, c.correction.bh].map((v, i) => <td className="p-2" key={i}>{number(v)}</td>)}<td className="p-2">{c.correction.provenance_status}</td></tr>)}</tbody>
      </table></div>
      <div className="overflow-x-auto"><table aria-label="Scanner purged fold audit" className="w-full text-xs">
        <thead><tr>{["Fold", "Train", "Test", "Purged", "Embargoed", "Remaining overlap", "Audit"].map((h) => <th className="p-2 text-left text-slate-400" key={h}>{h}</th>)}</tr></thead>
        <tbody>{validation.folds.map((f) => <tr key={f.label} className="border-t border-[var(--line)]"><td className="p-2">{f.label}</td><td>{f.train_ids.length}</td><td>{f.test_ids.length}</td><td>{f.purged_ids.length}</td><td>{f.embargoed_ids.length}</td><td>{f.audit.remaining_overlap_count}</td><td>{f.audit.valid ? "valid" : "unavailable"}</td></tr>)}</tbody>
      </table></div>
      <p className="text-xs text-slate-400">PBO: {validation.unavailable_statistics.pbo}. DSR: {validation.unavailable_statistics.dsr}.</p>
      {validation.caveats.map((warning) => <p className="text-[11px] text-slate-400" key={warning}>{warning}</p>)}
      <p className="break-all font-mono text-[10px] text-slate-500">Family {validation.family_fingerprint}; result {validation.result_fingerprint}</p>
    </section>}
  </div>;
}
