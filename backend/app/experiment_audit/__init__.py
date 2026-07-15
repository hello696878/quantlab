"""Phase 13 — read-only ExperimentStore structural integrity audit.

Commit 1 ships the models layer only: the finding / result dataclasses
(``AuditFinding`` / ``ExperimentRunAudit`` / ``ExperimentStoreAuditResult``), the
severity / code / status enums, deterministic finding utilities
(``sort_and_number_findings`` etc.), and audit-scoped path / frame contract
helpers (``is_safe_relative_artifact_path`` etc.) that model the current
``ExperimentStore`` layout **without importing its private internals**.  The audit
engine, renderers, and CLI land in later commits.  This layer performs no
filesystem access and mints no hashes.
"""

from app.experiment_audit.audit import (
    audit_experiment_run,
    audit_experiment_store,
    summarize_audit_result,
)
from app.experiment_audit.render import (
    AUDIT_DISCLAIMERS,
    export_audit_csv,
    export_audit_json,
    export_audit_markdown,
)
from app.experiment_audit.models import (
    CANONICAL_ARTIFACT_KEYS,
    CANONICAL_FRAME_NAMES,
    IGNORED_OS_FILES,
    AuditCode,
    AuditError,
    AuditFinding,
    AuditLevel,
    AuditOverallStatus,
    AuditRunStatus,
    AuditSeverity,
    ExperimentRunAudit,
    ExperimentStoreAuditResult,
    finding_sort_key,
    has_parent_traversal,
    is_absolute_artifact_path,
    is_canonical_artifact_filename,
    is_safe_relative_artifact_path,
    overall_status_for,
    severity_at_least,
    severity_rank,
    sort_and_number_findings,
    status_for_findings,
)

__all__ = [
    # models
    "AuditError",
    "AuditSeverity",
    "AuditCode",
    "AuditRunStatus",
    "AuditOverallStatus",
    "AuditLevel",
    "AuditFinding",
    "ExperimentRunAudit",
    "ExperimentStoreAuditResult",
    "finding_sort_key",
    "sort_and_number_findings",
    "severity_rank",
    "severity_at_least",
    "status_for_findings",
    "overall_status_for",
    "is_absolute_artifact_path",
    "has_parent_traversal",
    "is_safe_relative_artifact_path",
    "is_canonical_artifact_filename",
    "CANONICAL_ARTIFACT_KEYS",
    "CANONICAL_FRAME_NAMES",
    "IGNORED_OS_FILES",
    # engine
    "audit_experiment_run",
    "audit_experiment_store",
    "summarize_audit_result",
    # renderers
    "AUDIT_DISCLAIMERS",
    "export_audit_json",
    "export_audit_csv",
    "export_audit_markdown",
]
