"use client";

import type { ReactNode } from "react";
import ToastViewport from "@/components/ToastViewport";

/**
 * Mounts the global toast viewport alongside the app.  Toast state lives in a
 * module-level store (`lib/toast.ts`), so no React context is needed — any code
 * can call `toast.success(...)` / `notifyBackendOffline()` from anywhere.
 */
export default function ToastProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <ToastViewport />
    </>
  );
}
