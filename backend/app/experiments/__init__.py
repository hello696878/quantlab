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

__all__ = [
    "ExperimentRun",
    "ExperimentError",
    "best_effort_git_commit",
    "ExperimentStore",
]
