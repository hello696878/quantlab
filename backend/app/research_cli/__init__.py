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

__all__ = [
    "SyntheticDataConfig",
    "ExperimentConfig",
    "resolve_artifact_base_dir",
    "generate_synthetic_es_raw",
    "ExperimentResult",
    "run_es_ml_experiment",
]
