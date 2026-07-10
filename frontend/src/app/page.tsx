"use client";

import { useEffect, useState } from "react";
import AppShell, { type View } from "@/components/AppShell";
import BacktestForm from "@/components/BacktestForm";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import SmaSweepPanel from "@/components/SmaSweepPanel";
import SmaTrainTestPanel from "@/components/SmaTrainTestPanel";
import SmaWalkForwardPanel from "@/components/SmaWalkForwardPanel";
import StrategyComparisonPanel from "@/components/StrategyComparisonPanel";
import CsvBacktestPanel from "@/components/CsvBacktestPanel";
import StrategyBuilderPanel from "@/components/StrategyBuilderPanel";
import PortfolioWorkspace, {
  type PortfolioTab,
} from "@/components/PortfolioWorkspace";
import SaveBacktestModal from "@/components/SaveBacktestModal";
import SignalDiagnostics from "@/components/SignalDiagnostics";
import ShortModeDiagnostics from "@/components/ShortModeDiagnostics";
import RiskDiagnosticsCard from "@/components/RiskDiagnosticsCard";
import DataQualityCard from "@/components/DataQualityCard";
import BenchmarkComparisonCard from "@/components/BenchmarkComparisonCard";
import ExcessReturnChart from "@/components/ExcessReturnChart";
import ReproducibilityCard from "@/components/ReproducibilityCard";
import RobustnessLabCard from "@/components/RobustnessLabCard";
import StabilityLabCard from "@/components/StabilityLabCard";
import StrategyLibraryPanel from "@/components/StrategyLibraryPanel";
import { LIVE_MODELS, MODEL_REGISTRY } from "@/lib/modelRegistry";
import PaperReplicationsPanel from "@/components/PaperReplicationsPanel";
import {
  LIVE_PAPERS,
  PAPER_REGISTRY,
  type PaperEntry,
  type PaperRunPreset,
} from "@/lib/paperRegistry";
import QuantDisastersPanel from "@/components/QuantDisastersPanel";
import { DISASTER_REGISTRY, LIVE_DISASTERS } from "@/lib/disasterRegistry";
import OptionsLabPanel from "@/components/OptionsLabPanel";
import EventLabPanel from "@/components/EventLabPanel";
import YieldCurveLabPanel from "@/components/YieldCurveLabPanel";
import FxLabPanel from "@/components/FxLabPanel";
import CreditLabPanel from "@/components/CreditLabPanel";
import ScannerLabPanel from "@/components/ScannerLabPanel";
import AfmlLabPanel from "@/components/AfmlLabPanel";
import PortfolioRiskLabPanel from "@/components/PortfolioRiskLabPanel";
import RealEstateLabPanel from "@/components/RealEstateLabPanel";
import FuturesLabPanel from "@/components/FuturesLabPanel";
import VolatilityLabPanel from "@/components/VolatilityLabPanel";
import MicrostructureLabPanel from "@/components/MicrostructureLabPanel";
import CryptoDerivativesLabPanel from "@/components/CryptoDerivativesLabPanel";
import DefiRiskLabPanel from "@/components/DefiRiskLabPanel";
import TokenomicsLabPanel from "@/components/TokenomicsLabPanel";
import OnChainAnalyticsLabPanel from "@/components/OnChainAnalyticsLabPanel";
import AlternativeDataLabPanel from "@/components/AlternativeDataLabPanel";
import MacroRegimeLabPanel from "@/components/MacroRegimeLabPanel";
import ScenarioStudioPanel from "@/components/ScenarioStudioPanel";
import ResearchWorkspacePanel from "@/components/ResearchWorkspacePanel";
import DemoCenterPanel from "@/components/DemoCenterPanel";
import DataReliabilityPanel from "@/components/DataReliabilityPanel";
import QACommandCenterPanel from "@/components/QACommandCenterPanel";
import PortfolioShowcasePanel from "@/components/PortfolioShowcasePanel";
import DeveloperOnboardingPanel from "@/components/DeveloperOnboardingPanel";
import GlobeLabPanel from "@/components/GlobeLabPanel";
import { MARKETS } from "@/lib/globe/markets";
import {
  clearGlobeUrl,
  readGlobeParams,
  writeGlobeUrl,
} from "@/lib/globe/permalink";
import { TOUR_LIST } from "@/lib/globe/tours";
import { buildBenchmarkChartSeries } from "@/lib/benchmarkCharts";
import ShortSellingWarning from "@/components/ShortSellingWarning";
import ExportReportButton from "@/components/ExportReportButton";
import { buildBacktestReport, downloadTextFile } from "@/lib/reportExport";
import SavedBacktestsList from "@/components/SavedBacktestsList";
import SavedBacktestDetail from "@/components/SavedBacktestDetail";
import SavedReportsList from "@/components/SavedReportsList";
import SavedReportDetail from "@/components/SavedReportDetail";
import HomeDashboard from "@/components/HomeDashboard";
import SettingsPanel from "@/components/SettingsPanel";
import CommandPalette, { type Command } from "@/components/CommandPalette";
import { DEMO_PRESETS, type DemoPresetId } from "@/lib/demoPresets";
import { markChecklistStep } from "@/lib/onboarding";
import { notifyBackendOffline, toast } from "@/lib/toast";
import { applyAccent, loadSettings, resolveDateRange } from "@/lib/settings";
import {
  classifyApiError,
  runBacktest,
  runBbBacktest,
  runMomentumBacktest,
  runPairsBacktest,
  runRsiBacktest,
  runVbBacktest,
} from "@/lib/api";
import type {
  BacktestRequest,
  BacktestResponse,
  BbBacktestRequest,
  MomentumBacktestRequest,
  PairsBacktestRequest,
  RsiBacktestRequest,
  StrategyType,
  VbBacktestRequest,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Default parameters
// ---------------------------------------------------------------------------

// Defaults are demo-friendly starting points, not performance-optimized.
// Classic/long-term variants are available as one-click presets in the form.

const DEFAULT_SMA_PARAMS: BacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  fast_window: 20,
  slow_window: 100,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
  position_sizing: { type: "full_allocation" },
};

const DEFAULT_RSI_PARAMS: RsiBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  rsi_window: 14,
  oversold_threshold: 35,
  exit_threshold: 55,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_sizing: { type: "full_allocation" },
};

const DEFAULT_BB_PARAMS: BbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  bb_window: 20,
  num_std: 1.8,
  exit_band: "middle",
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_sizing: { type: "full_allocation" },
};

const DEFAULT_MOMENTUM_PARAMS: MomentumBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  momentum_window: 63,
  entry_threshold: 0.0,
  exit_threshold: 0.0,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
  position_sizing: { type: "full_allocation" },
};

const DEFAULT_VB_PARAMS: VbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 20,
  breakout_multiplier: 0.3,
  exit_window: 10,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
  position_sizing: { type: "full_allocation" },
};

const DEFAULT_PAIRS_PARAMS: PairsBacktestRequest = {
  asset_y: "KO",
  asset_x: "PEP",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 60,
  entry_z_score: 1.5,
  exit_z_score: 0.5,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

// Guided "Demo Crypto Momentum" preset — the long-only momentum defaults on a
// crypto ticker. Real backend run; only the inputs are prefilled.
const DEMO_CRYPTO_MOMENTUM_PARAMS: MomentumBacktestRequest = {
  ...DEFAULT_MOMENTUM_PARAMS,
  ticker: "BTC-USD",
  // 24/7 asset → let auto-detection pick the crypto (365) convention.
  annualization_mode: "auto",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a human-readable strategy label from the backtest response. */
function strategyLabel(r: BacktestResponse): string {
  if (r.strategy === "sma_crossover") {
    return `SMA ${r.fast_window}/${r.slow_window}`;
  }
  if (r.strategy === "rsi_mean_reversion") {
    return `RSI(${r.rsi_window ?? 14}) ${r.oversold_threshold}→${r.exit_threshold}`;
  }
  if (r.strategy === "bollinger_band") {
    const exit = r.bb_exit_band === "upper" ? "Upper" : "Mid";
    return `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 1.8}σ) exit:${exit}`;
  }
  if (r.strategy === "momentum") {
    const entry = r.momentum_entry_threshold ?? 0;
    const exit = r.momentum_exit_threshold ?? 0;
    return `Momentum(${r.momentum_window ?? 63}) entry:${entry} exit:${exit}`;
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `VolBreakout(${r.vb_lookback_window ?? 20}, ` +
      `${r.vb_breakout_multiplier ?? 0.3}x range, exit:${r.vb_exit_window ?? 10})`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Pairs ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `Z(${r.pairs_lookback_window ?? 60}) ` +
      `entry:${r.pairs_entry_z_score ?? 1.5} exit:${r.pairs_exit_z_score ?? 0.5}`
    );
  }
  return r.strategy;
}

/** Build a compact param summary shown beside the ticker in the results header. */
function paramSummary(r: BacktestResponse): string {
  const cost = `${r.transaction_cost_bps} bps`;
  const trades = `${r.num_trades} trade events`;
  const modeLabel =
    r.position_mode === "short_only"
      ? "Short-only · "
      : r.position_mode === "long_short"
        ? "Long/Short · "
        : "";
  if (r.strategy === "sma_crossover") {
    return `${modeLabel}SMA ${r.fast_window}/${r.slow_window} · ${cost} · ${trades}`;
  }
  if (r.strategy === "rsi_mean_reversion") {
    return (
      `RSI(${r.rsi_window ?? 14}) OB=${r.oversold_threshold} ` +
      `Exit=${r.exit_threshold} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "bollinger_band") {
    return (
      `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 1.8}σ) ` +
      `exit:${r.bb_exit_band ?? "middle"} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "momentum") {
    return (
      `${modeLabel}Momentum(${r.momentum_window ?? 63}) ` +
      `entry:${r.momentum_entry_threshold ?? 0} ` +
      `exit:${r.momentum_exit_threshold ?? 0} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `${modeLabel}VolBreakout lookback:${r.vb_lookback_window ?? 20} ` +
      `mult:${r.vb_breakout_multiplier ?? 0.3}x range ` +
      `exit mean:${r.vb_exit_window ?? 10} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Spread ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `lookback:${r.pairs_lookback_window ?? 60} ` +
      `entry:|z|>${r.pairs_entry_z_score ?? 1.5} ` +
      `exit z→±${r.pairs_exit_z_score ?? 0.5} · ${cost} · ${trades}`
    );
  }
  return `${cost} · ${trades}`;
}

function costModelBadgeLabel(r: BacktestResponse): string {
  if (!r.cost_model) return "";
  if (r.cost_model.type === "simple_bps") return "Simple BPS";
  if (r.cost_model.type === "conservative") return "Conservative cost";
  return "Commission + slippage";
}

const STRATEGY_HEADINGS: Record<
  StrategyType,
  { title: string; description: string }
> = {
  sma_crossover: {
    title: "SMA Crossover Backtest",
    description:
      "Long-only strategy that buys when the fast SMA crosses above the slow " +
      "SMA and exits when it crosses below. Signal is shifted one day forward " +
      "to prevent lookahead bias.",
  },
  rsi_mean_reversion: {
    title: "RSI Mean Reversion Backtest",
    description:
      "Long-only mean-reversion strategy that enters when RSI dips below the " +
      "oversold threshold and exits when RSI recovers above the exit threshold. " +
      "Signal is shifted one day forward to prevent lookahead bias.",
  },
  bollinger_band: {
    title: "Bollinger Band Mean Reversion Backtest",
    description:
      "Long-only mean-reversion strategy that enters when price falls below the " +
      "lower Bollinger Band and exits when price " +
      "recovers to the selected exit band. Signal is shifted one day forward to " +
      "prevent lookahead bias.",
  },
  momentum: {
    title: "Time-Series Momentum Backtest",
    description:
      "Long-only trend-following strategy. Enters when the trailing N-day return " +
      "exceeds the entry threshold and exits when it falls to or below the exit " +
      "threshold. An entry > exit gap creates a hysteresis band that reduces " +
      "turnover in choppy markets. Signal is shifted one day forward to prevent " +
      "lookahead bias.",
  },
  volatility_breakout: {
    title: "Volatility Breakout Backtest",
    description:
      "Long-only trend-following strategy. Enters when price breaks above the " +
      "prior rolling high plus a multiple of the prior high-low range. Exits " +
      "when price falls below the rolling mean exit level. Signal is shifted " +
      "one day forward to prevent lookahead bias.",
  },
  pairs: {
    title: "Pairs Trading Backtest",
    description:
      "Dollar-neutral statistical arbitrage on two correlated assets. Spread = " +
      "log(Y) − log(X). Enters long-spread (long Y / short X) when z-score " +
      "falls below −entry_z, short-spread (short Y / long X) when it rises " +
      "above +entry_z. Long-spread exits when z-score crosses above −exit_z; " +
      "short-spread exits when it crosses below +exit_z. Each leg gets 50 % of " +
      "capital. Benchmark is an equal-weight pair benchmark. Signal shifted one day " +
      "forward to prevent lookahead bias.",
  },
};

