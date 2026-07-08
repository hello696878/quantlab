"""Phase 11 — local experiment batch / sweep orchestration.

Commit 1 ships the *config layer only*: ``LocalExperimentBatchConfig`` (a base
:class:`~app.local_pipeline.config.LocalExperimentConfig` plus a sweep ``grid``)
and ``expand_grid`` (deterministic cartesian expansion into validated configs),
with ``BatchError`` for batch-spec failures and ``batch_item_id`` for stable ids.
The runner, CLI, and the optional ``batch_config_hash`` manifest fingerprint land
in later commits.
"""

from app.batch_experiments.config import (
    BatchError,
    LocalExperimentBatchConfig,
    batch_item_id,
    expand_grid,
)

__all__ = [
    "BatchError",
    "LocalExperimentBatchConfig",
    "batch_item_id",
    "expand_grid",
]
