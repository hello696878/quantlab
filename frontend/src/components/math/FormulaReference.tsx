"use client";

/**
 * Portfolio Risk Lab formula reference — LaTeX rendered locally with KaTeX
 * (no CDN, no remote scripts, no external render API).
 *
 * `SafeMath` renders display math via `katex.renderToString` with
 * `throwOnError: false` and a try/catch fallback to a styled raw-LaTeX code
 * block, so a malformed formula can never crash the page.
 */

import katex from "katex";

interface FormulaItem {
  label: string;
  latex: string;
  note?: string;
}

interface FormulaGroup {
  title: string;
  items: FormulaItem[];
}

export const FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Core portfolio risk",
    items: [
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
    items: [
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
    items: [
      { label: "Mean-variance objective", latex: "\\max_{\\mathbf{w}} \\frac{\\mathbf{w}^{\\top}\\boldsymbol{\\mu} - r_f}{\\sqrt{\\mathbf{w}^{\\top}\\Sigma\\mathbf{w}}} \\quad \\mathrm{s.t.}\\quad \\sum_i w_i = 1,\\; 0 \\le w_i \\le w_{\\max}", note: "Maximise Sharpe under a long-only box constraint." },
      { label: "Black-Litterman implied returns", latex: "\\boldsymbol{\\pi} = \\delta \\Sigma \\mathbf{w}_{\\mathrm{mkt}}", note: "Market-implied equilibrium returns." },
      { label: "Black-Litterman posterior returns", latex: "\\boldsymbol{\\mu}_{BL} = \\left[(\\tau\\Sigma)^{-1} + P^{\\top}\\Omega^{-1}P\\right]^{-1}\\left[(\\tau\\Sigma)^{-1}\\boldsymbol{\\pi} + P^{\\top}\\Omega^{-1}\\mathbf{q}\\right]", note: "Prior blended with views." },
      { label: "Turnover", latex: "\\mathrm{Turnover} = \\frac{1}{2}\\sum_i \\left|w_i^{\\mathrm{target}} - w_i^{\\mathrm{current}}\\right|", note: "Half the sum of absolute weight changes." },
    ],
  },
  {
    title: "Monte Carlo & robustness",
    items: [
      { label: "Daily Monte Carlo return", latex: "r_t \\sim \\mathcal{N}\\left(\\frac{\\mu_p}{252}, \\frac{\\sigma_p^2}{252}\\right)", note: "Parametric Gaussian draw (fixed seed)." },
      { label: "Wealth path", latex: "W_t = W_0 \\prod_{s=1}^{t}(1 + r_s)", note: "Compounded portfolio wealth." },
      { label: "Drawdown", latex: "DD_t = \\frac{W_t}{\\max_{0 \\le s \\le t} W_s} - 1", note: "Decline from the running peak." },
      { label: "Maximum drawdown", latex: "\\mathrm{MDD} = \\min_t DD_t", note: "Worst peak-to-trough decline." },
      { label: "Probability of loss", latex: "\\mathbb{P}(W_T < W_0)", note: "Share of paths ending below the start." },
      { label: "Probability of drawdown breach", latex: "\\mathbb{P}(\\mathrm{MDD} \\le d^*)", note: "Share of paths breaching the threshold." },
    ],
  },
];

/** Grouped, copyable LaTeX source (not rendered HTML). */
export const FORMULA_LATEX_TEXT = FORMULA_GROUPS.map((group) => {
  const rows = group.items
    .map((it) => `${it.label}:\n${it.latex}`)
    .join("\n\n");
  return `${group.title}\n\n${rows}`;
}).join("\n\n---\n\n");

/** Render display math with KaTeX; fall back to raw LaTeX on any failure. */
function SafeMath({ latex }: { latex: string }) {
  let html: string | null = null;
  try {
    html = katex.renderToString(latex, {
      displayMode: true,
      throwOnError: false,
    });
  } catch {
    html = null;
  }
  if (html) {
    return (
      <div
        className="ql-math"
        style={{ color: "var(--text-hi)" }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }
  return (
    <code
      className="mono block overflow-x-auto rounded px-2 py-1 text-[12px]"
      style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
    >
      {latex}
    </code>
  );
}

function FormulaRow({ item }: { item: FormulaItem }) {
  return (
    <div
      className="rounded-lg px-3 py-2"
      style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
    >
      <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
        {item.label}
      </p>
      <div className="mt-0.5">
        <SafeMath latex={item.latex} />
      </div>
      {item.note && (
        <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>
          {item.note}
        </p>
      )}
    </div>
  );
}

/** The full grouped, LaTeX-rendered formula reference. */
export default function FormulaReference() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {FORMULA_GROUPS.map((group) => (
        <section key={group.title} aria-label={group.title}>
          <p className="section-title mb-2">{group.title}</p>
          <div className="space-y-2">
            {group.items.map((item) => (
              <FormulaRow key={item.label} item={item} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
