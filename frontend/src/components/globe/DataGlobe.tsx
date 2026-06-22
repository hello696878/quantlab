"use client";

/**
 * Global Markets Globe v1.1 — canvas 2D "mission control" globe.
 *
 * A hand-built orthographic globe (no WebGL, no Three.js, no GeoJSON, no
 * textures) per the Claude Design VISUAL_REDESIGN spec (§13): radial-gradient
 * ocean + accent atmosphere halo, a coarse lat/lon dot-matrix landmass mask, a
 * 30° graticule, a starfield, region-colored pulsing markers with back-face
 * culling, great-circle "capital-flow" arcs with a travelling pulse, plus
 * drag-to-rotate, auto-rotate, reset, and hover tooltips.
 *
 * Honest stylized data-viz, NOT cartography or live data. If a 2D canvas
 * context is unavailable, it renders a graceful fallback message (the market
 * list in the page rail remains the keyboard-accessible path).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MARKETS,
  REGION_COLORS,
  type Market,
  type MarketRegion,
} from "@/lib/globe/markets";

const RAD = Math.PI / 180;
const DEFAULT_ROT = { lon: -40, lat: 18 };

// Coarse continent boxes [latMin, latMax, lonMin, lonMax] for the dot-matrix
// land mask. Deliberately blocky — a stylized silhouette, not a real map.
const LAND_BOXES: [number, number, number, number][] = [
  [30, 70, -160, -95], // N. America (west)
  [25, 60, -100, -58], // N. America (east)
  [8, 30, -112, -80], // Central America
  [-55, 12, -82, -34], // South America
  [36, 71, -10, 40], // Europe
  [-35, 37, -18, 52], // Africa
  [12, 42, 35, 60], // Middle East
  [8, 75, 60, 150], // Asia (core)
  [6, 30, 68, 90], // India
  [-10, 28, 95, 142], // SE Asia
  [-40, -10, 112, 154], // Australia
  [30, 46, 129, 146], // Japan
];

function isLand(lat: number, lon: number): boolean {
  for (const [a, b, c, d] of LAND_BOXES) {
    if (lat >= a && lat <= b && lon >= c && lon <= d) return true;
  }
  return false;
}

// Deterministic starfield (positions in [0,1] space + twinkle phase).
const STARS = (() => {
  let s = 0x9e3779b9 >>> 0;
  const rnd = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return Array.from({ length: 150 }, () => ({
    x: rnd(),
    y: rnd(),
    r: 0.3 + rnd() * 1.1,
    ph: rnd() * Math.PI * 2,
  }));
})();

interface Vec {
  x: number;
  y: number;
  z: number;
}

function latLonToVec(latDeg: number, lonDeg: number): Vec {
  const lat = latDeg * RAD;
  const lon = lonDeg * RAD;
  return {
    x: Math.cos(lat) * Math.sin(lon),
    y: Math.sin(lat),
    z: Math.cos(lat) * Math.cos(lon),
  };
}

function rotateVec(v: Vec, yawDeg: number, pitchDeg: number): Vec {
  const ay = -yawDeg * RAD;
  const x1 = v.x * Math.cos(ay) + v.z * Math.sin(ay);
  const z1 = -v.x * Math.sin(ay) + v.z * Math.cos(ay);
  const ap = pitchDeg * RAD;
  const y2 = v.y * Math.cos(ap) - z1 * Math.sin(ap);
  const z2 = v.y * Math.sin(ap) + z1 * Math.cos(ap);
  return { x: x1, y: y2, z: z2 };
}

function hexA(hex: string, a: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
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

interface DataGlobeProps {
  /** All markets to render (the globe always shows the full world). */
  markets?: Market[];
  /** Ids currently matching the filter; non-matching markers/arcs dim. null = all. */
  activeIds: Set<string> | null;
  arcs: readonly (readonly [string, string])[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  autoRotate: boolean;
  /** Bump to reset the camera to the default view. */
  resetSignal: number;
}

