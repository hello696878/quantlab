"""
Backtest Overfitting, PBO, Deflated Sharpe & Multiple Testing Diagnostics Lab
(Phase 53.0).

Local-first research diagnostics for selection bias across a bounded universe
of candidate strategies/configurations: Combinatorially Symmetric
Cross-Validation (CSCV) with the Probability of Backtest Overfitting (PBO),
the Probabilistic and Deflated Sharpe Ratios with an explicit
expected-maximum-Sharpe benchmark, Minimum Track Record Length,
Bonferroni / Holm / Benjamini–Hochberg multiple-testing corrections with
p-value provenance, and bounded candidate-dependence diagnostics — all
deterministic, dependency-light (numpy/scipy only), and conservatively
worded.

Honest scope: every number here is a research statistic under stated
assumptions — never proof of profitability, robustness, or safety; no
candidate is ever selected, recommended, deployed, or allocated capital.
"""

EXPORT_SCHEMA_VERSION = "overfitting_diagnostics_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
