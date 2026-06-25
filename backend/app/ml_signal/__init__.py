"""ML Signal Lab (Phase 4) — ModelSpec, provenance hashes, and split utilities.

Commit 1 ships configuration + leakage-safe splitting only.  No model training,
no prediction, no backtest evaluation, and deliberately no scikit-learn.  The
package is named ``ml_signal`` to stay distinct from the Phase 3 ``app.signals``
baseline package and the ``app.finml`` methodology toolkit it reuses.
"""

from app.ml_signal.spec import (
    ClassWeight,
    MlSignalError,
    ModelSpec,
    ModelType,
    SampleWeight,
    SignalMode,
    SplitType,
    TaskType,
    ThresholdRule,
    dataset_config_hash,
    model_config_hash,
    train_run_hash,
)
from app.ml_signal.splits import (
    PurgedFold,
    Split,
    chronological_holdout_split,
    purged_kfold_splits,
    walk_forward_splits,
)
from app.ml_signal.models import (
    BaseModel,
    DummyBaseline,
    LogisticRegression,
    RidgeRegression,
    build_model,
)
from app.ml_signal.training import (
    TrainedModel,
    select_design_matrix,
    select_features,
    train_model,
)
from app.ml_signal.prediction import (
    PredictionSignalConfig,
    predict_model,
    prediction_to_signal,
)

__all__ = [
    # spec + enums
    "ModelSpec",
    "ModelType",
    "TaskType",
    "ThresholdRule",
    "ClassWeight",
    "SampleWeight",
    "SplitType",
    "SignalMode",
    "MlSignalError",
    # hashes
    "dataset_config_hash",
    "model_config_hash",
    "train_run_hash",
    # splits
    "Split",
    "PurgedFold",
    "chronological_holdout_split",
    "walk_forward_splits",
    "purged_kfold_splits",
    # models
    "BaseModel",
    "DummyBaseline",
    "RidgeRegression",
    "LogisticRegression",
    "build_model",
    # training
    "TrainedModel",
    "train_model",
    "select_design_matrix",
    "select_features",
    # prediction -> signal
    "PredictionSignalConfig",
    "predict_model",
    "prediction_to_signal",
]
