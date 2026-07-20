"""
Phase 14 (commit 1) — evidence-pack data models, aggregation findings, JSON-safety
helpers, and completeness-derivation utilities.

This module is **pure**: it performs no filesystem access of any kind (no reads,
no writes, no ``stat``), opens no database, and mints no hashes.  It aggregates
*existing* evidence — Phase 13 ``AuditFinding`` objects are stored **verbatim**
(original ids / codes / severities preserved and serialized through their own
public ``to_dict()``); Phase 14's own aggregation findings live in a **separate
namespace** (``evidence_0000`` …), never colliding with Phase 13's
``finding_0000`` ids.

The only ``app.*`` dependency is the minimal public Phase 13 model surface
(``AuditFinding`` / ``AuditRunStatus``) needed to preserve audit-finding semantics
without lossy conversion.  It imports nothing from the reporting / catalog /
registry / dataset-lineage / db / pipeline packages, and no store-implementation
type.  Metrics and other dynamic dictionaries are held as an immutable, key-sorted,
strict-JSON-safe representation (``NaN`` / ``Infinity`` → ``None``).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, fields, replace
from enum import Enum
from typing import Any, Optional, Sequence

from app.experiment_audit import AuditFinding, AuditRunStatus

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


class EvidenceError(ValueError):
    """Invalid evidence-model construction or invalid completeness-policy input."""


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #


class EvidenceSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceCode(str, Enum):
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RUN_UNLOADABLE = "RUN_UNLOADABLE"
    COMPARISON_UNAVAILABLE = "COMPARISON_UNAVAILABLE"
    INCOMPATIBLE_SELECTED_RUNS = "INCOMPATIBLE_SELECTED_RUNS"
    REQUESTED_METRIC_MISSING = "REQUESTED_METRIC_MISSING"
    CATALOG_CONTEXT_UNAVAILABLE = "CATALOG_CONTEXT_UNAVAILABLE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


class EvidenceCompleteness(str, Enum):
    COMPLETE = "complete"
    WARNING = "warning"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class EvidenceLoadStatus(str, Enum):
    LOADED = "loaded"
    UNLOADABLE = "unloadable"
    UNAVAILABLE = "unavailable"


class EvidenceContextStatus(str, Enum):
    COLLECTED = "collected"
    NOT_COLLECTED = "not_collected"
    UNAVAILABLE = "unavailable"


class EvidenceComparisonStatus(str, Enum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


# Audit statuses an ExperimentRunEvidence may carry: the Phase 13 run statuses
# (verbatim vocabulary) plus "unavailable" for a run that could not be audited.
_ALLOWED_AUDIT_STATUSES: frozenset[str] = frozenset(
    {AuditRunStatus.VALID.value, AuditRunStatus.WARNING.value, AuditRunStatus.INVALID.value, "unavailable"}
)

# Phase 13 severities that make a run structurally incomplete.
_AUDIT_BLOCKING_SEVERITIES: frozenset[str] = frozenset({"error", "critical"})

_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|^[\\/]")


# --------------------------------------------------------------------------- #
# JSON-safe immutable representation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FrozenMap:
    """Immutable, key-sorted mapping representation (distinguishes objects from
    arrays so freeze/thaw round-trips unambiguously)."""

    items: tuple[tuple[str, Any], ...]


def _json_safe_scalar(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def freeze_json_value(value: Any) -> Any:
    """Immutable, deterministic, strict-JSON-safe copy of ``value``.

    Mappings become key-sorted ``_FrozenMap``; lists/tuples become tuples; non-finite
    floats become ``None``; str / int / bool / None pass through.  Any other type
    (e.g. ``pathlib.Path``, ``datetime``) raises :class:`EvidenceError`."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _json_safe_scalar(value)
    if isinstance(value, _FrozenMap):
        return value
    if isinstance(value, dict):
        frozen = tuple(
            sorted(((str(k), freeze_json_value(v)) for k, v in value.items()), key=lambda kv: kv[0])
        )
        return _FrozenMap(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json_value(v) for v in value)
    raise EvidenceError(f"unsupported type for JSON-safe evidence value: {type(value).__name__}")


