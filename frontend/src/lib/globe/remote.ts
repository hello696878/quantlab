/**
 * Global Markets Globe — backend data client (Phase 20.2).
 *
 * Fetches the typed country-dossier dataset from the FastAPI data layer
 * (`GET /api/globe/markets`) and maps each backend dossier into the frontend
 * `Market` shape the UI already consumes. If the backend is unavailable, the
 * caller falls back to the bundled static `MARKETS` — the Globe never breaks.
 *
 * The backend payload has a static illustrative core and may carry field-level
 * provenance for optional US FRED macro enrichment. Index and FX values are
 * mapped to the literal "Sample" so the UI never shows a fabricated level;
 * backend `change_pct` is in percent and is converted to the decimal expected
 * by the UI formatters.
 */

import {
  CROSS_LINKS,
  type MacroField,
  type MacroSourceState,
  type Market,
  type MarketRegion,
  type QuoteSourceState,
  type Sentiment,
} from "@/lib/globe/markets";

type StaticSampleStatus = "static_sample";
type DataStatus =
  | "static_sample"
  | "mixed_static_and_fred"
  | "mixed_static_and_quotes"
  | "mixed_static_fred_quotes";

// Macro may become non-static via optional FRED; indices/FX may become
// delayed-quote / quote-unavailable via the optional quote adapter. News stays
// static sample in this phase.
const MACRO_STATES: readonly MacroSourceState[] = [
  "static_sample",
  "fred_live",
  "fred_unavailable",
  "planned",
];
const QUOTE_STATES: readonly QuoteSourceState[] = [
  "static_sample",
  "delayed_quote",
  "quote_unavailable",
  "planned",
];
const DATA_STATUSES: readonly DataStatus[] = [
  "static_sample",
  "mixed_static_and_fred",
  "mixed_static_and_quotes",
  "mixed_static_fred_quotes",
];

/** Format a delayed level/rate for display (real quote shown; static = "Sample"). */
function formatQuote(n: number): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
const MACRO_FIELDS: readonly MacroField[] = [
  "gdp_growth",
  "inflation",
  "unemployment",
  "policy_rate",
  "debt_to_gdp",
];

interface DtoIndex {
  name: string;
  ticker: string;
  level: number;
  change_pct: number;
  sparkline: number[];
  is_sample: boolean;
  as_of_date?: string | null;
}
interface DtoMacro {
  gdp_growth: number;
  inflation: number;
  unemployment: number;
  policy_rate: number;
  debt_to_gdp: number;
  is_sample: boolean;
  as_of_date?: string | null;
  fred_fields: MacroField[];
  fred_as_of: Partial<Record<MacroField, string>>;
}
interface DtoFx {
  pair: string;
  rate: number;
  change_pct: number;
  is_sample: boolean;
  as_of_date?: string | null;
}
interface DtoRates {
  policy_rate: number;
  ten_year_yield: number | null;
  is_sample: true;
}
interface DtoStructure {
  market_cap: string;
  listed_companies: string;
  settlement: string;
  notes: string;
  is_sample: true;
}
interface DtoHeadline {
  title: string;
  sentiment: Sentiment;
  is_sample: true;
}
interface DtoLink {
  label: string;
  href: string;
}
interface DtoSourceStatus {
  macro: MacroSourceState;
  indices: QuoteSourceState;
  fx: QuoteSourceState;
  news: StaticSampleStatus;
}
interface DtoDossier {
  id: string;
  country: string;
  region: MarketRegion;
  subregion: string;
  flag: string;
  lat: number;
  lon: number;
  currency: string;
  exchange: string;
  trading_hours: string;
  timezone: string;
  static_data_notice: string;
  indices: DtoIndex[];
  macro: DtoMacro;
  fx: DtoFx[];
  rates: DtoRates;
  market_structure: DtoStructure;
  headlines: DtoHeadline[];
  links: DtoLink[];
  source_status: DtoSourceStatus;
}
interface DtoResponse {
  markets: DtoDossier[];
  count: number;
  data_status: DataStatus;
  notice: string;
  warnings?: string[];
}

