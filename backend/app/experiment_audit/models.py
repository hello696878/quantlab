"""
Phase 13 (commit 1) — audit data models, deterministic finding utilities, and
audit-scoped path / frame contract helpers.

This module is **pure and self-contained**: it performs no filesystem access of
any kind (no reads, no writes, no ``stat``, no ``resolve``), imports nothing from
``app.*`` (so it cannot couple to any private ``ExperimentStore`` internal — its
private absolute-path regex, its frame-name tuple, or its relative-path helper),
and mints no hashes.  It only defines validated, strict-JSON-safe result models
plus the path / frame *contract* helpers the Commit 2 engine will use.

The path helpers deliberately re-implement — not import — the current
``ExperimentStore`` relative-path contract; a parity test proves they agree with
the public ``ExperimentRun`` schema.  ``is_safe_relative_artifact_path`` models
the *schema* contract (a safe relative **subdirectory is allowed**);
``is_canonical_artifact_filename`` separately models the *save layout* (a bare
filename with no separators).  They are related but not identical concepts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from enum import Enum
from typing import Optional

__all__ = [
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
]


class AuditError(ValueError):
    """Invalid audit-model construction or audit-policy input.

    Used only for audit-layer misuse (an inconsistent result, an unsafe report
    path, a bad severity threshold).  It never wraps or hides ``ExperimentStore``
    errors — those surface as their own findings in later commits."""


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditCode(str, Enum):
    # entry classification
    EMPTY_STORE = "EMPTY_STORE"
    NON_RUN_DIRECTORY = "NON_RUN_DIRECTORY"
    ROOT_LEVEL_FILE = "ROOT_LEVEL_FILE"
    EMPTY_DIRECTORY = "EMPTY_DIRECTORY"
    IGNORED_OS_FILE = "IGNORED_OS_FILE"
    SYMLINK_ENTRY = "SYMLINK_ENTRY"
    # metadata
    MISSING_METADATA = "MISSING_METADATA"
    MALFORMED_METADATA_JSON = "MALFORMED_METADATA_JSON"
    INVALID_EXPERIMENT_RUN_SCHEMA = "INVALID_EXPERIMENT_RUN_SCHEMA"
    DIRECTORY_HASH_MISMATCH = "DIRECTORY_HASH_MISMATCH"
    # artifact paths
    ABSOLUTE_ARTIFACT_PATH = "ABSOLUTE_ARTIFACT_PATH"
    PATH_TRAVERSAL = "PATH_TRAVERSAL"
    INVALID_ARTIFACT_PATH = "INVALID_ARTIFACT_PATH"
    DUPLICATE_ARTIFACT_REFERENCE = "DUPLICATE_ARTIFACT_REFERENCE"
    ARTIFACT_NOT_A_FILE = "ARTIFACT_NOT_A_FILE"
    # artifact existence / layout
    MISSING_REFERENCED_ARTIFACT = "MISSING_REFERENCED_ARTIFACT"
    MISSING_EXPECTED_ARTIFACT = "MISSING_EXPECTED_ARTIFACT"
    ORPHAN_ARTIFACT = "ORPHAN_ARTIFACT"
    UNEXPECTED_FILE = "UNEXPECTED_FILE"
    CONFLICTING_FRAME_FORMAT = "CONFLICTING_FRAME_FORMAT"
    # deep readability
    UNREADABLE_ARTIFACT = "UNREADABLE_ARTIFACT"
    INVALID_FRAME_FORMAT = "INVALID_FRAME_FORMAT"
    FRAME_ROW_COUNT_IMPLAUSIBLE = "FRAME_ROW_COUNT_IMPLAUSIBLE"
    # hash chain
    HASH_CHAIN_FIELD_MISSING = "HASH_CHAIN_FIELD_MISSING"
    HASH_CHAIN_FIELD_FORMAT = "HASH_CHAIN_FIELD_FORMAT"


class AuditRunStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class AuditOverallStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"


class AuditLevel(str, Enum):
    """How deep the audit inspects each run (metadata-only < standard < deep)."""

    METADATA_ONLY = "metadata-only"
    STANDARD = "standard"
    DEEP = "deep"


# --------------------------------------------------------------------------- #
# audit-scoped path / frame contract helpers (no filesystem access)
# --------------------------------------------------------------------------- #

# Mirrors the current ExperimentStore path contract WITHOUT importing any private
# store internal — parity is proven against the public ExperimentRun schema in
# tests.  Absolute = a drive prefix (C:\ / C:/) or a leading slash/backslash (UNC).
_ABSOLUTE_ARTIFACT_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|^[\\/]")
_PATH_SEPARATORS = re.compile(r"[\\/]")

CANONICAL_ARTIFACT_KEYS: tuple[str, ...] = (
    "metadata",
    "model_params",
    "metrics",
    "predictions",
    "signal",
    "backtest",
)
CANONICAL_FRAME_NAMES: tuple[str, ...] = ("predictions", "signal", "backtest")
IGNORED_OS_FILES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def is_absolute_artifact_path(value: str) -> bool:
    """True if ``value`` is an absolute path (drive-letter / UNC / leading slash).

    Uses the raw value (matching the schema); does not touch the filesystem."""
    return isinstance(value, str) and bool(_ABSOLUTE_ARTIFACT_PATH_RE.search(value))


def has_parent_traversal(value: str) -> bool:
    """True if ``value`` has a ``..`` component under either slash convention."""
    return isinstance(value, str) and ".." in _PATH_SEPARATORS.split(value)


def is_safe_relative_artifact_path(value: str) -> bool:
    """Model the ExperimentStore *safety* contract: a non-empty, non-absolute path
    with no ``..`` component.  A safe relative **subdirectory is allowed** (the
    schema permits it), so this is looser than a bare canonical filename."""
    if not isinstance(value, str) or not value.strip():
        return False
    return not is_absolute_artifact_path(value) and not has_parent_traversal(value)


def is_canonical_artifact_filename(value: str) -> bool:
    """Model the *save layout*: a safe relative path that is additionally a **bare
    filename** (no path separators).  Stricter than ``is_safe_relative_artifact_path``."""
    if not is_safe_relative_artifact_path(value):
        return False
    return "/" not in value and "\\" not in value


# --------------------------------------------------------------------------- #
# severity / status helpers
# --------------------------------------------------------------------------- #

_SEVERITY_ORDER: tuple[AuditSeverity, ...] = (
    AuditSeverity.INFO,
    AuditSeverity.WARNING,
    AuditSeverity.ERROR,
    AuditSeverity.CRITICAL,
)


def severity_rank(severity) -> int:
    """Ordinal rank ``info < warning < error < critical`` (accepts enum or str)."""
    return _SEVERITY_ORDER.index(AuditSeverity(severity))


def severity_at_least(severity, threshold) -> bool:
    """True if ``severity`` is at least as severe as ``threshold``."""
    return severity_rank(severity) >= severity_rank(threshold)


def status_for_findings(findings) -> AuditRunStatus:
    """Canonical run status from its findings: invalid if any error/critical,
    warning if any warning (and no error/critical), else valid."""
    ranks = [severity_rank(f.severity) for f in findings]
    if any(r >= severity_rank(AuditSeverity.ERROR) for r in ranks):
        return AuditRunStatus.INVALID
    if any(r >= severity_rank(AuditSeverity.WARNING) for r in ranks):
        return AuditRunStatus.WARNING
    return AuditRunStatus.VALID


def overall_status_for(findings) -> AuditOverallStatus:
    """Canonical store status from all findings: failed if any error/critical,
    warning if any warning (and no error/critical), else ok."""
    ranks = [severity_rank(f.severity) for f in findings]
    if any(r >= severity_rank(AuditSeverity.ERROR) for r in ranks):
        return AuditOverallStatus.FAILED
    if any(r >= severity_rank(AuditSeverity.WARNING) for r in ranks):
        return AuditOverallStatus.WARNING
    return AuditOverallStatus.OK


# --------------------------------------------------------------------------- #
# finding model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class AuditFinding:
    """One deterministic, strict-JSON-safe audit finding.

    ``run_directory`` and ``relative_path`` are always **report-safe**
    (store-relative, no ``..``); an unsafe raw path being *reported* is carried in
    the descriptive ``actual`` field, never normalized into a path field.  Field
    declaration order is the stable serialization order."""

    finding_id: str = ""
    severity: AuditSeverity
    code: AuditCode
    message: str
    train_run_hash: Optional[str] = None
    run_directory: str
    artifact_name: Optional[str] = None
    relative_path: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "severity", AuditSeverity(self.severity))
            object.__setattr__(self, "code", AuditCode(self.code))
        except ValueError as exc:
            raise AuditError(f"invalid finding severity/code: {exc}") from exc
        if not isinstance(self.run_directory, str) or not self.run_directory:
            raise AuditError("run_directory must be a non-empty string")
        # run_directory is a store entry name or "." — never absolute / traversal.
        if self.run_directory != "." and not is_safe_relative_artifact_path(self.run_directory):
            raise AuditError(f"run_directory must be report-safe/relative: {self.run_directory!r}")
        if self.relative_path is not None and not is_safe_relative_artifact_path(self.relative_path):
            raise AuditError(
                f"relative_path must be report-safe/relative (unsafe values belong in "
                f"'actual', not a path field): {self.relative_path!r}"
            )

    def to_dict(self) -> dict:
        """Deterministic, strict-JSON-safe dict (enum values as strings)."""
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "code": self.code.value,
            "message": self.message,
            "train_run_hash": self.train_run_hash,
            "run_directory": self.run_directory,
            "artifact_name": self.artifact_name,
            "relative_path": self.relative_path,
            "expected": self.expected,
            "actual": self.actual,
        }


def finding_sort_key(finding: AuditFinding) -> tuple[str, str, str, str, str]:
    """Deterministic total order: run_directory, code, artifact_name,
    relative_path, message (``None`` sorts as an empty string)."""
    return (
        finding.run_directory,
        AuditCode(finding.code).value,
        finding.artifact_name or "",
        finding.relative_path or "",
        finding.message,
    )


def sort_and_number_findings(findings) -> tuple[AuditFinding, ...]:
    """Return a new tuple of findings sorted by :func:`finding_sort_key` with
    freshly assigned ``finding_0000``-style ids.  Inputs are **not mutated**
    (frozen findings are copied via ``dataclasses.replace``)."""
    ordered = sorted(findings, key=finding_sort_key)
    return tuple(
        replace(finding, finding_id=f"finding_{index:04d}")
        for index, finding in enumerate(ordered)
    )


# --------------------------------------------------------------------------- #
# per-run and store-level results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class ExperimentRunAudit:
    """Audit outcome for one run directory.  ``status`` must equal the canonical
    status derived from ``findings`` (valid ⟺ no warning/error/critical;
    warning ⟺ a warning and no error/critical; invalid ⟺ an error/critical)."""

    run_directory: str
    train_run_hash: Optional[str]
    status: AuditRunStatus
    findings: tuple[AuditFinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        try:
            object.__setattr__(self, "status", AuditRunStatus(self.status))
        except ValueError as exc:
            raise AuditError(f"invalid run status: {exc}") from exc
        if self.run_directory != "." and not is_safe_relative_artifact_path(self.run_directory):
            raise AuditError(f"run_directory must be report-safe/relative: {self.run_directory!r}")
        expected = status_for_findings(self.findings)
        if self.status != expected:
            raise AuditError(
                f"run status {self.status.value!r} inconsistent with findings "
                f"(expected {expected.value!r})"
            )

    def to_dict(self) -> dict:
        return {
            "run_directory": self.run_directory,
            "train_run_hash": self.train_run_hash,
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True, kw_only=True)
class ExperimentStoreAuditResult:
    """Deterministic, strict-JSON-safe whole-store audit result.

    Counts are non-negative and internally consistent: the three run-status counts
    sum to ``runs_discovered``, ``len(run_audits) == runs_discovered``,
    ``findings_total == len(findings)``, the by-severity and by-code tallies each
    sum to ``findings_total``, ``audited_run_hashes`` is duplicate-free, and
    ``overall_status`` matches the findings."""

    runs_discovered: int
    runs_valid: int
    runs_with_warnings: int
    runs_invalid: int
    non_run_entries: int
    findings_total: int
    findings_by_severity: dict
    findings_by_code: dict
    audited_run_hashes: tuple[str, ...]
    run_audits: tuple[ExperimentRunAudit, ...]
    findings: tuple[AuditFinding, ...]
    overall_status: AuditOverallStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "audited_run_hashes", tuple(self.audited_run_hashes))
        object.__setattr__(self, "run_audits", tuple(self.run_audits))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "findings_by_severity",
            {_enum_value(k): int(v) for k, v in dict(self.findings_by_severity).items()},
        )
        object.__setattr__(
            self,
            "findings_by_code",
            {_enum_value(k): int(v) for k, v in dict(self.findings_by_code).items()},
        )
        try:
            object.__setattr__(self, "overall_status", AuditOverallStatus(self.overall_status))
        except ValueError as exc:
            raise AuditError(f"invalid overall status: {exc}") from exc

        counts = {
            "runs_discovered": self.runs_discovered,
            "runs_valid": self.runs_valid,
            "runs_with_warnings": self.runs_with_warnings,
            "runs_invalid": self.runs_invalid,
            "non_run_entries": self.non_run_entries,
            "findings_total": self.findings_total,
        }
        for name, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AuditError(f"{name} must be a non-negative integer, got {value!r}")

        if self.findings_total != len(self.findings):
            raise AuditError(
                f"findings_total {self.findings_total} != len(findings) {len(self.findings)}"
            )
        if len(self.run_audits) != self.runs_discovered:
            raise AuditError(
                f"len(run_audits) {len(self.run_audits)} != runs_discovered {self.runs_discovered}"
            )
        status_sum = self.runs_valid + self.runs_with_warnings + self.runs_invalid
        if status_sum != self.runs_discovered:
            raise AuditError(
                f"runs_valid + runs_with_warnings + runs_invalid ({status_sum}) "
                f"!= runs_discovered ({self.runs_discovered})"
            )
        if len(set(self.audited_run_hashes)) != len(self.audited_run_hashes):
            raise AuditError("audited_run_hashes must be duplicate-free")
        for value in self.findings_by_severity.values():
            if value < 0:
                raise AuditError("findings_by_severity values must be non-negative")
        for value in self.findings_by_code.values():
            if value < 0:
                raise AuditError("findings_by_code values must be non-negative")
        if sum(self.findings_by_severity.values()) != self.findings_total:
            raise AuditError("findings_by_severity does not sum to findings_total")
        if sum(self.findings_by_code.values()) != self.findings_total:
            raise AuditError("findings_by_code does not sum to findings_total")
        expected_overall = overall_status_for(self.findings)
        if self.overall_status != expected_overall:
            raise AuditError(
                f"overall_status {self.overall_status.value!r} inconsistent with findings "
                f"(expected {expected_overall.value!r})"
            )

    def to_dict(self) -> dict:
        return {
            "runs_discovered": self.runs_discovered,
            "runs_valid": self.runs_valid,
            "runs_with_warnings": self.runs_with_warnings,
            "runs_invalid": self.runs_invalid,
            "non_run_entries": self.non_run_entries,
            "findings_total": self.findings_total,
            "findings_by_severity": dict(self.findings_by_severity),
            "findings_by_code": dict(self.findings_by_code),
            "audited_run_hashes": list(self.audited_run_hashes),
            "run_audits": [ra.to_dict() for ra in self.run_audits],
            "findings": [f.to_dict() for f in self.findings],
            "overall_status": self.overall_status.value,
        }


def _enum_value(key) -> str:
    return key.value if isinstance(key, Enum) else str(key)


# Sanity: the finding dataclass exposes fields in the documented order.
assert [f.name for f in fields(AuditFinding)] == [
    "finding_id", "severity", "code", "message", "train_run_hash",
    "run_directory", "artifact_name", "relative_path", "expected", "actual",
]
