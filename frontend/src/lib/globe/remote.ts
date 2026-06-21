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

interface DtoIndex {
  name: string;
  ticker: string;
  level: number;
  change_pct: number;
  sparkline: number[];
  is_sample: boolean;
}
interface DtoMacro {
  gdp_growth: number;
  inflation: number;
  unemployment: number;
  policy_rate: number;
  debt_to_gdp: number;
}
interface DtoFx {
  pair: string;
  rate: number;
  change_pct: number;
}
interface DtoStructure {
  market_cap: string;
  listed_companies: string;
  settlement: string;
  notes: string;
}
interface DtoHeadline {
  title: string;
  sentiment: Sentiment;
}
interface DtoDossier {
  id: string;
  country: string;
  region: string;
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
  market_structure: DtoStructure;
  headlines: DtoHeadline[];
}
interface DtoResponse {
  markets: DtoDossier[];
  count: number;
  data_status: string;
  notice: string;
}

export interface GlobeMarketsResult {
  markets: Market[];
  notice: string;
  dataStatus: string;
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
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`globe markets request failed: ${res.status}`);
  const data = (await res.json()) as DtoResponse;
  if (!data || !Array.isArray(data.markets) || data.markets.length === 0) {
    throw new Error("globe markets response was empty");
  }
  return {
    markets: data.markets.map(mapDossier),
    notice: data.notice,
    dataStatus: data.data_status,
  };
}
