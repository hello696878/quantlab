/**
 * Display-formatting helpers used across chart tooltips, metric cards,
 * and trade tables.
 */

/** 0.273 → "+27.3%" | −0.129 → "−12.9%" */
export function fmtPct(value: number, decimals = 1): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

/** Same as fmtPct but no leading +/− sign. */
export function fmtPctAbs(value: number, decimals = 1): string {
  return `${(Math.abs(value) * 100).toFixed(decimals)}%`;
}

/** 2.67 → "2.67" — for dimensionless ratios (Sharpe, Sortino). */
export function fmtRatio(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

/** 100000 → "$100.0K" | 1250000 → "$1.25M" */
export function fmtDollar(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

/** Compact dollar for Y-axis ticks — no decimals. */
export function fmtDollarTick(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

/** 2267 → "2,267" */
export function fmtInt(value: number): string {
  return value.toLocaleString("en-US");
}

/** "2020-10-16" → "Oct 2020" */
export function fmtMonthYear(dateStr: string): string {
  const [y, m] = dateStr.split("-");
  const months = [
    "Jan","Feb","Mar","Apr","May","Jun",
    "Jul","Aug","Sep","Oct","Nov","Dec",
  ];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

/** "2020-10-16" → "2020" — for sparse x-axis labels */
export function fmtYear(dateStr: string): string {
  return dateStr.slice(0, 4);
}

/** Format a decimal as a percentage string for tooltips, signed. */
export function fmtTooltipPct(value: number): string {
  return fmtPct(value, 2);
}
