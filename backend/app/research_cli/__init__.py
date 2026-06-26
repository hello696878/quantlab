"""Research CLI / demo runner (Phase 6).

Commit 1 ships the experiment configuration and the deterministic synthetic ES
raw-data generator.  No pipeline run, no CLI, no artifact writing yet (those land
in later commits).  Synthetic only; no network; no new model types; no sklearn.
"""

from app.research_cli.config import (
    ExperimentConfig,
    SyntheticDataConfig,
    resolve_artifact_base_dir,
)
from app.research_cli.synthetic import generate_synthetic_es_raw
from app.research_cli.pipeline import ExperimentResult, run_es_ml_experiment

# NOTE: ``app.research_cli.cli`` is intentionally **not** imported here.  Eagerly
# importing it would put the module in ``sys.modules`` before ``python -m
# app.research_cli.cli`` executes it, triggering a RuntimeWarning.  Import ``main``
# directly from ``app.research_cli.cli`` when you need it.

__all__ = [
    "SyntheticDataConfig",
    "ExperimentConfig",
    "resolve_artifact_base_dir",
    "generate_synthetic_es_raw",
    "ExperimentResult",
    "run_es_ml_experiment",
]
