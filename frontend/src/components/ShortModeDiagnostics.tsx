"use client";

import type { BacktestDiagnostics, PositionMode } from "@/lib/types";

/**
 * Direction / exposure diagnostics card for short-enabled backtests
 * (short_only / long_short).  Shows how much exposure was long vs short and
 * whether the short legs helped or hurt — gross, pre-cost figures from the
 * backend.  Borrow/margin costs are not modelled.
 */

function pct(v: number, decimals = 1): string {
  return `${(v * 100).toFixed(decimals)}%`;
}

function signedPct(v: number, decimals = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(decimals)}%`;
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: "pos" | "neg" | "neutral";
}) {
  const color =
    tone === "pos"
      ? "text-green-700"
      : tone === "neg"
        ? "text-red-700"
        : "text-slate-800";
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className={`mono mt-0.5 text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function toneFor(v: number): "pos" | "neg" | "neutral" {
  if (v > 0) return "pos";
  if (v < 0) return "neg";
  return "neutral";
}

export default function ShortModeDiagnostics({
  diagnostics,
  mode,
}: {
  diagnostics: BacktestDiagnostics;
  mode: PositionMode;
}) {
  const d = diagnostics;
  const shortHelped = d.short_return_contribution > 0;

  return (
    <div className="card space-y-4 p-5">
      <div className="flex items-center gap-2">
        <span className="section-title">Direction Diagnostics</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
          {mode === "short_only" ? "Short only" : "Long / Short"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Long entries" value={d.long_trade_count} />
        <Stat label="Short entries" value={d.short_trade_count} />
        <Stat label="Turnover" value={d.turnover_estimate.toFixed(1)} />
        <Stat
          label="Time in market"
          value={pct(d.percent_time_long + d.percent_time_short)}
        />
        <Stat label="Time long" value={pct(d.percent_time_long)} />
        <Stat label="Time short" value={pct(d.percent_time_short)} />
        <Stat label="Time cash" value={pct(d.percent_time_cash)} />
        <Stat
          label="Long gross (pre-cost)"
          value={signedPct(d.gross_long_return)}
          tone={toneFor(d.gross_long_return)}
        />
        <Stat
          label="Short gross (pre-cost)"
          value={signedPct(d.gross_short_return)}
          tone={toneFor(d.gross_short_return)}
        />
        <Stat
          label="Short contribution"
          value={signedPct(d.short_return_contribution)}
          tone={toneFor(d.short_return_contribution)}
        />
      </div>

      <p className="text-xs text-slate-400">
        {shortHelped
          ? "The short legs added to gross return over this period."
          : "The short legs detracted from gross return over this period — common when the asset trends up."}{" "}
        Gross figures exclude transaction costs; borrow fees, margin, and
        liquidation are <span className="font-medium text-slate-500">not modelled</span>.
      </p>
    </div>
  );
}
