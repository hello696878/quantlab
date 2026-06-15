/**
 * Unified Options Lab scenario presets.
 *
 * A preset seeds the common base inputs (S/K/T/r/q/σ/type) plus optional
 * per-model defaults (tree steps, Monte Carlo sims/seed, Heston params, payoff
 * preset, surface settings). Applying a preset re-seeds the tabs — tab-specific
 * fields stay local otherwise.
 *
 * These are **educational scenarios and model demonstrations**, NOT trading
 * recommendations. Wording is deliberately neutral.
 */

import type { MonteCarloPayoffType, OptionType } from "@/lib/types";

export interface OptionsScenarioBase {
  option_type: OptionType;
  underlying_price: number;
  strike: number;
  time_to_expiry: number;
  risk_free_rate: number;
  dividend_yield: number;
  volatility: number;
}

export interface OptionsScenarioTree {
  steps: number;
  exercise_style: "european" | "american";
}

export interface OptionsScenarioMonteCarlo {
  payoff_type: MonteCarloPayoffType;
  steps: number;
  simulations: number;
  seed: number;
  barrier_price?: number;
}

export interface OptionsScenarioHeston {
  initial_volatility: number;
  long_run_volatility: number;
  kappa: number;
  vol_of_vol: number;
  rho: number;
  steps: number;
  simulations: number;
  seed: number;
}

export interface OptionsScenarioSurface {
  base_vol: number;
  skew: number;
  smile: number;
  term: number;
}

export type OptionsLabTabId =
  | "pricing"
  | "implied_vol"
  | "payoff"
  | "tree"
  | "monte_carlo"
  | "surface"
  | "heston"
  | "compare";

export type OptionsScenarioCategory =
  | "Vanilla"
  | "Volatility regime"
  | "Exercise & skew"
  | "Path-dependent"
  | "Volatility research";

export interface OptionsScenarioPreset {
  id: string;
  name: string;
  category: OptionsScenarioCategory;
  description: string;
  /** Tabs this preset is most relevant to (used to suggest a primary tab). */
  appliesTo: OptionsLabTabId[];
  primaryTab: OptionsLabTabId;
  baseInputs: OptionsScenarioBase;
  treeInputs?: OptionsScenarioTree;
  monteCarloInputs?: OptionsScenarioMonteCarlo;
  hestonInputs?: OptionsScenarioHeston;
  /** id of a Payoff Builder leg preset to load. */
  payoffPresetId?: string;
  surfaceInputs?: OptionsScenarioSurface;
  warnings?: string[];
  educationalNotes?: string;
}

const HESTON_DEFAULT: OptionsScenarioHeston = {
  initial_volatility: 0.2,
  long_run_volatility: 0.2,
  kappa: 2.0,
  vol_of_vol: 0.5,
  rho: -0.7,
  steps: 252,
  simulations: 10000,
  seed: 42,
};

