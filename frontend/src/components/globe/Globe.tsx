"use client";

/**
 * Global Markets Globe — dependency-free interactive 3D globe.
 *
 * Rendered as pure SVG with a hand-rolled orthographic projection (lat/lon →
 * 3D unit sphere → rotated → projected to 2D). This deliberately avoids
 * Three.js / react-three-fiber and WebGL: it needs no extra npm packages, can
 * never crash on a machine without WebGL, and renders identically server- and
 * client-side. The accompanying market list (in GlobeLabPanel) is the
 * keyboard-accessible path; this canvas is a pointer-driven visual layer.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Market, MarketRegion } from "@/lib/globe/markets";

const DEG = Math.PI / 180;
const VB = 560; // viewBox size (square)
const CX = VB / 2;
const CY = VB / 2;
const R = 232; // sphere radius in viewBox units

const REGION_COLOR: Record<MarketRegion, string> = {
  Americas: "var(--cyan)",
  Europe: "var(--violet)",
  "Asia-Pacific": "var(--emerald)",
};

interface Rot {
  lon: number;
  lat: number;
}

interface Projected {
  x: number;
  y: number;
  z: number; // >0 = near (visible) hemisphere
}

/** Project geographic (lat, lon) onto the orthographic disc for rotation `rot`. */
function project(latDeg: number, lonDeg: number, rot: Rot): Projected {
  const lat = latDeg * DEG;
  const lon = lonDeg * DEG;
  const x = Math.cos(lat) * Math.sin(lon);
  const y = Math.sin(lat);
  const z = Math.cos(lat) * Math.cos(lon);
  // Yaw about the vertical axis so `rot.lon` faces the viewer.
  const a = -rot.lon * DEG;
  const x1 = x * Math.cos(a) + z * Math.sin(a);
  const z1 = -x * Math.sin(a) + z * Math.cos(a);
  // Pitch about the horizontal axis so `rot.lat` faces the viewer.
  const b = rot.lat * DEG;
  const y2 = y * Math.cos(b) - z1 * Math.sin(b);
  const z2 = y * Math.sin(b) + z1 * Math.cos(b);
  return { x: CX + R * x1, y: CY - R * y2, z: z2 };
}

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

function normLon(lon: number): number {
  let l = lon;
  while (l > 180) l -= 360;
  while (l < -180) l += 360;
  return l;
}

/** Build SVG path data for one graticule line, breaking it at the horizon. */
function linePath(points: { lat: number; lon: number }[], rot: Rot): string {
  let d = "";
  let pen = false;
  for (const pt of points) {
    const p = project(pt.lat, pt.lon, rot);
    if (p.z >= 0) {
      d += `${pen ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)} `;
      pen = true;
    } else {
      pen = false;
    }
  }
  return d;
}

// Precompute graticule sample points once (meridians + parallels).
const GRATICULE: { lat: number; lon: number }[][] = (() => {
  const lines: { lat: number; lon: number }[][] = [];
  for (let lon = -150; lon <= 180; lon += 30) {
    const pts: { lat: number; lon: number }[] = [];
    for (let lat = -80; lat <= 80; lat += 4) pts.push({ lat, lon });
    lines.push(pts);
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    const pts: { lat: number; lon: number }[] = [];
    for (let lon = -180; lon <= 180; lon += 4) pts.push({ lat, lon });
    lines.push(pts);
  }
  return lines;
})();

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(mq.matches);
    apply();
    mq.addEventListener?.("change", apply);
    return () => mq.removeEventListener?.("change", apply);
  }, []);
  return reduced;
}

