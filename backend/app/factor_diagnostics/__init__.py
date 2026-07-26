"""
Factor Exposure, Return Decomposition and Macro Sensitivity Diagnostics (v1).

Measures explicit sensitivities of ONE declared return series to SUPPLIED
factor and macro observations under a stated timing rule.  Everything the
lab reports is a measurement under the configured model, never a causal,
predictive or economic claim: a coefficient is a least-squares sensitivity,
an intercept is the model's unexplained mean under the stated specification
(never called alpha without that qualification), and a residual is what the
specification did not explain.

The lab does NOT prove causality, prove alpha, prove manager skill, predict
future returns, recommend factor exposure, recommend a macro trade,
recommend a portfolio, execute trades, provide investment advice or certify
a factor model.  No market or macroeconomic data is ever fetched: every
observation is supplied locally.
"""

EXPORT_SCHEMA_VERSION = "factor_diagnostics_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