def thaw_json_value(value: Any) -> Any:
    """Plain JSON-safe copy of a frozen value (``_FrozenMap`` → sorted dict,
    tuple → list, scalars unchanged)."""
    if isinstance(value, _FrozenMap):
        return {key: thaw_json_value(val) for key, val in value.items}
    if isinstance(value, tuple):
        return [thaw_json_value(v) for v in value]
    return value


def sanitize_json_value(value: Any) -> Any:
    """Deterministic, strict-JSON-safe plain copy (key-sorted; NaN/Infinity → None)."""
    return thaw_json_value(freeze_json_value(value))


def _canonical_key(value: Any) -> str:
    """Deterministic string key for sorting (from a frozen or plain value)."""
    return json.dumps(thaw_json_value(value), sort_keys=True, ensure_ascii=False, default=str)


def _require_report_safe_path(value: Optional[str], field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or _ABSOLUTE_PATH_RE.search(value) or ".." in re.split(r"[\\/]", value):
        raise EvidenceError(f"{field_name} must be a store-relative path (no absolute / '..'): {value!r}")


# --------------------------------------------------------------------------- #
# severity helpers
# --------------------------------------------------------------------------- #

_EVIDENCE_SEVERITY_ORDER: tuple[EvidenceSeverity, ...] = (
    EvidenceSeverity.INFO,
    EvidenceSeverity.WARNING,
    EvidenceSeverity.ERROR,
)


def evidence_severity_rank(severity) -> int:
    return _EVIDENCE_SEVERITY_ORDER.index(EvidenceSeverity(severity))


def evidence_severity_at_least(severity, threshold) -> bool:
    return evidence_severity_rank(severity) >= evidence_severity_rank(threshold)


# --------------------------------------------------------------------------- #
# aggregation finding model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class EvidenceFinding:
    """One Phase 14 aggregation finding — a separate namespace from Phase 13.

    ``finding_id`` is empty before numbering and ``evidence_0000`` afterwards; a
    ``finding_``-prefixed id (the Phase 13 namespace) is rejected.  ``context`` is a
    strict-JSON-safe scalar or an immutable mapping/array representation."""

    finding_id: str = ""
    severity: EvidenceSeverity
    code: EvidenceCode
    message: str
    train_run_hash: Optional[str] = None
    context: Any = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "severity", EvidenceSeverity(self.severity))
            object.__setattr__(self, "code", EvidenceCode(self.code))
        except ValueError as exc:
            raise EvidenceError(f"invalid evidence finding severity/code: {exc}") from exc
        if self.finding_id and self.finding_id.startswith("finding_"):
            raise EvidenceError(
                f"Phase 14 finding_id must not use the Phase 13 'finding_' namespace: {self.finding_id!r}"
            )
        object.__setattr__(self, "context", freeze_json_value(self.context))

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "code": self.code.value,
            "message": self.message,
            "train_run_hash": self.train_run_hash,
            "context": thaw_json_value(self.context),
        }


def evidence_finding_sort_key(finding: EvidenceFinding) -> tuple[str, str, str, str]:
    """Deterministic order: train_run_hash, code, context, message."""
    return (
        finding.train_run_hash or "",
        EvidenceCode(finding.code).value,
        _canonical_key(finding.context),
        finding.message,
    )


def sort_and_number_evidence_findings(findings) -> tuple[EvidenceFinding, ...]:
    """New tuple of findings sorted by :func:`evidence_finding_sort_key` with fresh
    ``evidence_0000`` ids.  Inputs are not mutated."""
    ordered = sorted(findings, key=evidence_finding_sort_key)
    return tuple(
        replace(finding, finding_id=f"evidence_{index:04d}") for index, finding in enumerate(ordered)
    )


