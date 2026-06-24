"""Futures supervised-label layer (Phase 3).

Ships the label config + return-based labels (`LabelSpec`, enums, the default ES
label registry, `label_config_hash`, `build_label_matrix`) and the supervised
`build_supervised_dataset` assembler (features + labels + provenance + trainable
flags). Signals and the backtest adapter land in later commits.
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
from app.labels.dataset import DatasetError, build_supervised_dataset

__all__ = [
    "LabelSpec",
    "LabelType",
    "ReturnType",
    "PriceSpace",
    "LabelError",
    "DEFAULT_ES_LABELS",
    "label_config_hash",
    "build_label_matrix",
    "DatasetError",
    "build_supervised_dataset",
]
