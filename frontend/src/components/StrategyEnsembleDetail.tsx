"use client";

import { useState, type ReactNode } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { number, percent, type Run, type Json } from "@/lib/strategyEnsemble";

const periodLabel = (value: string) => value.replace("T", " ").replace(/\.0+Z$/, " UTC");

export function DataTable({ title, headers, rows }: { title: string; headers: string[]; rows: ReactNode[][] }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / 50));
  const current = Math.min(page, pages - 1);
  return <section className="min-w-0 space-y-2">
    <h3 className="text-sm font-semibold">{title}</h3>
    <div className="max-w-full overflow-x-auto rounded border" style={{ borderColor: "var(--line)" }}>
      <table className="w-full text-left text-xs"><caption className="sr-only">{title}</caption>
        <thead style={{ background: "var(--glass)", color: "var(--text-hi)" }}><tr>{headers.map((h) => <th scope="col" className="p-3 whitespace-nowrap" key={h}>{h}</th>)}</tr></thead>
        <tbody>{rows.slice(current*50, (current+1)*50).map((row, i) => <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}>
          {row.map((v, j) => <td className="p-3 align-top break-words" key={j}>{v}</td>)}
        </tr>)}</tbody>
      </table>
      {rows.length === 0 && <p className="p-3 text-sm">No observations available.</p>}
    </div>
    {pages > 1 && <div className="flex gap-3 items-center text-xs">
      <button type="button" aria-label={`Previous ${title} page`} disabled={current === 0} onClick={() => setPage(current-1)}>&larr;</button>
      <span>{current+1} / {pages}</span>
      <button type="button" aria-label={`Next ${title} page`} disabled={current === pages-1} onClick={() => setPage(current+1)}>&rarr;</button>
    </div>}
  </section>;
}

export function StructuredData({ title, value }: { title: string; value: Json | unknown }) {
  return <details className="min-w-0 border-t pt-3" style={{ borderColor: "var(--line)" }}>
    <summary className="cursor-pointer text-sm font-medium">{title}</summary>
    <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs p-3" style={{ background: "var(--glass)", color: "var(--text)" }}>{JSON.stringify(value, null, 2)}</pre>
  </details>;
}