/** TopBar title + subtitle per workspace. */
const VIEW_META: Record<View, { title: string; subtitle: string }> = {
  home: {
    title: "Home",
    subtitle:
      "Research, backtest, optimize, and report trading strategies from one local dashboard.",
  },
  globe: {
    title: "Global Markets Globe",
    subtitle:
      "Explore 15 country dossiers with a static illustrative core and optional US FRED macro enrichment — not real-time market data or investment advice.",
  },
  backtest: {
    title: "Backtest",
    subtitle: "Run a single strategy on real historical market data.",
  },
  library: {
    title: "Strategy Library",
    subtitle:
      "What each strategy tests, when it fails, and how to validate it — research notes, not advice.",
  },
  replications: {
    title: "Paper Replications",
    subtitle:
      "Classic quant papers explained, with honest simplified demos — not full academic replications.",
  },
  disasters: {
    title: "Quant Disasters",
    subtitle:
      "How quant strategies fail — simplified risk-education case studies, not forensic investigations.",
  },
  options: {
    title: "Options Lab",
    subtitle:
      "European Black–Scholes pricing, Greeks, implied vol, and payoff diagrams — a deterministic educational calculator.",
  },
  events: {
    title: "Event Lab",
    subtitle:
      "Event-study abnormal returns (CAR/CAAR) and a simplified merger-arbitrage calculator — research diagnostic, no live filings.",
  },
  rates: {
    title: "Yield Curve Lab",
    subtitle:
      "Zero rates, discount factors, forward rates, curve shocks, and basic bond duration / convexity — synthetic curves, no live rates feed.",
  },
  fx: {
    title: "FX Lab",
    subtitle:
      "Spot/forward via interest rate parity, FX carry, PPP deviation, currency exposure, and Garman-Kohlhagen FX options — no live FX rates, not investment advice.",
  },
  credit: {
    title: "Credit Risk Lab",
    subtitle:
      "Merton structural credit, distance to default, hazard rates and survival curves, CDS spread approximation, and risky bond pricing — no live CDS data, not investment advice.",
  },
  risklab: {
    title: "Portfolio Risk Lab",
    subtitle:
      "Portfolio return, volatility, Sharpe, covariance/correlation, marginal & component risk contributions, historical VaR/CVaR, stress P&L, efficient frontier, min-variance and risk-parity portfolios — deterministic static sample data, not investment advice.",
  },
  realestate: {
    title: "Real Estate Lab",
    subtitle:
      "Income-property NOI, cap rate, valuation, mortgage amortization, LTV/DSCR, cash-on-cash, IRR, equity multiple, rent/vacancy/cap/rate stress scenarios, and a simple REIT NAV discount/premium — deterministic static sample data, not investment, tax, legal, or lending advice.",
  },
  futures: {
    title: "Futures & Commodities Lab",
    subtitle:
      "Cost-of-carry futures pricing, implied convenience yield, futures-curve shape (contango/backwardation/mixed), roll yield, calendar spreads, contract notional / margin / leverage P&L, and commodity scenario stress — deterministic static sample data, not investment or trading advice.",
  },
  volatility: {
    title: "Volatility Surface & Variance Swap Lab",
    subtitle:
      "Implied-vol inversion, volatility smile / skew / term structure, a 2-D volatility surface, realized-vol comparison, a simplified variance-swap fair strike, vega exposure, and volatility scenario stress — deterministic static sample data, not official VIX methodology, not investment or trading advice.",
  },
  microstructure: {
    title: "Market Microstructure & Execution Lab",
    subtitle:
      "Limit order-book summary (spread, depth ladder, imbalance, microprice), trade-tape VWAP/TWAP/imbalance, execution implementation shortfall, slippage, participation, a square-root market-impact approximation, an execution-schedule comparison, and liquidity stress scenarios — deterministic static sample data, no live order books, not investment, trading, or order-routing advice.",
  },
  cryptoderivatives: {
    title: "Crypto Perpetual Funding & Basis Lab",
    subtitle:
      "Spot / perpetual / dated-futures basis, funding-rate mechanics and annualized funding yield, long/short funding P&L, a cash-and-carry example, position margin / liquidation approximation, a funding-regime read, and funding/basis stress scenarios with interactive shock sliders, a basis curve, and funding/liquidation stress charts — deterministic static sample data, no live exchange data or crypto prices, not investment, trading, or liquidation advice.",
  },
  defirisk: {
    title: "DeFi Yield, Stablecoin Peg & Lending Risk Lab",
    subtitle:
      "Stablecoin peg deviation, lending/borrow APY with a kinked utilization rate model, collateral value / debt / LTV / health factor, an approximate liquidation price, net APY carry, a risk-regime read, and protocol stress scenarios with interactive shock sliders, a rate-curve chart, and health-factor/peg/net-APY stress charts — deterministic static sample data, no live protocol data or crypto prices, no wallets or smart-contract calls, not investment, lending, borrowing, or liquidation advice.",
  },
  tokenomics: {
    title: "Tokenomics, Unlock Schedule & Treasury Risk Lab",
    subtitle:
      "Market cap vs FDV, float ratio, unlock schedules and dilution pressure, emission inflation and a real staking-yield approximation, treasury runway, holder concentration, a tokenomics risk-regime read, and unlock/treasury stress scenarios with interactive shock sliders, an unlock-horizon selector, and unlock/runway/FDV/concentration charts — deterministic static sample data, no live token prices or on-chain data, no wallets or smart-contract calls, not investment, trading, token, or venture advice.",
  },
  onchain: {
    title: "On-Chain Flow, Exchange Reserve & Whale Concentration Lab",
    subtitle:
      "Exchange inflows/outflows and reserve ratios, active addresses, transfer volume, token velocity, an NVT-style valuation ratio, holder cohorts with a Gini-style concentration approximation, whale flows, an on-chain risk-regime read, and on-chain stress scenarios with interactive shock sliders plus flow, cohort, reserve, NVT, and velocity charts — deterministic static sample data, no live on-chain data or token prices, no wallets, RPC, or explorer APIs, not investment, trading, or token advice.",
  },
  altdata: {
    title: "Alternative Data, News Sentiment & Signal Decay Lab",
    subtitle:
      "Sample news/social/earnings/macro/supply-chain events with weighted sentiment, novelty, freshness decay, a leakage guard, event-study horizons, information coefficient, hit rate, a signal-decay curve, an alpha composite, a research risk-regime read, and scenario stresses with interactive shock sliders, a return-horizon selector, and timeline/decay/IC charts — deterministic static sample data, no live news or social media, no scraping, no LLM or provider APIs, not investment, trading, or signal advice.",
  },
  macroregime: {
    title: "Macro Regime & Cross-Asset Allocation Lab",
    subtitle:
      "Indicator z-scores and growth / inflation / policy / liquidity / credit / USD category scores, a composite macro regime read, regime-adjusted cross-asset assumptions, inverse-volatility / risk-parity-style / regime-tilted educational allocations with risk contributions, and macro stress scenarios — deterministic static sample data, no live macro or market data, not investment, trading, or asset-allocation advice.",
  },
  scenariostudio: {
    title: "Unified Scenario Studio & Report Builder",
    subtitle:
      "Deterministic scenario templates and global shock controls mapped through documented cross-lab impact scores — module impact charts, a scenario heatmap, baseline-vs-stress comparisons, a severity gauge, a regime read, and a copy-friendly educational report builder across macro, portfolio, crypto derivatives, DeFi, tokenomics, on-chain, alternative data, and microstructure — static sample data, no live data, not investment, trading, or asset-allocation advice, not a production risk report.",
  },
  democenter: {
    title: "Product Demo Center & Guided Walkthroughs",
    subtitle:
      "Guided product walkthroughs with audience and time-budget controls, a 21-module health dashboard with status and data-mode badges, a capability matrix, readiness/coverage/complexity scores, and a copy-friendly audience-tailored demo script builder (Markdown + JSON) — hand-written static demo metadata, no telemetry, no live data, not investment, trading, or compliance advice, and no module is a production trading system.",
  },
  portfolioshowcase: {
    title: "QuantLab Portfolio Showcase",
    subtitle:
      "The public-presentation view: what the platform demonstrates (full-stack quant research platform, interactive labs, deterministic demo data, scenario/report workflow, reliability & QA readiness), the suggested demo path with deep links, grouped project highlights, copyable one-sentence/recruiter/quant/technical pitches, and the standing safety panel — static presentation copy, educational only, not investment or trading advice, not a live trading system, not production compliance infrastructure.",
  },
  developeronboarding: {
    title: "Local Demo & Developer Onboarding",
    subtitle:
      "Everything needed to run, verify, and demo QuantLab locally: the environment checklist (mirroring the read-only scripts\\check_environment.ps1 doctor), copyable backend/tests/typecheck/dev/build/git commands (all run by the user — this page never runs anything), common troubleshooting fixes, and the suggested demo route with deep links — static reference copy, deterministic sample data, no live trading, not investment advice, not production compliance infrastructure.",
  },
  qacommandcenter: {
    title: "Release Readiness & QA Command Center",
    subtitle:
      "A hand-maintained 21-module QA registry with release-status and priority labels, ready/smoke/test-proxy/interactivity/chart coverage rates and the release score Q = 100(0.30R+0.20S+0.20T+0.15I+0.15C), a rule-based release decision, the per-module smoke-test matrix, a grouped manual regression checklist, the exact local verification commands (listed with copy buttons — never executed here), a known-limitations tracker, and copy-friendly release notes (Markdown + JSON) — static QA metadata, it never claims tests or builds were run, not a compliance system, not investment or trading advice.",
  },
  datareliability: {
    title: "Data Mode Registry & API Reliability Center",
    subtitle:
      "A hand-maintained registry of module data modes (static sample / user input / local calculation / optional external provider), the provider registry (optional yfinance/FRED/delayed-quote paths are disabled by default, fail closed, and are never relied on in tests), the offline fixture registry (including the KO/PEP pairs demo fallback), documented demo-safe/test-safe/fallback/exposure rates with a reliability score, and a copy-friendly Markdown/JSON reliability report — static reliability metadata, never a provider call, no availability guarantee, not investment, trading, or compliance advice, not a data governance system.",
  },
  researchworkspace: {
    title: "Research Workspace & Experiment Journal",
    subtitle:
      "Organize deterministic sample lab runs into saved research presets — stage runs, compare baseline vs stressed reads with change and guarded percentage-change formulas, inspect severity/coverage/reproducibility scores, a workflow timeline, and a methodology checklist, write experiment notes, and export copy-friendly Markdown or JSON summaries (optional browser-local drafts, no accounts, no cloud) — static sample data, no live data, not investment, trading, or asset-allocation advice, not production research or compliance records.",
  },
  scanner: {
    title: "Cross-Sectional Scanner",
    subtitle:
      "A second engine: rank a synthetic universe, form dollar-neutral long/short baskets, and run a lookahead-safe portfolio backtest — synthetic universe, no live market data, not investment advice.",
  },
  finml: {
    title: "AFML Methodology Lab",
    subtitle:
      "Leakage-aware financial-ML labeling: CUSUM event sampling, triple-barrier labels, sample concurrency, and uniqueness weights — synthetic demo data, not a trained model, not investment advice.",
  },
  csv: {
    title: "CSV Backtest",
    subtitle: "Upload your own price history and run a single-asset strategy.",
  },
  builder: {
    title: "Strategy Builder",
    subtitle: "Compose a long-only strategy from indicator rules — no code.",
  },
  portfolio: {
    title: "Portfolio Backtest",
    subtitle: "Equal-weight multi-asset portfolio with optional rebalancing.",
  },
  sweep: {
    title: "Parameter Sweep",
    subtitle: "Grid-search SMA fast/slow window combinations.",
  },
  "train-test": {
    title: "Train/Test Validation",
    subtitle: "In-sample parameter selection, out-of-sample evaluation.",
  },
  "walk-forward": {
    title: "Walk-Forward Optimization",
    subtitle: "Rolling re-optimisation with stitched out-of-sample equity.",
  },
  comparison: {
    title: "Strategy Comparison",
    subtitle: "Five single-asset strategies, one ticker, side by side.",
  },
  saved: {
    title: "Saved Backtests",
    subtitle: "Locally persisted results, stored in SQLite.",
  },
  reports: {
    title: "Saved Reports",
    subtitle: "Research reports saved locally in SQLite — view, download, print.",
  },
  settings: {
    title: "Settings",
    subtitle: "Local preferences for defaults, conventions, theme, and reports.",
  },
};

// ---------------------------------------------------------------------------
// Section heading inside content
// ---------------------------------------------------------------------------

function SectionIntro({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
      <p className="mt-1 text-sm text-slate-500 max-w-2xl">{children}</p>
    </div>
  );
}

