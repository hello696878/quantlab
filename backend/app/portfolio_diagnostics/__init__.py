"""
Portfolio Construction, Risk Budgeting, Diversification and Constraint
Diagnostics Lab (v1).

Local-first research diagnostics that construct and evaluate portfolio
weights under explicit covariance, risk-budget, exposure, turnover and
concentration assumptions: strict no-look-ahead estimation windows,
transparent solvers with independent post-solve constraint checks,
marginal / component / percentage risk contributions reconciled against
portfolio volatility, concentration and diversification descriptions,
cost-aware turnover diagnostics via linked Phase 55 cost models, and
regime-conditioned summaries via stored Phase 54 assignments.

The lab is NOT a live portfolio manager, broker, or execution system.  It
never applies weights anywhere, never recommends an allocation, never
identifies an optimal or safest portfolio, and never guarantees
diversification, risk reduction, or performance.  Every output is a
research measurement under configured assumptions.
"""

EXPORT_SCHEMA_VERSION = "portfolio_diagnostics_export_v1"
