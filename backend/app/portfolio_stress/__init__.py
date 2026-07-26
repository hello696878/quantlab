"""
Portfolio Stress Testing, Scenario Shock and Drawdown Attribution Lab (v1).

Local-first research diagnostics that apply explicit, deterministic stress
scenarios to STORED Phase 56 portfolio weights and attribute measured
portfolio losses, drawdowns, risk changes and cost effects: asset/group
price shocks with documented precedence, volatility and correlation stress
with PSD validation and never-silent repair, stressed risk recomputation
reconciled against baselines, liquidity/cost stress over linked Phase 55
assumptions, trailing-only historical drawdown episodes with per-asset
attribution, and bounded sensitivity surfaces.

The lab is NOT a prediction of future losses, a guarantee of worst-case
loss, regulatory stress testing, capital adequacy analysis, automatic
hedging or reallocation, trade execution, proof of safety or robustness,
or investment advice.  Every output is a measured consequence of explicit
configured assumptions, and no linked record is ever modified.
"""

EXPORT_SCHEMA_VERSION = "portfolio_stress_export_v1"
