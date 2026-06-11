"use client";

import { useMemo, useState } from "react";
import type {
  SensitivityMetric,
  SensitivityResult,
  SensitivityRun,
} from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";

interface Props {
  sensitivity?: SensitivityResult | null;
}

const METRIC_TABS: { id: SensitivityMetric; label: string; isPct: boolean }[] = [
  { id: "sharpe", label: "Sharpe", isPct: false },
  { id: "total_return", label: "Total Return", isPct: true },
  { id: "max_drawdown", label: "Max Drawdown", isPct: true },
];

const METRIC_LABEL: Record<SensitivityMetric, string> = {
  sharpe: "Sharpe",
  total_return: "Total Return",
  cagr: "CAGR",
  max_drawdown: "Max Drawdown",
  calmar: "Calmar",
};

function fmtMetric(v: number | null | undefined, isPct: boolean): string {
  if (typeof v !== "number") return "—";
  return isPct ? fmtPct(v) : fmtRatio(v);
}

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
 * Stability Lab v1 — parameter-sensitivity heatmap (SMA fast × slow).  Shows
 * whether the selected parameters sit in a stable region or an isolated spike.
 * Complements the Robustness Lab: robustness resamples *returns*, stability
 * varies *parameters*.  A research diagnostic, not an optimization tool.
 */
