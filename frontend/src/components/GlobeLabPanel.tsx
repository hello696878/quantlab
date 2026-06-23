"use client";

/**
 * Global Markets Globe v1.1 — "mission control" page.
 *
 * Three-zone, width-aware layout (wide / mid / narrow via a container
 * ResizeObserver): a left rail (search · region filter · market list ·
 * quick-jump), a center canvas globe (DataGlobe) with overlay controls + a
 * legend, and a right dossier panel — plus a bottom region "tape".
 *
 * Bundled data is static illustrative sample data. The backend may optionally
 * source selected US macro fields from FRED; index, FX, structure, and headline
 * data remain static, with no real-time coverage claim.
 */

import { useEffect, useRef, useState } from "react";
import type { View } from "@/components/AppShell";
import DataGlobe from "@/components/globe/DataGlobe";
import MarketDossier from "@/components/globe/MarketDossier";
import {
  MARKETS,
  MARKET_ARCS,
  MARKET_REGIONS,
  REGION_COLORS,
  STATIC_DATA_NOTICE,
  filterMarkets,
  meanIndexChange,
  regionRollup,
  type Market,
  type MarketRegion,
} from "@/lib/globe/markets";
import { fetchGlobeMarkets } from "@/lib/globe/remote";
import {
  buildGlobeShareUrl,
  resolveMarketId,
  writeGlobeUrl,
} from "@/lib/globe/permalink";
import { getTour, resolveTour } from "@/lib/globe/tours";
import { fmtPct } from "@/lib/format";

/** Stable list of bundled market ids — used to validate permalink ids. */
const MARKET_IDS: readonly string[] = MARKETS.map((m) => m.id);

type Mode = "wide" | "mid" | "narrow";

function useContainerMode(ref: React.RefObject<HTMLElement>): Mode {
  const [mode, setMode] = useState<Mode>("wide");
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      setMode(w >= 1120 ? "wide" : w >= 720 ? "mid" : "narrow");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return mode;
}

const QUICK_JUMP: { id: string; label: string }[] = [
  { id: "us", label: "US" },
  { id: "uk", label: "UK" },
  { id: "jp", label: "Japan" },
  { id: "hk", label: "Hong Kong" },
];

function changeColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

function MarketListItem({
  market,
  active,
  onSelect,
}: {
  market: Market;
  active: boolean;
  onSelect: () => void;
}) {
  const lead = market.indices[0];
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors"
      style={{
        background: active ? "var(--accent-softer)" : "var(--glass)",
        border: `1px solid ${active ? "var(--accent-line)" : "var(--line)"}`,
        boxShadow: active ? "inset 3px 0 0 var(--accent)" : undefined,
      }}
    >
      <span
        aria-hidden
        className="h-2 w-2 flex-shrink-0 rounded-full"
        style={{ background: REGION_COLORS[market.region], boxShadow: `0 0 6px ${REGION_COLORS[market.region]}` }}
      />
      <span aria-hidden className="text-base leading-none">
        {market.flag}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>
          {market.country}
        </span>
        <span className="mono block truncate text-[10px]" style={{ color: "var(--text-mut)" }}>
          {market.currency} · {market.exchange}
        </span>
      </span>
      {lead && (
        <span className="mono flex-shrink-0 text-xs font-semibold" style={{ color: changeColor(lead.changePct) }}>
          {fmtPct(lead.changePct, 2)}
        </span>
      )}
    </button>
  );
}

interface GlobeLabPanelProps {
  initialMarketId?: string | null;
  /** Optional guided-tour id to start on entry (Phase 20.7). */
  initialTour?: string | null;
  /** Open in presentation mode (Phase 20.7). */
  initialPresentation?: boolean;
  onNav: (view: View) => void;
}

