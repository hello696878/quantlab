/**
 * Global Markets Globe — backend data client (Phase 20.2).
 *
 * Fetches the typed country-dossier dataset from the FastAPI data layer
 * (`GET /api/globe/markets`) and maps each backend dossier into the frontend
 * `Market` shape the UI already consumes. If the backend is unavailable, the
 * caller falls back to the bundled static `MARKETS` — the Globe never breaks.
 *
 * Even the backend payload is **static illustrative sample data** (every record
 * is `is_sample`, `source_status` is `static_sample`). Index levels and FX
 * values are mapped to the literal "Sample" so the UI never shows a fabricated
 * level; backend `change_pct` is in percent and is converted to the decimal the
 * UI formatters expect.
 */

import {
  CROSS_LINKS,
  type Market,
  type MarketRegion,
  type Sentiment,
} from "@/lib/globe/markets";

type StaticSampleStatus = "static_sample";

interface DtoIndex {
  name: string;
  ticker: string;
  level: number;
  change_pct: number;
  sparkline: number[];
  is_sample: true;
}
interface DtoMacro {
  gdp_growth: number;
  inflation: number;
  unemployment: number;
  policy_rate: number;
  debt_to_gdp: number;
  is_sample: true;
}
interface DtoFx {
  pair: string;
  rate: number;
  change_pct: number;
  is_sample: true;
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
  macro: StaticSampleStatus;
  indices: StaticSampleStatus;
  fx: StaticSampleStatus;
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
  data_status: StaticSampleStatus;
  notice: string;
}

export interface GlobeMarketsResult {
  markets: Market[];
  notice: string;
  dataStatus: StaticSampleStatus;
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

function hasStaticSources(value: unknown): value is DtoSourceStatus {
  if (!isRecord(value)) return false;
  return ["macro", "indices", "fx", "news"].every(
    (key) => value[key] === "static_sample",
  );
}

function isDossier(value: unknown): value is DtoDossier {
  if (!isRecord(value)) return false;
  const d = value as Record<string, unknown>;
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
      isFiniteNumber(item.level) && isFiniteNumber(item.change_pct) && item.is_sample === true &&
      Array.isArray(item.sparkline) && item.sparkline.length > 1 && item.sparkline.every(isFiniteNumber)
    ) &&
    isRecord(macro) && ["gdp_growth", "inflation", "unemployment", "policy_rate", "debt_to_gdp"].every(
      (key) => isFiniteNumber(macro[key]),
    ) && macro.is_sample === true &&
    Array.isArray(fx) && fx.length > 0 && fx.every((item) =>
      isRecord(item) && isNonEmptyString(item.pair) && isFiniteNumber(item.rate) &&
      isFiniteNumber(item.change_pct) && item.is_sample === true
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
    ) &&
    hasStaticSources(d.source_status)
  );
}

function parseResponse(value: unknown): DtoResponse {
  if (!isRecord(value) || value.data_status !== "static_sample" ||
      !isNonEmptyString(value.notice) || !value.notice.includes("Static illustrative data") ||
      !Array.isArray(value.markets) || value.markets.length === 0 ||
      !value.markets.every(isDossier) || value.count !== value.markets.length) {
    throw new Error("globe markets response did not match the static dossier schema");
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
      level: "Sample", // never surface a fabricated level
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
      value: "Sample",
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
    notice: data.notice,
    dataStatus: data.data_status,
  };
}
