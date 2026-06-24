"""Futures supervised-label layer (Phase 3).

Commit 1 ships the label config + basic return-based labels: ``LabelSpec``, the
enums, the default ES label registry, ``label_config_hash``, and
``build_label_matrix`` (forward-return / direction / vol-adjusted). Dataset
assembly, signals, and the backtest adapter land in later commits.
"""

from app.labels.spec import (
    DEFAULT_ES_LABELS,
    LabelError,
    LabelSpec,
    LabelType,
    PriceSpace,
    ReturnType,
    label_config_hash,
)
from app.labels.futures_labels import build_label_matrix

__all__ = [
    "LabelSpec",
    "LabelType",
    "ReturnType",
    "PriceSpace",
    "LabelError",
    "DEFAULT_ES_LABELS",
    "label_config_hash",
    "build_label_matrix",
]
