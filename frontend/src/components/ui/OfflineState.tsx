"use client";

/**
 * Consistent "backend offline" panel for any SQLite-backed resource.  Explains
 * the data is safe (stored locally), how to start the backend, and offers
 * Retry / Go to Command Center.  Neon-theme amber info card.
 */

const START_COMMAND = [
  "cd C:\\quantlab\\backend",
  "C:\\quantlab\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
].join("\n");

const AMBER = "#fbbf24";

const DEFAULT_MESSAGE =
  "Saved local resources require the FastAPI backend because they are stored in SQLite. Your data is safe — nothing is lost.";

interface OfflineStateProps {
  title?: string;
  message?: string;
  /** Original technical error text, shown small for diagnostics (optional). */
  detail?: string | null;
  onRetry?: () => void;
  onGoHome?: () => void;
  /** Show the `uvicorn` start command (default true; hidden in compact mode). */
  showCommand?: boolean;
  /** Tighter layout for small panels (Command Center cards). */
  compact?: boolean;
}

export default function OfflineState({
  title = "Backend offline",
  message = DEFAULT_MESSAGE,
  detail,
  onRetry,
  onGoHome,
  showCommand = true,
  compact = false,
}: OfflineStateProps) {
  return (
    <div
      className={`rounded-xl ${compact ? "p-4" : "p-5"}`}
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
          <h3 className={`font-bold ${compact ? "text-sm" : "text-base"}`} style={{ color: AMBER }}>
            {title}
          </h3>
          <p className="mt-1 text-sm" style={{ color: "var(--text)" }}>
            {message}
          </p>

          {showCommand && !compact && (
            <>
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
            </>
          )}

          {(onRetry || onGoHome) && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {onRetry && (
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
              )}
              {onGoHome && (
                <button
                  type="button"
                  onClick={onGoHome}
                  className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors hover:brightness-125"
                  style={{ border: "1px solid var(--line)", color: "var(--text)" }}
                >
                  Go to Command Center
                </button>
              )}
            </div>
          )}

          {detail && !compact && (
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-mut)" }}>
              Details: {detail}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