# --------------------------------------------------------------------------- #
# artifact inventory
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class ArtifactInventoryEntry:
    """One artifact's inventory row.  ``exists`` / ``regular_file`` are tri-state
    (``True`` / ``False`` / ``None``); ``None`` means not checked (metadata-only) or
    unsafe/unavailable.  ``relative_path`` is store-relative or ``None`` — an unsafe
    raw value is never stored here (it stays in the Phase 13 finding's ``actual``)."""

    artifact_name: str
    relative_path: Optional[str] = None
    exists: Optional[bool] = None
    regular_file: Optional[bool] = None
    format: Optional[str] = None
    audit_finding_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_name, str) or not self.artifact_name:
            raise EvidenceError("artifact_name must be a non-empty string")
        _require_report_safe_path(self.relative_path, "relative_path")
        for name in ("exists", "regular_file"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise EvidenceError(f"{name} must be True, False, or None")
        object.__setattr__(self, "audit_finding_codes", tuple(str(c) for c in self.audit_finding_codes))

    def to_dict(self) -> dict:
        return {
            "artifact_name": self.artifact_name,
            "relative_path": self.relative_path,
            "exists": self.exists,
            "regular_file": self.regular_file,
            "format": self.format,
            "audit_finding_codes": list(self.audit_finding_codes),
        }


def _sorted_inventory(entries) -> tuple[ArtifactInventoryEntry, ...]:
    return tuple(sorted(entries, key=lambda e: (e.artifact_name, e.relative_path or "")))


# --------------------------------------------------------------------------- #
# catalog + comparison context
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class CatalogRunContext:
    """Optional per-run Phase 12 context — descriptive only (no recommendation)."""

    status: EvidenceContextStatus
    compatibility_group: Optional[str] = None
    group_size: Optional[int] = None
    peer_train_run_hashes: tuple[str, ...] = ()
    requested_metric: Optional[str] = None
    requested_metric_value: Optional[float] = None
    rank: Optional[int] = None
    maximize: Optional[bool] = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", EvidenceContextStatus(self.status))
        except ValueError as exc:
            raise EvidenceError(f"invalid catalog context status: {exc}") from exc
        object.__setattr__(
            self, "peer_train_run_hashes", tuple(sorted(set(self.peer_train_run_hashes)))
        )
        if self.group_size is not None and (not isinstance(self.group_size, int) or self.group_size < 0):
            raise EvidenceError("group_size must be a non-negative integer or None")
        if self.rank is not None and (not isinstance(self.rank, int) or self.rank < 1):
            raise EvidenceError("rank must be a positive integer or None")
        if self.requested_metric is None and (self.requested_metric_value is not None or self.rank is not None):
            raise EvidenceError("requested_metric_value/rank require an explicit requested_metric")
        object.__setattr__(self, "requested_metric_value", _json_safe_scalar(self.requested_metric_value))

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "compatibility_group": self.compatibility_group,
            "group_size": self.group_size,
            "peer_train_run_hashes": list(self.peer_train_run_hashes),
            "requested_metric": self.requested_metric,
            "requested_metric_value": self.requested_metric_value,
            "rank": self.rank,
            "maximize": self.maximize,
        }


