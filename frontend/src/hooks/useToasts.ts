"use client";

import { useSyncExternalStore } from "react";
import { getToasts, subscribeToasts, type Toast } from "@/lib/toast";

/**
 * Subscribe a component to the global toast store.  Uses
 * `useSyncExternalStore` so server and first client render both see an empty
 * list (no hydration mismatch) and updates are tear-free.
 */
export function useToasts(): Toast[] {
  return useSyncExternalStore(subscribeToasts, getToasts, getToasts);
}
