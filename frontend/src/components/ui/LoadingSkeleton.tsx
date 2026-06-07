"use client";

import type { CSSProperties } from "react";

/**
 * Loading-skeleton primitives.  All share the `.skeleton` class (defined in
 * globals.css) which provides the muted block + subtle shimmer.  Sizes are
 * chosen to roughly match the real content so layout doesn't jump on load.
 */

export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden />;
}

/** A few lines of fake text. */
export function SkeletonText({
  lines = 3,
  className = "",
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-3"
          style={{ width: i === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

/** A compact card skeleton (icon + two text lines). */
export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card flex items-center gap-3 p-4 ${className}`} aria-hidden>
      <Skeleton className="h-9 w-9 flex-shrink-0 rounded-lg" />
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-3.5" style={{ width: "55%" }} />
        <Skeleton className="h-3" style={{ width: "80%" }} />
      </div>
    </div>
  );
}

/** A table skeleton inside a card: header strip + N shimmer rows. */
export function SkeletonTable({
  rows = 5,
  cols = 4,
  caption,
}: {
  rows?: number;
  cols?: number;
  caption?: string;
}) {
  return (
    <div
      className="card overflow-hidden"
      role="status"
      aria-busy="true"
      aria-label={caption ?? "Loading…"}
    >
      <div
        className="flex gap-4 px-4 py-3"
        style={{ borderBottom: "1px solid var(--line)" }}
      >
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      <div>
        {Array.from({ length: rows }).map((_, r) => (
          <div
            key={r}
            className="flex items-center gap-4 px-4 py-3.5"
            style={{ borderBottom: "1px solid var(--line-faint)" }}
          >
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton
                key={c}
                className="h-3.5 flex-1"
                style={{ opacity: 1 - r * 0.12 }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
