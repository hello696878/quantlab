"use client";

import type { View } from "@/components/AppShell";

// ---------------------------------------------------------------------------
// Icons (minimal line glyphs, stroke = currentColor)
// ---------------------------------------------------------------------------

const ICONS: Record<string, string> = {
  backtest: "M4 4v16h16M8 16l3-4 3 2 4-6",
  sweep:
    "M4 4h4v4H4V4Zm6 0h4v4h-4V4Zm6 0h4v4h-4V4ZM4 10h4v4H4v-4Zm6 0h4v4h-4v-4Zm6 0h4v4h-4v-4ZM4 16h4v4H4v-4Zm6 0h4v4h-4v-4Zm6 0h4v4h-4v-4Z",
  research: "M11 4a7 7 0 1 0 4.95 11.95L20 20M11 4a7 7 0 0 1 7 7",
  walkfwd: "M3 17l5-5 4 3 5-7 4 4M3 21h18",
  compare: "M9 3v18M15 3v18M4 7h5M15 11h5M4 14h5M15 17h5",
  saved:
    "M5 3h11l3 3v15H5V3Zm3 0v6h7V3M8 14h8M8 17h8",
  report:
    "M7 3h7l4 4v14H7V3Zm7 0v4h4M10 12h5M10 16h5M10 8h2",
  settings:
    "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm8.4 3a8.4 8.4 0 0 0-.12-1.4l2-1.55-2-3.46-2.36.95a8.4 8.4 0 0 0-2.42-1.4L14.8 1.6h-4l-.3 2.94a8.4 8.4 0 0 0-2.42 1.4l-2.36-.95-2 3.46 2 1.55A8.4 8.4 0 0 0 3.6 12c0 .47.04.94.12 1.4l-2 1.55 2 3.46 2.36-.95a8.4 8.4 0 0 0 2.42 1.4l.3 2.94h4l.3-2.94a8.4 8.4 0 0 0 2.42-1.4l2.36.95 2-3.46-2-1.55c.08-.46.12-.93.12-1.4Z",
  upload: "M12 16V4m0 0L7 9m5-5 5 5M5 20h14",
  builder: "M4 7h7v7H4V7Zm9 3h7v7h-7v-7ZM7 4h10M16 14v6",
  portfolio: "M3 3v18h18M7 14l3-3 3 2 5-6",
};

function Icon({ name, size = 17 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Logo mark
// ---------------------------------------------------------------------------

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width={30} height={30} viewBox="0 0 32 32" fill="none">
        <rect
          x="1"
          y="1"
          width="30"
          height="30"
          rx="8"
          fill="rgba(var(--accent-rgb),0.12)"
          stroke="var(--accent)"
          strokeOpacity="0.5"
        />
        <path
          d="M6 22 L12 13 L17 18 L26 7"
          stroke="var(--accent)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <circle cx="26" cy="7" r="2.6" fill="var(--cyan)" />
      </svg>
      <div className="leading-[1.05]">
        <div
          className="font-extrabold text-[16px] tracking-[-0.02em]"
          style={{ color: "var(--text-hi)" }}
        >
          Quant<span style={{ color: "var(--accent)" }}>Lab</span>
        </div>
        <div
          className="mono text-[9px] tracking-[0.14em]"
          style={{ color: "var(--text-faint)" }}
        >
          RESEARCH TERMINAL
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export const NAV: { id: View; label: string; icon: string }[] = [
  { id: "backtest", label: "Backtest", icon: "backtest" },
  { id: "csv", label: "CSV Backtest", icon: "upload" },
  { id: "builder", label: "Strategy Builder", icon: "builder" },
  { id: "portfolio", label: "Portfolio Backtest", icon: "portfolio" },
  { id: "sweep", label: "Parameter Sweep", icon: "sweep" },
  { id: "train-test", label: "Train/Test Validation", icon: "research" },
  { id: "walk-forward", label: "Walk-Forward", icon: "walkfwd" },
  { id: "comparison", label: "Strategy Comparison", icon: "compare" },
  { id: "saved", label: "Saved Backtests", icon: "saved" },
  { id: "reports", label: "Saved Reports", icon: "report" },
  { id: "settings", label: "Settings", icon: "settings" },
];

interface SidebarProps {
  active: View;
  onNav: (view: View) => void;
}

export default function Sidebar({ active, onNav }: SidebarProps) {
  return (
    <aside
      className="shell-sidebar fixed bottom-0 left-0 right-0 z-30 flex h-16 w-full items-center gap-2 overflow-x-auto px-3 py-2 md:top-0 md:bottom-auto md:h-screen md:w-56 md:flex-col md:items-stretch md:overflow-visible md:px-3.5 md:py-5"
      style={{
        background: "rgba(8,11,20,0.55)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
      }}
    >
      <div className="hidden px-2 pb-6 pt-0.5 md:block">
        <Logo />
      </div>

      <nav className="flex w-full items-center gap-1 md:flex-col md:items-stretch">
        <div className="uplabel hidden px-2 pb-1.5 md:block">Workspaces</div>
        {NAV.map((n) => (
          <button
            key={n.id}
            type="button"
            onClick={() => onNav(n.id)}
            className={"navbtn" + (active === n.id ? " active" : "")}
          >
            <span className="navicon">
              <Icon name={n.icon} />
            </span>
            {n.label}
          </button>
        ))}
      </nav>

      <div className="mt-auto hidden flex-col gap-2.5 md:flex">
        <div className="glass px-3 py-2.5" style={{ borderRadius: 12 }}>
          <div className="mb-1.5 flex items-center gap-2">
            <span className="livedot" />
            <span className="uplabel" style={{ color: "var(--text)" }}>
              Engine
            </span>
          </div>
          <div
            className="mono text-[10.5px] leading-[1.6]"
            style={{ color: "var(--text-faint)" }}
          >
            FastAPI backtest core
            <br />
            yfinance market data
          </div>
        </div>
        <p
          className="px-2 text-[10px] leading-snug"
          style={{ color: "var(--text-faint)" }}
        >
          Research only · not financial advice
        </p>
      </div>
    </aside>
  );
}
