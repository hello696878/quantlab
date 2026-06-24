"""Futures feature engineering layer (Phase 2).

Commit 1 ships the declarative config + validation only: ``FeatureSpec``, the
enums, the default ES feature registry (specs, no math), the feature config
hash, and input/spec validation. Feature computation lands in later commits.
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

__all__ = [
    "FeatureSpec",
    "TransformType",
    "PriceSpace",
    "FeatureError",
    "DEFAULT_ES_FEATURES",
    "feature_config_hash",
    "validate_continuous_input",
    "validate_feature_specs",
]
