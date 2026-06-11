"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { RobustnessResult } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import { useAccentColors } from "@/lib/useAccentColors";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  CHART_REF_LINE,
} from "@/components/charts/chartTheme";

interface Props {
  robustness?: RobustnessResult | null;
}

const GRADE_STYLE: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-700",
  B: "bg-emerald-100 text-emerald-700",
  C: "bg-amber-100 text-amber-700",
  D: "bg-amber-100 text-amber-700",
  F: "bg-red-100 text-red-600",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mono mt-0.5 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}

/**
 * Robustness Lab v1 — block-bootstrap summary of how sensitive the result is
 * to resampling historical returns.  Research diagnostics, not guarantees:
 * a fragile strategy can still look good in one backtest.
 */
export default function RobustnessLabCard({ robustness }: Props) {
  const colors = useAccentColors();

  if (!robustness) {
    return (
      <div className="card p-5">
        <p className="section-title">Robustness Lab</p>
        <p className="mt-3 text-sm text-slate-500">
          Run bootstrap analysis to estimate how sensitive this result is to
          return resampling — enable{" "}
          <span className="font-medium text-slate-600">
            “Run robustness analysis”
          </span>{" "}
          in the Backtest form and re-run.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">
          Robustness diagnostics are research tools, not guarantees. A fragile
          strategy can still look good in one backtest.
        </p>
      </div>
    );
  }

  const s = robustness.summary;
  const histData = robustness.final_return_histogram.map((b) => ({
    mid: (b.lower + b.upper) / 2,
    label: `${fmtPct(b.lower)} → ${fmtPct(b.upper)}`,
    count: b.count,
  }));

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">
          Robustness Lab
          <span className="normal-case font-normal text-slate-400 ml-1">
            block bootstrap · {robustness.n_simulations.toLocaleString("en-US")} sims ·
            block {robustness.block_size} · seed {robustness.seed}
          </span>
        </p>
        {robustness.grade && (
          <span
            className={
              "rounded-full px-2.5 py-0.5 text-xs font-bold " +
              (GRADE_STYLE[robustness.grade] ?? "bg-slate-100 text-slate-600")
            }
            title="Heuristic rule-of-thumb summary — not a trading recommendation."
          >
            Grade {robustness.grade} · heuristic
          </span>
        )}
      </div>

      {s ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="P(loss)" value={fmtPct(s.probability_of_loss)} />
            <Stat label="Median final return" value={fmtPct(s.median_final_return)} />
            <Stat
              label="5th–95th final return"
              value={`${fmtPct(s.p05_final_return)} … ${fmtPct(s.p95_final_return)}`}
            />
            {typeof s.probability_of_outperforming_benchmark === "number" ? (
              <Stat
                label="P(beat benchmark)"
                value={fmtPct(s.probability_of_outperforming_benchmark)}
              />
            ) : (
              <Stat label="P(beat benchmark)" value="—" />
            )}
            <Stat label="Median max DD" value={fmtPct(s.median_max_drawdown)} />
            <Stat label="95th-pct max DD" value={fmtPct(s.p95_max_drawdown)} />
            <Stat label="Median Sharpe" value={fmtRatio(s.median_sharpe)} />
            <Stat
              label="5th–95th Sharpe"
              value={`${fmtRatio(s.p05_sharpe)} … ${fmtRatio(s.p95_sharpe)}`}
            />
          </div>

          {histData.length > 0 && (
            <div className="mt-4">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Simulated final returns
              </p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={histData} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="mid"
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fontSize: 10, fill: CHART_AXIS }}
                    axisLine={{ stroke: CHART_AXIS_LINE }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: CHART_AXIS }}
                    axisLine={false}
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip
                    content={
                      <NeonTooltip
                        formatValue={(v: number) => `${v} sims`}
                        // x-axis is a return bucket, not a date — label it as the
                        // bin's percent range instead of month/year.
                        formatLabel={(l) => {
                          const bin = histData.find((b) => b.mid === l);
                          if (bin) return bin.label;
                          return typeof l === "number" ? fmtPct(l) : "";
                        }}
                      />
                    }
                  />
                  <ReferenceLine x={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
                  <Bar dataKey="count" name="Simulations" fill={colors.accent} fillOpacity={0.75} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Not enough data to run the bootstrap for this backtest.
        </p>
      )}

      {robustness.warnings.length > 0 && (
        <ul className="mt-3 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
          {robustness.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        Bootstrap analysis resamples historical returns to estimate outcome
        uncertainty. Small samples and non-stationary markets limit
        interpretation; the heuristic grade is not a trading recommendation, and
        none of this proves alpha or guarantees future performance.
      </p>
    </div>
  );
}
