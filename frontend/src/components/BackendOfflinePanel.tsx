"use client";

/**
 * Friendly "backend offline" panel shown when a local SQLite-backed request
 * fails because the FastAPI backend is not running.  It explains that the data
 * is safe (stored locally) and how to start the backend, and offers Retry /
 * Go to Command Center actions.  Neon-theme info card (amber accent).
 */

const START_COMMAND = [
  "cd C:\\quantlab\\backend",
  "C:\\quantlab\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
].join("\n");

const AMBER = "#fbbf24";

interface BackendOfflinePanelProps {
  /** Human label for the resource, e.g. "saved reports" / "saved backtests". */
  resource: string;
  /** What the user can do with the resource (verbs), e.g. "view, download…". */
  capabilities?: string;
  /** Original technical error text, shown small for diagnostics (optional). */
  detail?: string | null;
  /** Re-attempt the failed request. */
  onRetry: () => void;
  /** Navigate to the Command Center (optional). */
  onGoHome?: () => void;
}

export default function BackendOfflinePanel({
  resource,
  capabilities = "view, download, print, or delete",
  detail,
  onRetry,
  onGoHome,
}: BackendOfflinePanelProps) {
  return (
    <div
      className="rounded-xl p-5"
      style={{
        border: "1px solid rgba(245,158,11,0.35)",
        background: "rgba(245,158,11,0.07)",
      }}
      role="status"
    >
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 flex-shrink-0 text-base" style={{ color: AMBER }}>
          ⚠
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-bold" style={{ color: AMBER }}>
            Backend offline
          </h3>
          <p className="mt-1 text-sm" style={{ color: "var(--text)" }}>
            Your {resource} are stored locally in SQLite through the FastAPI
            backend — <span className="font-semibold">nothing is lost</span>.
            Start the backend to {capabilities} {resource}.
          </p>

          <p className="mt-3 text-xs" style={{ color: "var(--text-mut)" }}>
            Start it from a terminal:
          </p>
          <pre
            className="mono mt-1 overflow-x-auto rounded-lg p-3 text-[11.5px] leading-relaxed"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--line)",
              color: "var(--text-hi)",
            }}
          >
            {START_COMMAND}
          </pre>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
              style={{
                background: "var(--accent-soft)",
                border: "1px solid var(--accent-line)",
                color: "var(--accent-text)",
              }}
            >
              Retry
            </button>
            {onGoHome && (
              <button
                type="button"
                onClick={onGoHome}
                className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors hover:brightness-125"
                style={{
                  border: "1px solid var(--line)",
                  color: "var(--text)",
                }}
              >
                Go to Command Center
              </button>
            )}
          </div>

          {detail && (
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-mut)" }}>
              Details: {detail}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