@dataclass(frozen=True, kw_only=True)
class ComparisonEvidence:
    """Phase 10 comparison context for the selection — no best-run / winner field."""

    status: EvidenceComparisonStatus
    selected_run_hashes: tuple[str, ...] = ()
    rows: tuple[Any, ...] = ()
    unavailable_reason: Optional[str] = None
    disclaimers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", EvidenceComparisonStatus(self.status))
        except ValueError as exc:
            raise EvidenceError(f"invalid comparison status: {exc}") from exc
        object.__setattr__(self, "selected_run_hashes", tuple(self.selected_run_hashes))
        object.__setattr__(self, "rows", tuple(freeze_json_value(dict(r)) for r in self.rows))
        object.__setattr__(self, "disclaimers", tuple(str(d) for d in self.disclaimers))

        if self.status == EvidenceComparisonStatus.NOT_APPLICABLE:
            if self.rows or self.unavailable_reason is not None:
                raise EvidenceError("not_applicable comparison must have no rows and no reason")
        elif self.status == EvidenceComparisonStatus.AVAILABLE:
            if len(self.selected_run_hashes) < 2:
                raise EvidenceError("available comparison requires at least two selected runs")
            if not self.rows:
                raise EvidenceError("available comparison requires rows")
            if self.unavailable_reason is not None:
                raise EvidenceError("available comparison must not carry an unavailable_reason")
        else:  # UNAVAILABLE
            if self.rows:
                raise EvidenceError("unavailable comparison must have no rows")
            if not self.unavailable_reason or not str(self.unavailable_reason).strip():
                raise EvidenceError("unavailable comparison requires an unavailable_reason")

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "selected_run_hashes": list(self.selected_run_hashes),
            "rows": [thaw_json_value(r) for r in self.rows],
            "unavailable_reason": self.unavailable_reason,
            "disclaimers": list(self.disclaimers),
        }


# --------------------------------------------------------------------------- #
# per-run evidence
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class ExperimentRunEvidence:
    """Aggregated evidence for one selected run.  Phase 13 ``audit_findings`` are
    stored verbatim (ids preserved).  Metadata fields may be ``None`` for an
    unavailable / unloadable run; ``created_at`` is persisted evidence only —
    Phase 14 generates no timestamp."""

    train_run_hash: str
    run_directory: str
    load_status: EvidenceLoadStatus
    completeness: EvidenceCompleteness
    audit_status: str
    audit_findings: tuple[AuditFinding, ...] = ()
    created_at: Optional[str] = None
    train_start: Optional[str] = None
    train_end: Optional[str] = None
    validation_start: Optional[str] = None
    validation_end: Optional[str] = None
    feature_columns: Optional[tuple[str, ...]] = None
    label_column: Optional[str] = None
    model_type: Optional[str] = None
    task_type: Optional[str] = None
    metrics: Any = None
    baseline_metrics: Any = None
    hash_chain: Any = None
    artifact_inventory: tuple[ArtifactInventoryEntry, ...] = ()
    catalog_context: Optional[CatalogRunContext] = None
    missing_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.train_run_hash, str) or not self.train_run_hash.strip():
            raise EvidenceError("train_run_hash must be a non-empty string")
        if not isinstance(self.run_directory, str) or not self.run_directory:
            raise EvidenceError("run_directory must be a non-empty string")
        _require_report_safe_path(self.run_directory, "run_directory")
        try:
            object.__setattr__(self, "load_status", EvidenceLoadStatus(self.load_status))
            object.__setattr__(self, "completeness", EvidenceCompleteness(self.completeness))
        except ValueError as exc:
            raise EvidenceError(f"invalid run load/completeness status: {exc}") from exc
        if self.audit_status not in _ALLOWED_AUDIT_STATUSES:
            raise EvidenceError(
                f"audit_status must be one of {sorted(_ALLOWED_AUDIT_STATUSES)}, got {self.audit_status!r}"
            )
        object.__setattr__(self, "audit_findings", tuple(self.audit_findings))
        if self.feature_columns is not None:
            object.__setattr__(self, "feature_columns", tuple(self.feature_columns))
        object.__setattr__(self, "metrics", None if self.metrics is None else freeze_json_value(self.metrics))
        object.__setattr__(
            self, "baseline_metrics", None if self.baseline_metrics is None else freeze_json_value(self.baseline_metrics)
        )
        object.__setattr__(self, "hash_chain", None if self.hash_chain is None else freeze_json_value(self.hash_chain))
        object.__setattr__(self, "artifact_inventory", _sorted_inventory(self.artifact_inventory))
        object.__setattr__(self, "missing_evidence", tuple(str(m) for m in self.missing_evidence))

    def to_dict(self) -> dict:
        return {
            "train_run_hash": self.train_run_hash,
            "run_directory": self.run_directory,
            "load_status": self.load_status.value,
            "completeness": self.completeness.value,
            "audit_status": self.audit_status,
            "audit_findings": [f.to_dict() for f in self.audit_findings],
            "created_at": self.created_at,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
            "feature_columns": None if self.feature_columns is None else list(self.feature_columns),
            "label_column": self.label_column,
            "model_type": self.model_type,
            "task_type": self.task_type,
            "metrics": None if self.metrics is None else thaw_json_value(self.metrics),
            "baseline_metrics": None if self.baseline_metrics is None else thaw_json_value(self.baseline_metrics),
            "hash_chain": None if self.hash_chain is None else thaw_json_value(self.hash_chain),
            "artifact_inventory": [a.to_dict() for a in self.artifact_inventory],
            "catalog_context": None if self.catalog_context is None else self.catalog_context.to_dict(),
            "missing_evidence": list(self.missing_evidence),
        }


