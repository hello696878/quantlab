"""
Meta-Labeling, Probability Calibration & Decision Threshold Lab (Phase 51.0).

A **local-first** research lab evaluating a secondary meta-label layer on top
of an existing primary signal: was the primary direction correct under a
documented outcome rule, are predicted probabilities reliable (calibration),
and how do decision thresholds trade coverage against precision/recall?

Priorities: leakage prevention (out-of-fold calibration via Model Validation
split memberships), calibration integrity (fit on train only), transparent
threshold trade-offs, and neutral interpretation.

Honest scope: meta-label 1 means the documented research outcome condition was
met — never that a trade would be profitable in production.  The lab trains no
trading strategy, sizes no positions, executes nothing, selects no "best"
model or threshold, and is not scientific certification or regulatory
validation.  Nothing here is investment, trading, or risk advice.
"""

from __future__ import annotations

EXPORT_SCHEMA_VERSION = "meta_labeling_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
