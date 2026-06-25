"use client";

import type { View } from "@/components/AppShell";

// ---------------------------------------------------------------------------
// Icons (minimal line glyphs, stroke = currentColor)
// ---------------------------------------------------------------------------

const ICONS: Record<string, string> = {
  home: "M3 11l9-8 9 8M5 9.5V21h5v-6h4v6h5V9.5",
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
  library: "M4 19.5V5a2 2 0 0 1 2-2h14v17H6a2 2 0 0 0-2 2Zm0 0A2.5 2.5 0 0 0 6.5 22H20M9 7h7M9 11h7",
  papers: "M8 3h8l4 4v14H8V3Zm8 0v4h4M4 7v14h12M11 11h6M11 15h6",
  warning: "M12 3 2.5 19.5h19L12 3Zm0 6v5m0 3.5v.5",
  options: "M3 12h4l3 7 4-14 3 7h4",
  events: "M4 5h16v15H4zM4 9h16M8 3v4M16 3v4",
  rates: "M3 17c3 0 4-9 7-9s4 6 7 6 3-7 4-7M3 21h18",
  fx: "M4 7h11l-3-3m3 3-3 3M20 17H9l3-3m-3 3 3 3",
  credit: "M4 6h16v12H4zM4 10h16M8 15h4",
  risklab: "M21 21H3V3M7 16l4-5 3 3 5-7M19 6h-3M19 6v3",
  realestate: "M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6M9 11h.01M15 11h.01",
  futures: "M3 17l5-6 4 3 4-7 5 4M3 21h18M3 3v18",
  scanner: "M4 14h3v6H4zM10.5 9h3v11h-3zM17 4h3v16h-3z",
  finml: "M4 18 9 9l4 5 3-6 4 7M4 4v16h16",
  globe:
    "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 0c2.5 2.4 3.8 5.6 3.8 9s-1.3 6.6-3.8 9c-2.5-2.4-3.8-5.6-3.8-9S9.5 5.4 12 3ZM3.2 9h17.6M3.2 15h17.6",
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
  { id: "home", label: "Home", icon: "home" },
  { id: "globe", label: "Global Markets Globe", icon: "globe" },
  { id: "backtest", label: "Backtest", icon: "backtest" },
  { id: "library", label: "Strategy Library", icon: "library" },
  { id: "comparison", label: "Strategy Comparison", icon: "compare" },
  { id: "replications", label: "Paper Replications", icon: "papers" },
  { id: "disasters", label: "Quant Disasters", icon: "warning" },
  { id: "options", label: "Options Lab", icon: "options" },
  { id: "events", label: "Event Lab", icon: "events" },
  { id: "rates", label: "Yield Curve Lab", icon: "rates" },
  { id: "fx", label: "FX Lab", icon: "fx" },
  { id: "credit", label: "Credit Risk Lab", icon: "credit" },
  { id: "risklab", label: "Portfolio Risk Lab", icon: "risklab" },
  { id: "realestate", label: "Real Estate Lab", icon: "realestate" },
  { id: "futures", label: "Futures & Commodities Lab", icon: "futures" },
  { id: "scanner", label: "Cross-Sectional Scanner", icon: "scanner" },
  { id: "finml", label: "AFML Methodology Lab", icon: "finml" },
  { id: "csv", label: "CSV Backtest", icon: "upload" },
  { id: "builder", label: "Strategy Builder", icon: "builder" },
  { id: "portfolio", label: "Portfolio Backtest", icon: "portfolio" },
  { id: "sweep", label: "Parameter Sweep", icon: "sweep" },
  { id: "train-test", label: "Train/Test Validation", icon: "research" },
  { id: "walk-forward", label: "Walk-Forward", icon: "walkfwd" },
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
      className="shell-sidebar fixed bottom-0 left-0 right-0 z-30 flex h-16 w-full items-center gap-2 overflow-x-auto px-3 py-2 md:top-0 md:bottom-auto md:h-screen md:w-56 md:flex-col md:items-stretch md:overflow-x-hidden md:overflow-y-auto md:px-3.5 md:py-5"
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
