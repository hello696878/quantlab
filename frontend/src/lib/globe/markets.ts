/**
 * Global Markets Globe — static illustrative market data (v1).
 *
 * IMPORTANT — this is deterministic, hand-authored SAMPLE data for the
 * educational showcase and frontend fallback. It is not a real-time feed. The
 * backend may optionally source selected US macro fields from FRED; index, FX,
 * market-cap, listed-company, and headline values remain illustrative unless
 * the optional delayed index/FX adapter enriches a supported primary quote.
 *
 * Cross-links route into existing QuantLab modules via the in-app `View`
 * router (this app is a single-page workspace switcher, not a multi-route
 * site, so links open the relevant lab rather than a deep-linked URL).
 */

import type { View } from "@/components/AppShell";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Region groups used for the filter chips and globe colouring. */
export type MarketRegion = "Americas" | "Europe" | "Asia-Pacific";

export const MARKET_REGIONS: readonly MarketRegion[] = [
  "Americas",
  "Europe",
  "Asia-Pacific",
] as const;

export type Sentiment = "Bullish" | "Bearish" | "Neutral";
export type MacroField =
  | "gdp_growth"
  | "inflation"
  | "unemployment"
  | "policy_rate"
  | "debt_to_gdp";

export const STATIC_DATA_NOTICE =
  "Static illustrative data is the default. Optional US FRED macro and delayed index/FX quote adapters may enrich supported fields; news integration is planned.";

export interface MarketIndex {
  name: string;
  ticker: string;
  /** "Sample" for static rows; formatted delayed level for an enriched primary row. */
  level: string;
  /** Illustrative daily change, decimal (0.0042 = +0.42%). */
  changePct: number;
  /** Deterministic illustrative shape for a mini sparkline (unitless). */
  sparkline: number[];
}

export interface MarketMacro {
  gdpGrowth: number; // % YoY (illustrative)
  inflation: number; // % YoY (illustrative)
  unemployment: number; // % (illustrative)
  policyRate: number; // % (illustrative)
  debtToGdp: number; // % of GDP (illustrative)
}

export interface MarketFx {
  pair: string;
  /** "Sample" for static rows; formatted delayed rate for an enriched primary row. */
  value: string;
  changePct: number;
}

export interface MarketStructure {
  marketCap: string;
  listedCompanies: string;
  settlement: string;
  notes: string;
}

export interface MarketHeadline {
  title: string;
  sentiment: Sentiment;
}

export interface MarketLink {
  label: string;
  /** In-app workspace to open (cross-link into an existing QuantLab module). */
  view: View;
}

/**
 * Provenance of a market's macro block. Bundled static data leaves this unset
 * (treated as "static_sample"); the backend data layer sets it per market.
 * Macro may be enriched from FRED; index/FX provenance is tracked separately
 * by QuoteSourceState. News remains static sample.
 */
export type MacroSourceState =
  | "static_sample"
  | "fred_live"
  | "fred_unavailable"
  | "planned";

/**
 * Provenance of a market's index / FX block. Bundled static data leaves this
 * unset (treated as "static_sample"); the optional delayed-quote adapter sets
 * it per market when enabled. Quotes are delayed, never real-time.
 */
export type QuoteSourceState =
  | "static_sample"
  | "delayed_quote"
  | "quote_unavailable"
  | "planned";

/**
 * Provenance of a market's news/headlines block. v1 is always static sample
 * (no live news); `news_unavailable` is the honest fallback when an unconfigured
 * news provider is requested.
 */
export type NewsSourceState = "static_sample" | "news_unavailable" | "planned";

