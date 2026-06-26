"""QuantLab experiment registry (Phase 5).

Commit 1 ships the ``ExperimentRun`` metadata schema, the ``ExperimentError``
exception, and a best-effort git-commit helper.  No artifact store, no registry
I/O, and no file writes yet (those land in later commits).
"""

from app.experiments.spec import (
    ExperimentError,
    ExperimentRun,
    best_effort_git_commit,
)
from app.experiments.store import ExperimentStore
from app.experiments.registry import (
    LoadedExperiment,
    compare_experiments,
    get_best_experiment,
    list_experiments,
    load_experiment_run,
    save_experiment_run,
)
from app.experiments.reports import summarize_experiment

__all__ = [
    "ExperimentRun",
    "ExperimentError",
    "best_effort_git_commit",
    "ExperimentStore",
    # registry
    "LoadedExperiment",
    "load_experiment_run",
    "list_experiments",
    "compare_experiments",
    "get_best_experiment",
    "save_experiment_run",
    # reports
    "summarize_experiment",
]
