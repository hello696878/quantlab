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

const MONTHS = [
  "Jan","Feb","Mar","Apr","May","Jun",
  "Jul","Aug","Sep","Oct","Nov","Dec",
] as const;

const YMD_RE = /^\d{4}-\d{2}(-\d{2})?/;

/**
 * Normalize an unknown date-like value to a "YYYY-MM-DD"-leading string.
 *
 * Chart libraries hand tooltip/tick formatters whatever the x-axis carries —
 * strings, numbers, Dates, or whole point objects — so date formatting must
 * never assume a string.  Returns:
 *   - a string starting with YYYY-MM(-DD) when the value is date-like,
 *   - the original string for non-date strings (safe pass-through),
 *   - null when nothing date-like (or string-like) can be extracted.
 */
export function normalizeDateInput(value: unknown): string | null {
  if (value == null) return null;

  if (typeof value === "string") {
    return value; // YYYY-MM-DD and ISO datetimes both match YMD_RE downstream
  }

  if (value instanceof Date) {
    return isNaN(value.getTime()) ? null : value.toISOString().slice(0, 10);
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    if (value > 1e11) return new Date(value).toISOString().slice(0, 10); // ms epoch
    if (value > 1e9) return new Date(value * 1000).toISOString().slice(0, 10); // s epoch
    if (Number.isInteger(value) && value >= 1900 && value <= 2200) {
      return String(value); // bare year
    }
    return String(value); // numeric but not a date — safe fallback string
  }

  if (typeof value === "object") {
    const o = value as { date?: unknown; x?: unknown; time?: unknown };
    if (o.date != null) return normalizeDateInput(o.date);
    if (o.x != null) return normalizeDateInput(o.x);
    if (o.time != null) return normalizeDateInput(o.time);
    return null;
  }

  return null;
}

/** "2020-10-16" / Date / ISO datetime → "Oct 2020"; never throws ("—" fallback). */
export function fmtMonthYear(value: unknown): string {
  const s = normalizeDateInput(value);
  if (s == null) return "—";
  if (!YMD_RE.test(s)) return s; // non-date string/number — show as-is, no garbage
  const y = s.slice(0, 4);
  const m = parseInt(s.slice(5, 7), 10);
  const month = MONTHS[m - 1];
  return month ? `${month} ${y}` : y;
}

/** "2020-10-16" / Date → "2020" — for sparse x-axis labels; never throws. */
export function fmtYear(value: unknown): string {
  const s = normalizeDateInput(value);
  if (s == null) return "—";
  return YMD_RE.test(s) || /^\d{4}$/.test(s) ? s.slice(0, 4) : s;
}

/** Format a decimal as a percentage string for tooltips, signed. */
export function fmtTooltipPct(value: number): string {
  return fmtPct(value, 2);
}
