"use client";

import { useEffect, useState } from "react";

/**
 * Resolve theme accent colors as concrete `rgb(...)` strings for chart libraries
 * (Recharts/SVG) that cannot consume `var(--…)` in stroke/fill attributes.
 *
 * Reads the `--accent-rgb` / `--accent-2-rgb` custom properties off `<html>` and
 * re-reads them whenever `data-accent` changes, so charts restyle live when the
 * user switches theme in Settings (no remount needed).
 *
 * Semantic series colors (positive green, negative/drawdown red, warning amber)
 * are intentionally returned as fixed values — they must stay meaningful across
 * every accent.
 */
export interface AccentColors {
  accent: string;
  accent2: string;
  pos: string;
  neg: string;
  warn: string;
  grid: string;
  axis: string;
}

const FIXED = {
  pos: "#2be0a8",
  neg: "#f06058",
  warn: "#f5c451",
  grid: "rgba(255,255,255,0.06)",
  axis: "#79839a",
};

const FALLBACK: AccentColors = {
  accent: "rgb(52, 224, 232)",
  accent2: "rgb(77, 139, 255)",
  ...FIXED,
};

function readColors(): AccentColors {
  if (typeof window === "undefined") return FALLBACK;
  const cs = getComputedStyle(document.documentElement);
  const rgb = (name: string, fallback: string) => {
    const triplet = cs.getPropertyValue(name).trim();
    return triplet ? `rgb(${triplet})` : fallback;
  };
  return {
    accent: rgb("--accent-rgb", FALLBACK.accent),
    accent2: rgb("--accent-2-rgb", FALLBACK.accent2),
    ...FIXED,
  };
}

export function useAccentColors(): AccentColors {
  const [colors, setColors] = useState<AccentColors>(FALLBACK);

  useEffect(() => {
    setColors(readColors());
    const observer = new MutationObserver(() => setColors(readColors()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-accent"],
    });
    return () => observer.disconnect();
  }, []);

  return colors;
}