interface GlobeProps {
  markets: Market[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function Globe({ markets, selectedId, onSelect }: GlobeProps) {
  const [rot, setRot] = useState<Rot>({ lon: -40, lat: 18 });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);

  const rotRef = useRef(rot);
  rotRef.current = rot;
  const autoRef = useRef(autoRotate);
  autoRef.current = autoRotate;
  const targetRef = useRef<Rot | null>(null);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const lastRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number | null>(null);
  const runningRef = useRef(false);

  const reducedMotion = usePrefersReducedMotion();
  const reducedRef = useRef(reducedMotion);
  reducedRef.current = reducedMotion;

  // Disable auto-rotation when the user prefers reduced motion.
  useEffect(() => {
    if (reducedMotion) setAutoRotate(false);
  }, [reducedMotion]);

  const startLoop = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    const step = () => {
      if (!runningRef.current) return;
      const cur = rotRef.current;
      if (draggingRef.current) {
        // Drag handler drives state directly; just keep the loop alive.
      } else if (targetRef.current) {
        const t = targetRef.current;
        let dLon = normLon(t.lon - cur.lon);
        const dLat = t.lat - cur.lat;
        if (Math.abs(dLon) < 0.3 && Math.abs(dLat) < 0.3) {
          targetRef.current = null;
          const snapped = { lon: normLon(t.lon), lat: t.lat };
          rotRef.current = snapped;
          setRot(snapped);
        } else {
          const next = {
            lon: normLon(cur.lon + dLon * 0.16),
            lat: cur.lat + dLat * 0.16,
          };
          rotRef.current = next;
          setRot(next);
        }
      } else if (autoRef.current && !reducedRef.current) {
        const next = { lon: normLon(cur.lon - 0.12), lat: cur.lat };
        rotRef.current = next;
        setRot(next);
      } else {
        runningRef.current = false;
        rafRef.current = null;
        return; // nothing to animate — idle
      }
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
  }, []);

  // Kick the animation loop on mount / when auto-rotate turns on.
  useEffect(() => {
    if (autoRotate && !reducedMotion) startLoop();
    return () => {
      runningRef.current = false;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [autoRotate, reducedMotion, startLoop]);

  // Centre the globe on the selected market (pauses auto-rotation).
  useEffect(() => {
    if (!selectedId) return;
    const m = markets.find((mk) => mk.id === selectedId);
    if (!m) return;
    setAutoRotate(false);
    targetRef.current = { lon: m.lon, lat: clamp(m.lat, -70, 70) };
    startLoop();
  }, [selectedId, markets, startLoop]);

  // ---- Pointer drag-to-rotate -------------------------------------------
  function onPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    draggingRef.current = true;
    movedRef.current = false;
    lastRef.current = { x: e.clientX, y: e.clientY };
    targetRef.current = null;
    (e.currentTarget as SVGSVGElement).setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    if (!draggingRef.current) return;
    const dx = e.clientX - lastRef.current.x;
    const dy = e.clientY - lastRef.current.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) movedRef.current = true;
    lastRef.current = { x: e.clientX, y: e.clientY };
    // Convert CSS-pixel deltas to degrees (scaled to the rendered size).
    const k = 0.36;
    const cur = rotRef.current;
    const next = {
      lon: normLon(cur.lon - dx * k),
      lat: clamp(cur.lat + dy * k, -82, 82),
    };
    rotRef.current = next;
    setRot(next);
  }
  function onPointerUp() {
    draggingRef.current = false;
    if (autoRef.current && !reducedRef.current) startLoop();
  }

  // ---- Derived geometry --------------------------------------------------
  const graticule = useMemo(
    () => GRATICULE.map((pts) => linePath(pts, rot)),
    [rot],
  );

  const projectedMarkers = useMemo(
    () =>
      markets
        .map((m) => ({ market: m, p: project(m.lat, m.lon, rot) }))
        .filter((x) => x.p.z > 0.02)
        // Draw far-but-visible markers first so near ones sit on top.
        .sort((a, b) => a.p.z - b.p.z),
    [markets, rot],
  );

  const hovered = hoveredId
    ? projectedMarkers.find((x) => x.market.id === hoveredId)
    : null;

