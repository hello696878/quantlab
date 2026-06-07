"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * App-level error boundary.  Catches unexpected render errors anywhere in the
 * tree and shows a friendly recovery panel instead of a blank/crashed UI.
 *
 * React error boundaries must be class components — there is no hook equivalent
 * for `getDerivedStateFromError` / `componentDidCatch`.
 */
export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface to the console for diagnostics; never sent anywhere (local-only).
    console.error("QuantLab caught a frontend error:", error, info);
  }

  private handleReload = (): void => {
    if (typeof window !== "undefined") window.location.reload();
  };

  private handleHome = (): void => {
    // The app's default view is the Command Center, so loading the root route
    // returns there with a fresh React tree.
    if (typeof window !== "undefined") window.location.assign("/");
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    const details = [error.name, error.message, error.stack]
      .filter(Boolean)
      .join("\n");

    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div
          className="w-full max-w-lg rounded-2xl p-6"
          style={{
            background: "rgba(10,14,24,0.96)",
            border: "1px solid rgba(240,96,88,0.35)",
            boxShadow: "var(--sh-md)",
          }}
        >
          <div className="flex items-start gap-3">
            <span aria-hidden className="mt-0.5 text-lg" style={{ color: "var(--neg)" }}>
              ⚠
            </span>
            <div className="min-w-0 flex-1">
              <h1 className="text-lg font-bold" style={{ color: "var(--text-hi)" }}>
                Something went wrong
              </h1>
              <p className="mt-1 text-sm" style={{ color: "var(--text)" }}>
                QuantLab hit a frontend error. Your saved data is local and
                should not be lost.
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={this.handleReload}
                  className="rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors"
                  style={{
                    background: "var(--accent-soft)",
                    border: "1px solid var(--accent-line)",
                    color: "var(--accent-text)",
                  }}
                >
                  Reload app
                </button>
                <button
                  type="button"
                  onClick={this.handleHome}
                  className="rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors hover:brightness-125"
                  style={{ border: "1px solid var(--line)", color: "var(--text)" }}
                >
                  Go to Command Center
                </button>
              </div>

              {details && (
                <details className="mt-4">
                  <summary
                    className="cursor-pointer text-xs"
                    style={{ color: "var(--text-mut)" }}
                  >
                    Technical details
                  </summary>
                  <pre
                    className="mono mt-2 max-h-48 overflow-auto rounded-lg p-3 text-[11px] leading-relaxed"
                    style={{
                      background: "var(--glass)",
                      border: "1px solid var(--line)",
                      color: "var(--text-mut)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {details}
                  </pre>
                </details>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
