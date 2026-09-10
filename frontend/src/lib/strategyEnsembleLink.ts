import { useEffect, useRef } from "react";

/** Narrow Phase 64 workspace permalink; existing Globe routing remains unchanged. */
export function isStrategyEnsembleLink(search?: string): boolean {
  const query = search ?? (typeof window === "undefined" ? "" : window.location.search);
  return new URLSearchParams(query).get("view") === "strategyensemble";
}

export function writeStrategyEnsembleLink(active: boolean): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (active) {
    for (const key of ["market", "tour", "presentation"]) url.searchParams.delete(key);
    url.searchParams.set("view", "strategyensemble");
  } else if (isStrategyEnsembleLink(url.search)) url.searchParams.delete("view");
  const next = url.pathname + url.search + url.hash;
  if (next !== window.location.pathname + window.location.search + window.location.hash) window.history.pushState(null, "", next);
}

/** Also cover demo and saved-resource navigation that bypasses sidebar handlers. */
export function useStrategyEnsembleLinkCleanup(view: string): void {
  const previous = useRef(view);
  useEffect(() => {
    if (previous.current === "strategyensemble" && view !== previous.current) writeStrategyEnsembleLink(false);
    previous.current = view;
  }, [view]);
}