# --------------------------------------------------------------------------- #
# summary + top-level pack
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class EvidenceSummary:
    completeness: EvidenceCompleteness
    selected_runs_total: int
    runs_complete: int
    runs_with_warnings: int
    runs_incomplete: int
    runs_unavailable: int
    phase14_findings_total: int
    phase13_findings_total: int

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "completeness", EvidenceCompleteness(self.completeness))
        except ValueError as exc:
            raise EvidenceError(f"invalid summary completeness: {exc}") from exc
        counts = {
            "selected_runs_total": self.selected_runs_total,
            "runs_complete": self.runs_complete,
            "runs_with_warnings": self.runs_with_warnings,
            "runs_incomplete": self.runs_incomplete,
            "runs_unavailable": self.runs_unavailable,
            "phase14_findings_total": self.phase14_findings_total,
            "phase13_findings_total": self.phase13_findings_total,
        }
        for name, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise EvidenceError(f"{name} must be a non-negative integer, got {value!r}")
        status_sum = self.runs_complete + self.runs_with_warnings + self.runs_incomplete + self.runs_unavailable
        if status_sum != self.selected_runs_total:
            raise EvidenceError(
                f"run status counts ({status_sum}) must sum to selected_runs_total ({self.selected_runs_total})"
            )

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness.value,
            "selected_runs_total": self.selected_runs_total,
            "runs_complete": self.runs_complete,
            "runs_with_warnings": self.runs_with_warnings,
            "runs_incomplete": self.runs_incomplete,
            "runs_unavailable": self.runs_unavailable,
            "phase14_findings_total": self.phase14_findings_total,
            "phase13_findings_total": self.phase13_findings_total,
        }


