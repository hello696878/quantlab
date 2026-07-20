"""Phase 14 — read-only local experiment evidence pack.

Commit 1 ships the models layer only: the evidence-pack dataclasses
(``ExperimentEvidencePack`` / ``ExperimentRunEvidence`` / ``ComparisonEvidence`` /
``CatalogRunContext`` / ``ArtifactInventoryEntry`` / ``EvidenceSummary``), the
Phase 14 aggregation ``EvidenceFinding`` (``evidence_`` namespace, distinct from
Phase 13's ``finding_`` findings), the completeness / status enums, the JSON-safety
helpers (``freeze_json_value`` / ``thaw_json_value`` / ``sanitize_json_value``), and
the completeness-derivation utilities.  Phase 13 ``AuditFinding`` objects are stored
verbatim.  This layer performs no filesystem access, opens no database, and mints no
hashes; the collector, renderers, and CLI land in later commits.
"""

from app.experiment_review.models import (
    ArtifactInventoryEntry,
    CatalogRunContext,
    ComparisonEvidence,
    EvidenceCode,
    EvidenceCompleteness,
    EvidenceComparisonStatus,
    EvidenceContextStatus,
    EvidenceError,
    EvidenceFinding,
    EvidenceLoadStatus,
    EvidenceSeverity,
    EvidenceSummary,
    ExperimentEvidencePack,
    ExperimentRunEvidence,
    dedupe_preserve_order,
    derive_pack_completeness,
    derive_run_completeness,
    evidence_finding_sort_key,
    evidence_severity_at_least,
    evidence_severity_rank,
    freeze_json_value,
    sanitize_json_value,
    sort_and_number_evidence_findings,
    thaw_json_value,
)

__all__ = [
    "EvidenceError",
    "EvidenceSeverity",
    "EvidenceCode",
    "EvidenceCompleteness",
    "EvidenceLoadStatus",
    "EvidenceContextStatus",
    "EvidenceComparisonStatus",
    "EvidenceFinding",
    "ArtifactInventoryEntry",
    "CatalogRunContext",
    "ComparisonEvidence",
    "ExperimentRunEvidence",
    "EvidenceSummary",
    "ExperimentEvidencePack",
    "freeze_json_value",
    "thaw_json_value",
    "sanitize_json_value",
    "dedupe_preserve_order",
    "evidence_finding_sort_key",
    "sort_and_number_evidence_findings",
    "evidence_severity_rank",
    "evidence_severity_at_least",
    "derive_run_completeness",
    "derive_pack_completeness",
]
