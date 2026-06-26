/**
 * Portfolio Risk Lab formula groups (Phase 25.1).
 *
 * Extracted from the original Portfolio Risk Lab formula reference so the lab can
 * consume the shared, generalized `FormulaReference` component. Content is
 * unchanged — only the data shape was generalized (`items` → `formulas`).
 */

import type { FormulaGroup } from "@/components/math/formulaTypes";

export const PORTFOLIO_RISK_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Core portfolio risk",
    formulas: [
      { label: "Portfolio return", latex: "r_p = \\mathbf{w}^{\\top}\\boldsymbol{\\mu}", note: "Weighted average expected return." },
      { label: "Portfolio variance", latex: "\\sigma_p^2 = \\mathbf{w}^{\\top}\\Sigma\\mathbf{w}", note: "Covariance-aware total variance." },
      { label: "Portfolio volatility", latex: "\\sigma_p = \\sqrt{\\mathbf{w}^{\\top}\\Sigma\\mathbf{w}}", note: "Standard deviation of portfolio return." },
      { label: "Sharpe ratio", latex: "S = \\frac{r_p - r_f}{\\sigma_p}", note: "Excess return per unit of volatility." },
      { label: "Correlation", latex: "\\rho_{ij} = \\frac{\\Sigma_{ij}}{\\sigma_i\\sigma_j}", note: "Covariance normalised by volatilities." },
      { label: "Marginal risk contribution", latex: "\\mathrm{MCR} = \\frac{\\Sigma\\mathbf{w}}{\\sigma_p}", note: "Sensitivity of risk to each weight." },
      { label: "Component risk contribution", latex: "\\mathrm{CCR}_i = w_i \\cdot \\mathrm{MCR}_i", note: "Each asset's share of total risk." },
      { label: "Percent risk contribution", latex: "\\mathrm{PRC}_i = \\frac{\\mathrm{CCR}_i}{\\sigma_p}", note: "Component contribution as a fraction." },
      { label: "Historical VaR", latex: "\\mathrm{VaR}_c = -Q_{1-c}(r_p)", note: "Positive loss convention." },
      { label: "Historical CVaR / Expected Shortfall", latex: "\\mathrm{CVaR}_c = -\\mathbb{E}\\left[r_p \\mid r_p \\le Q_{1-c}(r_p)\\right]", note: "Expected loss beyond VaR." },
      { label: "Stress P&L", latex: "\\Delta P = \\sum_i w_i s_i", note: "Weighted sum of asset shocks." },
    ],
  },
  {
    title: "Factor risk model",
    formulas: [
      { label: "Portfolio factor exposure", latex: "\\boldsymbol{\\beta}_p = B^{\\top}\\mathbf{w}", note: "Weighted asset betas." },
      { label: "Factor variance", latex: "\\sigma_{\\mathrm{factor}}^2 = \\boldsymbol{\\beta}_p^{\\top}F\\boldsymbol{\\beta}_p", note: "Variance explained by factors." },
      { label: "Specific variance", latex: "\\sigma_{\\mathrm{specific}}^2 = \\mathbf{w}^{\\top}D\\mathbf{w}", note: "Idiosyncratic (residual) variance." },
      { label: "Total model variance", latex: "\\sigma_{\\mathrm{model}}^2 = \\sigma_{\\mathrm{factor}}^2 + \\sigma_{\\mathrm{specific}}^2", note: "Factor plus specific." },
      { label: "Factor risk contribution", latex: "\\mathrm{FRC}_f = \\frac{\\beta_{p,f}(F\\boldsymbol{\\beta}_p)_f}{\\sigma_{\\mathrm{model}}^2}", note: "Variance-share per factor." },
      { label: "Specific risk contribution", latex: "\\mathrm{SRC} = \\frac{\\sigma_{\\mathrm{specific}}^2}{\\sigma_{\\mathrm{model}}^2}", note: "Factor % + specific % = 1." },
      { label: "Scenario asset impact", latex: "\\Delta r_i = \\sum_f \\beta_{i,f}\\Delta f + \\epsilon_i", note: "Beta-weighted factor shocks plus a specific shock." },
      { label: "Scenario portfolio P&L", latex: "\\Delta r_p = \\sum_i w_i \\Delta r_i", note: "Weighted asset impacts." },
    ],
  },
  {
    title: "Optimization & Black-Litterman",
    formulas: [
      { label: "Mean-variance objective", latex: "\\max_{\\mathbf{w}} \\frac{\\mathbf{w}^{\\top}\\boldsymbol{\\mu} - r_f}{\\sqrt{\\mathbf{w}^{\\top}\\Sigma\\mathbf{w}}} \\quad \\mathrm{s.t.}\\quad \\sum_i w_i = 1,\\; 0 \\le w_i \\le w_{\\max}", note: "Maximise Sharpe under a long-only box constraint." },
      { label: "Black-Litterman implied returns", latex: "\\boldsymbol{\\pi} = \\delta \\Sigma \\mathbf{w}_{\\mathrm{mkt}}", note: "Market-implied equilibrium returns." },
      { label: "Black-Litterman posterior returns", latex: "\\boldsymbol{\\mu}_{BL} = \\left[(\\tau\\Sigma)^{-1} + P^{\\top}\\Omega^{-1}P\\right]^{-1}\\left[(\\tau\\Sigma)^{-1}\\boldsymbol{\\pi} + P^{\\top}\\Omega^{-1}\\mathbf{q}\\right]", note: "Prior blended with views." },
      { label: "Turnover", latex: "\\mathrm{Turnover} = \\frac{1}{2}\\sum_i \\left|w_i^{\\mathrm{target}} - w_i^{\\mathrm{current}}\\right|", note: "Half the sum of absolute weight changes." },
    ],
  },
  {
    title: "Monte Carlo & robustness",
    formulas: [
      { label: "Daily Monte Carlo return", latex: "r_t \\sim \\mathcal{N}\\left(\\frac{\\mu_p}{252}, \\frac{\\sigma_p^2}{252}\\right)", note: "Parametric Gaussian draw (fixed seed)." },
      { label: "Wealth path", latex: "W_t = W_0 \\prod_{s=1}^{t}(1 + r_s)", note: "Compounded portfolio wealth." },
      { label: "Drawdown", latex: "DD_t = \\frac{W_t}{\\max_{0 \\le s \\le t} W_s} - 1", note: "Decline from the running peak." },
      { label: "Maximum drawdown", latex: "\\mathrm{MDD} = \\min_t DD_t", note: "Worst peak-to-trough decline." },
      { label: "Probability of loss", latex: "\\mathbb{P}(W_T < W_0)", note: "Share of paths ending below the start." },
      { label: "Probability of drawdown breach", latex: "\\mathbb{P}(\\mathrm{MDD} \\le d^*)", note: "Share of paths breaching the threshold." },
    ],
  },
];