@dataclass(frozen=True, kw_only=True)
class ExperimentEvidencePack:
    """Deterministic, strict-JSON-safe top-level evidence pack.  Selected hashes are
    duplicate-free (first-occurrence order); ``runs`` follow that order.  Phase 14
    findings use only ``evidence_`` ids; Phase 13 findings stay nested inside runs.
    Registry / dataset-lineage context defaults to the neutral ``not_collected``."""

    selected_run_hashes: tuple[str, ...]
    runs: tuple[ExperimentRunEvidence, ...]
    comparison: ComparisonEvidence
    evidence_summary: EvidenceSummary
    findings: tuple[EvidenceFinding, ...] = ()
    disclaimers: tuple[str, ...] = ()
    registry_context_status: EvidenceContextStatus = EvidenceContextStatus.NOT_COLLECTED
    dataset_lineage_context_status: EvidenceContextStatus = EvidenceContextStatus.NOT_COLLECTED
    catalog_context_status: EvidenceContextStatus = EvidenceContextStatus.NOT_COLLECTED

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_run_hashes", tuple(self.selected_run_hashes))
        object.__setattr__(self, "runs", tuple(self.runs))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "disclaimers", tuple(str(d) for d in self.disclaimers))
        for name in ("registry_context_status", "dataset_lineage_context_status", "catalog_context_status"):
            try:
                object.__setattr__(self, name, EvidenceContextStatus(getattr(self, name)))
            except ValueError as exc:
                raise EvidenceError(f"invalid {name}: {exc}") from exc

        if not self.selected_run_hashes:
            raise EvidenceError("at least one selected run hash is required")
        if len(set(self.selected_run_hashes)) != len(self.selected_run_hashes):
            raise EvidenceError("selected_run_hashes must be duplicate-free (first occurrence preserved)")
        if tuple(r.train_run_hash for r in self.runs) != self.selected_run_hashes:
            raise EvidenceError("runs must follow the selected_run_hashes order one-to-one")
        for finding in self.findings:
            if finding.finding_id and not finding.finding_id.startswith("evidence_"):
                raise EvidenceError(
                    f"pack findings must use the 'evidence_' namespace: {finding.finding_id!r}"
                )

    def to_dict(self) -> dict:
        return {
            "selected_run_hashes": list(self.selected_run_hashes),
            "runs": [r.to_dict() for r in self.runs],
            "comparison": self.comparison.to_dict(),
            "registry_context_status": self.registry_context_status.value,
            "dataset_lineage_context_status": self.dataset_lineage_context_status.value,
            "catalog_context_status": self.catalog_context_status.value,
            "evidence_summary": self.evidence_summary.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "disclaimers": list(self.disclaimers),
        }


# --------------------------------------------------------------------------- #
# deterministic + completeness helpers
# --------------------------------------------------------------------------- #


def dedupe_preserve_order(values: Sequence[str]) -> tuple[str, ...]:
    """Deduplicate keeping first occurrence; reject empty / whitespace hashes."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise EvidenceError("run hashes must be non-empty strings")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def derive_run_completeness(
    *,
    load_status,
    audit_findings,
    required_evidence_missing: bool = False,
    requested_metric_missing: bool = False,
) -> EvidenceCompleteness:
    """Per-run completeness (documented rules; reads public Phase 13 severities)."""
    load_status = EvidenceLoadStatus(load_status)
    if load_status in (EvidenceLoadStatus.UNAVAILABLE, EvidenceLoadStatus.UNLOADABLE):
        return EvidenceCompleteness.UNAVAILABLE
    severities = {f.severity.value for f in audit_findings}
    if severities & _AUDIT_BLOCKING_SEVERITIES:
        return EvidenceCompleteness.INCOMPLETE
    if required_evidence_missing or requested_metric_missing:
        return EvidenceCompleteness.INCOMPLETE
    if "warning" in severities:
        return EvidenceCompleteness.WARNING
    return EvidenceCompleteness.COMPLETE


def derive_pack_completeness(
    run_completeness,
    *,
    selection_warning: bool = False,
    selection_incomplete: bool = False,
) -> EvidenceCompleteness:
    """Top-level completeness (documented rules).  Neutral registry/lineage
    ``not_collected`` context is *not* an input here and never downgrades status.
    An empty run list yields ``UNAVAILABLE``."""
    statuses = [EvidenceCompleteness(s) for s in run_completeness]
    if not statuses:
        return EvidenceCompleteness.UNAVAILABLE
    if all(s == EvidenceCompleteness.UNAVAILABLE for s in statuses):
        return EvidenceCompleteness.UNAVAILABLE
    if (
        selection_incomplete
        or any(s == EvidenceCompleteness.INCOMPLETE for s in statuses)
        or any(s == EvidenceCompleteness.UNAVAILABLE for s in statuses)
    ):
        return EvidenceCompleteness.INCOMPLETE
    if selection_warning or any(s == EvidenceCompleteness.WARNING for s in statuses):
        return EvidenceCompleteness.WARNING
    return EvidenceCompleteness.COMPLETE


# Sanity: EvidenceFinding exposes fields in the documented order.
assert [f.name for f in fields(EvidenceFinding)] == [
    "finding_id", "severity", "code", "message", "train_run_hash", "context",
]