export interface Market {
  id: string;
  country: string;
  flag: string;
  region: MarketRegion;
  /** More specific geography shown in the dossier header. */
  subregion: string;
  lat: number;
  lon: number;
  currency: string;
  exchange: string;
  tradingHours: string;
  indices: MarketIndex[];
  macro: MarketMacro;
  fx: MarketFx[];
  marketStructure: MarketStructure;
  headlines: MarketHeadline[];
  links: MarketLink[];
  /** Macro provenance (undefined → static sample). Set by the backend layer. */
  macroSource?: MacroSourceState;
  /** Macro "as of" date when (partly) enriched from FRED. */
  macroAsOf?: string | null;
  /** Exact macro fields sourced from FRED; all remaining fields are sample data. */
  macroFredFields?: MacroField[];
  /** Per-field FRED observation dates. */
  macroFredAsOf?: Partial<Record<MacroField, string>>;
  /** Index-block provenance (undefined → static sample). Set by the quote adapter. */
  indicesSource?: QuoteSourceState;
  /** FX-block provenance (undefined → static sample). Set by the quote adapter. */
  fxSource?: QuoteSourceState;
  /** Delayed index "as of" date when enriched. */
  indicesAsOf?: string | null;
  /** Delayed FX "as of" date when enriched. */
  fxAsOf?: string | null;
  /** News-block provenance (undefined → static sample). */
  newsSource?: NewsSourceState;
}

// ---------------------------------------------------------------------------
// Deterministic sparkline generator
// ---------------------------------------------------------------------------

/**
 * Seeded pseudo-random walk → a 16-point illustrative sparkline. Fully
 * deterministic (same seed/drift always yields the same array) so the showcase
 * renders identically every run. Values orbit ~100 and carry no units — they
 * exist only to give each index card a distinct, stable shape.
 */
