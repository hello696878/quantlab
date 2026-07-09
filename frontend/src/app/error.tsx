"use client";

/**
 * Route-segment error boundary (Next.js app-router convention, 37.0 UX
 * polish). Catches render errors inside the page segment and shows a
 * friendly recovery panel with the framework's `reset()` retry — no raw
 * stack trace in the main view (technical detail stays collapsed), no claim
 * that any model output is valid after a failure. The app-level
 * `AppErrorBoundary` in the root layout remains the outer safety net.
 */

import { useEffect } from "react";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Local console only — QuantLab has no telemetry.
    console.error("QuantLab route error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div
        className="w-full max-w-lg rounded-2xl p-6"
        style={{
          background: "rgba(10,14,24,0.96)",
          border: "1px solid rgba(240,96,88,0.35)",
          boxShadow: "var(--sh-md)",
        }}
        role="alert"
      >
        <div className="flex items-start gap-3">
          <span aria-hidden className="mt-0.5 text-lg" style={{ color: "var(--neg)" }}>
            ⚠
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-bold" style={{ color: "var(--text-hi)" }}>
              This view hit an error
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text)" }}>
              Something went wrong while rendering this workspace. Any numbers shown
              before the error should not be trusted for this pass — retry or return
              to the dashboard. Your saved data is local and should not be lost.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => reset()}
                className="rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors"
                style={{
                  background: "var(--accent-soft)",
                  border: "1px solid var(--accent-line)",
                  color: "var(--accent-text)",
                }}
              >
                Try again
              </button>
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== "undefined") window.location.assign("/");
                }}
                className="rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors hover:brightness-125"
                style={{ border: "1px solid var(--line)", color: "var(--text)" }}
              >
                Back to dashboard
              </button>
            </div>

            {error?.message && (
              <details className="mt-4">
                <summary className="cursor-pointer text-xs" style={{ color: "var(--text-mut)" }}>
                  Technical details
                </summary>
                <pre
                  className="mono mt-2 max-h-40 overflow-auto rounded-lg p-3 text-[11px] leading-relaxed"
                  style={{
                    background: "var(--glass)",
                    border: "1px solid var(--line)",
                    color: "var(--text-mut)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {[error.name, error.message, error.digest ? `digest: ${error.digest}` : null]
                    .filter(Boolean)
                    .join("\n")}
                </pre>
              </details>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
