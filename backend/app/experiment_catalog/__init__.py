"""Phase 12 — read-only experiment catalog over persisted ``ExperimentStore`` runs.

Commit 1 ships the catalog core only: ``ExperimentCatalogRow`` (stable, JSON-safe
rows built from persisted ``ExperimentRun`` metadata), ``ExperimentCatalogFilter``
+ ``filter_experiment_catalog`` (safe, order-preserving filtering), and
``build_experiment_catalog`` / ``list_experiment_runs`` (discovery delegated to
the existing experiments registry).  The leaderboard, compatibility grouping,
exporters, and CLI land in later commits.  Read-only: nothing here runs,
retrains, or writes anything.
"""

from app.experiment_catalog.catalog import (
    CatalogError,
    ExperimentCatalogFilter,
    ExperimentCatalogRow,
    build_experiment_catalog,
    filter_experiment_catalog,
    list_experiment_runs,
)

__all__ = [
    "CatalogError",
    "ExperimentCatalogFilter",
    "ExperimentCatalogRow",
    "build_experiment_catalog",
    "filter_experiment_catalog",
    "list_experiment_runs",
]
