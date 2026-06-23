/**
 * Global Markets Globe — guided tour definitions (Phase 20.7).
 *
 * Frontend-only, static, educational curated walks across the existing 15 sample
 * markets. A tour is an ordered list of steps; each step selects a market and
 * shows a short educational explanation. These are **teaching lenses, not
 * recommendations, not signals, and not live data** — every dossier remains
 * static illustrative sample data by default (optional adapters may enrich
 * supported fields when configured).
 *
 * No data is fetched here; tours reference markets by id only.
 */

export type TourId = "global" | "asia" | "macro" | "risk";

export const TOUR_IDS: readonly TourId[] = ["global", "asia", "macro", "risk"];

export interface TourStep {
  /** Market id to select for this step (must exist in `lib/globe/markets`). */
  marketId: string;
  title: string;
  /** Short label for the lens of this step (e.g. "Rates & FX regime"). */
  focus: string;
  /** 1–2 sentence educational explanation. Never a recommendation or signal. */
  explanation: string;
  /** Optional generic "things to explore" hints (text only, no auto-prefill). */
  suggestedActions?: string[];
}

export interface GlobeTour {
  id: TourId;
  title: string;
  subtitle: string;
  description: string;
  steps: TourStep[];
}

export const TOURS: Record<TourId, GlobeTour> = {
  global: {
    id: "global",
    title: "Guided Global Tour",
    subtitle: "Five anchor markets",
    description:
      "A five-stop educational walk across global risk anchors — from the US " +
      "benchmark to Asia's tech supply chain, Japanese rates, European " +
      "cyclicals, and Indian growth.",
    steps: [
      {
        marketId: "us",
        title: "US: global risk benchmark",
        focus: "Benchmark & liquidity",
        explanation:
          "The US sits at the centre of global risk appetite — deep, liquid " +
          "equity indices and a policy-rate path that anchors discount rates " +
          "worldwide. Use it as an educational reference point for the rest of " +
          "the tour.",
        suggestedActions: [
          "Backtest an index strategy in Backtest Studio",
          "Compare strategies side by side in Strategy Comparison",
        ],
      },
      {
        marketId: "tw",
        title: "Taiwan: semiconductor supply-chain lens",
        focus: "Tech & supply chain",
        explanation:
          "Taiwan's benchmark is heavily geared to semiconductors, making it an " +
          "educational lens on the global technology and AI-hardware cycle — and " +
          "on single-name index concentration.",
        suggestedActions: ["Explore a synthetic universe in the Cross-Sectional Scanner"],
      },
      {
        marketId: "jp",
        title: "Japan: rates, yen, and equity regime",
        focus: "Rates & FX regime",
        explanation:
          "Japan illustrates how a weak yen, an evolving policy-rate stance, and " +
          "corporate-governance reform interact with an export-heavy equity market.",
        suggestedActions: ["Open the FX Lab", "Open the Yield Curve Lab"],
      },
      {
        marketId: "de",
        title: "Germany: European cyclicals and industrial beta",
        focus: "Industrial cyclicality",
        explanation:
          "Germany's export- and industrials-heavy index is an educational proxy " +
          "for European cyclical exposure and global manufacturing sensitivity.",
      },
      {
        marketId: "in",
        title: "India: growth and domestic-demand lens",
        focus: "Growth & domestic demand",
        explanation:
          "India highlights a fast-growing economy with strong domestic retail " +
          "inflows — an educational contrast to the more externally-driven " +
          "markets earlier in the tour.",
      },
    ],
  },
  asia: {
    id: "asia",
    title: "Asia Markets Tour",
    subtitle: "Six Asia-Pacific markets",
    description:
      "A six-stop educational walk across Asia-Pacific equity markets, from " +
      "Japan and the tech supply chain to South Asia's growth engine.",
    steps: [
      {
        marketId: "jp",
        title: "Japan: anchor of Asian equity markets",
        focus: "Regional anchor",
        explanation:
          "Japan is the largest developed market in the region — an educational " +
          "anchor for rates, currency, and export sensitivity across Asia.",
      },
      {
        marketId: "tw",
        title: "Taiwan: semiconductor heart of Asia",
        focus: "Tech supply chain",
        explanation:
          "Taiwan concentrates much of the world's advanced-chip manufacturing, " +
          "a teaching example of supply-chain and concentration dynamics.",
      },
      {
        marketId: "kr",
        title: "South Korea: memory chips and export beta",
        focus: "Exports & memory",
        explanation:
          "South Korea's market is memory-chip- and export-sensitive — an " +
          "educational view on the global hardware cycle and currency effects.",
      },
      {
        marketId: "hk",
        title: "Hong Kong: gateway and rates-sensitive hub",
        focus: "Gateway & USD peg",
        explanation:
          "Hong Kong is a gateway for mainland listings, with a currency peg that " +
          "ties local rates to the US — a useful lens on policy-linkage mechanics.",
      },
      {
        marketId: "sg",
        title: "Singapore: financial hub and REIT exposure",
        focus: "Financials & REITs",
        explanation:
          "Singapore's bank- and REIT-heavy index, with policy run via the " +
          "exchange-rate band, is an educational contrast to rate-targeting peers.",
      },
      {
        marketId: "in",
        title: "India: domestic-demand growth engine",
        focus: "Growth & domestic demand",
        explanation:
          "India closes the Asia tour as a fast-growing, domestically-driven " +
          "market — an educational counterpoint to the export-led economies above.",
      },
    ],
  },
  macro: {
    id: "macro",
    title: "Macro Regime Tour",
    subtitle: "Five macro regimes",
    description:
      "A five-stop educational comparison of macro regimes — policy rates, " +
      "inflation, and growth — across very different economies.",
    steps: [
      {
        marketId: "us",
        title: "US: the policy-rate anchor",
        focus: "Policy rate & inflation",
        explanation:
          "The US policy rate and inflation path set the global discount-rate " +
          "backdrop. Optional US FRED macro enrichment can illustrate selected " +
          "fields when configured; otherwise figures are static sample data.",
      },
      {
        marketId: "de",
        title: "Germany: euro-area growth and inflation",
        focus: "Euro-area macro",
        explanation:
          "Germany illustrates a low-growth, export-exposed euro-area economy — " +
          "an educational contrast in growth and inflation dynamics.",
      },
      {
        marketId: "jp",
        title: "Japan: low rates and a weak yen",
        focus: "Low rates & FX",
        explanation:
          "Japan is a teaching case for very low policy rates, high public debt, " +
          "and the feedback between currency and equities.",
      },
      {
        marketId: "ch",
        title: "Switzerland: low-inflation defensive economy",
        focus: "Low inflation & defensives",
        explanation:
          "Switzerland's low inflation and defensive, pharma-heavy market is an " +
          "educational example of a stability-oriented regime.",
      },
      {
        marketId: "br",
        title: "Brazil: high real rates and EM macro",
        focus: "High rates & EM",
        explanation:
          "Brazil rounds out the tour as an emerging-market regime with high real " +
          "policy rates and commodity sensitivity — an educational EM contrast.",
      },
    ],
  },
  risk: {
    id: "risk",
    title: "Risk Lens Tour",
    subtitle: "Five risk angles",
    description:
      "A five-stop educational tour of different risk angles — concentration, " +
      "policy, cyclicality, currency, and fiscal — across markets.",
    steps: [
      {
        marketId: "us",
        title: "US: the global risk benchmark",
        focus: "Benchmark risk",
        explanation:
          "The US benchmark frames global risk appetite and index concentration " +
          "in mega-cap technology — an educational starting reference.",
      },
      {
        marketId: "cn",
        title: "China: property and policy-driven risk",
        focus: "Property & policy risk",
        explanation:
          "China is a teaching example of property-sector and policy-driven risk, " +
          "with onshore market features such as daily price limits.",
      },
      {
        marketId: "tw",
        title: "Taiwan: concentration and supply-chain lens",
        focus: "Concentration risk",
        explanation:
          "Taiwan illustrates single-name and supply-chain concentration risk " +
          "around the semiconductor cycle — for education, not a forecast.",
      },
      {
        marketId: "de",
        title: "Germany: cyclical and energy-sensitivity risk",
        focus: "Cyclical risk",
        explanation:
          "Germany shows cyclical and manufacturing-sensitivity risk tied to the " +
          "global industrial cycle — an educational European angle.",
      },
      {
        marketId: "br",
        title: "Brazil: currency and fiscal-trajectory risk",
        focus: "FX & fiscal risk",
        explanation:
          "Brazil closes the tour as an educational view on currency and " +
          "fiscal-trajectory risk in an emerging market.",
      },
    ],
  },
};

/** Ordered list of tours for menus / palette. */
export const TOUR_LIST: GlobeTour[] = TOUR_IDS.map((id) => TOURS[id]);

export function isTourId(id: string | null | undefined): id is TourId {
  return !!id && (TOUR_IDS as readonly string[]).includes(id);
}

/** Get a tour by id (case-insensitive), or null if unknown. */
export function getTour(id: string | null | undefined): GlobeTour | null {
  if (!id) return null;
  const lower = id.trim().toLowerCase();
  const match = TOUR_IDS.find((t) => t === lower);
  return match ? TOURS[match] : null;
}

/**
 * Resolve a requested tour id.
 *  - empty / null   → no tour (`{ id: null, notFound: false }`)
 *  - known tour     → that tour id
 *  - unknown tour   → no tour, flagged `notFound` so the UI can show
 *                     "Tour not found; showing Globe normally."
 */
export function resolveTour(
  id: string | null | undefined,
): { id: TourId | null; notFound: boolean } {
  const normalized = id?.trim().toLowerCase();
  if (!normalized) return { id: null, notFound: false };
  const match = TOUR_IDS.find((t) => t === normalized);
  return match ? { id: match, notFound: false } : { id: null, notFound: true };
}
