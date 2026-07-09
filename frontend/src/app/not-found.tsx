/**
 * Not-found page (Next.js app-router convention, 37.0 UX polish). QuantLab is
 * a single-page workspace app — any unknown URL gets a friendly pointer back
 * to the dashboard (where the sidebar and command palette cover every
 * workspace). Server component; no client state needed.
 */

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div
        className="w-full max-w-md rounded-2xl p-6 text-center"
        style={{
          background: "rgba(10,14,24,0.96)",
          border: "1px solid var(--line)",
          boxShadow: "var(--sh-md)",
        }}
      >
        <p className="mono text-3xl font-bold" style={{ color: "var(--text-faint)" }} aria-hidden>
          404
        </p>
        <h1 className="mt-2 text-lg font-bold" style={{ color: "var(--text-hi)" }}>
          This page does not exist
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-mut)" }}>
          QuantLab&apos;s workspaces all live on the dashboard — use the sidebar or the
          command palette (Ctrl/Cmd+K) to jump to any module.
        </p>
        <Link
          href="/"
          className="mt-4 inline-block rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors"
          style={{
            background: "var(--accent-soft)",
            border: "1px solid var(--accent-line)",
            color: "var(--accent-text)",
          }}
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