export default function StrategyEnsembleDetail({ run }: { run: Run }) {
  const r = run.results;
  const ids = run.request.definitions.map((d) => d.strategy_id);
  if (!r) return <p role="status">{run.error_message ?? "Created. No analysis results yet."}</p>;
  const e = r.ensemble;
  return <div className="space-y-6 min-w-0" data-testid="strategy-ensemble-detail">
    <dl className="grid grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-3 text-sm">
      {[["Strategies", ids.length], ["Common periods", e.n], ["Mean absolute correlation", number(r.matrix.mean_absolute_correlation)],
        ["Effective count (matrix concentration)", number(r.matrix.effective_strategy_count)], ["Observed compounded return", percent(e.drawdown.compounded_return)],
        ["Maximum drawdown", percent(e.drawdown.max_drawdown)], ["Mean return per period", percent(e.mean_return)], ["Volatility per period", percent(e.volatility_per_period)]].map(([label, value]) =>
        <div key={label} className="border-b pb-2" style={{ borderColor: "var(--line)" }}><dt className="text-xs" style={{ color: "var(--text-mut)" }}>{label}</dt><dd className="mt-1 font-mono">{value}</dd></div>)}
    </dl>
    <DataTable title="Strategy identities and return basis" headers={["Strategy", "Source", "Dataset", "Basis", "Period / currency", "Leverage"]}
      rows={run.request.definitions.map((d) => [d.strategy_name, d.source_type, d.dataset_identity, d.gross_or_net, `${d.frequency} / ${d.currency}`, d.leverage_convention])} />
    <DataTable title="Exact alignment and missingness" headers={["Strategy", "Stored", "Missing", "Excluded", "Common / stored"]}
      rows={r.coverage.strategies.map((s) => [s.strategy_id, s.stored_periods, s.missing_periods, s.excluded_periods, percent(s.coverage_ratio)])} />
    <p className="text-xs">{r.coverage.exclusion_reason}. Observed timeline gaps: {r.coverage.gaps}. No missing returns are inserted.</p>
    <DataTable title="Static strategy-return weights" headers={["Strategy", "Original", "Effective"]}
      rows={ids.map((s) => [s, number(e.weights.original[s]), number(e.weights.effective[s])])} />
    <p className="text-xs">Gross weight: {number(e.weights.gross)}. Net weight: {number(e.weights.net)}. Returns are used verbatim; no additional internal leverage is applied.</p>
    <DataTable title="Pairwise similarity and empirical lower-tail overlap" headers={["Pair", "N", "Sample", "Pearson", "Spearman", "Joint loss", "Tail Jaccard", "Tail state"]}
      rows={r.pairwise.map((p) => [`${p.strategy_a} / ${p.strategy_b}`, p.n, p.alignment,
        <span title={p.correlations.pearson.reason ?? ""}>{number(p.correlations.pearson.value)}</span>,
        number(p.correlations.spearman.value), percent(p.joint_loss_rate), percent(p.empirical_lower_tail_overlap.jaccard),
        p.empirical_lower_tail_overlap.reason ?? p.empirical_lower_tail_overlap.ties])} />
    {r.matrix.values ? <DataTable title={`${r.matrix.method} matrix: strict common sample (N=${r.matrix.n})`}
      headers={["Strategy", ...r.matrix.strategy_ids]} rows={r.matrix.values.map((row, i) => [r.matrix.strategy_ids[i], ...row.map((v) =>
        <span style={{ color: v < 0 ? "var(--neg)" : "var(--text-hi)" }}>{number(v)}</span>)])} /> : <p role="status">Matrix unavailable: {r.matrix.reason}</p>}
    <p className="text-xs">Matrix rank: {number(r.matrix.rank, 0)}. Condition: {number(r.matrix.condition)}. Effective count is a matrix concentration diagnostic, not independence.</p>
    <section className="min-w-0 space-y-2" aria-label="Ensemble wealth chart">
      <h3 className="text-sm font-semibold">Ensemble wealth (initial reference 1)</h3>
      <div className="h-64 w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%"><LineChart data={e.drawdown.periods} margin={{ top: 12, right: 16, bottom: 8, left: 10 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
          <XAxis dataKey="period_end" tickFormatter={(v: string) => v.slice(0, 10)} minTickGap={60} tick={{ fontSize: 10, fill: "var(--text-mut)" }} />
          <YAxis tickFormatter={(v: number) => number(v, 2)} width={65} tick={{ fontSize: 10, fill: "var(--text-mut)" }} domain={["auto", "auto"]} />
          <Tooltip labelFormatter={(v) => periodLabel(String(v))} formatter={(v: number) => [number(v), "Wealth"]}
            contentStyle={{ background: "var(--bg)", borderColor: "var(--line)", color: "var(--text-hi)" }} />
          <Line name="Ensemble wealth" type="linear" dataKey="wealth" stroke="var(--chart-primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart></ResponsiveContainer>
      </div>
    </section>
    <DataTable title="Ensemble period reconciliation and drawdown" headers={["Period start", "Period end", "Return", "Wealth", "Peak", "Drawdown", "Residual"]}
      rows={e.drawdown.periods.map((p, i) => [periodLabel(p.period_start), periodLabel(p.period_end), percent(p.return_value), number(p.wealth), number(p.running_peak), percent(p.drawdown), number(e.periods[i].residual)])} />
    <DataTable title="Period contributions (arithmetic return)" headers={["Period end", ...ids]}
      rows={e.periods.map((p) => [periodLabel(p.period_end), ...ids.map((s) => percent(p.contributions[s]))])} />
    <DataTable title="Contribution summary" headers={["Strategy", "Arithmetic sum", "Signed share", "Positive periods", "Negative periods", "Absolute share"]}
      rows={e.contribution_summary.map((s) => [s.strategy_id, percent(s.arithmetic_contribution), percent(s.share), s.positive_periods, s.negative_periods, percent(s.absolute_share)])} />
    <p className="text-xs">Maximum reconciliation residual: {number(e.reconciliation_max_residual)}. Compounded return minus arithmetic sum: {percent(e.arithmetic_geometric_gap)}. Arithmetic sums are not geometrically linked attribution.</p>
    <DataTable title="Drawdown overlap" headers={["Pair", "Simultaneous", "State agreement", "Severe", "Deepest episode overlap", "Loss overlap"]}
      rows={r.pairwise.map((p) => [`${p.strategy_a} / ${p.strategy_b}`, p.drawdown_overlap.simultaneous_periods, percent(p.drawdown_overlap.state_agreement), p.drawdown_overlap.severe_periods, p.drawdown_overlap.deepest_episode_overlap, p.drawdown_overlap.loss_period_overlap])} />
    <DataTable title="Cost basis and turnover" headers={["Measure", "Value"]} rows={[
      ["Underlying basis", e.costs.basis], ["Completeness", e.costs.completeness], ["Underlying costs deducted again", e.costs.underlying_cost_deducted_again ? "Yes" : "No"],
      ["Gross ensemble reference", percent(e.costs.gross_ensemble_reference)], ["Net of strategy costs reference", percent(e.costs.net_of_strategy_costs_reference)],
      ["Allocation cost", percent(e.costs.allocation_cost)], ["Fully net ensemble", percent(e.costs.fully_net_ensemble)],
      ["Initial target allocation turnover", number(e.turnover.initial_allocation)], ["Subsequent target weight change", number(e.turnover.subsequent_target_weight_change)],
      ["Executed rebalance turnover", number(e.turnover.executed_rebalance_turnover)],
    ]} />
    <p className="text-xs">{e.costs.reason}</p>
    <DataTable title="Stored regime observations" headers={["Regime", "N / minimum", "State", "Mean return", "Volatility", "Observed full-path drawdown"]}
      rows={r.regimes.map((g) => [g.label, `${g.n} / ${g.minimum}`, g.rare ? "Rare / unavailable" : g.integrity,
        percent(g.statistics?.mean_return), percent(g.statistics?.volatility_per_period), percent(g.statistics?.minimum_observed_full_path_drawdown)])} />
    {r.validation.state === "available" ? <DataTable title="Training and held-out (frozen weights)" headers={["Sample", "N", "Mean return", "Volatility per period", "Observed compounded return", "Max drawdown"]}
      rows={[["Training", r.validation.training], ["Held-out", r.validation.held_out]].map(([label, value]) => {
        const v = value as import("@/lib/strategyEnsemble").ValidationBlock;
        return [String(label), v.n, percent(v.mean_return), percent(v.volatility_per_period), percent(v.drawdown.compounded_return), percent(v.drawdown.max_drawdown)];
      })} /> : <p className="text-sm">Held-out unavailable: {r.validation.reason}</p>}
    <DataTable title="Explicit weight sensitivity" headers={["Scenario", "N", "Return", "Max drawdown", "Absolute concentration", "Cost completeness"]}
      rows={r.sensitivity.map((s) => [s.label, s.n, percent(s.compounded_return), percent(s.max_drawdown), number(s.concentration), s.costs.completeness])} />
    <StructuredData title="Stored validation: training and held-out" value={r.validation} />
    <StructuredData title="Regime correlations, contributions and observed drawdowns" value={r.regimes} />
    <StructuredData title="Strategy drawdowns and episodes" value={r.strategy_drawdowns} />
    <StructuredData title="Ensemble episodes and descriptive contributions" value={e.drawdown.episodes} />
    <StructuredData title="Underlying strategy turnover and cost observations" value={e.turnover.underlying} />
    <StructuredData title="Pairwise statistics and tail thresholds" value={r.pairwise} />
    <StructuredData title="Raw p-values and multiple-testing corrections" value={r.multiple_testing} />
    <StructuredData title="Source identity and dataset lineage" value={run.links} />
    <StructuredData title="Fingerprints and declared policy" value={{ fingerprints: run.fingerprints, definitions: r.definition_fingerprints, policy: run.request.policy, analysis: run.request.analysis }} />
    <StructuredData title="Deferred integrations" value={r.deferred} />
    <aside className="text-xs space-y-2" style={{ color: "var(--text-mut)" }}>{r.warnings.map((w) => <p key={w}>{w}</p>)}</aside>
  </div>;
}