export default function GlobeLabPanel({
  initialMarketId,
  initialTour,
  initialPresentation,
  onNav,
}: GlobeLabPanelProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const mode = useContainerMode(wrapRef);

  const [region, setRegion] = useState<MarketRegion | "All">("All");
  const [query, setQuery] = useState("");

  // Resolve the deep-linked tour + market id together:
  //  - valid tour  → select the matching step's market, else the first step.
  //  - no tour      → resolve the market id (known id selects it; unknown id
  //                   falls back to the default market and flags `marketNotFound`).
  //  - invalid tour → no tour, flag `tourNotFound` for a friendly notice.
  const requestedTour = resolveTour(initialTour);
  const initialActiveTour = requestedTour.id ? getTour(requestedTour.id) : null;
  let initSelected: string | null;
  let initMarketNotFound = false;
  if (initialActiveTour) {
    const idx = initialMarketId
      ? initialActiveTour.steps.findIndex(
          (s) => s.marketId.toLowerCase() === initialMarketId.toLowerCase(),
        )
      : -1;
    initSelected =
      idx >= 0
        ? initialActiveTour.steps[idx].marketId
        : initialActiveTour.steps[0].marketId;
  } else {
    const r = resolveMarketId(initialMarketId, MARKET_IDS);
    initSelected = r.id;
    initMarketNotFound = r.notFound;
  }

  const [selectedId, setSelectedId] = useState<string | null>(initSelected);
  const [marketNotFound, setMarketNotFound] = useState<boolean>(initMarketNotFound);
  const [tourId, setTourId] = useState<string | null>(requestedTour.id);
  const [tourNotFound, setTourNotFound] = useState<boolean>(requestedTour.notFound);
  const [presentation, setPresentation] = useState<boolean>(initialPresentation ?? false);
  const [tourCopyMsg, setTourCopyMsg] = useState<string | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [resetSignal, setResetSignal] = useState(0);

  /**
   * User-initiated selection. During a tour: selecting another tour step jumps
   * to it; selecting an off-tour market leaves the curated tour. Always records
   * a history entry so browser back/forward walks the visited dossiers.
   */
  function selectMarket(id: string) {
    setMarketNotFound(false);
    const tour = getTour(tourId);
    if (tour && !tour.steps.some((s) => s.marketId === id)) {
      // Off-tour click → leave the tour.
      setTourId(null);
      setSelectedId(id);
      writeGlobeUrl({ market: id, tour: null, presentation }, "push");
      return;
    }
    setSelectedId(id);
    writeGlobeUrl({ market: id, tour: tourId, presentation }, "push");
  }
  /** User-initiated clear: closes the dossier and exits any active tour. */
  function clearSelection() {
    setSelectedId(null);
    setMarketNotFound(false);
    setTourId(null);
    writeGlobeUrl({ market: null, tour: null, presentation }, "push");
  }

  /** Advance to the next tour step (selecting its market). */
  function tourNext() {
    const tour = getTour(tourId);
    if (!tour) return;
    const step = tour.steps.findIndex((s) => s.marketId === selectedId);
    const idx = step < 0 ? 0 : Math.min(step + 1, tour.steps.length - 1);
    const id = tour.steps[idx].marketId;
    setSelectedId(id);
    setMarketNotFound(false);
    writeGlobeUrl({ market: id, tour: tour.id, presentation }, "push");
  }
  /** Go back to the previous tour step. */
  function tourPrev() {
    const tour = getTour(tourId);
    if (!tour) return;
    const step = tour.steps.findIndex((s) => s.marketId === selectedId);
    const idx = step < 0 ? 0 : Math.max(step - 1, 0);
    const id = tour.steps[idx].marketId;
    setSelectedId(id);
    setMarketNotFound(false);
    writeGlobeUrl({ market: id, tour: tour.id, presentation }, "push");
  }
  /** Exit the tour but keep the current market selected (drops ?tour). */
  function exitTour() {
    setTourId(null);
    setTourNotFound(false);
    setTourCopyMsg(null);
    writeGlobeUrl({ market: selectedId, tour: null, presentation }, "push");
  }
  /** Toggle presentation mode (replace — a view mode, not a navigation). */
  function togglePresentation() {
    const next = !presentation;
    setPresentation(next);
    writeGlobeUrl({ market: selectedId, tour: tourId, presentation: next }, "replace");
  }
  /** Copy a shareable link to the current tour step. */
  async function copyTourLink() {
    const url = buildGlobeShareUrl({ market: selectedId, tour: tourId, presentation });
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setTourCopyMsg("Copied tour link.");
        return;
      }
    } catch {
      // fall through to manual-copy message
    }
    setTourCopyMsg(`Could not copy automatically. Copy this link: ${url}`);
  }

  // Normalise the address bar to the resolved state on entry (covers deep-link
  // entry, the invalid-id/tour fallback, and programmatic jumps from the
  // palette/dashboard). Replace keeps a single history entry; in-panel clicks
  // push their own entries so browser back/forward walks the visited steps.
  useEffect(() => {
    writeGlobeUrl({ market: selectedId, tour: tourId, presentation }, "replace");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Market data: render bundled static data immediately, then upgrade to the
  // backend data layer if reachable (else fall back with a non-blocking warning).
  const [markets, setMarkets] = useState<Market[]>(MARKETS);
  const [dataStatus, setDataStatus] = useState<"loading" | "backend" | "fallback">("loading");
  const [hasFredEnrichment, setHasFredEnrichment] = useState(false);
  const [dataNotice, setDataNotice] = useState(STATIC_DATA_NOTICE);
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    let cancelled = false;
    const timeoutId = window.setTimeout(() => ctrl.abort(), 5000);
    fetchGlobeMarkets(ctrl.signal)
      .then((res) => {
        if (cancelled) return;
        setMarkets(res.markets);
        setHasFredEnrichment(
          res.dataStatus === "mixed_static_and_fred" ||
            res.dataStatus === "mixed_static_fred_quotes",
        );
        setDataNotice(res.notice);
        setWarnings(res.warnings);
        setDataStatus("backend");
      })
      .catch(() => {
        if (cancelled) return;
        setMarkets(MARKETS);
        setHasFredEnrichment(false);
        setDataNotice(STATIC_DATA_NOTICE);
        setWarnings([]);
        setDataStatus("fallback");
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      ctrl.abort();
    };
  }, []);

  const filtering = region !== "All" || query.trim() !== "";
  const filtered = filterMarkets(region, query, markets);
  const activeIds = filtering ? new Set(filtered.map((m) => m.id)) : null;
  const selected = markets.find((m) => m.id === selectedId) ?? null;
  const rollups = regionRollup(markets);
  const fredLive = markets.some((m) => m.macroSource === "fred_live");
  const fredUnavailable = !fredLive && markets.some((m) => m.macroSource === "fred_unavailable");
  const macroChip = fredLive
    ? { text: "Partial FRED macro (US)", tone: "var(--pos)" }
    : fredUnavailable
      ? { text: "FRED unavailable — static macro", tone: "var(--warn)" }
      : { text: "FRED macro optional (off)", tone: "var(--text-mut)" };

  const quotesLive = markets.some(
    (m) => m.indicesSource === "delayed_quote" || m.fxSource === "delayed_quote",
  );
  const quotesUnavailable =
    markets.some(
      (m) => m.indicesSource === "quote_unavailable" || m.fxSource === "quote_unavailable",
    );
  const quotesChip = quotesLive
    ? {
        text: quotesUnavailable ? "Delayed quotes · partial failures" : "Delayed quotes · partial coverage",
        tone: quotesUnavailable ? "var(--warn)" : "var(--pos)",
      }
    : quotesUnavailable
      ? { text: "Quotes unavailable — static", tone: "var(--warn)" }
      : { text: "Delayed quotes optional (off)", tone: "var(--text-mut)" };

  const newsUnavailable = markets.some((m) => m.newsSource === "news_unavailable");
  const newsChip = newsUnavailable
    ? { text: "News unavailable — static", tone: "var(--warn)" }
    : { text: "News: sample (live planned)", tone: "var(--text-mut)" };

  // If a filter/search hides the currently selected market, clear the dossier
  // and drop ?market from the URL (replace — this isn't a user navigation).
  // Skipped during a guided tour so the curated step stays selected.
  useEffect(() => {
    if (tourId || !selectedId || !filtering) return;
    if (!filterMarkets(region, query, markets).some((market) => market.id === selectedId)) {
      setSelectedId(null);
      setMarketNotFound(false);
      writeGlobeUrl({ market: null, tour: null, presentation }, "replace");
    }
  }, [filtering, query, region, selectedId, markets, tourId, presentation]);

  function resetView() {
    setRegion("All");
    setQuery("");
    setSelectedId(null);
    setMarketNotFound(false);
    setTourId(null);
    setResetSignal((k) => k + 1);
    writeGlobeUrl({ market: null, tour: null, presentation }, "push");
  }

  // ── Tour derivation (single source of truth = tourId + selectedId) ──────
  const activeTour = getTour(tourId);
  const tourStepIndex = activeTour
    ? activeTour.steps.findIndex((s) => s.marketId === selectedId)
    : -1;
  const tourStep =
    activeTour && tourStepIndex >= 0 ? activeTour.steps[tourStepIndex] : null;

  // ── Layout grids per container mode ─────────────────────────────────────
  // Presentation mode hides the rail/tape and emphasises globe + dossier.
  const gridStyle: React.CSSProperties = presentation
    ? mode === "narrow"
      ? { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr)", gridTemplateAreas: '"globe" "dossier"' }
      : { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr) 400px", gridTemplateAreas: '"globe dossier"', alignItems: "start" }
    : mode === "wide"
      ? { display: "grid", gap: 16, gridTemplateColumns: "248px minmax(0,1fr) 372px", gridTemplateAreas: '"rail globe dossier"', alignItems: "start" }
      : mode === "mid"
        ? { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr) 360px", gridTemplateAreas: '"globe globe" "rail dossier"', alignItems: "start" }
        : { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr)", gridTemplateAreas: '"globe" "rail" "dossier"' };

  const globeHeight = mode === "wide" ? 560 : mode === "mid" ? 460 : 360;
  const dossierScroll: React.CSSProperties =
    mode === "narrow" ? {} : { maxHeight: "calc(100vh - 7rem)", overflowY: "auto" };
  // In presentation mode the rail (and its filters) are hidden, so show all markers.
  const effectiveActiveIds = presentation ? null : activeIds;

  return (
    <div ref={wrapRef} className="space-y-4">
      {/* ── Page header / honesty disclaimer ──────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
                Global Markets Globe
              </h1>
              <span
                className="mono rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                v1.1
              </span>
            </div>
            {!presentation && (
              <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
                A mission-control map of {markets.length} sample markets backed by a
                typed country-dossier data layer. Drag the globe to rotate, click a
                marker — or a row in the rail — to open a country dossier with
                indices, macro vitals, currency &amp; rates, market structure,
                sample headlines, and QuantLab cross-links.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {presentation && (
              <span
                className="mono rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                Presentation mode
              </span>
            )}
            <span
              className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
              style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
            >
              Static core + optional adapters
            </span>
          </div>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {dataNotice} Not real-time market data and not investment advice.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span
            className="mono rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{
              background: dataStatus === "fallback" ? "var(--warn-soft)" : "var(--accent-softer)",
              border: `1px solid ${dataStatus === "fallback" ? "var(--line)" : "var(--accent-line)"}`,
              color: dataStatus === "fallback" ? "var(--warn)" : "var(--accent-text)",
            }}
          >
            {dataStatus === "backend"
              ? hasFredEnrichment && quotesLive
                ? "Backend static + FRED + delayed quotes"
                : hasFredEnrichment
                  ? "Backend static + partial FRED"
                  : quotesLive
                    ? "Backend static + delayed quotes"
                    : "Backend static dataset"
              : dataStatus === "fallback"
                ? "Bundled static fallback"
                : "Loading data layer…"}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ background: `color-mix(in oklch, ${macroChip.tone} 12%, transparent)`, border: `1px solid color-mix(in oklch, ${macroChip.tone} 30%, transparent)`, color: macroChip.tone }}
          >
            {macroChip.text}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ background: `color-mix(in oklch, ${quotesChip.tone} 12%, transparent)`, border: `1px solid color-mix(in oklch, ${quotesChip.tone} 30%, transparent)`, color: quotesChip.tone }}
          >
            {quotesChip.text}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ background: `color-mix(in oklch, ${newsChip.tone} 12%, transparent)`, border: `1px solid color-mix(in oklch, ${newsChip.tone} 30%, transparent)`, color: newsChip.tone }}
          >
            {newsChip.text}
          </span>
        </div>
      </div>

      {/* Non-blocking fallback warning when the backend data layer is unreachable. */}
      {dataStatus === "fallback" && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          <span aria-hidden className="mt-0.5 flex-shrink-0">⚠</span>
          <p>Backend globe data unavailable; using bundled static sample data.</p>
        </div>
      )}

      {/* Non-blocking FRED adapter notices (e.g. enabled but no API key). */}
      {warnings.length > 0 && (
        <div
          role="status"
          className="rounded-xl p-3 text-xs"
          style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
        >
          {warnings.map((w) => (
            <p key={w} className="flex items-start gap-2">
              <span aria-hidden className="mt-0.5 flex-shrink-0">ⓘ</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}

      {/* Friendly fallback when a permalink names an unknown market id. */}
      {marketNotFound && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          <span aria-hidden className="mt-0.5 flex-shrink-0">⚠</span>
          <p className="flex-1">Market not found; showing default market.</p>
          <button
            type="button"
            onClick={() => setMarketNotFound(false)}
            aria-label="Dismiss market-not-found notice"
            className="flex-shrink-0 px-1"
            style={{ color: "var(--text-mut)" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Friendly fallback when a permalink names an unknown tour id. */}
      {tourNotFound && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          <span aria-hidden className="mt-0.5 flex-shrink-0">⚠</span>
          <p className="flex-1">Tour not found; showing Globe normally.</p>
          <button
            type="button"
            onClick={() => setTourNotFound(false)}
            aria-label="Dismiss tour-not-found notice"
            className="flex-shrink-0 px-1"
            style={{ color: "var(--text-mut)" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Guided Tour card (Phase 20.7) ─────────────────────────────────── */}
      {activeTour && (
        <div
          className="card panel-glow p-4"
          role="region"
          aria-label={`Guided tour: ${activeTour.title}`}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="mono rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                  style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
                >
                  Guided tour
                </span>
                <h2 className="text-sm font-bold" style={{ color: "var(--text-hi)" }}>
                  {activeTour.title}
                </h2>
                <span className="mono text-[11px]" style={{ color: "var(--text-mut)" }} aria-live="polite">
                  Step {Math.max(tourStepIndex, 0) + 1} / {activeTour.steps.length}
                </span>
              </div>
              {tourStep && (
                <>
                  <p className="mt-1.5 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                    {selected?.flag} {tourStep.title}
                  </p>
                  <p className="mono text-[10px] uppercase tracking-wide" style={{ color: "var(--accent-text)" }}>
                    {tourStep.focus}
                  </p>
                  <p className="mt-1 max-w-2xl text-xs" style={{ color: "var(--text-mut)" }}>
                    {tourStep.explanation}
                  </p>
                  {tourStep.suggestedActions && tourStep.suggestedActions.length > 0 && (
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {tourStep.suggestedActions.map((a) => (
                        <li
                          key={a}
                          className="rounded-md px-2 py-0.5 text-[10px]"
                          style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
                        >
                          {a}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
            <div className="flex items-center gap-1" aria-hidden>
              {activeTour.steps.map((s, i) => (
                <span
                  key={s.marketId}
                  className="h-1.5 rounded-full transition-all"
                  style={{
                    width: i === tourStepIndex ? 16 : 6,
                    background: i === tourStepIndex ? "var(--accent)" : "var(--line)",
                  }}
                />
              ))}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={tourPrev}
              disabled={tourStepIndex <= 0}
              aria-label="Previous tour step"
              className="rounded-md px-3 py-1 text-xs font-semibold transition-colors disabled:opacity-40"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
            >
              ← Previous
            </button>
            <button
              type="button"
              onClick={tourNext}
              disabled={tourStepIndex >= activeTour.steps.length - 1}
              aria-label="Next tour step"
              className="rounded-md px-3 py-1 text-xs font-semibold transition-colors disabled:opacity-40"
              style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
            >
              Next →
            </button>
            <button
              type="button"
              onClick={copyTourLink}
              aria-label="Copy a shareable link to this tour step"
              className="rounded-md px-3 py-1 text-xs font-semibold transition-colors"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
            >
              🔗 Copy dossier link
            </button>
            <button
              type="button"
              onClick={exitTour}
              aria-label="Exit guided tour"
              className="rounded-md px-3 py-1 text-xs font-medium transition-colors"
              style={{ border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              Exit tour
            </button>
          </div>
          {tourCopyMsg && (
            <p role="status" aria-live="polite" className="mt-2 break-words text-[11px]" style={{ color: "var(--accent-text)" }}>
              {tourCopyMsg}
            </p>
          )}
          <p className="mt-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
            Educational tour only. Data is static by default; optional macro and
            delayed quote adapters may enrich supported fields when configured. Not
            investment advice.
          </p>
        </div>
      )}

      {/* ── Mission-control grid ──────────────────────────────────────────── */}
      <div style={gridStyle}>
        {/* Left rail (hidden in presentation mode) */}
        {!presentation && (
        <div style={{ gridArea: "rail" }} className="card flex flex-col gap-3 p-3">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search market, currency, index…"
            aria-label="Search markets"
            className="ql-input px-3 py-2 text-sm"
          />
          <div className="ql-segmented w-full" role="group" aria-label="Filter markets by region">
            {(["All", ...MARKET_REGIONS] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={"ql-segmented-option flex-1" + (region === r ? " active" : "")}
                onClick={() => setRegion(r)}
              >
                {r === "Asia-Pacific" ? "APAC" : r}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <span className="section-title" aria-live="polite">
              Markets ({filtered.length})
            </span>
            {selectedId && (
              <button
                type="button"
                onClick={clearSelection}
                className="text-[11px] font-medium"
                style={{ color: "var(--accent-text)" }}
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex flex-col gap-1.5 overflow-y-auto pr-0.5" style={{ maxHeight: mode === "narrow" ? undefined : globeHeight - 150 }}>
            {filtered.map((m) => (
              <MarketListItem
                key={m.id}
                market={m}
                active={m.id === selectedId}
                onSelect={() => selectMarket(m.id)}
              />
            ))}
            {filtered.length === 0 && (
              <div
                role="status"
                className="rounded-lg px-3 py-5 text-center text-xs"
                style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
              >
                No sample markets match this search and region.
              </div>
            )}
          </div>

          <div>
            <p className="section-title mb-1.5">Quick jump</p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_JUMP.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => {
                    setRegion("All");
                    setQuery("");
                    selectMarket(q.id);
                  }}
                  className="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-colors"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        )}

        {/* Center globe */}
        <div style={{ gridArea: "globe" }} className="card relative overflow-hidden p-0">
          <div style={{ height: globeHeight }}>
            <DataGlobe
              markets={markets}
              activeIds={effectiveActiveIds}
              arcs={MARKET_ARCS}
              selectedId={selectedId}
              onSelect={selectMarket}
              autoRotate={autoRotate}
              resetSignal={resetSignal}
            />
          </div>

          {/* Top overlay controls */}
          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-3">
            <span
              className="mono rounded-md px-2 py-1 text-[10px] uppercase tracking-wide"
              style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              Static sample data
            </span>
            <div className="pointer-events-auto flex gap-1.5">
              <button
                type="button"
                onClick={() => setAutoRotate((v) => !v)}
                aria-pressed={autoRotate}
                aria-label={autoRotate ? "Pause globe rotation" : "Resume globe rotation"}
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
              >
                {autoRotate ? "⏸ Spin" : "▶ Spin"}
              </button>
              <button
                type="button"
                onClick={resetView}
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
              >
                Reset
              </button>
              <button
                type="button"
                onClick={togglePresentation}
                aria-pressed={presentation}
                aria-label={presentation ? "Exit presentation mode" : "Enter presentation mode"}
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                style={{
                  background: presentation ? "var(--accent-softer)" : "rgba(8,11,20,0.6)",
                  border: `1px solid ${presentation ? "var(--accent-line)" : "var(--line)"}`,
                  color: presentation ? "var(--accent-text)" : "var(--text-hi)",
                }}
              >
                {presentation ? "⤢ Exit present" : "⤢ Present"}
              </button>
            </div>
          </div>

          {/* Legend */}
          <div className="pointer-events-none absolute bottom-0 left-0 flex flex-wrap items-center gap-3 p-3">
            {MARKET_REGIONS.map((r) => (
              <span key={r} className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--text-mut)" }}>
                <span className="h-2 w-2 rounded-full" style={{ background: REGION_COLORS[r], boxShadow: `0 0 6px ${REGION_COLORS[r]}` }} />
                {r === "Asia-Pacific" ? "APAC" : r}
              </span>
            ))}
            <span className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--text-mut)" }}>
              <span className="inline-block h-[2px] w-4" style={{ background: "rgba(52,214,224,0.7)" }} />
              Capital-flow arcs (illustrative)
            </span>
          </div>
        </div>

        {/* Right dossier */}
        <div style={{ gridArea: "dossier", ...dossierScroll }}>
          {selected ? (
            <MarketDossier market={selected} onNav={onNav} onClose={clearSelection} />
          ) : (
            <div className="card flex min-h-[300px] flex-col items-center justify-center p-8 text-center">
              <span aria-hidden className="text-4xl">🌐</span>
              <p className="mt-3 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Select a market
              </p>
              <p className="mt-1 max-w-xs text-xs" style={{ color: "var(--text-mut)" }}>
                Click a marker on the globe or a row in the rail to open its
                financial dossier — all static illustrative sample data.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom region tape (hidden in presentation mode) ──────────────── */}
      {!presentation && (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {rollups.map((r) => (
          <button
            key={r.region}
            type="button"
            onClick={() => {
              setQuery("");
              setRegion(r.region);
            }}
            className="card flex items-center justify-between gap-3 p-3 text-left"
          >
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: REGION_COLORS[r.region], boxShadow: `0 0 6px ${REGION_COLORS[r.region]}` }} />
              <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
                {r.region}
              </span>
            </span>
            <span className="text-right">
              <span className="mono block text-sm font-semibold" style={{ color: changeColor(r.avgChange) }}>
                {fmtPct(r.avgChange, 2)}
              </span>
              <span className="mono block text-[10px]" style={{ color: "var(--text-mut)" }}>
                ▲{r.advancers} ▼{r.decliners}
              </span>
            </span>
          </button>
        ))}
        {selected && (
          <div className="card flex items-center justify-between gap-3 p-3 sm:col-span-2 lg:col-span-4">
            <span className="flex items-center gap-2">
              <span aria-hidden className="text-base">{selected.flag}</span>
              <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
                {selected.country} · {selected.indices[0]?.name}
              </span>
            </span>
            <span className="mono text-sm font-semibold" style={{ color: changeColor(meanIndexChange(selected)) }}>
              {fmtPct(meanIndexChange(selected), 2)}
            </span>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
