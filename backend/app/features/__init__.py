"""Futures feature engineering layer (Phase 2).

Declarative config + validation (``FeatureSpec``, enums, the default ES feature
registry, the feature config hash) plus the leakage-safe ``build_feature_matrix``
builder. Commit 2 implements the basic price/return/volatility/rolling features;
the remaining transforms land in later commits.
"""

from app.features.spec import (
    DEFAULT_ES_FEATURES,
    FeatureError,
    FeatureSpec,
    PriceSpace,
    TransformType,
    feature_config_hash,
)
from app.features.validation import (
    validate_continuous_input,
    validate_feature_specs,
)
from app.features.futures_features import build_feature_matrix

__all__ = [
    "FeatureSpec",
    "TransformType",
    "PriceSpace",
    "FeatureError",
    "DEFAULT_ES_FEATURES",
    "feature_config_hash",
    "validate_continuous_input",
    "validate_feature_specs",
    "build_feature_matrix",
]
