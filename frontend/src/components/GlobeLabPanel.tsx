"use client";

/**
 * Global Markets Globe — v1 (static illustrative showcase).
 *
 * Composes the dependency-free SVG globe with a region filter, search box, a
 * keyboard-accessible market list (the a11y / no-pointer fallback), and the
 * market dossier side panel. All data is static sample data — no live market
 * data, FX, macro, or news is fetched (see lib/globe/markets.ts).
 */

import { useState } from "react";
import type { View } from "@/components/AppShell";
import Globe from "@/components/globe/Globe";
import MarketDossier from "@/components/globe/MarketDossier";
import {
  MARKETS,
  MARKET_REGIONS,
  filterMarkets,
  findMarketById,
  type Market,
  type MarketRegion,
} from "@/lib/globe/markets";
import { fmtPct } from "@/lib/format";

const REGION_COLOR: Record<MarketRegion, string> = {
  Americas: "var(--cyan)",
  Europe: "var(--violet)",
  "Asia-Pacific": "var(--emerald)",
};

function MarketListItem({
  market,
  active,
  onSelect,
}: {
  market: Market;
  active: boolean;
  onSelect: () => void;
}) {
  const top = market.indices[0];
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors"
      style={{
        background: active ? "var(--accent-softer)" : "var(--glass)",
        border: `1px solid ${active ? "var(--accent-line)" : "var(--line)"}`,
      }}
    >
      <span aria-hidden className="text-lg leading-none">
        {market.flag}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
          {market.country}
        </span>
        <span className="block truncate text-[11px]" style={{ color: "var(--text-mut)" }}>
          <span style={{ color: REGION_COLOR[market.region] }}>{market.region}</span>
          {" · "}
          {market.currency} · {market.exchange}
        </span>
      </span>
      {top && (
        <span
          className="mono flex-shrink-0 text-xs font-semibold"
          style={{ color: top.changePct > 0 ? "var(--pos)" : top.changePct < 0 ? "var(--neg)" : "var(--text-mut)" }}
        >
          {fmtPct(top.changePct, 2)}
        </span>
      )}
    </button>
  );
}

interface GlobeLabPanelProps {
  initialMarketId?: string | null;
  onNav: (view: View) => void;
}

export default function GlobeLabPanel({ initialMarketId, onNav }: GlobeLabPanelProps) {
  const [region, setRegion] = useState<MarketRegion | "All">("All");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(initialMarketId ?? null);

  const filtered = filterMarkets(region, query);
  const selected = findMarketById(selectedId);

  function resetView() {
    setRegion("All");
    setQuery("");
    setSelectedId(null);
  }

  return (
    <div className="space-y-5">
      {/* ── Header / disclaimer ─────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              Global Markets Globe
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore an interactive 3D map of {MARKETS.length} sample
              investable markets. Click a marker — or a row in the list — to open a
              country dossier with equity indices, a macro snapshot, currency &amp;
              rates, market structure, sample headlines, and cross-links into
              QuantLab.
            </p>
          </div>
          <span
            className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            Static data v1
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Static illustrative sample data — not real-time market data and not
          investment advice. Live FRED macro, delayed index / FX quotes, a
          news / sentiment feed, and GeoJSON country borders are planned future
          work.
        </p>
      </div>

      {/* ── Controls ────────────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="ql-segmented" role="group" aria-label="Filter markets by region">
            {(["All", ...MARKET_REGIONS] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={"ql-segmented-option" + (region === r ? " active" : "")}
                onClick={() => setRegion(r)}
              >
                {r}
              </button>
            ))}
          </div>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search country, currency, exchange, index…"
            aria-label="Search markets"
            className="ql-input flex-1 px-3 py-1.5"
            style={{ minWidth: 220 }}
          />
          <button
            type="button"
            onClick={resetView}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
            style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
          >
            Reset
          </button>
        </div>
      </div>

      {/* ── Globe + list (left) and dossier (right) ─────────────────────── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="card p-4">
            <Globe markets={filtered} selectedId={selectedId} onSelect={setSelectedId} />
          </div>

          {/* Keyboard-accessible market list (also the WebGL-free fallback) */}
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="section-title">Markets ({filtered.length})</p>
              {selectedId && (
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="text-xs font-medium"
                  style={{ color: "var(--accent-text)" }}
                >
                  Clear selection
                </button>
              )}
            </div>
            {filtered.length === 0 ? (
              <p className="px-1 py-6 text-center text-sm" style={{ color: "var(--text-mut)" }}>
                No markets match your filter. <button type="button" onClick={resetView} className="underline">Reset</button>.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
                {filtered.map((m) => (
                  <MarketListItem
                    key={m.id}
                    market={m}
                    active={m.id === selectedId}
                    onSelect={() => setSelectedId(m.id)}
                  />
                ))}
              </div>
            )}
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              The globe is a pure-SVG visualization (no WebGL required). If 3D
              rendering is ever unavailable, use this list to open any dossier.
            </p>
          </div>
        </div>

        {/* Dossier */}
        <div>
          {selected ? (
            <MarketDossier market={selected} onNav={onNav} onClose={() => setSelectedId(null)} />
          ) : (
            <div className="card flex h-full min-h-[300px] flex-col items-center justify-center p-8 text-center">
              <span aria-hidden className="text-4xl">
                🌐
              </span>
              <p className="mt-3 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Select a market
              </p>
              <p className="mt-1 max-w-xs text-xs" style={{ color: "var(--text-mut)" }}>
                Click a marker on the globe or a row in the list to open its
                financial dossier — all static illustrative sample data.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
