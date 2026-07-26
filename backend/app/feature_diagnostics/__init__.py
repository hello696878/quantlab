"""
Feature Importance, Stability and Drift Diagnostics Lab (Phase 52.0).

Local-first research lab: held-out permutation importance as the primary
method (deterministic seeds, bounded repeats), model-native impurity and
coefficient magnitudes as clearly-labelled training-data references, rank
stability across validation splits, bounded correlated-feature grouping, and
feature distribution / importance drift diagnostics.

Dependency-light by design: deterministic numpy estimators (logistic,
ridge-linear, bounded CART tree) fitted in-process — no scikit-learn, no
SHAP, no pickle/joblib, no model files, no network.

Honest scope: importance is a measured sensitivity under one method and one
metric — never causality, profitability, or a recommendation to keep or
delete a feature.
"""

EXPORT_SCHEMA_VERSION = "feature_diagnostics_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
