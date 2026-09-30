import { useEffect, useRef } from "react";

export function isMLLifecycleLink(search?: string): boolean {
  return new URLSearchParams(search ?? (typeof window === "undefined" ? "" : window.location.search)).get("view") === "mllifecycle";
}

export function writeMLLifecycleLink(active: boolean): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (active) {
    for (const key of ["market", "tour", "presentation"]) url.searchParams.delete(key);
    url.searchParams.set("view", "mllifecycle");
  } else if (isMLLifecycleLink(url.search)) url.searchParams.delete("view");
  const next = url.pathname + url.search + url.hash;
  if (next !== window.location.pathname + window.location.search + window.location.hash) window.history.pushState(null, "", next);
}

export function useMLLifecycleLinkCleanup(view: string): void {
  const previous = useRef(view);
  useEffect(() => {
    if (previous.current === "mllifecycle" && view !== previous.current) writeMLLifecycleLink(false);
    previous.current = view;
  }, [view]);
}