export default function DataGlobe({
  markets = MARKETS,
  activeIds,
  arcs,
  selectedId,
  onSelect,
  autoRotate,
  resetSignal,
}: DataGlobeProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [canvasOk, setCanvasOk] = useState(true);
  const [hover, setHover] = useState<{ m: Market; x: number; y: number } | null>(null);

  const reduced = usePrefersReducedMotion();

  // Mutable refs read by the stable animation loop (avoid stale closures).
  const rotRef = useRef({ ...DEFAULT_ROT });
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });
  const tickRef = useRef(0);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const lastPtrRef = useRef({ x: 0, y: 0 });
  const targetRef = useRef<{ lon: number; lat: number } | null>(null);
  const screenRef = useRef<{ id: string; sx: number; sy: number }[]>([]);
  const hoverIdRef = useRef<string | null>(null);

  const propsRef = useRef({ markets, activeIds, selectedId, autoRotate, arcs, reduced });
  propsRef.current = { markets, activeIds, selectedId, autoRotate, arcs, reduced };

  const byId = useRef(new Map<string, Market>());
  byId.current = new Map(markets.map((m) => [m.id, m]));

  // Reset camera on demand.
  useEffect(() => {
    rotRef.current = { ...DEFAULT_ROT };
    targetRef.current = null;
  }, [resetSignal]);

  // Centre on the selected market (snap under reduced motion, else tween).
  useEffect(() => {
    if (!selectedId) return;
    const m = byId.current.get(selectedId);
    if (!m) return;
    const target = { lon: m.lon, lat: clamp(m.lat, -68, 68) };
    if (reduced) {
      rotRef.current = target;
      targetRef.current = null;
    } else {
      targetRef.current = target;
    }
  }, [selectedId, reduced]);

  const draw = useCallback((ctx: CanvasRenderingContext2D) => {
    const { w, h } = sizeRef.current;
    if (w === 0 || h === 0) return;
    const p = propsRef.current;
    const tick = tickRef.current;
    const phase = tick * 0.033; // seconds-ish
    const cx = w / 2;
    const cy = h / 2;
    const R = Math.min(w, h) * 0.42;
    const rot = rotRef.current;

    ctx.clearRect(0, 0, w, h);

    // ── Starfield ────────────────────────────────────────────────────────
    for (const st of STARS) {
      const tw = p.reduced ? 0.6 : 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(phase * 1.3 + st.ph));
      ctx.fillStyle = `rgba(190, 210, 245, ${(0.10 + 0.5 * tw * (st.r / 1.4)).toFixed(3)})`;
      ctx.fillRect(st.x * w, st.y * h, st.r, st.r);
    }

    // ── Atmosphere halo ──────────────────────────────────────────────────
    // createRadialGradient cannot read CSS vars — use a resolved accent glow.
    const glow = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.25);
    glow.addColorStop(0, "rgba(52, 214, 224, 0)");
    glow.addColorStop(0.55, "rgba(52, 214, 224, 0.12)");
    glow.addColorStop(1, "rgba(52, 214, 224, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.25, 0, Math.PI * 2);
    ctx.fill();

    // ── Ocean sphere ─────────────────────────────────────────────────────
    const ocean = ctx.createRadialGradient(
      cx - R * 0.32,
      cy - R * 0.36,
      R * 0.1,
      cx,
      cy,
      R,
    );
    ocean.addColorStop(0, "#1a2b4d");
    ocean.addColorStop(0.55, "#0e1830");
    ocean.addColorStop(1, "#060a16");
    ctx.fillStyle = ocean;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fill();

    // Clip to the sphere for land + graticule.
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();

    // ── Land dot-matrix (front hemisphere only) ──────────────────────────
    for (let lat = -84; lat <= 84; lat += 3) {
      for (let lon = -180; lon < 180; lon += 3) {
        if (!isLand(lat, lon)) continue;
        const v = rotateVec(latLonToVec(lat, lon), rot.lon, rot.lat);
        if (v.z <= 0.02) continue;
        const sx = cx + R * v.x;
        const sy = cy - R * v.y;
        const a = 0.12 + 0.5 * v.z;
        ctx.fillStyle = `rgba(116, 170, 196, ${a.toFixed(3)})`;
        const d = 0.9 + v.z * 0.9;
        ctx.fillRect(sx, sy, d, d);
      }
    }

    // ── Graticule (30°) ──────────────────────────────────────────────────
    ctx.strokeStyle = "rgba(130, 165, 220, 0.10)";
    ctx.lineWidth = 0.7;
    for (let lon = -150; lon <= 180; lon += 30) {
      ctx.beginPath();
      let pen = false;
      for (let lat = -80; lat <= 80; lat += 4) {
        const v = rotateVec(latLonToVec(lat, lon), rot.lon, rot.lat);
        if (v.z >= 0) {
          const sx = cx + R * v.x;
          const sy = cy - R * v.y;
          if (pen) ctx.lineTo(sx, sy);
          else ctx.moveTo(sx, sy);
          pen = true;
        } else pen = false;
      }
      ctx.stroke();
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      ctx.beginPath();
      let pen = false;
      for (let lon = -180; lon <= 180; lon += 4) {
        const v = rotateVec(latLonToVec(lat, lon), rot.lon, rot.lat);
        if (v.z >= 0) {
          const sx = cx + R * v.x;
          const sy = cy - R * v.y;
          if (pen) ctx.lineTo(sx, sy);
          else ctx.moveTo(sx, sy);
          pen = true;
        } else pen = false;
      }
      ctx.stroke();
    }
    ctx.restore();

    // ── Rim light ────────────────────────────────────────────────────────
    ctx.strokeStyle = "rgba(120, 200, 230, 0.35)";
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.stroke();

    // ── Great-circle arcs ────────────────────────────────────────────────
    for (const [aId, bId] of p.arcs) {
      const ma = byId.current.get(aId);
      const mb = byId.current.get(bId);
      if (!ma || !mb) continue;
      const dim =
        p.activeIds != null && !p.activeIds.has(aId) && !p.activeIds.has(bId);
      const va = latLonToVec(ma.lat, ma.lon);
      const vb = latLonToVec(mb.lat, mb.lon);
      const dot = clamp(va.x * vb.x + va.y * vb.y + va.z * vb.z, -1, 1);
      const omega = Math.acos(dot);
      const sinO = Math.sin(omega) || 1e-6;
      const N = 48;
      ctx.beginPath();
      let pen = false;
      for (let i = 0; i <= N; i++) {
        const t = i / N;
        const k1 = Math.sin((1 - t) * omega) / sinO;
        const k2 = Math.sin(t * omega) / sinO;
        const lift = 1 + 0.18 * Math.sin(Math.PI * t);
        const vx = (va.x * k1 + vb.x * k2) * lift;
        const vy = (va.y * k1 + vb.y * k2) * lift;
        const vz = (va.z * k1 + vb.z * k2) * lift;
        const rv = rotateVec({ x: vx, y: vy, z: vz }, rot.lon, rot.lat);
        if (rv.z >= 0) {
          const sx = cx + R * rv.x;
          const sy = cy - R * rv.y;
          if (pen) ctx.lineTo(sx, sy);
          else ctx.moveTo(sx, sy);
          pen = true;
        } else pen = false;
      }
      ctx.strokeStyle = dim ? "rgba(120, 150, 190, 0.12)" : "rgba(52, 214, 224, 0.38)";
      ctx.lineWidth = 1.1;
      ctx.stroke();

      // Travelling pulse along the arc.
      if (!p.reduced && !dim) {
        const t = (phase * 0.22) % 1;
        const k1 = Math.sin((1 - t) * omega) / sinO;
        const k2 = Math.sin(t * omega) / sinO;
        const lift = 1 + 0.18 * Math.sin(Math.PI * t);
        const rv = rotateVec(
          { x: (va.x * k1 + vb.x * k2) * lift, y: (va.y * k1 + vb.y * k2) * lift, z: (va.z * k1 + vb.z * k2) * lift },
          rot.lon,
          rot.lat,
        );
        if (rv.z >= 0) {
          ctx.fillStyle = "rgba(140, 240, 250, 0.9)";
          ctx.beginPath();
          ctx.arc(cx + R * rv.x, cy - R * rv.y, 1.8, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // ── Markers ──────────────────────────────────────────────────────────
    const screen: { id: string; sx: number; sy: number }[] = [];
    const drawn = p.markets
      .map((m) => ({ m, v: rotateVec(latLonToVec(m.lat, m.lon), rot.lon, rot.lat) }))
      .filter((o) => o.v.z > 0.02)
      .sort((a, b) => a.v.z - b.v.z);

    for (const { m, v } of drawn) {
      const sx = cx + R * v.x;
      const sy = cy - R * v.y;
      screen.push({ id: m.id, sx, sy });
      const isSel = m.id === p.selectedId;
      const isHover = hoverIdRef.current === m.id;
      const active = p.activeIds == null || p.activeIds.has(m.id);
      const base = REGION_COLORS[m.region as MarketRegion] ?? "#34d6e0";
      const alpha = active ? 1 : 0.22;

      // Pulsing halo.
      const pulse = p.reduced ? 0.5 : 0.5 + 0.5 * Math.sin(phase * 2 + m.lat);
      const haloR = (isSel ? 10 : 7) + pulse * (isSel ? 6 : 4);
      ctx.beginPath();
      ctx.arc(sx, sy, haloR, 0, Math.PI * 2);
      ctx.fillStyle = hexA(base, (isSel ? 0.16 : 0.1) * alpha * (1 - pulse * 0.5));
      ctx.fill();

      // Selected ring.
      if (isSel) {
        ctx.beginPath();
        ctx.arc(sx, sy, 11, 0, Math.PI * 2);
        ctx.strokeStyle = hexA(base, 0.9);
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      // Core dot.
      const coreR = isSel ? 4.6 : isHover ? 4 : 3.2;
      ctx.beginPath();
      ctx.arc(sx, sy, coreR, 0, Math.PI * 2);
      ctx.fillStyle = hexA(base, alpha);
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = `rgba(6, 10, 22, ${alpha})`;
      ctx.stroke();

      // Selected label.
      if (isSel) {
        const label = `${m.country}`;
        ctx.font = "600 12px Manrope, ui-sans-serif, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(6, 10, 22, 0.72)";
        ctx.fillRect(sx - tw / 2 - 6, sy - 30, tw + 12, 17);
        ctx.fillStyle = "#e8ecf6";
        ctx.fillText(label, sx, sy - 16);
      }
    }
    screenRef.current = screen;
  }, []);

  // ── Animation loop + sizing (set up once) ──────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setCanvasOk(false);
      return;
    }

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      sizeRef.current = { w, h, dpr };
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(resize);
      ro.observe(wrap);
    } else {
      window.addEventListener("resize", resize);
    }

    let frameId = 0;
    let lastFrame = 0;
    const animate = (now: number) => {
      frameId = window.requestAnimationFrame(animate);
      const p = propsRef.current;
      const frameInterval = p.reduced && !draggingRef.current && !targetRef.current ? 250 : 33;
      if (now - lastFrame < frameInterval) return;

      const steps = lastFrame === 0 ? 1 : Math.min((now - lastFrame) / 33, 4);
      lastFrame = now;
      tickRef.current += steps;
      const rot = rotRef.current;
      const tgt = targetRef.current;
      if (!draggingRef.current) {
        if (tgt) {
          let dLon = normLon(tgt.lon - rot.lon);
          const dLat = tgt.lat - rot.lat;
          if (Math.abs(dLon) < 0.4 && Math.abs(dLat) < 0.4) {
            rotRef.current = { lon: normLon(tgt.lon), lat: tgt.lat };
            targetRef.current = null;
          } else {
            const easing = 1 - Math.pow(0.84, steps);
            rotRef.current = {
              lon: normLon(rot.lon + dLon * easing),
              lat: rot.lat + dLat * easing,
            };
          }
        } else if (p.autoRotate && !p.reduced) {
          rotRef.current = { lon: normLon(rot.lon - 0.18 * steps), lat: rot.lat };
        }
      }
      draw(ctx);
    };
    frameId = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(frameId);
      ro?.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [draw]);

  // ── Pointer interaction ────────────────────────────────────────────────
  function hitTest(clientX: number, clientY: number): Market | null {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let best: { id: string; d: number } | null = null;
    const activeIds = propsRef.current.activeIds;
    for (const s of screenRef.current) {
      if (activeIds != null && !activeIds.has(s.id)) continue;
      const d = Math.hypot(s.sx - x, s.sy - y);
      if (d < 14 && (!best || d < best.d)) best = { id: s.id, d };
    }
    return best ? byId.current.get(best.id) ?? null : null;
  }

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    draggingRef.current = true;
    movedRef.current = false;
    lastPtrRef.current = { x: e.clientX, y: e.clientY };
    targetRef.current = null;
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    if (draggingRef.current) {
      const dx = e.clientX - lastPtrRef.current.x;
      const dy = e.clientY - lastPtrRef.current.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) movedRef.current = true;
      lastPtrRef.current = { x: e.clientX, y: e.clientY };
      const r = rotRef.current;
      rotRef.current = {
        lon: normLon(r.lon - dx * 0.32),
        lat: clamp(r.lat + dy * 0.32, -82, 82),
      };
      return;
    }
    const m = hitTest(e.clientX, e.clientY);
    const wrap = wrapRef.current;
    if (m && wrap) {
      hoverIdRef.current = m.id;
      const rect = wrap.getBoundingClientRect();
      setHover({ m, x: e.clientX - rect.left, y: e.clientY - rect.top });
    } else {
      hoverIdRef.current = null;
      setHover((current) => (current ? null : current));
    }
  }
  function onPointerUp(e: React.PointerEvent<HTMLCanvasElement>) {
    const wasDragging = draggingRef.current;
    draggingRef.current = false;
    if (wasDragging && !movedRef.current) {
      const m = hitTest(e.clientX, e.clientY);
      if (m) onSelect(m.id);
    }
  }

  if (!canvasOk) {
    return (
      <div
        className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-2xl p-8 text-center"
        style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
      >
        <span aria-hidden className="text-3xl">🌐</span>
        <p className="mt-3 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
          3D globe unavailable in this browser
        </p>
        <p className="mt-1 max-w-xs text-xs" style={{ color: "var(--text-mut)" }}>
          Use the market list below. Core market data is illustrative; optional
          FRED fields retain their source labels.
        </p>
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative h-full w-full" style={{ minHeight: 320 }}>
      <canvas
        ref={canvasRef}
        className="block h-full w-full"
        style={{ touchAction: "none", cursor: hover ? "pointer" : "grab" }}
        role="img"
        aria-label="Interactive 3D globe of sample world markets. Use the market list for a keyboard-accessible view."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          draggingRef.current = false;
          hoverIdRef.current = null;
          setHover(null);
        }}
        onPointerLeave={() => {
          draggingRef.current = false;
          hoverIdRef.current = null;
          setHover(null);
        }}
      />
      {hover && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-lg px-2.5 py-1.5"
          style={{
            left: hover.x,
            top: hover.y - 14,
            background: "rgba(8,11,20,0.92)",
            border: "1px solid var(--line-strong)",
            boxShadow: "var(--sh-md)",
          }}
        >
          <p className="whitespace-nowrap text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
            {hover.m.flag} {hover.m.country}
          </p>
          <p className="mono whitespace-nowrap text-[10px]" style={{ color: "var(--text-mut)" }}>
            {hover.m.region} · {hover.m.indices[0]?.ticker ?? ""}
          </p>
        </div>
      )}
    </div>
  );
}