  return (
    <div className="relative w-full">
      <svg
        viewBox={`0 0 ${VB} ${VB}`}
        className="w-full select-none"
        style={{ touchAction: "none", cursor: draggingRef.current ? "grabbing" : "grab", maxHeight: 520 }}
        role="img"
        aria-label="Interactive 3D globe of sample world markets. Use the market list below for a keyboard-accessible view."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <defs>
          <radialGradient id="globeOcean" cx="38%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#1b2b4d" />
            <stop offset="55%" stopColor="#0d1730" />
            <stop offset="100%" stopColor="#060a16" />
          </radialGradient>
          <radialGradient id="globeSheen" cx="34%" cy="28%" r="55%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.16)" />
            <stop offset="60%" stopColor="rgba(255,255,255,0.03)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <radialGradient id="globeAtmo" cx="50%" cy="50%" r="50%">
            <stop offset="80%" stopColor="rgba(var(--accent-rgb),0)" />
            <stop offset="93%" stopColor="rgba(var(--accent-rgb),0.20)" />
            <stop offset="100%" stopColor="rgba(var(--accent-rgb),0)" />
          </radialGradient>
        </defs>

        {/* Atmosphere glow */}
        <circle cx={CX} cy={CY} r={R + 26} fill="url(#globeAtmo)" />

        {/* Sphere */}
        <circle cx={CX} cy={CY} r={R} fill="url(#globeOcean)" />
        <circle
          cx={CX}
          cy={CY}
          r={R}
          fill="none"
          stroke="rgba(var(--accent-rgb),0.45)"
          strokeWidth={1.2}
        />

        {/* Graticule */}
        <g stroke="rgba(120,160,220,0.16)" strokeWidth={0.8} fill="none">
          {graticule.map((d, i) =>
            d ? <path key={i} d={d} /> : null,
          )}
        </g>

        {/* Lit-side sheen overlay */}
        <circle cx={CX} cy={CY} r={R} fill="url(#globeSheen)" pointerEvents="none" />

        {/* Markers */}
        {projectedMarkers.map(({ market, p }) => {
          const isSelected = market.id === selectedId;
          const isHovered = market.id === hoveredId;
          const color = isSelected ? "var(--accent)" : REGION_COLOR[market.region];
          const coreR = isSelected ? 5 : isHovered ? 4.2 : 3.3;
          return (
            <g
              key={market.id}
              transform={`translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`}
              style={{ cursor: "pointer" }}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(market.id);
              }}
              onPointerEnter={() => setHoveredId(market.id)}
              onPointerLeave={() => setHoveredId(null)}
            >
              {/* Pulsing halo */}
              <circle
                className="globe-pulse"
                r={6}
                fill="none"
                stroke={color}
                strokeWidth={1.4}
                style={{ animationDelay: `${(market.lat + 90) * 12}ms` }}
              />
              {isSelected && (
                <circle r={9} fill="none" stroke={color} strokeWidth={1.4} opacity={0.7} />
              )}
              {/* Core dot */}
              <circle r={coreR} fill={color} stroke="#060a16" strokeWidth={1} />
              {/* Generous invisible hit target */}
              <circle r={12} fill="transparent" />
              {isSelected && (
                <text
                  y={-13}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={700}
                  fill="var(--text-hi)"
                  style={{ paintOrder: "stroke", stroke: "#060a16", strokeWidth: 3 }}
                >
                  {market.flag} {market.country}
                </text>
              )}
            </g>
          );
        })}

        {/* Hover tooltip (drawn last, above markers) */}
        {hovered && hovered.market.id !== selectedId && (
          <g
            transform={`translate(${hovered.p.x.toFixed(1)} ${hovered.p.y.toFixed(1)})`}
            pointerEvents="none"
          >
            <text
              y={-13}
              textAnchor="middle"
              fontSize={12}
              fontWeight={700}
              fill="var(--text-hi)"
              style={{ paintOrder: "stroke", stroke: "#060a16", strokeWidth: 3 }}
            >
              {hovered.market.flag} {hovered.market.country}
            </text>
          </g>
        )}
      </svg>

      {/* Controls */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={() => setAutoRotate((v) => !v)}
          disabled={reducedMotion}
          className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50"
          style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
        >
          {autoRotate ? "⏸ Pause spin" : "▶ Auto-rotate"}
        </button>
        <span className="text-[11px]" style={{ color: "var(--text-mut)" }}>
          Drag to rotate · click a marker for its dossier
        </span>
      </div>
    </div>
  );
}