export const OPTIONS_SCENARIOS: OptionsScenarioPreset[] = [
  {
    id: "atm-equity-call",
    name: "ATM Equity Call",
    category: "Vanilla",
    description:
      "Educational scenario: an at-the-money 1-year European call on a non-dividend equity. The canonical Black–Scholes reference case.",
    appliesTo: ["pricing", "tree", "monte_carlo", "compare"],
    primaryTab: "pricing",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.2,
    },
    treeInputs: { steps: 200, exercise_style: "european" },
    monteCarloInputs: { payoff_type: "european_call", steps: 252, simulations: 10000, seed: 42 },
    hestonInputs: HESTON_DEFAULT,
    educationalNotes: "BS ≈ 10.45. Tree and Monte Carlo should land near this with enough steps/sims.",
  },
  {
    id: "otm-equity-call",
    name: "OTM Equity Call",
    category: "Vanilla",
    description:
      "Educational scenario: an out-of-the-money call (strike above spot). Lower price, higher leverage to upside moves.",
    appliesTo: ["pricing", "tree", "monte_carlo", "compare"],
    primaryTab: "pricing",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 120,
      time_to_expiry: 0.5,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.25,
    },
    treeInputs: { steps: 200, exercise_style: "european" },
    monteCarloInputs: { payoff_type: "european_call", steps: 126, simulations: 20000, seed: 42 },
    hestonInputs: HESTON_DEFAULT,
  },
  {
    id: "itm-equity-put",
    name: "ITM Equity Put",
    category: "Vanilla",
    description:
      "Educational scenario: an in-the-money put (strike above spot). Useful for inspecting put Greeks and put-side pricing.",
    appliesTo: ["pricing", "tree", "compare"],
    primaryTab: "pricing",
    baseInputs: {
      option_type: "put",
      underlying_price: 100,
      strike: 110,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.22,
    },
    treeInputs: { steps: 200, exercise_style: "european" },
    monteCarloInputs: { payoff_type: "european_put", steps: 252, simulations: 10000, seed: 42 },
    hestonInputs: { ...HESTON_DEFAULT, initial_volatility: 0.22, long_run_volatility: 0.22 },
  },
  {
    id: "high-vol-regime",
    name: "High Volatility Regime",
    category: "Volatility regime",
    description:
      "Stress-test-style preset: elevated volatility (≈45%). Demonstrates how option values and simulated path dispersion grow with σ.",
    appliesTo: ["pricing", "monte_carlo", "heston", "compare"],
    primaryTab: "monte_carlo",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.45,
    },
    treeInputs: { steps: 200, exercise_style: "european" },
    monteCarloInputs: { payoff_type: "european_call", steps: 252, simulations: 20000, seed: 42 },
    hestonInputs: {
      ...HESTON_DEFAULT,
      initial_volatility: 0.45,
      long_run_volatility: 0.45,
      vol_of_vol: 0.8,
    },
    warnings: ["High-volatility, high vol-of-vol parameters increase Monte Carlo dispersion."],
  },
  {
    id: "low-vol-regime",
    name: "Low Volatility Regime",
    category: "Volatility regime",
    description:
      "Model demonstration: a calm, low-volatility (≈10%) regime. Tighter distributions and smaller option premia.",
    appliesTo: ["pricing", "monte_carlo", "heston", "compare"],
    primaryTab: "monte_carlo",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.1,
    },
    treeInputs: { steps: 200, exercise_style: "european" },
    monteCarloInputs: { payoff_type: "european_call", steps: 252, simulations: 10000, seed: 42 },
    hestonInputs: {
      ...HESTON_DEFAULT,
      initial_volatility: 0.1,
      long_run_volatility: 0.1,
      vol_of_vol: 0.3,
    },
  },
  {
    id: "negative-skew-heston",
    name: "Negative Skew / Heston Leverage Effect",
    category: "Exercise & skew",
    description:
      "Model demonstration: strongly negative price/variance correlation (ρ = −0.8) and meaningful vol-of-vol, producing the equity leverage effect (downside skew).",
    appliesTo: ["heston", "surface", "compare"],
    primaryTab: "heston",
    baseInputs: {
      option_type: "put",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.2,
    },
    hestonInputs: {
      initial_volatility: 0.2,
      long_run_volatility: 0.22,
      kappa: 1.5,
      vol_of_vol: 0.6,
      rho: -0.8,
      steps: 252,
      simulations: 12000,
      seed: 42,
    },
    surfaceInputs: { base_vol: 0.2, skew: 0.25, smile: 0.35, term: 0.02 },
    educationalNotes: "Negative ρ raises downside (put) implied vols relative to upside calls.",
  },
  {
    id: "american-put-early-exercise",
    name: "American Put Early Exercise",
    category: "Exercise & skew",
    description:
      "Model demonstration: a deep-in-the-money American put where early exercise is optimal. Compare American vs European in Tree Pricing.",
    appliesTo: ["tree", "compare"],
    primaryTab: "tree",
    baseInputs: {
      option_type: "put",
      underlying_price: 70,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.25,
    },
    treeInputs: { steps: 200, exercise_style: "american" },
    educationalNotes: "American put ≥ European put; the early-exercise diagnostic should fire.",
  },
  {
    id: "asian-option-demo",
    name: "Asian Option Demo",
    category: "Path-dependent",
    description:
      "Model demonstration: an arithmetic-average Asian call. Averaging lowers effective volatility, so the Asian price sits below the vanilla call.",
    appliesTo: ["monte_carlo"],
    primaryTab: "monte_carlo",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.25,
    },
    monteCarloInputs: { payoff_type: "asian_call", steps: 252, simulations: 20000, seed: 42 },
    educationalNotes: "Path-dependent: more time steps refine the average.",
  },
  {
    id: "barrier-option-demo",
    name: "Barrier Option Demo",
    category: "Path-dependent",
    description:
      "Model demonstration: an up-and-out call with a knock-out barrier at 120. Barrier monitoring is discrete over the simulated steps.",
    appliesTo: ["monte_carlo"],
    primaryTab: "monte_carlo",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.2,
    },
    monteCarloInputs: {
      payoff_type: "up_and_out_call",
      steps: 252,
      simulations: 20000,
      seed: 42,
      barrier_price: 120,
    },
    warnings: ["Barrier monitoring is discrete over the simulated time steps."],
  },
  {
    id: "synthetic-vol-surface-demo",
    name: "Synthetic Vol Surface Demo",
    category: "Volatility research",
    description:
      "Model demonstration: a synthetic option chain (Black–Scholes + parametric skew/smile) for exploring the smile, term structure, and SVI fit — not live market data.",
    appliesTo: ["surface"],
    primaryTab: "surface",
    baseInputs: {
      option_type: "call",
      underlying_price: 100,
      strike: 100,
      time_to_expiry: 1,
      risk_free_rate: 0.05,
      dividend_yield: 0,
      volatility: 0.2,
    },
    surfaceInputs: { base_vol: 0.2, skew: 0.15, smile: 0.3, term: 0.02 },
    educationalNotes: "Generate the sample surface, then inspect the smile / SVI / heatmap.",
  },
];

export function getOptionsScenario(id: string): OptionsScenarioPreset | undefined {
  return OPTIONS_SCENARIOS.find((s) => s.id === id);
}