export default function StabilityLabCard({ sensitivity }: Props) {
  const [metricTab, setMetricTab] = useState<SensitivityMetric | null>(null);

  // Heatmap metric: tab selection (client-side re-coloring from runs) falls
  // back to the server-configured metric.
  const s = sensitivity;
  const activeMetric: SensitivityMetric = metricTab ?? s?.metric ?? "sharpe";
  const activeIsPct = METRIC_TABS.find((t) => t.id === activeMetric)?.isPct ?? false;

  const runByCell = useMemo(() => {
    const map = new Map<string, SensitivityRun>();
    for (const r of s?.runs ?? []) map.set(`${r.fast_window}|${r.slow_window}`, r);
    return map;
  }, [s]);

  const { minV, maxV } = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const r of s?.runs ?? []) {
      const v = r.valid && r.metrics ? r.metrics[activeMetric] : null;
      if (typeof v === "number") {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
    }
    return { minV: lo, maxV: hi };
  }, [s, activeMetric]);

  if (!s) {
    return (
      <div className="card p-5">
        <p className="section-title">Stability Lab</p>
        <p className="mt-3 text-sm text-slate-500">
          Run a parameter sweep to check whether the selected parameters sit in a
          stable region or an isolated spike — enable{" "}
          <span className="font-medium text-slate-600">“Run Stability Lab”</span>{" "}
          in the Backtest form (SMA Crossover) and re-run.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">
          Sensitivity analysis explores nearby parameter choices. It is a research
          diagnostic, not an optimization recommendation.
        </p>
      </div>
    );
  }

  if (!s.supported) {
    return (
      <div className="card p-5">
        <p className="section-title">Stability Lab</p>
        <p className="mt-3 text-sm text-slate-500">
          Stability Lab v1 currently supports SMA Crossover. Sweeps for other
          strategies are planned.
        </p>
      </div>
    );
  }

  const sel = s.selected_point;
  const best = s.summary?.best_params;
  const summary = s.summary;

  // Intensity 0..1 within the visible metric range (higher = better for every
  // supported metric — max drawdown is negative, so closer to 0 is better).
  const intensity = (v: number): number => {
    if (!(maxV > minV)) return 0.6;
    return (v - minV) / (maxV - minV);
  };

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">
          Stability Lab
          <span className="normal-case font-normal text-slate-400 ml-1">
            parameter sensitivity · {s.x_param} × {s.y_param}
          </span>
        </p>
        <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
          {METRIC_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setMetricTab(t.id)}
              className={
                "px-2.5 py-1 text-[11px] font-medium transition-colors " +
                (activeMetric === t.id
                  ? "bg-blue-600 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50")
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap — CSS grid; rows = slow_window (top = largest), cols = fast. */}
      <div className="mt-3 overflow-x-auto">
        <div className="inline-block min-w-full">
          <div
            className="grid gap-[3px]"
            style={{
              gridTemplateColumns: `64px repeat(${s.x_values.length}, minmax(44px, 1fr))`,
            }}
          >
            {[...s.y_values].reverse().map((slow) => (
              <FragmentRow
                key={`row-${slow}`}
                slow={slow}
                xValues={s.x_values}
                runByCell={runByCell}
                activeMetric={activeMetric}
                activeIsPct={activeIsPct}
                intensity={intensity}
                selected={sel ?? null}
                best={best ?? null}
              />
            ))}
            {/* X-axis labels */}
            <div className="px-1 py-1 text-right text-[10px] font-medium text-slate-400">
              slow ↑ / fast →
            </div>
            {s.x_values.map((fast) => (
              <div
                key={`x-${fast}`}
                className="py-1 text-center text-[10px] font-medium text-slate-400"
              >
                {fast}
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-1 text-[10px] text-slate-400">
        Showing {METRIC_LABEL[activeMetric]} per fast/slow combination. Ring =
        selected parameters{best ? ", ★ = best cell in grid" : ""}. Blank cells are
        invalid (fast ≥ slow). The stability summary below uses the{" "}
        {METRIC_LABEL[s.metric]} metric configured at run time.
      </p>

      {summary && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="Stability score (heuristic)"
            value={
              typeof summary.stability_score === "number"
                ? summary.stability_score.toFixed(2)
                : "—"
            }
          />
          <Stat
            label={`Selected ${METRIC_LABEL[s.metric]}`}
            value={fmtMetric(summary.selected_value, s.metric !== "sharpe" && s.metric !== "calmar")}
          />
          <Stat
            label="Neighbor median"
            value={fmtMetric(summary.neighbor_median, s.metric !== "sharpe" && s.metric !== "calmar")}
          />
          <Stat
            label="Best in grid"
            value={
              best
                ? `${fmtMetric(summary.best_value, s.metric !== "sharpe" && s.metric !== "calmar")} @ ${best.fast_window}/${best.slow_window}`
                : "—"
            }
          />
        </div>
      )}

      {summary &&
        (summary.fragility_flag ? (
          <p className="mt-2 rounded-lg bg-amber-100 px-3 py-2 text-xs font-medium text-amber-700">
            {summary.explanation}
          </p>
        ) : (
          <p className="mt-2 text-xs text-slate-500">{summary.explanation}</p>
        ))}

      {s.warnings.length > 0 && (
        <ul className="mt-3 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
          {s.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        Stable regions are generally more credible than isolated peaks, but
        parameter sweeps can still overfit if used to choose the best result.
        Robustness Lab resamples returns; Stability Lab varies parameters — they
        are complementary diagnostics, not guarantees.
      </p>
    </div>
  );
}

function FragmentRow({
  slow,
  xValues,
  runByCell,
  activeMetric,
  activeIsPct,
  intensity,
  selected,
  best,
}: {
  slow: number;
  xValues: number[];
  runByCell: Map<string, SensitivityRun>;
  activeMetric: SensitivityMetric;
  activeIsPct: boolean;
  intensity: (v: number) => number;
  selected: { fast_window: number; slow_window: number } | null;
  best: { fast_window: number; slow_window: number } | null;
}) {
  return (
    <>
      <div className="flex items-center justify-end pr-1.5 text-[10px] font-medium text-slate-400">
        {slow}
      </div>
      {xValues.map((fast) => {
        const run = runByCell.get(`${fast}|${slow}`);
        const value = run?.valid && run.metrics ? run.metrics[activeMetric] : null;
        const isSelected =
          selected?.fast_window === fast && selected?.slow_window === slow;
        const isBest = best?.fast_window === fast && best?.slow_window === slow;
        const title = run
          ? run.valid && run.metrics
            ? `fast ${fast} / slow ${slow}\n${activeMetric}: ${fmtMetric(value, activeIsPct)}\ntotal return: ${fmtPct(run.metrics.total_return)}\nmax drawdown: ${fmtPct(run.metrics.max_drawdown)}\ntrades: ${run.num_trades ?? "—"}`
            : `fast ${fast} / slow ${slow}\ninvalid: ${run.warning ?? "fast ≥ slow"}`
          : `fast ${fast} / slow ${slow}`;
        return (
          <div
            key={`cell-${fast}-${slow}`}
            title={title}
            className={
              "flex h-9 items-center justify-center rounded text-[10px] font-semibold tabular-nums " +
              (isSelected ? "ring-2 ring-blue-500 " : "") +
              (value == null ? "text-slate-300" : "text-slate-900")
            }
            style={{
              background:
                value == null
                  ? "rgba(148,163,184,0.08)"
                  : `rgba(var(--accent-rgb), ${(0.12 + 0.78 * intensity(value)).toFixed(3)})`,
            }}
          >
            {value == null ? "·" : fmtMetric(value, activeIsPct)}
            {isBest && <span className="ml-0.5">★</span>}
          </div>
        );
      })}
    </>
  );
}
