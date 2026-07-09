"""Phase 11 — local experiment batch / sweep orchestration.

The config layer (``LocalExperimentBatchConfig`` + ``expand_grid``) turns a base
:class:`~app.local_pipeline.config.LocalExperimentConfig` and a sweep ``grid`` into
a deterministic list of validated configs.  The runner
(``run_local_experiment_batch``) executes that list sequentially through the
existing Phase 9 pipeline, saving successful runs via ``ExperimentStore`` and
recording per-item status / errors, with a ``batch_config_hash`` manifest
fingerprint (not an ML lineage hash).  The CLI and Phase 10 comparison wiring land
in a later commit.
"""

from app.batch_experiments.config import (
    BatchError,
    LocalExperimentBatchConfig,
    batch_item_id,
    expand_grid,
)
from app.batch_experiments.runner import (
    LocalExperimentBatchItem,
    LocalExperimentBatchResult,
    batch_config_hash,
    run_local_experiment_batch,
    summarize_batch_result,
)

__all__ = [
    # config layer
    "BatchError",
    "LocalExperimentBatchConfig",
    "batch_item_id",
    "expand_grid",
    # runner layer
    "LocalExperimentBatchItem",
    "LocalExperimentBatchResult",
    "batch_config_hash",
    "run_local_experiment_batch",
    "summarize_batch_result",
]
