"""Phase 12 — read-only experiment catalog over persisted ``ExperimentStore`` runs.

The catalog core (``ExperimentCatalogRow`` / ``ExperimentCatalogFilter`` /
``build_experiment_catalog`` / ``filter_experiment_catalog``) turns persisted
``ExperimentRun`` metadata into deterministic, JSON-safe rows and filters them
safely, with discovery delegated to the existing experiments registry.  The
leaderboard layer (``rank_experiment_catalog`` + ``ExperimentLeaderboardSpec``),
compatibility grouping (``group_compatible_runs``), and the deterministic
CSV / JSON / Markdown exporters are pure functions over those rows — descriptive
only.  Read-only: nothing here runs, retrains, or writes anything; the CLI lands
in a later commit.
"""

from app.experiment_catalog.catalog import (
    CatalogError,
    ExperimentCatalogFilter,
    ExperimentCatalogRow,
    build_experiment_catalog,
    filter_experiment_catalog,
    list_experiment_runs,
)
from app.experiment_catalog.leaderboard import (
    ExperimentCompatibilityGroup,
    ExperimentLeaderboardSpec,
    export_catalog_csv,
    export_catalog_json,
    export_catalog_markdown,
    group_compatible_runs,
    rank_experiment_catalog,
)

__all__ = [
    # catalog core
    "CatalogError",
    "ExperimentCatalogFilter",
    "ExperimentCatalogRow",
    "build_experiment_catalog",
    "filter_experiment_catalog",
    "list_experiment_runs",
    # leaderboard / grouping / exporters
    "ExperimentCompatibilityGroup",
    "ExperimentLeaderboardSpec",
    "export_catalog_csv",
    "export_catalog_json",
    "export_catalog_markdown",
    "group_compatible_runs",
    "rank_experiment_catalog",
]