function makeSparkline(seed: number, drift: number): number[] {
  let s = seed >>> 0;
  const rand = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const out: number[] = [];
  let v = 100;
  for (let i = 0; i < 16; i += 1) {
    v *= 1 + drift + (rand() - 0.5) * 0.022;
    out.push(Math.round(v * 100) / 100);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Shared cross-links (open the related QuantLab module — market context is not
// yet pre-filled; deep-linked, market-aware routing is future work).
// ---------------------------------------------------------------------------

export const CROSS_LINKS: MarketLink[] = [
  { label: "Backtest an index strategy", view: "backtest" },
  { label: "Open Cross-Sectional Scanner", view: "scanner" },
  { label: "View rates (Yield Curve Lab)", view: "rates" },
  { label: "Open FX Lab", view: "fx" },
];

// ---------------------------------------------------------------------------
// Sample markets (15) — all values are static illustrative placeholders.
// ---------------------------------------------------------------------------

export const MARKETS: Market[] = [
  {
    id: "us",
    country: "United States",
    flag: "🇺🇸",
    region: "Americas",
    subregion: "North America",
    lat: 38,
    lon: -97,
    currency: "USD",
    exchange: "NYSE / Nasdaq",
    tradingHours: "09:30–16:00 ET",
    indices: [
      { name: "S&P 500", ticker: "SPX", level: "Sample", changePct: 0.0042, sparkline: makeSparkline(101, 0.0012) },
      { name: "Nasdaq 100", ticker: "NDX", level: "Sample", changePct: 0.0068, sparkline: makeSparkline(102, 0.0016) },
      { name: "Dow Jones", ticker: "DJIA", level: "Sample", changePct: 0.0021, sparkline: makeSparkline(103, 0.0008) },
    ],
    macro: { gdpGrowth: 2.1, inflation: 3.2, unemployment: 3.9, policyRate: 5.25, debtToGdp: 122 },
    fx: [{ pair: "DXY (USD index)", value: "Sample", changePct: -0.0012 }],
    marketStructure: {
      marketCap: "Very large (sample)",
      listedCompanies: "~5,000 (sample)",
      settlement: "T+1",
      notes: "Deep, highly liquid equity market; mega-cap technology drives index concentration.",
    },
    headlines: [
      { title: "Mega-cap technology leads the benchmark higher", sentiment: "Bullish" },
      { title: "Rate-path uncertainty weighs on small caps", sentiment: "Bearish" },
      { title: "Earnings season opens with mixed guidance", sentiment: "Neutral" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "ca",
    country: "Canada",
    flag: "🇨🇦",
    region: "Americas",
    subregion: "North America",
    lat: 56,
    lon: -106,
    currency: "CAD",
    exchange: "Toronto Stock Exchange (TSX)",
    tradingHours: "09:30–16:00 ET",
    indices: [
      { name: "S&P/TSX Composite", ticker: "TSX", level: "Sample", changePct: 0.0015, sparkline: makeSparkline(201, 0.0007) },
    ],
    macro: { gdpGrowth: 1.4, inflation: 3.1, unemployment: 5.7, policyRate: 5.0, debtToGdp: 107 },
    fx: [{ pair: "USD/CAD", value: "Sample", changePct: 0.0009 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~3,400 (sample)",
      settlement: "T+1",
      notes: "Index tilted toward financials and energy / natural resources.",
    },
    headlines: [
      { title: "Energy names support the resource-heavy index", sentiment: "Bullish" },
      { title: "Housing-sensitive financials trade cautiously", sentiment: "Neutral" },
      { title: "Loonie softens as rate-cut bets build", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "uk",
    country: "United Kingdom",
    flag: "🇬🇧",
    region: "Europe",
    subregion: "Western Europe",
    lat: 54,
    lon: -2,
    currency: "GBP",
    exchange: "London Stock Exchange (LSE)",
    tradingHours: "08:00–16:30 GMT",
    indices: [
      { name: "FTSE 100", ticker: "UKX", level: "Sample", changePct: 0.0011, sparkline: makeSparkline(301, 0.0005) },
      { name: "FTSE 250", ticker: "MCX", level: "Sample", changePct: -0.0008, sparkline: makeSparkline(302, 0.0003) },
    ],
    macro: { gdpGrowth: 0.6, inflation: 4.0, unemployment: 4.2, policyRate: 5.25, debtToGdp: 101 },
    fx: [{ pair: "GBP/USD", value: "Sample", changePct: 0.0017 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~1,900 (sample)",
      settlement: "T+2",
      notes: "Large-cap index is internationally exposed; heavy weight in energy, miners, and banks.",
    },
    headlines: [
      { title: "Sterling strength caps overseas-earner gains", sentiment: "Neutral" },
      { title: "Defensive dividend payers attract flows", sentiment: "Bullish" },
      { title: "Domestic mid-caps lag on growth worries", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "de",
    country: "Germany",
    flag: "🇩🇪",
    region: "Europe",
    subregion: "Western Europe",
    lat: 51,
    lon: 10,
    currency: "EUR",
    exchange: "Deutsche Börse (Xetra)",
    tradingHours: "09:00–17:30 CET",
    indices: [
      { name: "DAX 40", ticker: "DAX", level: "Sample", changePct: 0.0034, sparkline: makeSparkline(401, 0.0011) },
    ],
    macro: { gdpGrowth: 0.2, inflation: 2.9, unemployment: 5.9, policyRate: 4.0, debtToGdp: 64 },
    fx: [{ pair: "EUR/USD", value: "Sample", changePct: 0.0006 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~450 (sample)",
      settlement: "T+2",
      notes: "Export- and industrials-heavy benchmark; sensitive to global manufacturing cycles.",
    },
    headlines: [
      { title: "Industrials rebound on improving order books", sentiment: "Bullish" },
      { title: "Auto sector watches China demand closely", sentiment: "Neutral" },
      { title: "Manufacturing PMI stays in contraction", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "fr",
    country: "France",
    flag: "🇫🇷",
    region: "Europe",
    subregion: "Western Europe",
    lat: 46,
    lon: 2,
    currency: "EUR",
    exchange: "Euronext Paris",
    tradingHours: "09:00–17:30 CET",
    indices: [
      { name: "CAC 40", ticker: "CAC", level: "Sample", changePct: 0.0019, sparkline: makeSparkline(501, 0.0009) },
    ],
    macro: { gdpGrowth: 0.8, inflation: 3.0, unemployment: 7.3, policyRate: 4.0, debtToGdp: 111 },
    fx: [{ pair: "EUR/USD", value: "Sample", changePct: 0.0006 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~470 (sample)",
      settlement: "T+2",
      notes: "Strong luxury-goods and consumer weighting alongside industrials and energy.",
    },
    headlines: [
      { title: "Luxury leaders pace the index", sentiment: "Bullish" },
      { title: "Investors weigh fiscal-deficit headlines", sentiment: "Neutral" },
      { title: "Consumer demand signals soften", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "ch",
    country: "Switzerland",
    flag: "🇨🇭",
    region: "Europe",
    subregion: "Western Europe",
    lat: 47,
    lon: 8,
    currency: "CHF",
    exchange: "SIX Swiss Exchange",
    tradingHours: "09:00–17:30 CET",
    indices: [
      { name: "SMI", ticker: "SMI", level: "Sample", changePct: 0.0007, sparkline: makeSparkline(601, 0.0006) },
    ],
    macro: { gdpGrowth: 1.0, inflation: 1.4, unemployment: 2.1, policyRate: 1.75, debtToGdp: 38 },
    fx: [{ pair: "USD/CHF", value: "Sample", changePct: -0.0011 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~250 (sample)",
      settlement: "T+2",
      notes: "Defensive, low-volatility index dominated by pharma and consumer staples.",
    },
    headlines: [
      { title: "Defensive heavyweights underpin the index", sentiment: "Bullish" },
      { title: "Strong franc pressures exporters", sentiment: "Bearish" },
      { title: "Low domestic inflation supports policy patience", sentiment: "Neutral" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "jp",
    country: "Japan",
    flag: "🇯🇵",
    region: "Asia-Pacific",
    subregion: "East Asia",
    lat: 36,
    lon: 138,
    currency: "JPY",
    exchange: "Tokyo Stock Exchange (TSE)",
    tradingHours: "09:00–15:00 JST",
    indices: [
      { name: "Nikkei 225", ticker: "NKY", level: "Sample", changePct: 0.0081, sparkline: makeSparkline(701, 0.0018) },
      { name: "TOPIX", ticker: "TPX", level: "Sample", changePct: 0.0063, sparkline: makeSparkline(702, 0.0014) },
    ],
    macro: { gdpGrowth: 1.3, inflation: 2.8, unemployment: 2.5, policyRate: -0.1, debtToGdp: 255 },
    fx: [{ pair: "USD/JPY", value: "Sample", changePct: 0.0024 }],
    marketStructure: {
      marketCap: "Very large (sample)",
      listedCompanies: "~3,900 (sample)",
      settlement: "T+2",
      notes: "Corporate-governance reform and a weak yen are recurring index themes.",
    },
    headlines: [
      { title: "Governance-reform optimism lifts exporters", sentiment: "Bullish" },
      { title: "Weak yen flatters overseas earnings", sentiment: "Neutral" },
      { title: "Markets watch for a policy-rate exit", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "cn",
    country: "China",
    flag: "🇨🇳",
    region: "Asia-Pacific",
    subregion: "East Asia",
    lat: 35,
    lon: 104,
    currency: "CNY",
    exchange: "Shanghai / Shenzhen",
    tradingHours: "09:30–15:00 CST",
    indices: [
      { name: "CSI 300", ticker: "CSI300", level: "Sample", changePct: -0.0027, sparkline: makeSparkline(801, -0.0004) },
      { name: "SSE Composite", ticker: "SHCOMP", level: "Sample", changePct: -0.0014, sparkline: makeSparkline(802, -0.0002) },
    ],
    macro: { gdpGrowth: 4.8, inflation: 0.4, unemployment: 5.1, policyRate: 3.45, debtToGdp: 84 },
    fx: [{ pair: "USD/CNY", value: "Sample", changePct: 0.0008 }],
    marketStructure: {
      marketCap: "Very large (sample)",
      listedCompanies: "~5,300 (sample)",
      settlement: "T+1",
      notes: "Onshore A-shares with notable retail participation and daily price limits.",
    },
    headlines: [
      { title: "Property-sector concerns linger", sentiment: "Bearish" },
      { title: "Stimulus speculation supports sentiment", sentiment: "Bullish" },
      { title: "Low inflation keeps policy easing in view", sentiment: "Neutral" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "hk",
    country: "Hong Kong",
    flag: "🇭🇰",
    region: "Asia-Pacific",
    subregion: "East Asia",
    lat: 22.3,
    lon: 114.2,
    currency: "HKD",
    exchange: "HKEX",
    tradingHours: "09:30–16:00 HKT",
    indices: [
      { name: "Hang Seng", ticker: "HSI", level: "Sample", changePct: -0.0019, sparkline: makeSparkline(901, -0.0003) },
    ],
    macro: { gdpGrowth: 3.2, inflation: 1.9, unemployment: 2.9, policyRate: 5.75, debtToGdp: 4 },
    fx: [{ pair: "USD/HKD", value: "Sample", changePct: 0.0001 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~2,600 (sample)",
      settlement: "T+2",
      notes: "Gateway for mainland listings; HKD operates under a USD currency peg band.",
    },
    headlines: [
      { title: "Southbound flows steady the index", sentiment: "Neutral" },
      { title: "Mainland tech listings rebound", sentiment: "Bullish" },
      { title: "High USD-linked rates pressure valuations", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "tw",
    country: "Taiwan",
    flag: "🇹🇼",
    region: "Asia-Pacific",
    subregion: "East Asia",
    lat: 23.7,
    lon: 121,
    currency: "TWD",
    exchange: "Taiwan Stock Exchange (TWSE)",
    tradingHours: "09:00–13:30 CST",
    indices: [
      { name: "TAIEX", ticker: "TWII", level: "Sample", changePct: 0.0072, sparkline: makeSparkline(1001, 0.0017) },
    ],
    macro: { gdpGrowth: 3.1, inflation: 2.2, unemployment: 3.4, policyRate: 2.0, debtToGdp: 28 },
    fx: [{ pair: "USD/TWD", value: "Sample", changePct: 0.0012 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~1,000 (sample)",
      settlement: "T+2",
      notes: "Index dominated by semiconductors; highly geared to the global tech cycle.",
    },
    headlines: [
      { title: "Semiconductor demand drives the benchmark", sentiment: "Bullish" },
      { title: "AI supply-chain orders stay firm", sentiment: "Bullish" },
      { title: "Index concentration raises single-name risk", sentiment: "Neutral" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "kr",
    country: "South Korea",
    flag: "🇰🇷",
    region: "Asia-Pacific",
    subregion: "East Asia",
    lat: 36.5,
    lon: 127.8,
    currency: "KRW",
    exchange: "Korea Exchange (KRX)",
    tradingHours: "09:00–15:30 KST",
    indices: [
      { name: "KOSPI", ticker: "KOSPI", level: "Sample", changePct: 0.0041, sparkline: makeSparkline(1101, 0.0010) },
    ],
    macro: { gdpGrowth: 2.2, inflation: 2.6, unemployment: 2.8, policyRate: 3.5, debtToGdp: 55 },
    fx: [{ pair: "USD/KRW", value: "Sample", changePct: 0.0015 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~2,500 (sample)",
      settlement: "T+2",
      notes: "Export- and memory-chip-sensitive market; large single-name index weights.",
    },
    headlines: [
      { title: "Memory-chip upcycle hopes lift sentiment", sentiment: "Bullish" },
      { title: "Won weakness draws policy attention", sentiment: "Neutral" },
      { title: "Exporters eye softer global demand", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "in",
    country: "India",
    flag: "🇮🇳",
    region: "Asia-Pacific",
    subregion: "South Asia",
    lat: 22,
    lon: 79,
    currency: "INR",
    exchange: "NSE / BSE",
    tradingHours: "09:15–15:30 IST",
    indices: [
      { name: "NIFTY 50", ticker: "NIFTY", level: "Sample", changePct: 0.0055, sparkline: makeSparkline(1201, 0.0015) },
      { name: "SENSEX", ticker: "SENSEX", level: "Sample", changePct: 0.0049, sparkline: makeSparkline(1202, 0.0014) },
    ],
    macro: { gdpGrowth: 6.5, inflation: 5.1, unemployment: 7.8, policyRate: 6.5, debtToGdp: 82 },
    fx: [{ pair: "USD/INR", value: "Sample", changePct: 0.0007 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~5,400 (sample)",
      settlement: "T+1",
      notes: "Fast-growing market with strong domestic retail (SIP) inflows.",
    },
    headlines: [
      { title: "Domestic inflows underpin the rally", sentiment: "Bullish" },
      { title: "Valuations screen rich versus peers", sentiment: "Neutral" },
      { title: "Sticky food inflation tempers rate-cut hopes", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "sg",
    country: "Singapore",
    flag: "🇸🇬",
    region: "Asia-Pacific",
    subregion: "Southeast Asia",
    lat: 1.35,
    lon: 103.8,
    currency: "SGD",
    exchange: "Singapore Exchange (SGX)",
    tradingHours: "09:00–17:00 SGT",
    indices: [
      { name: "Straits Times", ticker: "STI", level: "Sample", changePct: 0.0013, sparkline: makeSparkline(1301, 0.0006) },
    ],
    macro: { gdpGrowth: 1.8, inflation: 3.4, unemployment: 2.0, policyRate: 3.8, debtToGdp: 168 },
    fx: [{ pair: "USD/SGD", value: "Sample", changePct: -0.0004 }],
    marketStructure: {
      marketCap: "Mid (sample)",
      listedCompanies: "~640 (sample)",
      settlement: "T+2",
      notes: "Regional financial hub; index is bank- and REIT-heavy. Policy runs via the exchange-rate band, not a policy rate.",
    },
    headlines: [
      { title: "Bank dividends anchor the index", sentiment: "Bullish" },
      { title: "REITs steady as rate expectations ease", sentiment: "Neutral" },
      { title: "Trade-exposed names track global demand", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "au",
    country: "Australia",
    flag: "🇦🇺",
    region: "Asia-Pacific",
    subregion: "Oceania",
    lat: -25,
    lon: 133,
    currency: "AUD",
    exchange: "Australian Securities Exchange (ASX)",
    tradingHours: "10:00–16:00 AEST",
    indices: [
      { name: "S&P/ASX 200", ticker: "AS51", level: "Sample", changePct: 0.0023, sparkline: makeSparkline(1401, 0.0009) },
    ],
    macro: { gdpGrowth: 1.5, inflation: 3.6, unemployment: 4.1, policyRate: 4.35, debtToGdp: 50 },
    fx: [{ pair: "AUD/USD", value: "Sample", changePct: 0.0014 }],
    marketStructure: {
      marketCap: "Large (sample)",
      listedCompanies: "~2,000 (sample)",
      settlement: "T+2",
      notes: "Index dominated by banks and miners; sensitive to commodity prices and China demand.",
    },
    headlines: [
      { title: "Miners track firmer commodity prices", sentiment: "Bullish" },
      { title: "Banks steady amid stable margins", sentiment: "Neutral" },
      { title: "Sticky services inflation delays cuts", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
  {
    id: "br",
    country: "Brazil",
    flag: "🇧🇷",
    region: "Americas",
    subregion: "South America",
    lat: -10,
    lon: -55,
    currency: "BRL",
    exchange: "B3 (Brasil Bolsa Balcão)",
    tradingHours: "10:00–17:00 BRT",
    indices: [
      { name: "Ibovespa", ticker: "IBOV", level: "Sample", changePct: 0.0036, sparkline: makeSparkline(1501, 0.0011) },
    ],
    macro: { gdpGrowth: 2.9, inflation: 4.5, unemployment: 7.5, policyRate: 10.5, debtToGdp: 74 },
    fx: [{ pair: "USD/BRL", value: "Sample", changePct: -0.0021 }],
    marketStructure: {
      marketCap: "Mid (sample)",
      listedCompanies: "~430 (sample)",
      settlement: "T+2",
      notes: "Commodity- and financials-heavy index; high real policy rates are a recurring theme.",
    },
    headlines: [
      { title: "Commodity exporters lead gains", sentiment: "Bullish" },
      { title: "Falling policy rate aids domestic names", sentiment: "Bullish" },
      { title: "Fiscal-trajectory questions cap upside", sentiment: "Bearish" },
    ],
    links: CROSS_LINKS,
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function findMarketById(id: string | null | undefined): Market | null {
  if (!id) return null;
  return MARKETS.find((m) => m.id === id) ?? null;
}

/** Filter by region group ("All" returns everything), then optional text query. */
export function filterMarkets(
  region: MarketRegion | "All",
  query: string,
  list: Market[] = MARKETS,
): Market[] {
  const q = query.trim().toLowerCase();
  return list.filter((m) => {
    if (region !== "All" && m.region !== region) return false;
    if (!q) return true;
    return (
      m.country.toLowerCase().includes(q) ||
      m.currency.toLowerCase().includes(q) ||
      m.exchange.toLowerCase().includes(q) ||
      m.region.toLowerCase().includes(q) ||
      m.subregion.toLowerCase().includes(q) ||
      m.indices.some(
        (i) =>
          i.name.toLowerCase().includes(q) || i.ticker.toLowerCase().includes(q),
      )
    );
  });
}

export const SENTIMENT_TONE: Record<Sentiment, "positive" | "danger" | "default"> = {
  Bullish: "positive",
  Bearish: "danger",
  Neutral: "default",
};

// ---------------------------------------------------------------------------
// Visual-redesign helpers (Globe v1.1)
// ---------------------------------------------------------------------------

/**
 * Region marker colors for the globe + dossier, matching the Claude Design
 * spec (VISUAL_REDESIGN §2). Concrete hex (not theme accents) so the four
 * regions stay distinguishable regardless of the active accent theme.
 */
export const REGION_COLORS: Record<MarketRegion, string> = {
  Americas: "#5b9bff",
  Europe: "#2bd6a0",
  "Asia-Pacific": "#f0b648",
};

/** Illustrative "capital-flow" connections drawn as great-circle arcs. */
export const MARKET_ARCS: readonly [string, string][] = [
  ["us", "uk"],
  ["us", "jp"],
  ["cn", "hk"],
  ["tw", "us"],
  ["sg", "in"],
] as const;

/** Mean of a market's sample index daily changes (illustrative only). */
export function meanIndexChange(market: Market): number {
  if (market.indices.length === 0) return 0;
  const sum = market.indices.reduce((acc, i) => acc + i.changePct, 0);
  return sum / market.indices.length;
}

/**
 * Deterministic directional bias from the static sample index changes. This is
 * an illustrative label for the dossier "bias pill" — not a forecast, a model
 * output, or a recommendation.
 */
export function marketBias(market: Market): Sentiment {
  const m = meanIndexChange(market);
  if (m > 0.002) return "Bullish";
  if (m < -0.0005) return "Bearish";
  return "Neutral";
}

export interface RegionRollup {
  region: MarketRegion;
  /** Average of each member market's mean index change (illustrative). */
  avgChange: number;
  advancers: number;
  decliners: number;
  count: number;
}

/** Region tape rollup for the dashboard + globe bottom strip (sample data). */
export function regionRollup(markets: Market[] = MARKETS): RegionRollup[] {
  return MARKET_REGIONS.map((region) => {
    const members = markets.filter((m) => m.region === region);
    const changes = members.map(meanIndexChange);
    const avgChange =
      changes.length === 0
        ? 0
        : changes.reduce((a, b) => a + b, 0) / changes.length;
    return {
      region,
      avgChange,
      advancers: changes.filter((c) => c > 0).length,
      decliners: changes.filter((c) => c < 0).length,
      count: members.length,
    };
  });
}
