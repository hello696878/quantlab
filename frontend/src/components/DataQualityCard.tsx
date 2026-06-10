"use client";

import type { DataQuality } from "@/lib/types";

interface Props {
  provider?: string | null;
  quality: DataQuality;
}

const PROVIDER_LABEL: Record<string, string> = {
  yfinance: "Yahoo Finance (yfinance)",
  csv_upload: "CSV upload",
  synthetic: "Synthetic (test)",
};

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-medium text-slate-700">{value}</p>
    </div>
  );
}

/**
 * Compact data-source / data-quality summary for a backtest result.  Purely
 * informational — warnings are amber notes, not errors (unusable data already
 * fails at fetch time).
 */
export default function DataQualityCard({ provider, quality }: Props) {
  const providerLabel =
    PROVIDER_LABEL[provider ?? quality.provider] ?? (provider || quality.provider);
  const range =
    quality.actual_start_date && quality.actual_end_date
      ? `${quality.actual_start_date} → ${quality.actual_end_date}`
      : "—";

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">Data Source</p>
        <span className="text-xs text-slate-500">
          {quality.adjusted ? "Adjusted prices" : "Prices as provided"} ·{" "}
          {quality.price_column_used}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <Item label="Provider" value={providerLabel} />
        <Item label="Rows" value={quality.row_count.toLocaleString("en-US")} />
        <Item label="Actual range" value={range} />
        <Item
          label="Missing / dup. dates"
          value={`${quality.missing_value_count} / ${quality.duplicate_date_count}`}
        />
      </div>

      {quality.warnings.length > 0 ? (
        <ul className="mt-3 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
          {quality.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-slate-500">No data warnings.</p>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        Market data may contain gaps, revisions, missing values, or
        provider-specific errors.{" "}
        {(provider ?? quality.provider) === "yfinance" &&
          "Yahoo Finance / yfinance is convenient for research but is not a professional-grade data feed."}
      </p>
    </div>
  );
}
