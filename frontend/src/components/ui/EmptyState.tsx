"use client";

import type { ReactNode } from "react";

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary";
}

interface EmptyStateProps {
  title: string;
  description?: string;
  /** Optional decorative glyph/icon shown above the title. */
  icon?: ReactNode;
  actions?: EmptyStateAction[];
  /** Tighter padding for use inside small panels (e.g. Command Center cards). */
  compact?: boolean;
}

/**
 * Consistent "nothing here yet" panel.  Always offers a clear next action when
 * one is provided.  Never renders placeholder/fake rows.
 */
export default function EmptyState({
  title,
  description,
  icon,
  actions,
  compact = false,
}: EmptyStateProps) {
  return (
    <div className={`card text-center ${compact ? "p-6" : "p-10"}`}>
      {icon && (
        <div className="mb-3 flex justify-center" style={{ color: "var(--text-mut)" }}>
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
        {title}
      </p>
      {description && (
        <p className="mx-auto mt-1.5 max-w-md text-xs" style={{ color: "var(--text-mut)" }}>
          {description}
        </p>
      )}
      {actions && actions.length > 0 && (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {actions.map((a) => {
            const primary = (a.variant ?? "primary") === "primary";
            return (
              <button
                key={a.label}
                type="button"
                onClick={a.onClick}
                className="rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors hover:brightness-125"
                style={
                  primary
                    ? {
                        background: "var(--accent-soft)",
                        border: "1px solid var(--accent-line)",
                        color: "var(--accent-text)",
                      }
                    : { border: "1px solid var(--line)", color: "var(--text)" }
                }
              >
                {a.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
