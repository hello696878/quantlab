"""
Experiment reporting (Phase 10).

A read-only reporting / rendering layer over persisted Phase 5 ``ExperimentRun``
artifacts (generic — works for Phase 6 Research CLI runs and Phase 9 local runs).
It **wraps** the existing ``compare_experiments`` / ``get_best_experiment`` /
``summarize_experiment`` helpers and adds deterministic Markdown / CSV / JSON
renderers with standing disclaimers.  It does not retrain, add metrics, or change
the ``ExperimentRun`` schema.
"""

from app.reporting.render import (
    DISCLAIMERS,
    export_experiment_comparison_csv,
    export_experiment_comparison_json,
    export_experiment_report_json,
    render_experiment_report_markdown,
)
from app.reporting.summary import (
    ExperimentComparisonRow,
    ExperimentRunSummary,
    best_experiment_run,
    compare_experiment_runs,
    summarize_experiment_run,
)

__all__ = [
    "ExperimentRunSummary",
    "ExperimentComparisonRow",
    "summarize_experiment_run",
    "compare_experiment_runs",
    "best_experiment_run",
    "DISCLAIMERS",
    "render_experiment_report_markdown",
    "export_experiment_report_json",
    "export_experiment_comparison_csv",
    "export_experiment_comparison_json",
]