export interface GlobeMarketsResult {
  markets: Market[];
  notice: string;
  dataStatus: DataStatus;
  warnings: string[];
}

const REGIONS: readonly MarketRegion[] = ["Americas", "Europe", "Asia-Pacific"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function hasValidSources(value: unknown): value is DtoSourceStatus {
  if (!isRecord(value)) return false;
  const macroOk = MACRO_STATES.includes(value.macro as MacroSourceState);
  const indicesOk = QUOTE_STATES.includes(value.indices as QuoteSourceState);
  const fxOk = QUOTE_STATES.includes(value.fx as QuoteSourceState);
  const newsOk = value.news === "static_sample";
  return macroOk && indicesOk && fxOk && newsOk;
}

function hasValidMacroProvenance(
  value: unknown,
  source: MacroSourceState,
): boolean {
  if (!isRecord(value)) return false;
  const fields = value.fred_fields;
  const dates = value.fred_as_of;
  if (!Array.isArray(fields) || !isRecord(dates)) return false;
  if (
    new Set(fields).size !== fields.length ||
    !fields.every((field) => MACRO_FIELDS.includes(field as MacroField))
  ) {
    return false;
  }
  const datesValid = Object.entries(dates).every(
    ([field, observationDate]) =>
      MACRO_FIELDS.includes(field as MacroField) &&
      fields.includes(field) &&
      isNonEmptyString(observationDate),
  );
  if (!datesValid) return false;
  if (source === "fred_live") {
    return (
      fields.length > 0 &&
      fields.every((field) => isNonEmptyString(dates[field as MacroField]))
    );
  }
  return fields.length === 0 && Object.keys(dates).length === 0;
}

function isDossier(value: unknown): value is DtoDossier {
  if (!isRecord(value)) return false;
  const d = value as Record<string, unknown>;
  if (!hasValidSources(d.source_status)) return false;
  const sources = d.source_status;
  const indices = d.indices;
  const fx = d.fx;
  const headlines = d.headlines;
  const macro = d.macro;
  const rates = d.rates;
  const structure = d.market_structure;
  const links = d.links;
  return (
    ["id", "country", "subregion", "flag", "currency", "exchange", "trading_hours", "timezone", "static_data_notice"].every(
      (key) => isNonEmptyString(d[key]),
    ) &&
    REGIONS.includes(d.region as MarketRegion) &&
    isFiniteNumber(d.lat) && d.lat >= -90 && d.lat <= 90 &&
    isFiniteNumber(d.lon) && d.lon >= -180 && d.lon <= 180 &&
    Array.isArray(indices) && indices.length > 0 && indices.every((item) =>
      isRecord(item) && isNonEmptyString(item.name) && isNonEmptyString(item.ticker) &&
      isFiniteNumber(item.level) && isFiniteNumber(item.change_pct) && typeof item.is_sample === "boolean" &&
      (item.as_of_date == null || isNonEmptyString(item.as_of_date)) &&
      Array.isArray(item.sparkline) && item.sparkline.length > 1 && item.sparkline.every(isFiniteNumber)
    ) &&
    isRecord(macro) && ["gdp_growth", "inflation", "unemployment", "policy_rate", "debt_to_gdp"].every(
      (key) => isFiniteNumber(macro[key]),
    ) && typeof macro.is_sample === "boolean" &&
    (macro.as_of_date == null || isNonEmptyString(macro.as_of_date)) &&
    hasValidMacroProvenance(macro, sources.macro) &&
    Array.isArray(fx) && fx.length > 0 && fx.every((item) =>
      isRecord(item) && isNonEmptyString(item.pair) && isFiniteNumber(item.rate) &&
      isFiniteNumber(item.change_pct) && typeof item.is_sample === "boolean" &&
      (item.as_of_date == null || isNonEmptyString(item.as_of_date))
    ) &&
    isRecord(rates) && isFiniteNumber(rates.policy_rate) &&
      (rates.ten_year_yield === null || isFiniteNumber(rates.ten_year_yield)) && rates.is_sample === true &&
    isRecord(structure) && ["market_cap", "listed_companies", "settlement", "notes"].every(
      (key) => isNonEmptyString(structure[key]),
    ) && structure.is_sample === true &&
    Array.isArray(headlines) && headlines.length > 0 && headlines.every((item) =>
      isRecord(item) && isNonEmptyString(item.title) &&
      ["Bullish", "Bearish", "Neutral"].includes(String(item.sentiment)) && item.is_sample === true
    ) &&
    Array.isArray(links) && links.length > 0 && links.every((item) =>
      isRecord(item) && isNonEmptyString(item.label) && isNonEmptyString(item.href)
    )
  );
}

function parseResponse(value: unknown): DtoResponse {
  const dataStatusOk =
    isRecord(value) &&
    DATA_STATUSES.includes(value.data_status as DataStatus);
  const warningsOk =
    !isRecord(value) ||
    value.warnings === undefined ||
    (Array.isArray(value.warnings) && value.warnings.every(isNonEmptyString));
  if (!isRecord(value) || !dataStatusOk || !warningsOk ||
      !isNonEmptyString(value.notice) || !value.notice.includes("Static illustrative data") ||
      !Array.isArray(value.markets) || value.markets.length === 0 ||
      !value.markets.every(isDossier) || value.count !== value.markets.length) {
    throw new Error("globe markets response did not match the dossier schema");
  }
  return value as unknown as DtoResponse;
}

function mapDossier(d: DtoDossier): Market {
  return {
    id: d.id,
    country: d.country,
    flag: d.flag,
    region: d.region as MarketRegion,
    subregion: d.subregion,
    lat: d.lat,
    lon: d.lon,
    currency: d.currency,
    exchange: d.exchange,
    tradingHours: d.trading_hours,
    indices: d.indices.map((i) => ({
      name: i.name,
      ticker: i.ticker,
      // Static rows show the literal "Sample"; only a real delayed quote shows a level.
      level: i.is_sample ? "Sample" : formatQuote(i.level),
      changePct: i.change_pct / 100, // percent → decimal for fmtPct
      sparkline: i.sparkline,
    })),
    macro: {
      gdpGrowth: d.macro.gdp_growth,
      inflation: d.macro.inflation,
      unemployment: d.macro.unemployment,
      policyRate: d.macro.policy_rate,
      debtToGdp: d.macro.debt_to_gdp,
    },
    fx: d.fx.map((f) => ({
      pair: f.pair,
      value: f.is_sample ? "Sample" : formatQuote(f.rate),
      changePct: f.change_pct / 100,
    })),
    marketStructure: {
      marketCap: d.market_structure.market_cap,
      listedCompanies: d.market_structure.listed_companies,
      settlement: d.market_structure.settlement,
      notes: d.market_structure.notes,
    },
    headlines: d.headlines.map((h) => ({ title: h.title, sentiment: h.sentiment })),
    links: CROSS_LINKS,
    macroSource: d.source_status.macro,
    macroAsOf: d.macro.as_of_date ?? null,
    macroFredFields: d.macro.fred_fields,
    macroFredAsOf: d.macro.fred_as_of,
    indicesSource: d.source_status.indices,
    fxSource: d.source_status.fx,
    indicesAsOf: d.indices[0]?.as_of_date ?? null,
    fxAsOf: d.fx[0]?.as_of_date ?? null,
  };
}

/**
 * Fetch the backend market dossiers and map them to the UI `Market` shape.
 * Throws on any failure (network, non-2xx, empty) so the caller can fall back
 * to the bundled static data.
 */
export async function fetchGlobeMarkets(
  signal?: AbortSignal,
): Promise<GlobeMarketsResult> {
  const res = await fetch("/api/globe/markets", {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`globe markets request failed: ${res.status}`);
  const data = parseResponse(await res.json());
  return {
    markets: data.markets.map(mapDossier),
    warnings: data.warnings ?? [],
    notice: data.notice,
    dataStatus: data.data_status,
  };
}
