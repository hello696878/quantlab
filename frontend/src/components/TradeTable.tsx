"use client";

import { useState } from "react";
import type { TradeRecord } from "@/lib/types";
import { fmtMonthYear } from "@/lib/format";

interface Props {
  trades: TradeRecord[];
}

const PAGE_SIZE = 20;

/**
 * Visual style per trade action.  Green = took long exposure, red = took short
 * exposure, slate = closed to cash.  Covers single-asset long/short actions and
 * the pairs spread actions.
 */
function actionStyle(action: TradeRecord["action"]): {
  pillCls: string;
  arrow: string;
} {
  switch (action) {
    case "BUY":
    case "FLIP_TO_LONG":
    case "LONG SPREAD":
      return { pillCls: "bg-green-100 text-green-700", arrow: "▲ " };
    case "SHORT":
    case "FLIP_TO_SHORT":
    case "SHORT SPREAD":
      return { pillCls: "bg-red-100 text-red-700", arrow: "▼ " };
    case "SELL":
    case "COVER":
    case "EXIT":
    default:
      return { pillCls: "bg-slate-100 text-slate-600", arrow: "● " };
  }
}

const REASON_LABEL: Record<string, string> = {
  signal_entry: "Signal entry",
  signal_exit: "Signal exit",
  signal_flip: "Signal flip",
  stop_loss: "Stop loss",
  take_profit: "Take profit",
  trailing_stop: "Trailing stop",
  max_holding_days: "Max holding",
};

const RISK_REASONS = new Set([
  "stop_loss",
  "take_profit",
  "trailing_stop",
  "max_holding_days",
]);

export default function TradeTable({ trades }: Props) {
  const [page, setPage] = useState(0);
  // Only show the Reason column when risk management is active (trades carry a reason).
  const hasReason = trades.some((t) => t.reason != null);

  if (!trades.length) {
    return (
      <div className="text-center py-10 text-slate-400 text-sm">
        No trades were generated in this backtest period.
        <br />
        <span className="text-xs mt-1 block">
          This usually means the selected strategy did not trigger an entry
          within the selected date range.
        </span>
      </div>
    );
  }

  const totalPages = Math.ceil(trades.length / PAGE_SIZE);
  const visible = trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div>
      {/* Scrollable table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 w-8">
                #
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Date
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Action
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                Price
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                Shares
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                Transaction Cost (USD)
              </th>
              {hasReason && (
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Reason
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.map((trade, idx) => {
              const globalIdx = page * PAGE_SIZE + idx + 1;
              const { pillCls, arrow } = actionStyle(trade.action);
              return (
                <tr
                  key={globalIdx}
                  className="hover:bg-slate-50 transition-colors"
                >
                  <td className="px-4 py-2.5 text-xs text-slate-400 tabular">
                    {globalIdx}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700 whitespace-nowrap">
                    <span className="hidden sm:inline">
                      {fmtMonthYear(trade.date)}
                    </span>
                    <span className="sm:hidden">{trade.date}</span>
                    <span className="ml-1 text-xs text-slate-400">
                      {trade.date}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={
                        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold " +
                        pillCls
                      }
                    >
                      {arrow}{trade.action.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular text-slate-800 font-medium">
                    ${trade.price.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular text-slate-600">
                    {trade.shares.toLocaleString("en-US", {
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular text-slate-600">
                    ${trade.cost.toFixed(2)}
                  </td>
                  {hasReason && (
                    <td className="px-4 py-2.5 text-xs whitespace-nowrap">
                      {trade.reason ? (
                        <span
                          className={
                            "inline-flex items-center rounded-full px-2 py-0.5 font-medium " +
                            (RISK_REASONS.has(trade.reason)
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500")
                          }
                        >
                          {REASON_LABEL[trade.reason] ?? trade.reason}
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>
            Showing {page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, trades.length)} of {trades.length}{" "}
            trades
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 rounded border border-slate-200 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => setPage(i)}
                className={
                  "px-2.5 py-1 rounded border text-xs font-medium " +
                  (i === page
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-slate-200 hover:bg-slate-100 text-slate-600")
                }
              >
                {i + 1}
              </button>
            ))}
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page === totalPages - 1}
              className="px-2 py-1 rounded border border-slate-200 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
