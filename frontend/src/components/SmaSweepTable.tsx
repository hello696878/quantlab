"use client";

/**
 * Sortable results table for the SMA parameter sweep.
 *
 * - Click any column header to sort ascending; click again to toggle direction.
 * - The Sharpe Ratio column is heat-coloured: low → amber, high → green.
 * - Default sort: Sharpe descending (best first).
 */

import { useState } from "react";
import type { SmaSweepRow } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";

type SortKey = keyof SmaSweepRow;
type SortDir = "asc" | "desc";

interface Column {
  key: SortKey;
  label: string;
  title: string;
  fmt: (v: number) => string;
  align: "left" | "right";
}

const COLUMNS: Column[] = [
  {
    key: "fast_window",
    label: "Fast",
    title: "Fast SMA window (trading days)",
    fmt: (v) => String(v),
    align: "right",
  },
  {
    key: "slow_window",
    label: "Slow",
    title: "Slow SMA window (trading days)",
    fmt: (v) => String(v),
    align: "right",
  },
  {
    key: "sharpe_ratio",
    label: "Sharpe",
    title: "Annualised Sharpe ratio (rf = 0%)",
    fmt: (v) => fmtRatio(v),
    align: "right",
  },
  {
    key: "cagr",
    label: "CAGR",
    title: "Compound annual growth rate",
    fmt: (v) => fmtPct(v),
    align: "right",
  },
  {
    key: "calmar_ratio",
    label: "Calmar",
    title: "CAGR divided by absolute max drawdown",
    fmt: (v) => fmtRatio(v),
    align: "right",
  },
  {
    key: "total_return",
    label: "Total Return",
    title: "Total return over the full period",
    fmt: (v) => fmtPct(v),
    align: "right",
  },
  {
    key: "max_drawdown",
    label: "Max DD",
    title: "Maximum peak-to-trough drawdown",
    fmt: (v) => fmtPct(v),
    align: "right",
  },
  {
    key: "sortino_ratio",
    label: "Sortino",
    title: "Annualised Sortino ratio (rf = 0%)",
    fmt: (v) => fmtRatio(v),
    align: "right",
  },
  {
    key: "volatility",
    label: "Volatility",
    title: "Annualised return volatility",
    fmt: (v) => fmtPct(v),
    align: "right",
  },
  {
    key: "num_trades",
    label: "Trades",
    title: "Total BUY + SELL events over the period",
    fmt: (v) => String(v),
    align: "right",
  },
];

/**
 * Interpolate a 0–1 scalar to a dark amber → dark emerald heatmap fill.
 * Dark-toned so the light cell text remains readable on the dark theme.
 */
function sharpeColor(t: number): string {
  // t=0 → dark amber (74,52,20),  t=1 → dark emerald (19,64,44)
  const r = Math.round(74 - t * (74 - 19));
  const g = Math.round(52 + t * (64 - 52));
  const b = Math.round(20 + t * (44 - 20));
  return `rgb(${r},${g},${b})`;
}

interface Props {
  rows: SmaSweepRow[];
}

export default function SmaSweepTable({ rows }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("sharpe_ratio");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey] as number;
    const bv = b[sortKey] as number;
    return sortDir === "asc" ? av - bv : bv - av;
  });

  if (rows.length === 0) {
    return (
      <p className="text-center text-slate-400 text-sm py-8">
        No valid combinations found — all fast_window values were ≥ slow_window.
      </p>
    );
  }

  // Pre-compute Sharpe range for heat-colouring.
  const sharpes = rows.map((r) => r.sharpe_ratio);
  const minSharpe = Math.min(...sharpes);
  const maxSharpe = Math.max(...sharpes);
  const sharpeSpan = maxSharpe - minSharpe;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b-2 border-slate-200">
            {COLUMNS.map(({ key, label, title }) => (
              <th
                key={key}
                title={title}
                onClick={() => handleSort(key)}
                className={
                  "px-3 py-2 font-semibold text-slate-600 cursor-pointer select-none " +
                  "whitespace-nowrap hover:text-blue-600 transition-colors " +
                  "text-right first:text-left"
                }
              >
                {label}
                {sortKey === key && (
                  <span className="ml-1 text-blue-500 text-xs">
                    {sortDir === "desc" ? "↓" : "↑"}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={`${row.fast_window}-${row.slow_window}`}
              className={
                "border-b border-slate-100 " +
                (i % 2 === 0 ? "bg-white" : "bg-slate-50") +
                " hover:bg-blue-50 transition-colors"
              }
            >
              {COLUMNS.map(({ key, fmt }) => {
                const raw = row[key] as number;
                const isSharpe = key === "sharpe_ratio";
                const t =
                  sharpeSpan > 1e-9 ? (row.sharpe_ratio - minSharpe) / sharpeSpan : 0.5;
                // Best-performing combination gets a neon accent outline + glow.
                const isBest =
                  isSharpe && sharpeSpan > 1e-9 && row.sharpe_ratio === maxSharpe;

                return (
                  <td
                    key={key}
                    className="px-3 py-1.5 text-right text-slate-700 tabular-nums first:text-left first:font-medium"
                    style={
                      isSharpe
                        ? {
                            backgroundColor: sharpeColor(t),
                            fontWeight: 600,
                            ...(isBest
                              ? {
                                  outline: "1.5px solid var(--accent)",
                                  outlineOffset: "-2px",
                                  boxShadow:
                                    "inset 0 0 14px -2px rgba(var(--accent-rgb), 0.65)",
                                  color: "var(--accent-text)",
                                }
                              : {}),
                          }
                        : undefined
                    }
                  >
                    {fmt(raw)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
