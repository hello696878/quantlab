"use client";

import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";
import { openCommandPalette, useIsMac } from "@/components/CommandPalette";

/** Discoverability hint that also opens the command palette on click. */
function PaletteHint() {
  const isMac = useIsMac();
  return (
    <button
      type="button"
      onClick={openCommandPalette}
      title="Search commands (Ctrl/Cmd + K)"
      className="glass hidden items-center gap-2 px-3 py-1.5 transition-colors hover:brightness-125 sm:flex"
      style={{ borderRadius: 999 }}
    >
      <svg
        width={13}
        height={13}
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--text-mut)"
        strokeWidth="2"
        strokeLinecap="round"
        aria-hidden
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m21 21-4.3-4.3" />
      </svg>
      <span className="uplabel" style={{ color: "var(--text)" }}>
        Search
      </span>
      <kbd className="mono text-[11px]" style={{ color: "var(--text-mut)" }}>
        {isMac ? "⌘K" : "Ctrl K"}
      </kbd>
    </button>
  );
}

/** Live UTC clock. */
function Clock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Render nothing until mounted (avoids hydration mismatch on the timestamp).
  if (!now) return null;

  return (
    <span className="mono text-[12px]" style={{ color: "var(--text-mut)" }}>
      {now.toLocaleTimeString("en-US", { hour12: false })}
    </span>
  );
}

/**
 * Real backend health indicator.
 * Polls /api/health (via the existing fetch layer) — no fake data.
 */
function ApiStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      const ok = await checkHealth();
      if (!cancelled) setOnline(ok);
    }
    ping();
    const id = setInterval(ping, 20_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const label = online === null ? "…" : online ? "ONLINE" : "OFFLINE";
  const color =
    online === null
      ? "var(--text-mut)"
      : online
        ? "var(--pos)"
        : "var(--neg)";

  return (
    <div
      className="glass flex items-center gap-2 px-3 py-1.5"
      style={{ borderRadius: 999 }}
    >
      <span
        className="livedot"
        style={
          online === false
            ? { background: "var(--neg)", boxShadow: "0 0 8px var(--neg)" }
            : undefined
        }
      />
      <span className="uplabel" style={{ color: "var(--text)" }}>
        API
      </span>
      <span className="mono text-[11.5px]" style={{ color }}>
        {label}
      </span>
    </div>
  );
}

interface TopBarProps {
  title: string;
  subtitle?: string;
}

export default function TopBar({ title, subtitle }: TopBarProps) {
  return (
    <header
      className="topbar sticky top-0 z-20 flex items-center gap-4 px-7 py-4"
      style={{
        borderBottom: "1px solid var(--line)",
        background: "rgba(8,11,20,0.72)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
      }}
    >
      <div className="flex min-w-0 items-center gap-3">
        {/* Accent terminal rule next to the page title */}
        <span
          aria-hidden
          style={{
            width: 3,
            alignSelf: "stretch",
            minHeight: 28,
            borderRadius: 2,
            background: "var(--accent)",
            boxShadow: "0 0 12px -1px rgba(var(--accent-rgb), 0.7)",
            flexShrink: 0,
          }}
        />
        <div className="min-w-0">
          <h1
            className="m-0 text-[19px] font-bold tracking-[-0.01em]"
            style={{ color: "var(--text-hi)" }}
          >
            {title}
          </h1>
          {subtitle && (
            <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--text-mut)" }}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
      <div className="ml-auto flex items-center gap-3.5">
        <PaletteHint />
        <Clock />
        <ApiStatus />
      </div>
    </header>
  );
}
