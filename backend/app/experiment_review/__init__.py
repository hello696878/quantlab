"""Phase 14 — read-only local experiment evidence pack.

The models layer supplies the evidence-pack dataclasses (``ExperimentEvidencePack`` /
``ExperimentRunEvidence`` / ``ComparisonEvidence`` / ``CatalogRunContext`` /
``ArtifactInventoryEntry`` / ``EvidenceSummary``), the Phase 14 aggregation
``EvidenceFinding`` (``evidence_`` namespace, distinct from Phase 13's ``finding_``
findings), the completeness / status enums, the JSON-safety and evidence-safe
serialization helpers, and the completeness-derivation utilities.  Phase 13 findings
are stored verbatim in memory and made evidence-safe only on serialization.

``collect_experiment_evidence_pack`` builds a pack read-only from an existing store;
the renderers turn one into deterministic JSON / CSV / Markdown strings.  Nothing in
this package writes to the filesystem, opens a database, or mints a hash — only the
CLI, in a later commit, writes to explicit output paths.
"""

from app.experiment_review.collect import collect_experiment_evidence_pack
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
from app.experiment_review.render import (
    EVIDENCE_DISCLAIMERS,
    export_evidence_pack_csv,
    export_evidence_pack_json,
    export_evidence_pack_markdown,
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
    # collector
    "collect_experiment_evidence_pack",
    # renderers
    "EVIDENCE_DISCLAIMERS",
    "export_evidence_pack_json",
    "export_evidence_pack_csv",
    "export_evidence_pack_markdown",
]
