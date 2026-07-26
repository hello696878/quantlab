"""
Market Regime Robustness & Conditional Performance Diagnostics Lab
(Phase 54.0).

Local-first research diagnostics that condition candidate outcomes on
explicitly defined market regimes — volatility, trend, liquidity, drawdown
state, user-supplied categorical states, and bounded combined regimes — with
a strict **no-look-ahead policy**: every regime label is formed from trailing
windows with an explicit availability lag, threshold-fitting subsets carry
distinct integrity states (verified-causal, verified-from-validation-split,
declared, full-sample-descriptive, invalid), and centered/future windows are
rejected outright.  Conditional metrics, coverage, rank stability across
regimes, concentration, and transition diagnostics are all deterministic,
bounded, and neutrally worded.

Honest scope: regimes are descriptive research states — never predictions;
conditional statistics never prove causality, profitability, or safety; no
regime or candidate is ever selected, switched to, or recommended.
"""

EXPORT_SCHEMA_VERSION = "regime_diagnostics_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
