"use client";

import { useState } from "react";
import PortfolioBacktestPanel from "@/components/PortfolioBacktestPanel";
import PortfolioOptimizePanel from "@/components/PortfolioOptimizePanel";

type PortfolioTab = "backtest" | "optimize";

const TABS: { id: PortfolioTab; label: string }[] = [
  { id: "backtest", label: "Equal-Weight Backtest" },
  { id: "optimize", label: "Portfolio Optimization" },
];

export default function PortfolioWorkspace() {
  const [tab, setTab] = useState<PortfolioTab>("backtest");

  return (
    <div className="space-y-6">
      <div className="flex gap-1 p-1 bg-slate-100 rounded-xl w-fit">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={
              "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors " +
              (tab === t.id
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "backtest" ? <PortfolioBacktestPanel /> : <PortfolioOptimizePanel />}
    </div>
  );
}