// Extra search aliases for the per-country dossier palette commands, so common
// abbreviations ("US", "UK", "Japan") and short codes resolve the right market.
const GLOBE_MARKET_ALIASES: Record<string, string> = {
  us: "US USA U.S. America United States",
  ca: "CA Canada",
  uk: "UK U.K. Britain Great Britain United Kingdom",
  de: "DE Germany Deutschland",
  fr: "FR France",
  ch: "CH Switzerland Swiss",
  jp: "JP Japan Nippon",
  cn: "CN China Mainland",
  hk: "HK Hong Kong",
  tw: "TW Taiwan",
  kr: "KR Korea South Korea",
  in: "IN India",
  sg: "SG Singapore",
  au: "AU Australia",
  br: "BR Brazil Brasil",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [view, setView] = useState<View>("home");

  // Guided-demo banner ("Demo parameters loaded. Click Run to execute.") and
  // the portfolio sub-tab a demo should open on.  `portfolioKey` is bumped to
  // remount PortfolioWorkspace so a demo lands on the right tab even if the
  // user is already in the Portfolio Lab.
  const [demoNotice, setDemoNotice] = useState<string | null>(null);
  const [portfolioTab, setPortfolioTab] = useState<PortfolioTab>("backtest");
  const [portfolioKey, setPortfolioKey] = useState(0);
  const [builderDemoTemplateId, setBuilderDemoTemplateId] = useState<string | null>(
    null,
  );
  const [builderSavedTemplateId, setBuilderSavedTemplateId] = useState<
    number | null
  >(null);
  const [builderKey, setBuilderKey] = useState(0);

  // Saved backtests state
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [savedRefreshKey, setSavedRefreshKey] = useState(0);
  const [savedDetailId, setSavedDetailId] = useState<number | null>(null);
  // Strategy Library: which model page is open (null = index); key remounts.
  const [librarySlug, setLibrarySlug] = useState<string | null>(null);
  const [libraryKey, setLibraryKey] = useState(0);
  // Paper Replications: same pattern.
  const [paperSlug, setPaperSlug] = useState<string | null>(null);
  const [paperKey, setPaperKey] = useState(0);
  // Quant Disasters: same pattern.
  const [disasterSlug, setDisasterSlug] = useState<string | null>(null);
  const [disasterKey, setDisasterKey] = useState(0);
  // Options Lab: which tab to open on (deep-linked from the palette).
  const [optionsTab, setOptionsTab] = useState<
    | "pricing"
    | "implied_vol"
    | "payoff"
    | "tree"
    | "monte_carlo"
    | "surface"
    | "heston"
    | "compare"
    | "education"
  >("pricing");
  const [optionsKey, setOptionsKey] = useState(0);
  // Scenario preset to seed the Options Lab with on (re)mount (palette deep-link).
  const [optionsPreset, setOptionsPreset] = useState<string | null>(null);
  // Event Lab: which tab to open on (deep-linked from the palette).
  const [eventsTab, setEventsTab] = useState<"study" | "multi" | "merger" | "education">(
    "study",
  );
  const [eventsKey, setEventsKey] = useState(0);
  // Yield Curve Lab: which tab to open on (deep-linked from the palette).
  const [ratesTab, setRatesTab] = useState<"builder" | "shocks" | "bond" | "shortrate" | "education">(
    "builder",
  );
  const [ratesKey, setRatesKey] = useState(0);

  // FX Lab: which tab to open on (deep-linked from the palette).
  const [fxTab, setFxTab] = useState<"forward" | "carry" | "ppp" | "exposure" | "options" | "education">(
    "forward",
  );
  const [fxKey, setFxKey] = useState(0);

  // Credit Risk Lab: which tab to open on (deep-linked from the palette).
  const [creditTab, setCreditTab] = useState<"merton" | "hazard" | "cds" | "bond" | "education">(
    "merton",
  );
  const [creditKey, setCreditKey] = useState(0);

  // Cross-Sectional Scanner: which strategy to seed (deep-linked from the palette).
  const [scannerStrategy, setScannerStrategy] =
    useState<"cross_sectional_reversal" | "cross_sectional_momentum">("cross_sectional_reversal");
  const [scannerKey, setScannerKey] = useState(0);

  // AFML Methodology Lab: which tab to open on (deep-linked from the palette).
  const [finmlTab, setFinmlTab] = useState<"cusum" | "labeling" | "uniqueness" | "purgedcv" | "seqboot" | "fracdiff" | "education">("cusum");
  const [finmlKey, setFinmlKey] = useState(0);

  // Global Markets Globe: which market to preselect (deep-linked from palette),
  // plus optional guided-tour id and presentation-mode flag (Phase 20.7).
  const [globeMarketId, setGlobeMarketId] = useState<string | null>(null);
  const [globeTour, setGlobeTour] = useState<string | null>(null);
  const [globePresentation, setGlobePresentation] = useState(false);
  const [globeKey, setGlobeKey] = useState(0);

  // Saved reports (Report Gallery) state
  const [savedReportsRefreshKey, setSavedReportsRefreshKey] = useState(0);
  const [savedReportDetailId, setSavedReportDetailId] = useState<number | null>(
    null,
  );

  // Backtest state
  const [strategy, setStrategy] = useState<StrategyType>("sma_crossover");
  const [smaParams, setSmaParams] = useState<BacktestRequest>(DEFAULT_SMA_PARAMS);
  const [rsiParams, setRsiParams] = useState<RsiBacktestRequest>(DEFAULT_RSI_PARAMS);
  const [bbParams, setBbParams] = useState<BbBacktestRequest>(DEFAULT_BB_PARAMS);
  const [momentumParams, setMomentumParams] = useState<MomentumBacktestRequest>(
    DEFAULT_MOMENTUM_PARAMS,
  );
  const [vbParams, setVbParams] = useState<VbBacktestRequest>(DEFAULT_VB_PARAMS);
  const [pairsParams, setPairsParams] = useState<PairsBacktestRequest>(
    DEFAULT_PAIRS_PARAMS,
  );
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Bumping this key remounts BacktestForm so its internal numeric string
  // states re-derive from the (settings-prefilled) param props.
  const [formKey, setFormKey] = useState(0);

  // Apply local settings once on startup: set the theme accent and prefill the
  // single-backtest forms' common fields (capital, cost, date range).  Runs in
  // an effect (client-only, post-hydration) so it never causes an SSR mismatch,
  // and only on mount so it never overrides edits the user makes afterwards.
  useEffect(() => {
    const s = loadSettings();
    applyAccent(s.accent_color);
    const { start_date, end_date } = resolveDateRange(s);
    const commonBase = {
      initial_capital: s.default_initial_capital,
      transaction_cost_bps: s.default_transaction_cost_bps,
      cost_model: {
        type: "simple_bps" as const,
        transaction_cost_bps: s.default_transaction_cost_bps,
      },
      start_date,
      end_date,
    };
    const commonSingleAsset = {
      ...commonBase,
      annualization_mode: s.annualization_convention,
    };
    setSmaParams((p) => ({ ...p, ...commonSingleAsset }));
    setRsiParams((p) => ({ ...p, ...commonSingleAsset }));
    setBbParams((p) => ({ ...p, ...commonSingleAsset }));
    setMomentumParams((p) => ({ ...p, ...commonSingleAsset }));
    setVbParams((p) => ({ ...p, ...commonSingleAsset }));
    setPairsParams((p) => ({ ...p, ...commonBase }));
    setFormKey((k) => k + 1);
  }, []);

  // Globe permalinks: deep-link entry + browser back/forward.
  //  - On first load, if the URL is a globe permalink (/?view=globe&market=…,
  //    or /globe?market=… which redirects here), open the globe with that
  //    market. An unknown id is handled by the panel (default + notice).
  //  - On popstate, re-derive the workspace from the URL so the dossier (or
  //    leaving the globe) always matches the address bar — no stale selection.
  useEffect(() => {
    const entry = readGlobeParams();
    if (entry.isGlobe) {
      openGlobe(entry.market, {
        tour: entry.tour,
        presentation: entry.presentation,
        push: false,
      });
    }

    function onPopState() {
      const here = readGlobeParams();
      if (here.isGlobe) {
        setSavedDetailId(null);
        setSavedReportDetailId(null);
        setDemoNotice(null);
        setGlobeMarketId(here.market);
        setGlobeTour(here.tour);
        setGlobePresentation(here.presentation);
        setGlobeKey((k) => k + 1);
        setView("globe");
      } else {
        setGlobeMarketId(null);
        setGlobeTour(null);
        setGlobePresentation(false);
        setView("home");
      }
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRun() {
    if (loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setShowSaveForm(false);

    try {
      const data =
        strategy === "sma_crossover"
          ? await runBacktest(smaParams)
          : strategy === "rsi_mean_reversion"
            ? await runRsiBacktest(rsiParams)
            : strategy === "bollinger_band"
              ? await runBbBacktest(bbParams)
              : strategy === "momentum"
                ? await runMomentumBacktest(momentumParams)
                : strategy === "volatility_breakout"
                  ? await runVbBacktest(vbParams)
                  : await runPairsBacktest(pairsParams);
      setResult(data);
      setDemoNotice(null); // a real run replaces the "click Run" hint
      markChecklistStep("ran_backtest");
    } catch (err) {
      const cls = classifyApiError(err);
      setError(cls.message);
      if (cls.backendUnavailable) notifyBackendOffline();
    } finally {
      setLoading(false);
    }
  }

  function handleNav(next: View) {
    const leavingGlobe = view === "globe" && next !== "globe";
    setView(next);
    setDemoNotice(null);
    setBuilderDemoTemplateId(null);
    if (next !== "saved") setSavedDetailId(null);
    if (next !== "reports") setSavedReportDetailId(null);
    // Sidebar navigation always lands on the library index (palette commands
    // deep-open a specific model page instead).
    setLibrarySlug(null);
    setLibraryKey((k) => k + 1);
    setPaperSlug(null);
    setPaperKey((k) => k + 1);
    setDisasterSlug(null);
    setDisasterKey((k) => k + 1);
    // Sidebar / nav-command entry to the globe always opens with no market
    // preselected (palette market commands deep-select via openGlobe instead).
    // Keep the address bar in sync so the globe is shareable and back/forward
    // works: entering pushes ?view=globe; leaving clears the globe query.
    if (next === "globe") {
      setGlobeMarketId(null);
      setGlobeTour(null);
      setGlobePresentation(false);
      setGlobeKey((k) => k + 1);
      writeGlobeUrl({ market: null }, "push");
    } else if (leavingGlobe) {
      clearGlobeUrl("push");
    }
  }

  /**
   * Open the Global Markets Globe, optionally preselecting a market dossier and
   * starting a guided tour / presentation mode (Phase 20.7).
   * `push` (default) records a history entry so the state is shareable and
   * back/forward works; the initial deep-link entry passes `push: false` since
   * the loaded URL is already the current history entry (the panel normalises
   * it on mount). When a tour is requested the panel resolves the actual market
   * (first step or the matching step) and normalises the URL on mount.
   */
  function openGlobe(
    marketId: string | null,
    opts: { tour?: string | null; presentation?: boolean; push?: boolean } = {},
  ) {
    const tour = opts.tour ?? null;
    const presentation = opts.presentation ?? false;
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setDemoNotice(null);
    setGlobeMarketId(marketId);
    setGlobeTour(tour);
    setGlobePresentation(presentation);
    setGlobeKey((k) => k + 1);
    setView("globe");
    if (opts.push ?? true) {
      writeGlobeUrl({ market: marketId, tour, presentation }, "push");
    }
  }

  /** Open the Strategy Library on a specific model page (command palette). */
  function openLibraryPage(slug: string | null) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setLibrarySlug(slug);
    setLibraryKey((k) => k + 1);
    setView("library");
  }

  /** Open Paper Replications on a specific paper page. */
  function openPaperPage(slug: string | null) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setPaperSlug(slug);
    setPaperKey((k) => k + 1);
    setView("replications");
  }

  /** Open Quant Disasters on a specific case study. */
  function openDisasterPage(slug: string | null) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setDisasterSlug(slug);
    setDisasterKey((k) => k + 1);
    setView("disasters");
  }

  /**
   * Launch a paper-inspired preset: preselect the strategy, load its demo
   * defaults (with the preset's ticker), and navigate.  Never auto-runs and
   * never claims full replication — the notice says "inspired demo".
   */
  function handleRunPaperPreset(preset: PaperRunPreset, paper: PaperEntry) {
    handleRunFromLibrary(preset.strategyId);
    if (preset.ticker) {
      if (preset.strategyId === "momentum") {
        setMomentumParams({ ...DEFAULT_MOMENTUM_PARAMS, ticker: preset.ticker });
      } else if (preset.strategyId === "sma_crossover") {
        setSmaParams({ ...DEFAULT_SMA_PARAMS, ticker: preset.ticker });
      }
    }
    setDemoNotice(
      `Paper-inspired preset loaded (${paper.authors} ${paper.year}). This is a ` +
        "simplified educational demo, not a full replication. Click Run to execute.",
    );
  }

  /**
   * "Run in Backtest Studio" from the Strategy Library: preselect the strategy,
   * load its demo defaults, and navigate.  Never auto-runs, never fabricates
   * results, and leaves global preferences (cost defaults, annualization,
   * theme) untouched.
   */
  function handleRunFromLibrary(id: StrategyType) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setStrategy(id);
    if (id === "sma_crossover") setSmaParams(DEFAULT_SMA_PARAMS);
    else if (id === "rsi_mean_reversion") setRsiParams(DEFAULT_RSI_PARAMS);
    else if (id === "bollinger_band") setBbParams(DEFAULT_BB_PARAMS);
    else if (id === "momentum") setMomentumParams(DEFAULT_MOMENTUM_PARAMS);
    else if (id === "volatility_breakout") setVbParams(DEFAULT_VB_PARAMS);
    else if (id === "pairs") setPairsParams(DEFAULT_PAIRS_PARAMS);
    setResult(null);
    setError(null);
    setFormKey((k) => k + 1);
    setDemoNotice(
      "Strategy loaded from the Strategy Library with default parameters. Click Run to execute.",
    );
    setView("backtest");
  }

  /**
   * Load a guided-demo preset: navigate to the right workspace and prefill the
   * form.  Never auto-runs — the real backend call only happens when the user
   * clicks Run.  No results are fabricated.
   */
  function handleDemo(id: DemoPresetId) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    switch (id) {
      case "sma_backtest":
        setStrategy("sma_crossover");
        setSmaParams(DEFAULT_SMA_PARAMS);
        setResult(null);
        setError(null);
        setFormKey((k) => k + 1);
        setDemoNotice(
          "Demo parameters loaded (SPY · SMA Crossover 20/100 · 2015–2023). Click Run to execute.",
        );
        setView("backtest");
        break;
      case "crypto_momentum":
        setStrategy("momentum");
        setSmaParams((p) => ({ ...p, annualization_mode: "auto" }));
        setMomentumParams(DEMO_CRYPTO_MOMENTUM_PARAMS);
        setResult(null);
        setError(null);
        setFormKey((k) => k + 1);
        setDemoNotice(
          "Demo parameters loaded (BTC-USD · Time-Series Momentum · 2015–2023). Click Run to execute.",
        );
        setView("backtest");
        break;
      case "portfolio_risk":
        setPortfolioTab("risk");
        setPortfolioKey((k) => k + 1);
        setDemoNotice(
          "Demo loaded: SPY, QQQ, GLD, TLT in the Risk Dashboard. Click Run to execute.",
        );
        setView("portfolio");
        break;
      case "efficient_frontier":
        setPortfolioTab("frontier");
        setPortfolioKey((k) => k + 1);
        setDemoNotice(
          "Demo loaded: efficient frontier for SPY, QQQ, GLD, TLT (2,000 portfolios). Click Run to execute.",
        );
        setView("portfolio");
        break;
      case "strategy_builder":
        setBuilderDemoTemplateId("sma-trend-filter");
        setBuilderSavedTemplateId(null);
        setBuilderKey((k) => k + 1);
        setDemoNotice(
          "Loading SMA Trend Filter demo template. When it appears below, click Run Strategy to execute.",
        );
        setView("builder");
        break;
    }
    toast.info("Demo parameters loaded", "Click Run to execute a real backtest.");
  }

  /** Open the Portfolio Lab on a specific sub-tab (shared by the palette). */
  function goToPortfolioTab(tab: PortfolioTab) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setDemoNotice(null);
    setPortfolioTab(tab);
    setPortfolioKey((k) => k + 1);
    setView("portfolio");
  }

  /** Download the current single-asset backtest as a Markdown report. */
  function exportCurrentReport() {
    if (!result) return;
    const tpl = loadSettings().default_report_template;
    const report = buildBacktestReport(result, {}, tpl);
    downloadTextFile(report.filename, report.content);
    markChecklistStep("exported_report");
  }

  /** Open a saved backtest's detail (shared by Home cards + palette search). */
  function openSavedBacktest(id: number) {
    setDemoNotice(null);
    setSavedReportDetailId(null);
    setSavedDetailId(id);
    setView("saved");
  }

  /** Open a saved report's detail (shared by Home cards + palette search). */
  function openSavedReport(id: number) {
    setDemoNotice(null);
    setSavedDetailId(null);
    setSavedReportDetailId(id);
    setView("reports");
  }

  /** Load a saved (My Templates) custom strategy into the builder. */
  function openSavedTemplate(id: number) {
    setBuilderSavedTemplateId(id);
    setBuilderDemoTemplateId(null);
    setBuilderKey((k) => k + 1);
    setDemoNotice(null);
    setView("builder");
  }

  /** Load a built-in gallery template into the builder. */
  function openGalleryTemplate(id: string) {
    setBuilderDemoTemplateId(id);
    setBuilderSavedTemplateId(null);
    setBuilderKey((k) => k + 1);
    setDemoNotice(null);
    setView("builder");
  }

  // Command palette entries — all reuse the same navigation / demo / portfolio
  // handlers as the sidebar and onboarding, so behaviour can never diverge.
  // Demo definitions come straight from DEMO_PRESETS (no duplication).
  const NAV_COMMANDS: { view: View; title: string; keywords: string }[] = [
    { view: "home", title: "Go to Home", keywords: "command center dashboard" },
    { view: "globe", title: "Open Global Markets Globe", keywords: "globe global markets world markets country macro fx indices market dossier united states japan taiwan germany india europe asia explore map 3d earth" },
    { view: "backtest", title: "Go to Backtest", keywords: "single asset run strategy" },
    { view: "library", title: "Open Strategy Library", keywords: "models catalog docs education strategy pages" },
    { view: "replications", title: "Open Paper Replications", keywords: "papers research academic momentum pairs replication" },
    { view: "disasters", title: "Open Quant Disasters", keywords: "risk education failures ltcm crash blowup lessons" },
    { view: "options", title: "Open Options Lab", keywords: "options black-scholes greeks implied volatility payoff straddle strangle covered call protective put" },
    { view: "events", title: "Open Event Lab", keywords: "event study abnormal return car caar merger arbitrage deal spread event-driven earnings event" },
    { view: "rates", title: "Open Yield Curve Lab", keywords: "yield curve rates zero rate discount factor forward rate duration convexity dv01 bond pricing fixed income short rate vasicek cir mean reversion" },
    { view: "fx", title: "Open FX Lab", keywords: "fx foreign exchange currency forward rate interest rate parity carry ppp purchasing power parity exposure garman kohlhagen fx option" },
    { view: "credit", title: "Open Credit Risk Lab", keywords: "credit credit risk merton structural model distance to default default probability hazard rate survival curve cds credit spread risky bond recovery rate" },
    { view: "scanner", title: "Open Cross-Sectional Scanner", keywords: "scanner cross-sectional rank long short universe equity scanner factor ranking mean reversion momentum dollar neutral scanner lab second engine" },
    { view: "finml", title: "Open AFML Methodology Lab", keywords: "afml financial ml machine learning triple barrier cusum event sampling sample uniqueness concurrency labeling meta-labeling purged k-fold embargo cross validation leakage label overlap sequential bootstrap fractional differentiation fracdiff stationarity cpcv lopez de prado" },
    { view: "risklab", title: "Open Portfolio Risk Lab", keywords: "portfolio risk lab analytics expected return volatility sharpe covariance correlation marginal component risk contribution value at risk var cvar expected shortfall stress scenario efficient frontier minimum variance risk parity allocation weights" },
    { view: "realestate", title: "Open Real Estate Lab", keywords: "real estate property reit noi net operating income cap rate valuation mortgage amortization ltv loan to value dscr debt service coverage cash on cash irr equity multiple rent vacancy stress nav premium discount ffo dividend yield" },
    { view: "futures", title: "Open Futures and Commodities Lab", keywords: "futures commodities commodity cost of carry convenience yield contango backwardation curve roll yield calendar spread margin leverage notional crude oil gold natural gas wheat basis scenario stress" },
    { view: "volatility", title: "Open Volatility Lab", keywords: "volatility surface variance swap implied vol iv smile skew term structure realized vol vega black scholes option chain fair strike vix scenario stress derivatives" },
    { view: "microstructure", title: "Open Market Microstructure Lab", keywords: "microstructure execution order book limit order book bid ask spread depth imbalance microprice vwap twap implementation shortfall slippage market impact participation rate liquidity stress execution schedule transaction cost analysis tca" },
    { view: "cryptoderivatives", title: "Open Crypto Derivatives Lab", keywords: "crypto derivatives perpetual perp futures funding rate basis annualized carry cash and carry liquidation margin leverage btc eth sol bitcoin ethereum solana contango backwardation funding pnl interactive shock slider basis curve chart" },
    { view: "defirisk", title: "Open DeFi Risk Lab", keywords: "defi decentralized finance stablecoin peg depeg lending borrow apy utilization kink interest rate model collateral health factor ltv loan to value liquidation threshold net apy carry usdc usdt dai aave protocol stress interactive shock slider rate curve chart" },
    { view: "tokenomics", title: "Open Tokenomics Risk Lab", keywords: "tokenomics token unlock schedule vesting cliff dilution fdv fully diluted valuation market cap float ratio emission inflation staking real yield treasury runway burn holder concentration crypto fundamentals interactive shock slider horizon chart" },
    { view: "onchain", title: "Open On-Chain Analytics Lab", keywords: "on-chain onchain exchange inflow outflow net flow exchange reserve active addresses transfer volume transaction count token velocity nvt whale concentration gini holder cohort crypto analytics interactive shock slider flow chart" },
    { view: "altdata", title: "Open Alternative Data Lab", keywords: "alternative data alt data news sentiment social sentiment earnings macro supply chain events novelty freshness leakage guard information coefficient ic hit rate signal decay alpha score event study interactive shock slider timeline decay chart" },
    { view: "macroregime", title: "Open Macro Regime Lab", keywords: "macro regime cross asset allocation growth inflation policy liquidity credit stress usd pressure z-score goldilocks stagflation recession risk parity inverse volatility regime tilt" },
    { view: "scenariostudio", title: "Open Scenario Studio", keywords: "scenario studio unified cross lab report builder stress template soft landing inflation growth shock liquidity crunch credit crypto risk off depeg inflow panic severe combo impact score heatmap severity regime markdown report" },
    { view: "researchworkspace", title: "Open Research Workspace", keywords: "research workspace experiment journal saved presets run comparison baseline stressed severity coverage reproducibility methodology checklist workflow timeline notes markdown json export local drafts" },
    { view: "democenter", title: "Open Demo Center", keywords: "demo center product walkthrough guided tour showcase presentation module health capability matrix readiness demo script builder audience founder investor recruiter portfolio" },
    { view: "datareliability", title: "Open Data Reliability Center", keywords: "data reliability center data mode registry offline fixtures provider registry yfinance fred test safety deterministic fallback external exposure reliability score" },
    { view: "qacommandcenter", title: "Open QA Command Center", keywords: "qa command center release readiness smoke test matrix regression checklist release notes commands pytest typecheck build known limitations release decision" },
    { view: "portfolioshowcase", title: "Open Portfolio Showcase", keywords: "portfolio showcase public presentation pitch recruiter quant technical demo path highlights launch pack resume interview linkedin" },
    { view: "developeronboarding", title: "Open Developer Onboarding", keywords: "developer onboarding local demo launcher environment doctor commands troubleshooting venv uvicorn pytest typecheck npm setup" },
    { view: "csv", title: "Go to CSV Upload", keywords: "import upload data file" },
    { view: "builder", title: "Go to Custom Strategy Builder", keywords: "no code rules indicator" },
    { view: "portfolio", title: "Go to Portfolio Lab", keywords: "multi asset weights" },
    { view: "sweep", title: "Go to Research Tools", keywords: "sweep validation optimization research" },
    { view: "sweep", title: "Go to Parameter Sweep", keywords: "grid search sma fast slow" },
    { view: "train-test", title: "Go to Train/Test Validation", keywords: "in sample out of sample" },
    { view: "walk-forward", title: "Go to Walk-Forward Optimization", keywords: "rolling reoptimization" },
    { view: "comparison", title: "Go to Strategy Comparison", keywords: "compare strategies side by side" },
    { view: "saved", title: "Go to Saved Backtests", keywords: "history persisted sqlite" },
    { view: "reports", title: "Go to Saved Reports", keywords: "report gallery markdown" },
    { view: "settings", title: "Go to Settings", keywords: "preferences theme defaults" },
  ];

  const PORTFOLIO_COMMANDS: { tab: PortfolioTab; title: string; keywords: string }[] = [
    { tab: "backtest", title: "Open Portfolio Backtest", keywords: "equal weight rebalance" },
    { tab: "optimize", title: "Open Portfolio Optimization", keywords: "min volatility max sharpe weights" },
    { tab: "walk-forward", title: "Open Walk-Forward Portfolio Optimization", keywords: "rolling" },
    { tab: "frontier", title: "Open Efficient Frontier", keywords: "mean variance random portfolios" },
    { tab: "risk", title: "Open Risk Dashboard", keywords: "var drawdown correlation" },
    { tab: "stress", title: "Open Stress Test", keywords: "scenario crash shock" },
    { tab: "factor", title: "Open Factor Analysis", keywords: "regression exposure beta" },
  ];

  const DEMO_COMMAND_TITLES: Record<DemoPresetId, string> = {
    sma_backtest: "Load Demo Backtest",
    crypto_momentum: "Load Crypto Momentum Demo",
    portfolio_risk: "Load Portfolio Risk Demo",
    efficient_frontier: "Load Efficient Frontier Demo",
    strategy_builder: "Load Strategy Builder Demo",
  };

  const commands: Command[] = [
    ...NAV_COMMANDS.map((c) => ({
      id: `nav-${c.title}`,
      group: "Navigation",
      title: c.title,
      keywords: c.keywords,
      run: () => handleNav(c.view),
    })),
    ...DEMO_PRESETS.map((p) => ({
      id: `demo-${p.id}`,
      group: "Guided demos",
      title: DEMO_COMMAND_TITLES[p.id],
      keywords: `demo preset ${p.detail}`,
      hint: "prefill",
      run: () => handleDemo(p.id),
    })),
    ...PORTFOLIO_COMMANDS.map((c) => ({
      id: `pf-${c.tab}`,
      group: "Portfolio tools",
      title: c.title,
      keywords: c.keywords,
      run: () => goToPortfolioTab(c.tab),
    })),
    ...MODEL_REGISTRY.map((m) => ({
      id: `library-${m.slug}`,
      group: "Strategy Library",
      title: `Open ${m.name} page`,
      keywords: `strategy library docs ${m.category} ${m.status} ${m.slug}`,
      run: () => openLibraryPage(m.slug),
    })),
    ...LIVE_MODELS.filter((m) => m.strategyId).map((m) => ({
      id: `library-run-${m.slug}`,
      group: "Strategy Library",
      title: `Run ${m.name} backtest`,
      keywords: `strategy library run backtest ${m.slug}`,
      hint: "prefill",
      run: () => handleRunFromLibrary(m.strategyId!),
    })),
    ...PAPER_REGISTRY.map((p) => ({
      id: `paper-${p.slug}`,
      group: "Paper Replications",
      title: `Open ${p.authors} (${p.year}) replication page`,
      keywords: `paper replication ${p.title} ${p.category} ${p.status} ${p.replicationLevel} ${p.slug}`,
      run: () => openPaperPage(p.slug),
    })),
    ...LIVE_PAPERS.filter((p) => p.runPreset).map((p) => ({
      id: `paper-run-${p.slug}`,
      group: "Paper Replications",
      title: `Run ${p.authors} (${p.year}) inspired demo`,
      keywords: `paper replication demo run ${p.slug}`,
      hint: "prefill",
      run: () => handleRunPaperPreset(p.runPreset!, p),
    })),
    ...DISASTER_REGISTRY.map((d) => ({
      id: `disaster-${d.slug}`,
      group: "Quant Disasters",
      title: `Open ${d.title} (${d.year}) case study`,
      keywords: `disaster risk lesson ${d.title} ${d.category} ${d.severity} ${d.slug}`,
      run: () => openDisasterPage(d.slug),
    })),
    {
      id: "workflow-robustness",
      group: "Trust Layer",
      title: "Open Robustness Lab workflow",
      keywords: "robustness bootstrap monte carlo resample uncertainty trust",
      hint: "backtest",
      run: () => handleNav("backtest"),
    },
    {
      id: "workflow-stability",
      group: "Trust Layer",
      title: "Open Stability Lab workflow",
      keywords: "stability sensitivity heatmap parameters sweep trust",
      hint: "backtest",
      run: () => handleNav("backtest"),
    },
    ...(
      [
        ["pricing", "pricing", "Open Black-Scholes Calculator", "options pricing greeks delta gamma vega theta rho"],
        ["implied_vol", "implied_vol", "Open Implied Volatility Solver", "options implied volatility iv solver"],
        ["payoff", "payoff", "Open Payoff Builder", "options payoff straddle strangle covered call protective put bull call bear put spread"],
        ["tree", "tree", "Open Options Tree Pricing", "options tree pricing binomial crr lattice american early exercise convergence"],
        ["tree", "tree-american", "Open American Option Calculator", "options american option early exercise put call binomial tree lattice"],
        ["tree", "tree-binomial", "Open Binomial Tree Pricing", "options binomial crr tree lattice convergence steps black-scholes"],
        ["monte_carlo", "monte-carlo", "Open Monte Carlo Options", "options monte carlo mc gbm path simulation standard error confidence interval"],
        ["monte_carlo", "monte-carlo-lab", "Open Options Monte Carlo Lab", "options monte carlo mc simulation stochastic paths variance reduction antithetic"],
        ["monte_carlo", "monte-carlo-asian", "Open Asian Option Pricing", "options asian option average price monte carlo path dependent exotic"],
        ["monte_carlo", "monte-carlo-barrier", "Open Barrier Option Pricing", "options barrier option knock out up and out down and out monte carlo exotic"],
        ["surface", "surface", "Open Volatility Surface", "options volatility surface vol surface implied volatility smile skew term structure moneyness svi"],
        ["surface", "surface-svi", "Open SVI Fit", "options svi volatility smile fit calibration research surface"],
        ["surface", "surface-vol", "Open Options Vol Surface", "options vol surface implied volatility iv heatmap moneyness expiry"],
        ["surface", "surface-smile", "Open IV Smile", "options iv smile volatility skew moneyness term structure surface"],
        ["heston", "heston", "Open Heston Model", "options heston stochastic volatility vol of vol kappa rho leverage effect variance process"],
        ["heston", "heston-stochvol", "Open Stochastic Volatility Lab", "options stochastic volatility heston vol of vol variance mean reversion leverage effect"],
        ["heston", "heston-pricing", "Open Heston Options Pricing", "options heston monte carlo stochastic volatility european call put pricing"],
        ["compare", "compare", "Open Model Comparison", "options compare models cross model black-scholes binomial monte carlo heston"],
      ] as const
    ).map(([t, id, title, keywords]) => ({
      id: `options-${id}`,
      group: "Options Lab",
      title,
      keywords,
      run: () => {
        setOptionsPreset(null);
        setOptionsTab(t);
        setOptionsKey((k) => k + 1);
        handleNav("options");
      },
    })),
    ...(
      [
        ["atm-equity-call", "Open Options Lab — ATM Equity Call preset"],
        ["american-put-early-exercise", "Open Options Lab — American Put preset"],
        ["asian-option-demo", "Open Options Lab — Asian Option preset"],
        ["negative-skew-heston", "Open Options Lab — Heston Leverage preset"],
        ["synthetic-vol-surface-demo", "Open Options Lab — Vol Surface preset"],
      ] as const
    ).map(([presetId, title]) => ({
      id: `options-preset-${presetId}`,
      group: "Options Lab",
      title,
      keywords: `options scenario preset demo ${presetId.replace(/-/g, " ")}`,
      hint: "prefill" as const,
      run: () => {
        setOptionsPreset(presetId);
        setOptionsKey((k) => k + 1);
        handleNav("options");
      },
    })),
    ...(
      [
        ["study", "Open Event Study", "event study abnormal return car benchmark adjusted earnings"],
        ["multi", "Open Multi-Event Study", "multi event study caar average abnormal return aar"],
        ["merger", "Open Merger Arb Calculator", "merger arbitrage deal spread breakeven probability annualized return"],
      ] as const
    ).map(([t, title, keywords]) => ({
      id: `events-${t}`,
      group: "Event Lab",
      title,
      keywords,
      run: () => {
        setEventsTab(t);
        setEventsKey((k) => k + 1);
        handleNav("events");
      },
    })),
    ...(
      [
        ["builder", "Open Rates Lab", "yield curve rates zero rate discount factor forward rate curve builder"],
        ["bond", "Open Bond Pricing", "bond pricing duration convexity dv01 yield to maturity coupon fixed income"],
        ["shocks", "Open Curve Shocks", "yield curve shocks parallel steepener flattener butterfly rates"],
        ["shortrate", "Open Short Rate Models", "short rate vasicek cir cox ingersoll ross mean reversion interest rate model zero coupon feller condition"],
        ["shortrate", "Open Vasicek Model", "vasicek short rate gaussian mean reversion interest rate model"],
        ["shortrate", "Open CIR Model", "cir cox ingersoll ross short rate square root mean reversion feller condition"],
      ] as const
    ).map(([t, title, keywords], i) => ({
      id: `rates-${t}-${i}`,
      group: "Yield Curve Lab",
      title,
      keywords,
      run: () => {
        setRatesTab(t);
        setRatesKey((k) => k + 1);
        handleNav("rates");
      },
    })),
    ...(
      [
        ["forward", "Open FX Forward Calculator", "fx forward interest rate parity irp spot currency foreign exchange"],
        ["carry", "Open FX Carry Calculator", "fx carry interest differential currency foreign exchange"],
        ["ppp", "Open PPP Calculator", "ppp purchasing power parity fx valuation deviation currency"],
        ["exposure", "Open Currency Exposure", "currency exposure fx stress base currency foreign exchange"],
        ["options", "Open FX Options", "fx option garman kohlhagen call put delta gamma vega currency"],
      ] as const
    ).map(([t, title, keywords], i) => ({
      id: `fx-${t}-${i}`,
      group: "FX Lab",
      title,
      keywords,
      run: () => {
        setFxTab(t);
        setFxKey((k) => k + 1);
        handleNav("fx");
      },
    })),
    ...(
      [
        ["merton", "Open Merton Model", "merton structural credit model distance to default default probability equity call"],
        ["hazard", "Open Hazard Rate Model", "hazard rate survival curve default probability reduced form credit intensity"],
        ["cds", "Open CDS Spread Calculator", "cds credit default swap spread protection leg premium leg credit"],
        ["bond", "Open Risky Bond Pricing", "risky bond defaultable bond credit spread recovery hazard pricing"],
      ] as const
    ).map(([t, title, keywords], i) => ({
      id: `credit-${t}-${i}`,
      group: "Credit Risk Lab",
      title,
      keywords,
      run: () => {
        setCreditTab(t);
        setCreditKey((k) => k + 1);
        handleNav("credit");
      },
    })),
    ...(
      [
        ["cross_sectional_reversal", "Open Scanner Lab", "scanner lab cross-sectional rank long short universe second engine"],
        ["cross_sectional_reversal", "Open Cross-Sectional Reversal Demo", "cross-sectional reversal mean reversion long short rank scanner demo"],
        ["cross_sectional_momentum", "Open Cross-Sectional Momentum Demo", "cross-sectional momentum long short rank scanner demo"],
      ] as const
    ).map(([s, title, keywords], i) => ({
      id: `scanner-${i}`,
      group: "Cross-Sectional Scanner",
      title,
      keywords,
      run: () => {
        setScannerStrategy(s);
        setScannerKey((k) => k + 1);
        handleNav("scanner");
      },
    })),
    ...(
      [
        ["cusum", "Open CUSUM Sampling", "cusum event sampling afml financial ml cumulative filter"],
        ["labeling", "Open Triple-Barrier Labeling", "triple barrier labeling afml profit take stop loss vertical label"],
        ["uniqueness", "Open Sample Uniqueness", "sample uniqueness concurrency overlapping labels afml sample weights"],
        ["purgedcv", "Open Purged K-Fold CV", "purged k-fold cross validation embargo leakage label overlap afml cpcv planned"],
        ["purgedcv", "Open Embargo CV", "embargo cross validation purged k-fold leakage afml financial ml cv"],
        ["seqboot", "Open Sequential Bootstrap", "sequential bootstrap afml sample uniqueness overlapping labels bootstrap concurrency financial ml sampling"],
        ["seqboot", "Open AFML Sequential Bootstrap", "sequential bootstrap uniqueness aware sampling afml random bootstrap comparison"],
        ["fracdiff", "Open Fractional Differentiation", "fractional differentiation fracdiff differencing stationarity memory retention time series preprocessing afml"],
        ["fracdiff", "Open AFML Fractional Differentiation", "fractional differencing fracdiff stationarity transform memory afml"],
      ] as const
    ).map(([t, title, keywords], i) => ({
      id: `finml-${t}-${i}`,
      group: "AFML Methodology Lab",
      title,
      keywords,
      run: () => {
        setFinmlTab(t);
        setFinmlKey((k) => k + 1);
        handleNav("finml");
      },
    })),
    ...(
      [
        ["Portfolio VaR and CVaR", "portfolio value at risk var cvar expected shortfall tail risk historical confidence level loss"],
        ["Risk Contribution Lab", "portfolio risk contribution marginal component percent risk budgeting concentration which assets drive risk"],
        ["Efficient Frontier Lab", "portfolio efficient frontier minimum variance risk parity mean variance optimization candidate portfolios"],
        ["Portfolio Factor Exposure", "portfolio factor exposure beta equity market size value momentum rates credit fx dollar commodity volatility loadings"],
        ["Portfolio Scenario Stress", "portfolio scenario stress test equity selloff rates shock usd squeeze commodity rally credit stress shock factor impact worst best asset"],
        ["Factor Risk Decomposition", "portfolio factor risk decomposition specific idiosyncratic risk contribution factor covariance variance share"],
        ["Portfolio Optimization Lab", "portfolio optimization mean variance constrained long only max sharpe min variance target return target volatility candidate search construction"],
        ["Black-Litterman Lab", "black litterman bl implied equilibrium returns posterior views prior tau risk aversion tilt blend"],
        ["Max Sharpe Portfolio", "max sharpe portfolio optimization tangency best risk adjusted return constrained long only"],
        ["Portfolio Rebalance Analysis", "portfolio rebalance turnover hypothetical delta weight change current target largest increase decrease"],
        ["Portfolio Monte Carlo Lab", "portfolio monte carlo simulation fixed seed paths terminal wealth distribution fan chart parametric gaussian probability of loss"],
        ["Portfolio Robustness Lab", "portfolio robustness assumption sensitivity scenarios return volatility correlation rate shifts sharpe stability optimization robustness"],
        ["Portfolio Drawdown Simulation", "portfolio drawdown simulation max drawdown distribution breach probability threshold underwater monte carlo"],
        ["Portfolio Bootstrap Stress", "portfolio bootstrap resampling historical returns stress robustness non parametric simulation distribution"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `risklab-${title}`,
      group: "Portfolio Risk Lab",
      title,
      keywords,
      run: () => handleNav("risklab"),
    })),
    ...(
      [
        ["Volatility Surface Lab", "volatility surface implied vol iv smile skew term structure 2d grid moneyness maturity option chain"],
        ["Implied Volatility Solver", "implied volatility solver iv inversion bisection black scholes recover sigma option price"],
        ["Variance Swap Lab", "variance swap fair strike volatility strike option strip approximation log contract replication"],
        ["Vega Exposure Lab", "vega exposure portfolio vega by maturity moneyness bucket option greeks volatility risk"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `volatility-${title}`,
      group: "Volatility Lab",
      title,
      keywords,
      run: () => handleNav("volatility"),
    })),
    ...(
      [
        ["Open Market Microstructure Lab", "microstructure execution lab order book trade tape vwap twap implementation shortfall slippage market impact liquidity"],
        ["Order Book Imbalance Lab", "order book imbalance depth ladder bid ask spread microprice top of book level book pressure"],
        ["VWAP and TWAP Lab", "vwap twap volume weighted average price time weighted average price trade tape benchmark execution"],
        ["Implementation Shortfall Lab", "implementation shortfall slippage arrival price benchmark execution cost market impact participation transaction cost analysis tca"],
        ["Execution Schedule Lab", "execution schedule immediate twap vwap participation of volume pov child orders impact spread cost completion"],
        ["Liquidity Stress Lab", "liquidity stress spread widening depth halving volatility spike volume drought scenario microprice imbalance"],
        ["Execution Cost Attribution", "execution cost attribution tca spread impact timing fees residual implementation shortfall benchmark arrival vwap twap"],
        ["TCA Lab", "tca transaction cost analysis execution cost attribution benchmark shortfall spread impact timing fees"],
        ["Market Impact Attribution", "market impact attribution square root impact cost participation execution cost tca spread timing"],
        ["Order Flow Toxicity Lab", "order flow toxicity ofi order flow imbalance queue imbalance signed volume informed flow liquidity diagnostics"],
        ["VPIN Liquidity Lab", "vpin volume synchronized probability informed trading toxicity bucket imbalance liquidity metric flow toxicity"],
        ["Effective Spread Lab", "effective spread realized spread bps trade price mid quoted spread quality execution quality"],
        ["Adverse Selection Lab", "adverse selection cost effective minus realized spread informed flow markout post trade drift"],
        ["Liquidity Regime Lab", "liquidity regime classification calm balanced one sided toxic flow stressed illiquid kyle lambda amihud illiquidity"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `microstructure-${title}`,
      group: "Market Microstructure Lab",
      title,
      keywords,
      run: () => handleNav("microstructure"),
    })),
    ...(
      [
        ["Open Crypto Derivatives Lab", "crypto derivatives perpetual perp futures funding basis lab btc eth sol bitcoin ethereum solana annualized carry liquidation margin leverage"],
        ["Perpetual Funding Lab", "perpetual funding rate 8h annualized funding yield long short funding pnl perp mark index premium discount"],
        ["Crypto Basis Lab", "crypto basis perp basis dated futures basis annualized basis contango backwardation curve shape spot perp futures"],
        ["Funding Rate Carry Lab", "funding carry cash and carry annualized basis expected gross carry costs best contract spot futures convergence"],
        ["Liquidation Distance Lab", "liquidation distance price approximation margin ratio initial maintenance margin leverage liquidation buffer"],
        ["Crypto Basis Scenario Stress", "crypto scenario stress funding spike negative perp premium blowout discount spot selloff rally basis convergence margin stress volatility shock"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `cryptoderivatives-${title}`,
      group: "Crypto Derivatives Lab",
      title,
      keywords,
      run: () => handleNav("cryptoderivatives"),
    })),
    ...(
      [
        ["Open DeFi Risk Lab", "defi risk lab stablecoin peg lending borrow apy utilization health factor liquidation net apy protocol stress usdc usdt dai eth wbtc"],
        ["Stablecoin Peg Lab", "stablecoin peg deviation depeg bps target peg market price reserve quality usdc usdt dai"],
        ["DeFi Lending APY Lab", "defi lending apy borrow apy utilization kink interest rate model slope reserve factor supply rate"],
        ["Health Factor Lab", "health factor collateral value debt value ltv loan to value liquidation threshold collateral factor"],
        ["Liquidation Distance Lab", "defi liquidation price approximation liquidation distance collateral drawdown health factor buffer"],
        ["DeFi Stress Scenario Lab", "defi stress scenario depeg collateral drawdown utilization spike liquidity drought borrow rate shock threshold cut protocol stress combo"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `defirisk-${title}`,
      group: "DeFi Risk Lab",
      title,
      keywords,
      run: () => handleNav("defirisk"),
    })),
    ...(
      [
        ["Open Tokenomics Risk Lab", "tokenomics risk lab token unlock treasury fdv market cap float emission staking concentration crypto fundamentals"],
        ["Unlock Schedule Lab", "unlock schedule vesting cliff team investor ecosystem foundation tranche dilution pressure tokens circulating"],
        ["FDV Dilution Lab", "fdv fully diluted valuation market cap ratio float ratio dilution low float future supply"],
        ["Treasury Runway Lab", "treasury runway months burn rate stables treasury tokens revenue adjusted protocol treasury"],
        ["Holder Concentration Lab", "holder concentration top holder share insider foundation community whale concentration score"],
        ["Tokenomics Stress Scenario Lab", "tokenomics stress scenario price drawdown unlock acceleration emission increase treasury drawdown burn increase concentration shock severe combo"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `tokenomics-${title}`,
      group: "Tokenomics Risk Lab",
      title,
      keywords,
      run: () => handleNav("tokenomics"),
    })),
    ...(
      [
        ["Open On-Chain Analytics Lab", "onchain on-chain analytics lab exchange flow reserve whale concentration velocity nvt active addresses crypto"],
        ["Exchange Reserve Lab", "exchange reserve tokens reserve ratio reserve value exchange balance crypto onchain"],
        ["Net Exchange Flow Lab", "net exchange flow inflow outflow deposits withdrawals sell pressure accumulation exchange netflow"],
        ["Whale Concentration Lab", "whale concentration top holder share top 10 50 100 whale net flow gini holder cohort distribution"],
        ["Token Velocity Lab", "token velocity transfer volume circulating supply turnover activity onchain"],
        ["NVT Activity Lab", "nvt ratio network value to transactions market cap transfer value valuation activity onchain"],
        ["On-Chain Stress Scenario Lab", "onchain stress scenario inflow spike outflow wave whale deposit accumulation address slowdown transfer collapse velocity burst concentration shock severe combo"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `onchain-${title}`,
      group: "On-Chain Analytics Lab",
      title,
      keywords,
      run: () => handleNav("onchain"),
    })),
    ...(
      [
        ["Open Alternative Data Lab", "alternative data alt data lab news sentiment social earnings macro supply chain signal decay leakage alpha"],
        ["News Sentiment Lab", "news sentiment score weighted sentiment intensity relevance reliability positive negative neutral events"],
        ["Signal Decay Lab", "signal decay curve horizon correlation half life information coefficient decay 1d 5d 20d"],
        ["Leakage Guard Lab", "leakage guard look ahead bias timestamp alignment feature available event time point in time"],
        ["Event Study Signal Lab", "event study forward return horizon average signal ic information coefficient hit rate"],
        ["Alternative Data Stress Scenario Lab", "alternative data stress scenario news burst noise spike reliability downgrade lag increase novelty collapse crowded leakage severe combo"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `altdata-${title}`,
      group: "Alternative Data Lab",
      title,
      keywords,
      run: () => handleNav("altdata"),
    })),
    ...(
      [
        ["Open Macro Regime Lab", "macro regime lab growth inflation policy liquidity credit usd cross asset allocation scores"],
        ["Cross-Asset Allocation Lab", "cross asset allocation inverse volatility risk parity regime tilted weights portfolio educational"],
        ["Inflation Shock Lab", "inflation shock macro regime hot cpi tight policy stagflation scenario"],
        ["Recession Stress Lab", "recession credit stress weak growth credit spreads macro regime scenario"],
        ["Liquidity Regime Lab", "liquidity easing regime money supply funding spread policy macro"],
        ["Macro Scenario Stress Lab", "macro scenario stress growth slowdown inflation spike disinflation policy tightening credit shock usd shock severe combo"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `macroregime-${title}`,
      group: "Macro Regime Lab",
      title,
      keywords,
      run: () => handleNav("macroregime"),
    })),
    ...(
      [
        ["Open Scenario Studio", "scenario studio unified cross lab stress templates global shock controls impact dashboard educational"],
        ["Cross-Lab Scenario Studio", "cross lab scenario impact scores macro portfolio crypto defi tokenomics onchain alternative data microstructure heatmap radar"],
        ["Report Builder", "report builder generated markdown sections executive summary limitations copy educational research summary"],
        ["Cross-Asset Stress Report", "cross asset stress report severe combo broad risk off composite severity scenario regime"],
        ["Crypto Stress Report", "crypto stress report crypto risk off stablecoin depeg exchange inflow panic funding unlock whale scenario"],
        ["Macro Stress Report", "macro stress report inflation reacceleration growth shock liquidity crunch credit stress policy scenario"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `scenariostudio-${title}`,
      group: "Scenario Studio",
      title,
      keywords,
      run: () => handleNav("scenariostudio"),
    })),
    ...(
      [
        ["Open Research Workspace", "research workspace experiment journal saved presets lab runs organize educational"],
        ["Experiment Journal", "experiment journal run cards notes scenario baseline stressed severity confidence label"],
        ["Saved Presets", "saved research presets macro stress crypto risk off defi liquidity tokenomics unlock alternative data cross asset pack"],
        ["Run Comparison", "run comparison table baseline stressed change percent change severity ranking sort"],
        ["Research Report Builder", "research report builder markdown json export copy sections overview assumptions methodology limitations next steps"],
        ["Methodology Checklist", "methodology checklist reproducibility score assumptions limitations run notes documentation checks"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `researchworkspace-${title}`,
      group: "Research Workspace",
      title,
      keywords,
      run: () => handleNav("researchworkspace"),
    })),
    ...(
      [
        ["Open Demo Center", "demo center product walkthrough guided tour module health capability matrix demo script"],
        ["Product Walkthrough", "product walkthrough guided steps demo path tour presentation showcase portfolio"],
        ["Founder Demo Tour", "founder investor product tour globe backtest scenario studio research workspace fifteen minutes"],
        ["Quant Research Tour", "quant research workflow tour backtest comparison portfolio risk macro scenario journal methodology"],
        ["Crypto Risk Demo", "crypto risk research tour funding basis defi tokenomics onchain cross lab stress demo"],
        ["Macro Stress Demo", "macro portfolio stress tour regime scores risk lab scenario studio inflation demo"],
        ["Module Health Dashboard", "module health dashboard status data mode badges stable demo static sample experimental readiness"],
        ["Demo Script Builder", "demo script builder audience time budget markdown json copy sections opening overview limitations closing"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `democenter-${title}`,
      group: "Demo Center",
      title,
      keywords,
      run: () => handleNav("democenter"),
    })),
    ...(
      [
        ["Open Data Reliability Center", "data reliability center registry deterministic demos offline fixtures provider exposure"],
        ["Data Mode Registry", "data mode registry static sample user input local calculation optional external provider module modes"],
        ["Offline Fixtures", "offline fixtures pairs demo fallback ko pep deterministic test safe sample registry"],
        ["Provider Registry", "provider registry yfinance fred delayed quotes network api key allowed in tests fail closed"],
        ["Test Safety Matrix", "test safety matrix monkeypatch fixtures no network deterministic tests providers disabled"],
        ["API Reliability Report", "api reliability report markdown json demo safe test safe fallback coverage external exposure score"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `datareliability-${title}`,
      group: "Data Reliability Center",
      title,
      keywords,
      run: () => handleNav("datareliability"),
    })),
    ...(
      [
        ["Open QA Command Center", "qa command center release readiness smoke test regression release notes quality"],
        ["Release Readiness", "release readiness score ready rate decision ready for demo blocked needs review"],
        ["Smoke Test Matrix", "smoke test matrix module route steps expected result status label"],
        ["Regression Checklist", "manual regression checklist grouped by category copy friendly qa steps"],
        ["Release Notes Builder", "release notes builder markdown json copy draft highlights data policy"],
        ["Backend Test Commands", "backend test commands pytest venv python backend tests command checklist"],
        ["Frontend Build Checklist", "frontend build checklist npx tsc noemit npm run build typecheck user local"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `qacommandcenter-${title}`,
      group: "QA Command Center",
      title,
      keywords,
      run: () => handleNav("qacommandcenter"),
    })),
    ...(
      [
        ["Open Portfolio Showcase", "portfolio showcase public presentation what quantlab demonstrates demo path highlights pitches"],
        ["Public Project Summary", "public project summary recruiter quant researcher technical architecture docs public_project_summary"],
        ["Demo Video Script", "demo video script 60 second 3 minute 8 minute recording screen order docs demo_video_script"],
        ["Screenshot Checklist", "screenshot checklist capture targets routes captions docs screenshot_checklist screenshot plan"],
        ["LinkedIn Drafts", "linkedin post drafts technical quant full stack product learning recruiter docs linkedin_post_drafts"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `portfolioshowcase-${title}`,
      group: "Portfolio Showcase",
      title,
      keywords,
      run: () => handleNav("portfolioshowcase"),
    })),
    ...(
      [
        ["Open Developer Onboarding", "developer onboarding local demo environment checklist commands troubleshooting setup"],
        ["Local Demo Guide", "local demo guide backend frontend startup demo route three minute eight minute docs local_demo_guide"],
        ["Environment Doctor", "environment doctor check_environment script python venv node npm dependencies ports read only docs environment_doctor"],
        ["Command Reference", "command reference backend run tests typecheck build dev git commit tag clean artifacts docs command_reference"],
        ["Troubleshooting", "troubleshooting uvicorn venv pytest node_modules ports yfinance nan formulas execution policy docs troubleshooting"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `developeronboarding-${title}`,
      group: "Developer Onboarding",
      title,
      keywords,
      run: () => handleNav("developeronboarding"),
    })),
    ...(
      [
        ["Cost of Carry Lab", "futures cost of carry pricing spot forward convenience yield storage rate model fair value commodity"],
        ["Futures Curve Lab", "futures curve contango backwardation mixed term structure maturity basis slope shape commodity"],
        ["Roll Yield Calculator", "futures roll yield near next contract calendar spread carry contango backwardation"],
        ["Commodity Scenario Stress", "futures commodity scenario stress spot rally selloff contango steepening backwardation storage convenience margin"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `futures-${title}`,
      group: "Futures & Commodities Lab",
      title,
      keywords,
      run: () => handleNav("futures"),
    })),
    ...(
      [
        ["Cap Rate Calculator", "real estate cap rate noi net operating income property valuation value income capitalization"],
        ["Mortgage DSCR Lab", "real estate mortgage amortization dscr debt service coverage ratio ltv loan to value monthly payment interest"],
        ["REIT NAV Lab", "real estate reit nav net asset value per share premium discount p ffo funds from operations dividend yield"],
        ["Real Estate Scenario Stress", "real estate scenario stress rent growth vacancy shock cap rate expansion interest rate shock downside combo cash on cash irr equity multiple"],
        ["Mortgage Prepayment Lab", "mortgage mbs prepayment cpr smm psa cash flow amortization pool agency pass through speed"],
        ["MBS PSA Model", "mbs psa prepayment standard model ramp speed 100 cpr pool age seasoning"],
        ["MBS WAL and Duration", "mbs weighted average life wal duration convexity price discount yield mortgage backed security"],
        ["CPR to SMM Calculator", "cpr smm single monthly mortality conditional prepayment rate conversion mortgage mbs"],
      ] as const
    ).map(([title, keywords]) => ({
      id: `realestate-${title}`,
      group: "Real Estate Lab",
      title,
      keywords,
      run: () => handleNav("realestate"),
    })),
    {
      id: "globe-open",
      group: "Global Markets Globe",
      title: "Explore Global Markets",
      keywords:
        "globe global markets world markets country macro fx indices market dossier map 3d earth explore europe asia americas",
      run: () => openGlobe(null),
    },
    ...MARKETS.map((m) => ({
      id: `globe-${m.id}`,
      group: "Global Markets Globe",
      title: `Open ${m.country} Market Dossier`,
      keywords: `globe market dossier ${GLOBE_MARKET_ALIASES[m.id] ?? m.id} ${m.country} ${m.region} ${m.subregion} ${m.currency} ${m.exchange} ${m.indices
        .map((i) => `${i.name} ${i.ticker}`)
        .join(" ")}`,
      run: () => openGlobe(m.id),
    })),
    ...TOUR_LIST.map((t) => ({
      id: `globe-tour-${t.id}`,
      group: "Global Markets Globe",
      title:
        t.id === "global"
          ? "Start Global Markets Tour"
          : t.id === "asia"
            ? "Start Asia Markets Tour"
            : t.id === "macro"
              ? "Start Macro Regime Tour"
              : "Start Risk Lens Tour",
      keywords: `globe guided tour presentation walkthrough demo ${t.id} ${t.title} ${t.subtitle} ${t.steps
        .map((s) => s.marketId)
        .join(" ")}`,
      run: () => openGlobe(null, { tour: t.id }),
    })),
    {
      id: "globe-presentation",
      group: "Global Markets Globe",
      title: "Open Globe Presentation Mode",
      keywords:
        "globe presentation mode demo screenshot clean fullscreen kiosk briefing present",
      run: () => openGlobe(null, { presentation: true }),
    },
    {
      id: "globe-presentation-tw",
      group: "Global Markets Globe",
      title: "Open Taiwan Globe Presentation",
      keywords: "globe presentation taiwan tw dossier demo screenshot present",
      run: () => openGlobe("tw", { presentation: true }),
    },
    {
      id: "globe-presentation-us",
      group: "Global Markets Globe",
      title: "Open US Globe Presentation",
      keywords: "globe presentation us usa united states dossier demo screenshot present",
      run: () => openGlobe("us", { presentation: true }),
    },
    // Report actions are only offered when they actually work (a result exists).
    ...(result
      ? [
          {
            id: "report-export-current",
            group: "Report",
            title: "Export current backtest report (Markdown)",
            keywords: "download md save export report current result",
            hint: result.ticker,
            run: exportCurrentReport,
          },
        ]
      : []),
  ];

  const heading = STRATEGY_HEADINGS[strategy];
  const meta = VIEW_META[view];

  return (
    <AppShell
      active={view}
      onNav={handleNav}
      title={meta.title}
      subtitle={meta.subtitle}
    >
      <div className="space-y-8">
        {/* Guided-demo banner — shown in the target workspace after a demo is
            loaded; cleared on navigation or once a real run completes. */}
        {demoNotice && view !== "home" && (
          <div
            className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
            style={{
              background: "var(--accent-softer)",
              border: "1px solid var(--accent-line)",
              color: "var(--accent-text)",
            }}
          >
            <span aria-hidden className="mt-0.5 flex-shrink-0">
              ⚡
            </span>
            <p className="flex-1">{demoNotice}</p>
            <button
              type="button"
              onClick={() => setDemoNotice(null)}
              aria-label="Dismiss demo hint"
              className="flex-shrink-0 px-1 text-slate-400 transition-colors hover:text-slate-900"
            >
              ✕
            </button>
          </div>
        )}

        {/* ── Home / Command Center ────────────────────────────────────── */}
        {view === "home" && (
          <HomeDashboard
            onNav={handleNav}
            onDemo={handleDemo}
            onOpenBacktest={openSavedBacktest}
            onOpenReport={openSavedReport}
            onOpenLibraryPage={openLibraryPage}
            onOpenPaperPage={openPaperPage}
            onOpenDisasterPage={openDisasterPage}
            onOpenGlobe={openGlobe}
            onStartTour={(tour) => openGlobe(null, { tour })}
          />
        )}

        {/* ── Global Markets Globe ─────────────────────────────────────── */}
        {view === "globe" && (
          <GlobeLabPanel
            key={globeKey}
            initialMarketId={globeMarketId}
            initialTour={globeTour}
            initialPresentation={globePresentation}
            onNav={handleNav}
          />
        )}

        {/* ── Backtest ─────────────────────────────────────────────────── */}
        {view === "backtest" && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                {heading.title}
              </h1>
              <p className="mt-1 text-sm text-slate-500 max-w-2xl">
                {heading.description}
              </p>
            </div>

            <BacktestForm
              key={formKey}
              strategy={strategy}
              onStrategyChange={(s) => {
                setStrategy(s);
                setResult(null);
                setError(null);
              }}
              smaParams={smaParams}
              onSmaParamsChange={setSmaParams}
              rsiParams={rsiParams}
              onRsiParamsChange={setRsiParams}
              bbParams={bbParams}
              onBbParamsChange={setBbParams}
              momentumParams={momentumParams}
              onMomentumParamsChange={setMomentumParams}
              vbParams={vbParams}
              onVbParamsChange={setVbParams}
              pairsParams={pairsParams}
              onPairsParamsChange={setPairsParams}
              onSubmit={handleRun}
              loading={loading}
            />

            {/* Loading skeleton */}
            {loading && (
              <div className="card p-8 text-center">
                <div className="inline-flex items-center gap-3 text-slate-500">
                  <svg
                    className="animate-spin h-5 w-5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    />
                  </svg>
                  <span className="text-sm font-medium">
                    Fetching data and running backtest…
                  </span>
                </div>
              </div>
            )}

            {/* Error banner */}
            {error && !loading && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
                <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
                <div>
                  <p className="text-sm font-semibold text-red-700">
                    Backtest failed
                  </p>
                  <p className="text-sm text-red-600 mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* Results */}
            {result && !loading && (
              <>
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="text-lg font-bold text-slate-900">
                    {result.ticker}
                  </h2>
                  <span className="text-slate-400 text-sm">
                    {result.start_date} → {result.end_date}
                  </span>
                  <span className="text-xs text-slate-400">
                    {paramSummary(result)}
                  </span>
                  {result.cost_model && (
                    <span
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600"
                      title={result.cost_model.label}
                    >
                      {costModelBadgeLabel(result)}
                      {" · "}
                      {result.effective_cost_bps ?? result.transaction_cost_bps} bps
                    </span>
                  )}
                  {result.position_sizing && (
                    <span
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600"
                      title={result.position_sizing.label}
                    >
                      {result.position_sizing.type === "fixed_fraction"
                        ? "Fixed fraction"
                        : result.position_sizing.type === "volatility_target"
                          ? "Vol target"
                          : result.position_sizing.type === "max_exposure"
                            ? "Max exposure"
                            : "Full alloc"}
                      {typeof result.average_exposure === "number" && (
                        <> · {Math.round(result.average_exposure * 100)}% avg</>
                      )}
                    </span>
                  )}
                  {result.risk_management && (
                    <span
                      className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-700"
                      title={result.risk_management.label}
                    >
                      Risk rules
                      {result.risk_diagnostics
                        ? ` · ${result.risk_diagnostics.risk_exit_count} exits`
                        : ""}
                    </span>
                  )}
                  {result.periods_per_year && (
                    <span
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600"
                      title={
                        result.annualization_warning ??
                        "Annualization convention for CAGR / Calmar / Sharpe / Sortino / volatility"
                      }
                    >
                      {result.annualization_mode === "auto"
                        ? `Auto → ${
                            result.annualization_mode_used === "crypto_365"
                              ? "Crypto 365"
                              : "Trading 252"
                          }`
                        : result.annualization_mode_used === "crypto_365"
                          ? "Crypto 365"
                          : "Trading 252"}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-2">
                    <ExportReportButton
                      getReport={(tpl) => buildBacktestReport(result, {}, tpl)}
                    />
                    {!showSaveForm && (
                      <button
                        type="button"
                        onClick={() => setShowSaveForm(true)}
                        className="px-3 py-1 rounded-lg text-xs font-semibold text-blue-700
                                   border border-blue-200 hover:bg-blue-50 transition-colors"
                      >
                        Save backtest
                      </button>
                    )}
                  </span>
                </div>

                {showSaveForm && (
                  <SaveBacktestModal
                    result={result}
                    onSaved={(id) => {
                      setShowSaveForm(false);
                      setSavedRefreshKey((k) => k + 1);
                      setSavedDetailId(id);
                      markChecklistStep("saved_backtest");
                      setView("saved");
                    }}
                    onCancel={() => setShowSaveForm(false)}
                  />
                )}

                <MetricsGrid
                  strategy={result.strategy_metrics}
                  benchmark={result.benchmark_metrics}
                  ticker={result.ticker}
                  strategyLabel={strategyLabel(result)}
                />

                <SignalDiagnostics
                  numTrades={result.num_trades}
                  strategy={result.strategy}
                  positionMode={result.position_mode}
                />

                {result.risk_management && (
                  <RiskDiagnosticsCard
                    risk={result.risk_management}
                    diagnostics={result.risk_diagnostics ?? null}
                  />
                )}

                {result.benchmark_analytics && (
                  <BenchmarkComparisonCard
                    analytics={result.benchmark_analytics}
                    strategyMetrics={result.strategy_metrics}
                  />
                )}

                {result.data_quality && (
                  <DataQualityCard
                    provider={result.data_provider}
                    quality={result.data_quality}
                  />
                )}

                {result.reproducibility && (
                  <ReproducibilityCard reproducibility={result.reproducibility} />
                )}

                <RobustnessLabCard robustness={result.robustness} />

                <StabilityLabCard sensitivity={result.sensitivity} />

                {(result.position_mode === "short_only" ||
                  result.position_mode === "long_short") && (
                  <>
                    <ShortSellingWarning />
                    {result.diagnostics && (
                      <ShortModeDiagnostics
                        diagnostics={result.diagnostics}
                        mode={result.position_mode}
                      />
                    )}
                  </>
                )}

                {(() => {
                  const bench = buildBenchmarkChartSeries(
                    result.equity_curve,
                    result.benchmark_analytics,
                  );
                  return (
                    <>
                      <div className="card p-6">
                        <p className="section-title mb-4">
                          Equity Curve
                          {bench.showBenchmark && (
                            <span className="normal-case font-normal text-slate-400 ml-1">
                              vs {bench.benchmarkLabel}
                            </span>
                          )}
                        </p>
                        <EquityCurveChart
                          data={bench.data}
                          benchmarkLabel={bench.benchmarkLabel}
                          showBenchmark={bench.showBenchmark}
                        />
                        {bench.showBenchmark && (
                          <p className="mt-2 text-[11px] text-slate-400">
                            Benchmark comparison does not change strategy trades. It
                            compares the strategy against a reference asset over
                            aligned dates.
                            {result.benchmark_analytics?.mode === "custom_ticker" &&
                              " Custom benchmark returns are aligned by date; limited overlap may affect alpha, beta, and information ratio."}
                          </p>
                        )}
                      </div>

                      <div className="card p-6">
                        <p className="section-title mb-4">
                          Drawdown
                          {bench.showBenchmark && (
                            <span className="normal-case font-normal text-slate-400 ml-1">
                              vs {bench.benchmarkLabel}
                            </span>
                          )}
                        </p>
                        <DrawdownChart
                          data={bench.data}
                          benchmarkLabel={bench.benchmarkLabel}
                          showBenchmark={bench.showBenchmark}
                        />
                      </div>

                      {bench.showBenchmark && (
                        <div className="card p-6">
                          <p className="section-title mb-4">
                            Cumulative Excess Return
                            <span className="normal-case font-normal text-slate-400 ml-1">
                              strategy − {bench.benchmarkLabel}
                            </span>
                          </p>
                          <ExcessReturnChart
                            data={bench.data}
                            benchmarkLabel={bench.benchmarkLabel}
                          />
                          <p className="mt-2 text-[11px] text-slate-400">
                            Difference of cumulative returns from the first aligned
                            date (not a compounded active-equity curve). Above zero =
                            ahead of the benchmark; below = behind.
                          </p>
                        </div>
                      )}
                    </>
                  );
                })()}

                <div className="card p-6">
                  <p className="section-title mb-4">
                    Trade Log{" "}
                    <span className="normal-case font-normal text-slate-400 ml-1">
                      ({result.num_trades} events)
                    </span>
                  </p>
                  <TradeTable trades={result.trades} />
                  <p className="mt-3 text-xs text-slate-400">
                    Most built-in strategies are <span className="font-medium text-slate-500">long-only</span>:
                    they hold cash when flat and can stay out of the market during
                    downtrends — staying flat is expected, not a bug. Use{" "}
                    <span className="font-medium text-slate-500">Pairs Trading</span>{" "}
                    for non-directional exposure.
                  </p>
                </div>
              </>
            )}
          </>
        )}

        {/* ── Strategy Library ─────────────────────────────────────────── */}
        {view === "library" && (
          <StrategyLibraryPanel
            key={libraryKey}
            initialSlug={librarySlug}
            onRunStrategy={handleRunFromLibrary}
            onOpenComparison={() => handleNav("comparison")}
            onOpenPaper={openPaperPage}
            onOpenDisaster={openDisasterPage}
          />
        )}

        {/* ── Paper Replications ───────────────────────────────────────── */}
        {view === "replications" && (
          <PaperReplicationsPanel
            key={paperKey}
            initialSlug={paperSlug}
            onRunPreset={handleRunPaperPreset}
            onOpenStrategy={openLibraryPage}
            onOpenDisaster={openDisasterPage}
            onOpenOptions={() => handleNav("options")}
          />
        )}

        {/* ── Quant Disasters ──────────────────────────────────────────── */}
        {view === "disasters" && (
          <QuantDisastersPanel
            key={disasterKey}
            initialSlug={disasterSlug}
            onOpenStrategy={openLibraryPage}
            onOpenPaper={openPaperPage}
            onOpenOptions={() => handleNav("options")}
          />
        )}

        {/* ── Options Lab ──────────────────────────────────────────────── */}
        {view === "options" && (
          <OptionsLabPanel key={optionsKey} initialTab={optionsTab} initialPresetId={optionsPreset} />
        )}

        {/* ── Event Lab ────────────────────────────────────────────────── */}
        {view === "events" && <EventLabPanel key={eventsKey} initialTab={eventsTab} />}

        {/* ── Yield Curve Lab ──────────────────────────────────────────── */}
        {view === "rates" && <YieldCurveLabPanel key={ratesKey} initialTab={ratesTab} />}

        {/* ── FX Lab ───────────────────────────────────────────────────── */}
        {view === "fx" && <FxLabPanel key={fxKey} initialTab={fxTab} />}

        {/* ── Credit Risk Lab ──────────────────────────────────────────── */}
        {view === "credit" && <CreditLabPanel key={creditKey} initialTab={creditTab} />}

        {/* ── Cross-Sectional Scanner ──────────────────────────────────── */}
        {view === "scanner" && <ScannerLabPanel key={scannerKey} initialStrategy={scannerStrategy} />}

        {/* ── AFML Methodology Lab ─────────────────────────────────────── */}
        {view === "finml" && <AfmlLabPanel key={finmlKey} initialTab={finmlTab} />}

        {/* ── Portfolio Risk Lab ───────────────────────────────────────── */}
        {view === "risklab" && <PortfolioRiskLabPanel />}

        {/* ── Real Estate Lab ──────────────────────────────────────────── */}
        {view === "realestate" && <RealEstateLabPanel />}

        {/* ── Futures & Commodities Lab ────────────────────────────────── */}
        {view === "futures" && <FuturesLabPanel />}

        {/* ── Volatility Surface & Variance Swap Lab ───────────────────── */}
        {view === "volatility" && <VolatilityLabPanel />}

        {/* ── Market Microstructure & Execution Lab ────────────────────── */}
        {view === "microstructure" && <MicrostructureLabPanel />}

        {/* ── Crypto Perpetual Funding & Basis Lab ─────────────────────── */}
        {view === "cryptoderivatives" && <CryptoDerivativesLabPanel />}

        {/* ── DeFi Yield, Stablecoin Peg & Lending Risk Lab ────────────── */}
        {view === "defirisk" && <DefiRiskLabPanel />}

        {/* ── Tokenomics, Unlock Schedule & Treasury Risk Lab ──────────── */}
        {view === "tokenomics" && <TokenomicsLabPanel />}

        {/* ── On-Chain Flow, Exchange Reserve & Whale Concentration Lab ── */}
        {view === "onchain" && <OnChainAnalyticsLabPanel />}

        {/* ── Alternative Data, News Sentiment & Signal Decay Lab ──────── */}
        {view === "altdata" && <AlternativeDataLabPanel />}

        {/* ── Macro Regime & Cross-Asset Allocation Lab ─────────────────── */}
        {view === "macroregime" && <MacroRegimeLabPanel />}

        {view === "scenariostudio" && <ScenarioStudioPanel />}

        {view === "researchworkspace" && <ResearchWorkspacePanel />}

        {view === "democenter" && <DemoCenterPanel onNav={(route) => handleNav(route as View)} />}

        {view === "datareliability" && <DataReliabilityPanel />}

        {view === "qacommandcenter" && <QACommandCenterPanel />}

        {view === "portfolioshowcase" && <PortfolioShowcasePanel onNav={(route) => handleNav(route as View)} />}

        {view === "developeronboarding" && <DeveloperOnboardingPanel onNav={(route) => handleNav(route as View)} />}

        {/* ── CSV Backtest ─────────────────────────────────────────────── */}
        {view === "csv" && (
          <>
            <SectionIntro title="CSV Upload Backtest">
              Upload your own historical price CSV and run any single-asset
              strategy on it. The file needs a date column (date / datetime /
              timestamp) and a close column (close / adj_close); optional OHLCV
              columns are ignored. Pairs Trading is not available for uploads.
            </SectionIntro>
            <CsvBacktestPanel />
          </>
        )}

        {/* ── Strategy Builder ─────────────────────────────────────────── */}
        {view === "builder" && (
          <>
            <SectionIntro title="Custom Strategy Builder">
              Compose a long-only, single-asset strategy from predefined
              indicator rules (SMA, RSI, Bollinger Bands, Momentum, close, and
              constants). Define when to enter and when to exit — no code, no
              short selling, no leverage. Rules are evaluated safely on the
              server with vectorised math.
            </SectionIntro>
            <StrategyBuilderPanel
              key={builderKey}
              initialGalleryTemplateId={builderDemoTemplateId ?? undefined}
              initialSavedTemplateId={builderSavedTemplateId ?? undefined}
            />
          </>
        )}

        {/* ── Portfolio Backtest ───────────────────────────────────────── */}
        {view === "portfolio" && (
          <>
            <SectionIntro title="Multi-Asset Portfolio">
              Backtest an equal-weight, long-only portfolio with optional
              rebalancing, or optimize long-only weights (minimum volatility or
              maximum Sharpe) over a historical window. Optimization is
              in-sample and can overfit — it is not investment advice.
            </SectionIntro>
            <PortfolioWorkspace key={portfolioKey} initialTab={portfolioTab} />
          </>
        )}

        {/* ── SMA Parameter Sweep ──────────────────────────────────────── */}
        {view === "sweep" && (
          <>
            <SectionIntro title="SMA Crossover Parameter Sweep">
              Test every combination of fast and slow SMA windows on the same
              asset and date range. Compare Sharpe ratio, CAGR, and max drawdown
              to identify robust parameter regions and avoid over-fitted
              outliers.
            </SectionIntro>
            <SmaSweepPanel />
          </>
        )}

        {/* ── SMA Train/Test Validation ────────────────────────────────── */}
        {view === "train-test" && (
          <>
            <SectionIntro title="SMA Train/Test Out-of-Sample Validation">
              Split your date range into in-sample (IS) and out-of-sample (OOS)
              periods. Run a parameter sweep on IS data only, select the best
              parameters by your chosen metric, then evaluate them on unseen OOS
              data. Reveals whether IS performance is genuine or a product of
              over-fitting.
            </SectionIntro>
            <SmaTrainTestPanel />
          </>
        )}

        {/* ── SMA Walk-Forward ─────────────────────────────────────────── */}
        {view === "walk-forward" && (
          <>
            <SectionIntro title="SMA Walk-Forward Optimization">
              Repeatedly roll a training window forward, sweep SMA parameters
              in-sample, select the best pair, and evaluate it on the
              immediately following out-of-sample window. The out-of-sample
              results are stitched together to form a realistic equity curve
              that avoids look-ahead bias. Parameter stability analysis shows
              whether the strategy requires stable parameters or adapts
              erratically.
            </SectionIntro>
            <SmaWalkForwardPanel />
          </>
        )}

        {/* ── Strategy Comparison ──────────────────────────────────────── */}
        {view === "comparison" && (
          <>
            <SectionIntro title="Strategy Comparison">
              Run five single-asset strategies on the same ticker and date range
              using fixed default parameters. Compare their equity curves,
              risk-adjusted returns, and drawdowns side-by-side to understand
              which strategy styles suited different market environments. Pairs
              Trading is excluded (requires two assets).
            </SectionIntro>
            <StrategyComparisonPanel />
          </>
        )}

        {/* ── Saved Backtests ──────────────────────────────────────────── */}
        {view === "saved" && (
          <>
            <SectionIntro title="Saved Backtests">
              Backtests you have saved are stored locally in a SQLite database.
              Click any row to view the full result, equity curve, and trade
              log.
            </SectionIntro>

            {savedDetailId !== null ? (
              <SavedBacktestDetail
                id={savedDetailId}
                onBack={() => setSavedDetailId(null)}
                onGoHome={() => handleNav("home")}
              />
            ) : (
              <SavedBacktestsList
                refreshKey={savedRefreshKey}
                onSelect={(id) => setSavedDetailId(id)}
                onGoHome={() => handleNav("home")}
                onRunBacktest={() => handleNav("backtest")}
              />
            )}
          </>
        )}

        {/* ── Saved Reports (Report Gallery) ───────────────────────────── */}
        {view === "reports" && (
          <>
            <SectionIntro title="Saved Reports">
              Research reports you save are stored locally in a SQLite database
              (Markdown text only — PDF files are not stored). Open any report to
              read it, download the Markdown, or print / save it as a PDF from
              your browser.
            </SectionIntro>

            {savedReportDetailId !== null ? (
              <SavedReportDetail
                id={savedReportDetailId}
                onBack={() => setSavedReportDetailId(null)}
                onDeleted={() => {
                  setSavedReportDetailId(null);
                  setSavedReportsRefreshKey((k) => k + 1);
                }}
                onGoHome={() => handleNav("home")}
              />
            ) : (
              <SavedReportsList
                refreshKey={savedReportsRefreshKey}
                onSelect={(id) => setSavedReportDetailId(id)}
                onGoHome={() => handleNav("home")}
                onRunBacktest={() => handleNav("backtest")}
              />
            )}
          </>
        )}

        {/* ── Settings ─────────────────────────────────────────────────── */}
        {view === "settings" && (
          <>
            <SectionIntro title="App Settings">
              Configure local defaults that prefill forms and control display
              conventions. Stored in your browser only — no account, no cloud
              sync.
            </SectionIntro>
            <SettingsPanel />
          </>
        )}
      </div>

      {/* Global command palette (Ctrl/Cmd + K) — overlays every workspace. */}
      <CommandPalette
        commands={commands}
        onOpenBacktest={openSavedBacktest}
        onOpenReport={openSavedReport}
        onOpenSavedTemplate={openSavedTemplate}
        onOpenGalleryTemplate={openGalleryTemplate}
      />
    </AppShell>
  );
}
