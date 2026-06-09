"use client";

import type { RiskDiagnostics, RiskManagementResolved } from "@/lib/types";

interface Props {
  risk: RiskManagementResolved;
  diagnostics: RiskDiagnostics | null;
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mono mt-0.5 text-base font-semibold text-slate-800">{value}</p>
    </div>
  );
}

/**
 * Compact diagnostics for an active risk-management run.  Shows what rules were
 * applied and how many exits each triggered.  When nothing triggered it says so
 * plainly — no scary warning.
 */
export default function RiskDiagnosticsCard({ risk, diagnostics }: Props) {
  const total = diagnostics?.risk_exit_count ?? 0;

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">Risk Management</p>
        <span className="text-xs text-slate-500">{risk.label}</span>
      </div>

      {total === 0 ? (
        <p className="mt-3 text-sm text-slate-500">
          No risk exits triggered — the strategy exited on its own signals over
          this period.
        </p>
      ) : (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat label="Risk exits" value={total} />
          <Stat label="Stop loss" value={diagnostics?.stop_loss_count ?? 0} />
          <Stat label="Take profit" value={diagnostics?.take_profit_count ?? 0} />
          <Stat label="Trailing" value={diagnostics?.trailing_stop_count ?? 0} />
          <Stat label="Max holding" value={diagnostics?.max_holding_exit_count ?? 0} />
        </div>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        Risk rules close positions to cash (never reverse). Exits are daily
        close-based and simplified — intraday breaches, gaps, and liquidity are
        not modelled. Risk rules are not investment recommendations.
      </p>
    </div>
  );
}
