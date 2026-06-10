/**
 * Local application settings / preferences (v1).
 *
 * Single-user, browser-only: everything is persisted in `localStorage` — there
 * is no account system and no cloud sync.  Settings prefill new forms and
 * control display conventions (theme accent, default report template).  The
 * annualization convention is sent with new single-asset Backtest and Strategy
 * Comparison requests; portfolio tools keep their own 252-day convention.
 */

import type { ReportTemplate } from "./reportExport";

export type DateRangeOption =
  | "last_1y"
  | "last_3y"
  | "last_5y"
  | "last_10y"
  | "custom";

export type AnnualizationConvention = "trading_days_252" | "crypto_365" | "auto";

export type AccentColor =
  | "cyan"
  | "blue"
  | "emerald"
  | "violet"
  | "amber"
  | "risk";

export interface AppSettings {
  default_initial_capital: number;
  default_transaction_cost_bps: number;
  default_benchmark_ticker: string;
  default_risk_free_rate: number;
  default_date_range: DateRangeOption;
  /** Used only when `default_date_range === "custom"`. */
  custom_start_date: string;
  custom_end_date: string;
  annualization_convention: AnnualizationConvention;
  accent_color: AccentColor;
  default_report_template: ReportTemplate;
}

export const DEFAULT_SETTINGS: AppSettings = {
  default_initial_capital: 100_000,
  default_transaction_cost_bps: 10,
  default_benchmark_ticker: "SPY",
  default_risk_free_rate: 0.02,
  default_date_range: "last_10y",
  custom_start_date: "2015-01-01",
  custom_end_date: "2023-12-31",
  annualization_convention: "trading_days_252",
  accent_color: "cyan",
  default_report_template: "standard",
};

// ---------------------------------------------------------------------------
// Option lists (for select inputs)
// ---------------------------------------------------------------------------

export const DATE_RANGE_OPTIONS: { id: DateRangeOption; label: string }[] = [
  { id: "last_1y", label: "Last 1 year" },
  { id: "last_3y", label: "Last 3 years" },
  { id: "last_5y", label: "Last 5 years" },
  { id: "last_10y", label: "Last 10 years" },
  { id: "custom", label: "Custom range" },
];

export const ANNUALIZATION_OPTIONS: {
  id: AnnualizationConvention;
  label: string;
}[] = [
  { id: "trading_days_252", label: "252 trading days (equities)" },
  { id: "crypto_365", label: "365 days (crypto / 24-7)" },
  { id: "auto", label: "Auto (ticker-based)" },
];

export const ACCENT_OPTIONS: { id: AccentColor; label: string; swatch: string }[] = [
  { id: "cyan", label: "Cyan", swatch: "#34e0e8" },
  { id: "blue", label: "Blue", swatch: "#4d8bff" },
  { id: "emerald", label: "Emerald", swatch: "#2be0a8" },
  { id: "violet", label: "Violet", swatch: "#a78bfa" },
  { id: "amber", label: "Amber", swatch: "#fbbf24" },
  { id: "risk", label: "Risk", swatch: "#f06058" },
];

const ACCENT_IDS = ACCENT_OPTIONS.map((a) => a.id);
const DATE_RANGE_IDS = DATE_RANGE_OPTIONS.map((d) => d.id);
const ANNUALIZATION_IDS = ANNUALIZATION_OPTIONS.map((a) => a.id);
const TEMPLATE_IDS: ReportTemplate[] = [
  "standard",
  "executive_summary",
  "quant_tear_sheet",
  "risk_report",
];

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

export const SETTINGS_STORAGE_KEY = "quantlab.settings.v1";

function num(value: unknown, fallback: number, min?: number): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  if (min !== undefined && n < min) return fallback;
  return n;
}

function oneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

function isValidISODate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

/** Coerce arbitrary stored/partial data into a complete, valid AppSettings. */
export function sanitizeSettings(raw: unknown): AppSettings {
  const r = (raw ?? {}) as Record<string, unknown>;
  const ticker =
    typeof r.default_benchmark_ticker === "string" &&
    r.default_benchmark_ticker.trim()
      ? r.default_benchmark_ticker.trim().toUpperCase()
      : DEFAULT_SETTINGS.default_benchmark_ticker;

  return {
    default_initial_capital: num(
      r.default_initial_capital,
      DEFAULT_SETTINGS.default_initial_capital,
      // Must be strictly positive; fall back if <= 0.
      Number.MIN_VALUE,
    ),
    default_transaction_cost_bps: num(
      r.default_transaction_cost_bps,
      DEFAULT_SETTINGS.default_transaction_cost_bps,
      0,
    ),
    default_benchmark_ticker: ticker,
    default_risk_free_rate: num(
      r.default_risk_free_rate,
      DEFAULT_SETTINGS.default_risk_free_rate,
      0,
    ),
    default_date_range: oneOf(
      r.default_date_range,
      DATE_RANGE_IDS,
      DEFAULT_SETTINGS.default_date_range,
    ),
    custom_start_date: isValidISODate(r.custom_start_date)
      ? r.custom_start_date
      : DEFAULT_SETTINGS.custom_start_date,
    custom_end_date: isValidISODate(r.custom_end_date)
      ? r.custom_end_date
      : DEFAULT_SETTINGS.custom_end_date,
    annualization_convention: oneOf(
      r.annualization_convention,
      ANNUALIZATION_IDS,
      DEFAULT_SETTINGS.annualization_convention,
    ),
    accent_color: oneOf(r.accent_color, ACCENT_IDS, DEFAULT_SETTINGS.accent_color),
    default_report_template: oneOf(
      r.default_report_template,
      TEMPLATE_IDS,
      DEFAULT_SETTINGS.default_report_template,
    ),
  };
}

/** Load and validate settings from localStorage (defaults on the server). */
export function loadSettings(): AppSettings {
  if (typeof window === "undefined") return { ...DEFAULT_SETTINGS };
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

/** Persist settings (after sanitising) and return the stored value. */
export function saveSettings(settings: AppSettings): AppSettings {
  const clean = sanitizeSettings(settings);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(clean));
    } catch {
      // Ignore quota / availability errors — settings stay in-memory.
    }
  }
  return clean;
}

/** Clear stored settings and return the defaults. */
export function resetSettings(): AppSettings {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(SETTINGS_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
  return { ...DEFAULT_SETTINGS };
}

// ---------------------------------------------------------------------------
// Derived helpers
// ---------------------------------------------------------------------------

function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export interface ResolvedDateRange {
  start_date: string;
  end_date: string;
}

const RANGE_YEARS: Record<Exclude<DateRangeOption, "custom">, number> = {
  last_1y: 1,
  last_3y: 3,
  last_5y: 5,
  last_10y: 10,
};

/** Resolve the preferred default date range into concrete YYYY-MM-DD bounds. */
export function resolveDateRange(
  settings: AppSettings,
  today: Date = new Date(),
): ResolvedDateRange {
  if (settings.default_date_range === "custom") {
    return {
      start_date: settings.custom_start_date,
      end_date: settings.custom_end_date,
    };
  }
  const years = RANGE_YEARS[settings.default_date_range];
  const start = new Date(today);
  start.setFullYear(start.getFullYear() - years);
  return { start_date: isoDate(start), end_date: isoDate(today) };
}

// ---------------------------------------------------------------------------
// Theme accent
// ---------------------------------------------------------------------------

/** Apply the accent color to the document root (CSS reads `[data-accent]`). */
export function applyAccent(accent: AccentColor): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-accent", accent);
  }
}
