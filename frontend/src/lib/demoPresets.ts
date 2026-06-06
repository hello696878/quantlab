// ---------------------------------------------------------------------------
// Guided demo presets
//
// These describe *which* workspace a guided demo opens and *what* it prefills.
// They carry NO results — clicking a demo only navigates + prefills a form.
// The actual analysis is always a real backend API call made when the user
// clicks Run.  No performance numbers are ever fabricated here.
//
// Concrete backtest parameter objects live in `page.tsx` (which owns the form
// state); this module only holds the lightweight catalogue used to render the
// guided-demo shortcuts.
// ---------------------------------------------------------------------------

import type { View } from "@/components/AppShell";

export type DemoPresetId =
  | "sma_backtest"
  | "crypto_momentum"
  | "portfolio_risk"
  | "efficient_frontier"
  | "strategy_builder";

export interface DemoPresetMeta {
  id: DemoPresetId;
  label: string;
  /** One-line summary of the prefilled inputs (not results). */
  detail: string;
  /** Workspace this demo opens. */
  target: View;
}

export const DEMO_PRESETS: DemoPresetMeta[] = [
  {
    id: "sma_backtest",
    label: "Demo Backtest",
    detail: "SPY · SMA Crossover 20/100 · 2015–2023",
    target: "backtest",
  },
  {
    id: "crypto_momentum",
    label: "Demo Crypto Momentum",
    detail: "BTC-USD · Time-Series Momentum · 2015–2023",
    target: "backtest",
  },
  {
    id: "portfolio_risk",
    label: "Demo Portfolio Risk",
    detail: "SPY · QQQ · GLD · TLT · Risk Dashboard",
    target: "portfolio",
  },
  {
    id: "efficient_frontier",
    label: "Demo Efficient Frontier",
    detail: "SPY · QQQ · GLD · TLT · 2,000 portfolios",
    target: "portfolio",
  },
  {
    id: "strategy_builder",
    label: "Demo Strategy Builder",
    detail: "Load SMA Trend Filter or Momentum + Trend",
    target: "builder",
  },
];
