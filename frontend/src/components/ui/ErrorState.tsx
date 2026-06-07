"use client";

import RetryButton from "@/components/ui/RetryButton";

/**
 * Consistent inline error card for non-offline failures.  Shows a title, a
 * readable message, an optional Retry, and the raw technical text tucked inside
 * a collapsed <details> (no huge stack traces by default).
 */

interface ErrorStateProps {
  title?: string;
  message: string;
  /** Raw technical detail, collapsed by default. */
  detail?: string | null;
  onRetry?: () => void;
}

export default function ErrorState({
  title = "Something went wrong",
  message,
  detail,
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        border: "1px solid rgba(240,96,88,0.35)",
        background: "rgba(240,96,88,0.07)",
      }}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 flex-shrink-0" style={{ color: "var(--neg)" }}>
          ⚠
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
            {title}
          </p>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text)" }}>
            {message}
          </p>

          {onRetry && (
            <RetryButton onClick={onRetry} className="mt-3" />
          )}

          {detail && detail !== message && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs" style={{ color: "var(--text-mut)" }}>
                Technical details
              </summary>
              <pre
                className="mono mt-2 max-h-40 overflow-auto rounded-lg p-2.5 text-[11px] leading-relaxed"
                style={{
                  background: "var(--glass)",
                  border: "1px solid var(--line)",
                  color: "var(--text-mut)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {detail}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
