"""
Phase 13 (commit 2) — tolerant, sequential, read-only ExperimentStore audit engine.

``audit_experiment_store`` walks every immediate entry under the store root once,
in sorted order, classifying each (run / non-run) and validating metadata-bearing
directories through a **tolerant ladder** that emits a finding at each failing rung
instead of aborting — so one malformed run never stops the whole-store survey.
``audit_experiment_run`` audits a single named run directory.  Both are strictly
read-only: this module contains **no filesystem mutation** of any kind (a guard
test asserts it, and a byte-level snapshot proves the store is unchanged).

It imports only public ``ExperimentRun`` / ``ExperimentStore`` / ``ExperimentError``
— never a private store internal, and never the fail-fast public discovery / load
helpers (which abort on the first corrupt run) — and mints no hashes.  In deep mode
it reads frames through the public ``ExperimentStore.read_frame`` only after every
safety precondition (schema-valid, safe, non-symlink, existing regular file) has
passed.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from app.experiment_audit.models import (
    CANONICAL_ARTIFACT_KEYS,
    CANONICAL_FRAME_NAMES,
    IGNORED_OS_FILES,
    AuditCode,
    AuditError,
    AuditFinding,
    AuditLevel,
    AuditSeverity,
    ExperimentRunAudit,
    ExperimentStoreAuditResult,
    has_parent_traversal,
    is_absolute_artifact_path,
    is_safe_relative_artifact_path,
    overall_status_for,
    sort_and_number_findings,
    status_for_findings,
)
from app.experiments import ExperimentError, ExperimentRun, ExperimentStore

__all__ = [
    "audit_experiment_run",
    "audit_experiment_store",
    "summarize_audit_result",
]

_METADATA_FILENAME = "metadata.json"
_HASH_CHAIN_FIELDS: tuple[str, ...] = (
    "train_run_hash",
    "continuous_config_hash",
    "feature_config_hash",
    "label_config_hash",
    "dataset_config_hash",
    "model_config_hash",
)
_ARTIFACT_EXTENSIONS = frozenset({".json", ".parquet", ".csv"})
_FRAME_EXTENSIONS = frozenset({".parquet", ".csv"})

_LEVEL_RANK = {
    AuditLevel.METADATA_ONLY: 0,
    AuditLevel.STANDARD: 1,
    AuditLevel.DEEP: 2,
}


def _f(severity, code, message, *, run_directory, **kw) -> AuditFinding:
    return AuditFinding(
        severity=severity, code=code, message=message, run_directory=run_directory, **kw
    )


def _is_ignored_os_file(name: str) -> bool:
    lowered = name.lower()
    return any(lowered == ignored.lower() for ignored in IGNORED_OS_FILES)


# --------------------------------------------------------------------------- #
# artifact-path safety (raw values — no filesystem access)
# --------------------------------------------------------------------------- #


def _check_artifact_path_safety(raw_ap, run_directory: str) -> tuple[list[AuditFinding], set]:
    """Path-safety over a raw ``artifact_paths`` dict, before any filesystem touch.

    Returns ``(findings, safe_keys)`` where ``safe_keys`` maps to (key, value)
    pairs whose value is a safe relative path (checked later for existence).
    Unsafe values are reported with the offending value in ``actual`` — never in
    ``relative_path`` (which stays report-safe)."""
    findings: list[AuditFinding] = []
    safe: list[tuple[str, str]] = []
    if not isinstance(raw_ap, dict):
        return findings, set()

    first_seen: dict[str, str] = {}
    for key in sorted(raw_ap, key=str):
        value = raw_ap[key]
        akey = str(key)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.INVALID_ARTIFACT_PATH,
                    f"artifact path for {akey!r} is empty or not a string",
                    run_directory=run_directory, artifact_name=akey, actual=repr(value),
                )
            )
            continue
        if has_parent_traversal(value):
            findings.append(
                _f(
                    AuditSeverity.CRITICAL, AuditCode.PATH_TRAVERSAL,
                    f"artifact path for {akey!r} contains a parent-traversal component",
                    run_directory=run_directory, artifact_name=akey, actual=value,
                )
            )
            continue
        if is_absolute_artifact_path(value):
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.ABSOLUTE_ARTIFACT_PATH,
                    f"artifact path for {akey!r} is absolute (must be store-relative)",
                    run_directory=run_directory, artifact_name=akey, actual=value,
                )
            )
            continue
        # safe relative value (a bare filename or a safe subdirectory)
        if value in first_seen:
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.DUPLICATE_ARTIFACT_REFERENCE,
                    f"artifact keys {first_seen[value]!r} and {akey!r} reference the same file",
                    run_directory=run_directory, artifact_name=akey, relative_path=value,
                    expected=first_seen[value], actual=akey,
                )
            )
        else:
            first_seen[value] = akey
            safe.append((akey, value))
    return findings, set(safe)


# --------------------------------------------------------------------------- #
# per-run audit (tolerant ladder)
# --------------------------------------------------------------------------- #


def _audit_run_directory(store: ExperimentStore, run_dir: Path, level: AuditLevel):
    """Audit one metadata-bearing directory. Returns ``(findings, train_run_hash)``
    where ``train_run_hash`` is the parseable persisted hash (schema-valid) or None."""
    name = run_dir.name
    findings: list[AuditFinding] = []
    metadata_path = run_dir / _METADATA_FILENAME

    # Step 1 — read metadata.json text
    try:
        text = metadata_path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(
            _f(
                AuditSeverity.ERROR, AuditCode.UNREADABLE_ARTIFACT,
                f"metadata.json could not be read: {type(exc).__name__}",
                run_directory=name, artifact_name="metadata", relative_path=_METADATA_FILENAME,
            )
        )
        return findings, None

    # Step 2 — parse raw JSON
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        findings.append(
            _f(
                AuditSeverity.ERROR, AuditCode.MALFORMED_METADATA_JSON,
                "metadata.json is not valid JSON",
                run_directory=name, artifact_name="metadata", relative_path=_METADATA_FILENAME,
            )
        )
        return findings, None

    raw_ap = raw.get("artifact_paths") if isinstance(raw, dict) else None

    # Step 3 — raw artifact-path safety (runs even if the schema later fails)
    path_findings, safe_pairs = _check_artifact_path_safety(raw_ap, name)
    findings.extend(path_findings)

    # Hash-chain presence (detectable from the raw dict regardless of schema)
    if isinstance(raw, dict):
        for field_name in _HASH_CHAIN_FIELDS:
            value = raw.get(field_name)
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    _f(
                        AuditSeverity.ERROR, AuditCode.HASH_CHAIN_FIELD_MISSING,
                        f"hash-chain field {field_name!r} is missing or empty",
                        run_directory=name, artifact_name=field_name,
                    )
                )

    # Step 4 — schema validation
    run: Optional[ExperimentRun] = None
    try:
        run = ExperimentRun.model_validate(raw)
    except ValidationError:
        findings.append(
            _f(
                AuditSeverity.ERROR, AuditCode.INVALID_EXPERIMENT_RUN_SCHEMA,
                "metadata does not validate as an ExperimentRun",
                run_directory=name, artifact_name="metadata", relative_path=_METADATA_FILENAME,
            )
        )

    train_run_hash: Optional[str] = None
    if run is not None:
        train_run_hash = run.train_run_hash
        # Step 5 — directory / hash consistency
        if run.train_run_hash != name:
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.DIRECTORY_HASH_MISMATCH,
                    "directory name does not match the persisted train_run_hash",
                    run_directory=name, expected=name, actual=run.train_run_hash,
                )
            )

    # standard / deep — existence, layout, orphans (only when artifact_paths is a dict)
    if _LEVEL_RANK[level] >= _LEVEL_RANK[AuditLevel.STANDARD] and isinstance(raw_ap, dict):
        findings.extend(_check_artifacts_on_disk(run_dir, raw_ap, safe_pairs))
        if level == AuditLevel.DEEP and run is not None:
            findings.extend(_check_frames_readable(store, run_dir))

    return findings, train_run_hash


def _check_artifacts_on_disk(run_dir: Path, raw_ap: dict, safe_pairs: set) -> list[AuditFinding]:
    """Standard-level existence / layout / orphan checks (read-only)."""
    name = run_dir.name
    findings: list[AuditFinding] = []
    referenced = {str(v) for v in raw_ap.values() if isinstance(v, str)}

    # referenced-artifact existence (safe values only; never follow symlinks)
    for key, value in sorted(safe_pairs):
        target = run_dir / value
        if target.is_symlink():
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.SYMLINK_ENTRY,
                    f"referenced artifact {key!r} is a symlink (not followed)",
                    run_directory=name, artifact_name=key, relative_path=value,
                )
            )
            continue
        if not target.exists():
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.MISSING_REFERENCED_ARTIFACT,
                    f"referenced artifact {key!r} does not exist",
                    run_directory=name, artifact_name=key, relative_path=value,
                )
            )
        elif target.is_dir():
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.ARTIFACT_NOT_A_FILE,
                    f"referenced artifact {key!r} is a directory, not a file",
                    run_directory=name, artifact_name=key, relative_path=value,
                )
            )

    # canonical keys expected but absent from artifact_paths
    for canonical in CANONICAL_ARTIFACT_KEYS:
        if canonical not in raw_ap:
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.MISSING_EXPECTED_ARTIFACT,
                    f"canonical artifact key {canonical!r} is not referenced in artifact_paths",
                    run_directory=name, artifact_name=canonical,
                )
            )

    # disk survey: orphan / unexpected / ignored-os / symlink / conflicting frames
    frame_exts: dict[str, set] = {}
    for child in sorted(run_dir.iterdir(), key=lambda p: p.name):
        cname = child.name
        if child.is_symlink():
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.SYMLINK_ENTRY,
                    f"run directory contains a symlink {cname!r} (not followed)",
                    run_directory=name, relative_path=cname,
                )
            )
            continue
        stem, suffix = child.stem, child.suffix
        if stem in CANONICAL_FRAME_NAMES and suffix in _FRAME_EXTENSIONS:
            frame_exts.setdefault(stem, set()).add(suffix)
        if cname == _METADATA_FILENAME or cname in referenced:
            continue  # the metadata file itself, or a referenced artifact
        if _is_ignored_os_file(cname):
            findings.append(
                _f(
                    AuditSeverity.INFO, AuditCode.IGNORED_OS_FILE,
                    f"ignored OS file {cname!r} present in the run directory",
                    run_directory=name, relative_path=cname,
                )
            )
        elif suffix in _ARTIFACT_EXTENSIONS:
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.ORPHAN_ARTIFACT,
                    f"artifact-like file {cname!r} is not referenced by artifact_paths",
                    run_directory=name, relative_path=cname,
                )
            )
        else:
            findings.append(
                _f(
                    AuditSeverity.INFO, AuditCode.UNEXPECTED_FILE,
                    f"unexpected file {cname!r} in the run directory",
                    run_directory=name, relative_path=cname,
                )
            )

    for stem in sorted(frame_exts):
        if _FRAME_EXTENSIONS <= frame_exts[stem]:
            findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.CONFLICTING_FRAME_FORMAT,
                    f"frame {stem!r} exists as both parquet and csv",
                    run_directory=name, artifact_name=stem,
                    expected="one frame format", actual="parquet+csv",
                )
            )
    return findings


def _check_frames_readable(store: ExperimentStore, run_dir: Path) -> list[AuditFinding]:
    """Deep-level: read each present, non-symlink frame via the public loader."""
    name = run_dir.name
    findings: list[AuditFinding] = []
    for frame in CANONICAL_FRAME_NAMES:
        present = None
        for suffix in (".parquet", ".csv"):
            candidate = run_dir / f"{frame}{suffix}"
            if candidate.is_symlink():
                present = None
                break  # symlink already reported at standard level; do not read it
            if candidate.exists():
                present = candidate
                break
        if present is None:
            continue
        try:
            df = store.read_frame(name, frame)
        except Exception as exc:  # noqa: BLE001 — one bad frame must not abort the audit
            findings.append(
                _f(
                    AuditSeverity.ERROR, AuditCode.INVALID_FRAME_FORMAT,
                    f"frame {frame!r} could not be read: {type(exc).__name__}",
                    run_directory=name, artifact_name=frame, relative_path=present.name,
                )
            )
            continue
        if len(df) == 0:
            findings.append(
                _f(
                    AuditSeverity.INFO, AuditCode.FRAME_ROW_COUNT_IMPLAUSIBLE,
                    f"frame {frame!r} loaded with zero rows (soft plausibility signal)",
                    run_directory=name, artifact_name=frame, relative_path=present.name,
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #


def _validate_run_directory_arg(run_directory: str) -> None:
    if not isinstance(run_directory, str) or not run_directory or run_directory in (".", ".."):
        raise AuditError(f"run_directory must be a bare run-directory name, got {run_directory!r}")
    if "/" in run_directory or "\\" in run_directory:
        raise AuditError(f"run_directory must not contain a path separator: {run_directory!r}")
    if is_absolute_artifact_path(run_directory) or has_parent_traversal(run_directory):
        raise AuditError(f"run_directory must be a safe root-level name: {run_directory!r}")


def audit_experiment_run(
    store: ExperimentStore,
    run_directory: str,
    *,
    level: "str | AuditLevel" = AuditLevel.STANDARD,
) -> ExperimentRunAudit:
    """Audit one metadata-bearing run directory under ``store.base_dir``.

    ``run_directory`` must be a **safe bare name** (no separators / traversal /
    absolute); anything else raises :class:`AuditError`.  A missing directory, a
    symlink directory (never followed), a plain file, or a directory without a
    ``metadata.json`` (an unrelated non-run entry) also raises :class:`AuditError`.
    Findings are locally sorted and numbered.  Read-only; no writes."""
    level = AuditLevel(level)
    _validate_run_directory_arg(run_directory)
    target = store.base_dir / run_directory
    if target.is_symlink():
        raise AuditError(f"run directory {run_directory!r} is a symlink; not followed")
    if not target.exists():
        raise AuditError(f"run directory {run_directory!r} does not exist")
    if not target.is_dir():
        raise AuditError(f"run directory {run_directory!r} is not a directory")
    if not (target / _METADATA_FILENAME).exists():
        raise AuditError(f"{run_directory!r} is not a run directory (no metadata.json)")

    findings, train_run_hash = _audit_run_directory(store, target, level)
    numbered = sort_and_number_findings(findings)
    return ExperimentRunAudit(
        run_directory=run_directory,
        train_run_hash=train_run_hash,
        status=status_for_findings(numbered),
        findings=numbered,
    )


def audit_experiment_store(
    store: ExperimentStore,
    *,
    level: "str | AuditLevel" = AuditLevel.STANDARD,
) -> ExperimentStoreAuditResult:
    """Audit every immediate entry under ``store.base_dir`` tolerantly (read-only).

    Enumerates entries in sorted order, classifies each, and audits metadata-bearing
    directories through the tolerant ladder — a single malformed run never aborts
    the survey.  Raises :class:`AuditError` only if the store root is missing or is
    not a directory."""
    level = AuditLevel(level)
    base = store.base_dir
    if not base.exists() or not base.is_dir():
        raise AuditError(f"audit root is not an existing directory: {base.name!r}")

    entries = sorted(base.iterdir(), key=lambda p: p.name)
    raw_findings: list[AuditFinding] = []
    run_meta: list[tuple[str, Optional[str]]] = []  # (name, hash|None) for run dirs
    non_run_entries = 0

    if not entries:
        raw_findings.append(
            _f(
                AuditSeverity.INFO, AuditCode.EMPTY_STORE,
                "the ExperimentStore contains no entries",
                run_directory=".",
            )
        )

    for entry in entries:
        name = entry.name
        if entry.is_symlink():
            raw_findings.append(
                _f(
                    AuditSeverity.WARNING, AuditCode.SYMLINK_ENTRY,
                    f"root entry {name!r} is a symlink (not followed)",
                    run_directory=".", relative_path=name,
                )
            )
            non_run_entries += 1
            continue
        if entry.is_file():
            if _is_ignored_os_file(name):
                raw_findings.append(
                    _f(
                        AuditSeverity.INFO, AuditCode.IGNORED_OS_FILE,
                        f"ignored OS file {name!r} at the store root",
                        run_directory=".", relative_path=name,
                    )
                )
            else:
                raw_findings.append(
                    _f(
                        AuditSeverity.INFO, AuditCode.ROOT_LEVEL_FILE,
                        f"regular file {name!r} at the store root (not a run)",
                        run_directory=".", relative_path=name,
                    )
                )
            non_run_entries += 1
            continue
        if entry.is_dir():
            children = sorted(entry.iterdir(), key=lambda p: p.name)
            if (entry / _METADATA_FILENAME).exists():
                findings, train_run_hash = _audit_run_directory(store, entry, level)
                raw_findings.extend(findings)
                run_meta.append((name, train_run_hash))
                continue
            if not children:
                raw_findings.append(
                    _f(
                        AuditSeverity.INFO, AuditCode.EMPTY_DIRECTORY,
                        f"directory {name!r} is empty",
                        run_directory=name,
                    )
                )
            elif any(c.suffix in _ARTIFACT_EXTENSIONS for c in children if not c.is_dir()):
                raw_findings.append(
                    _f(
                        AuditSeverity.WARNING, AuditCode.MISSING_METADATA,
                        f"directory {name!r} has experiment-like artifacts but no metadata.json",
                        run_directory=name,
                    )
                )
            else:
                raw_findings.append(
                    _f(
                        AuditSeverity.INFO, AuditCode.NON_RUN_DIRECTORY,
                        f"directory {name!r} is not an experiment run",
                        run_directory=name,
                    )
                )
            non_run_entries += 1

    numbered = sort_and_number_findings(raw_findings)

    by_dir: dict[str, list[AuditFinding]] = {}
    for finding in numbered:
        by_dir.setdefault(finding.run_directory, []).append(finding)

    run_audits = []
    for name, train_run_hash in run_meta:
        run_findings = tuple(by_dir.get(name, ()))
        run_audits.append(
            ExperimentRunAudit(
                run_directory=name,
                train_run_hash=train_run_hash,
                status=status_for_findings(run_findings),
                findings=run_findings,
            )
        )

    runs_valid = sum(1 for ra in run_audits if ra.status.value == "valid")
    runs_with_warnings = sum(1 for ra in run_audits if ra.status.value == "warning")
    runs_invalid = sum(1 for ra in run_audits if ra.status.value == "invalid")

    return ExperimentStoreAuditResult(
        runs_discovered=len(run_meta),
        runs_valid=runs_valid,
        runs_with_warnings=runs_with_warnings,
        runs_invalid=runs_invalid,
        non_run_entries=non_run_entries,
        findings_total=len(numbered),
        findings_by_severity=dict(Counter(f.severity.value for f in numbered)),
        findings_by_code=dict(Counter(f.code.value for f in numbered)),
        audited_run_hashes=tuple(sorted({h for _, h in run_meta if h is not None})),
        run_audits=tuple(run_audits),
        findings=numbered,
        overall_status=overall_status_for(numbered),
    )


def summarize_audit_result(result: ExperimentStoreAuditResult) -> dict:
    """A compact, deterministic, strict-JSON-safe summary (no host paths / timestamps)."""
    return {
        "overall_status": result.overall_status.value,
        "runs_discovered": result.runs_discovered,
        "runs_valid": result.runs_valid,
        "runs_with_warnings": result.runs_with_warnings,
        "runs_invalid": result.runs_invalid,
        "non_run_entries": result.non_run_entries,
        "findings_total": result.findings_total,
        "findings_by_severity": dict(result.findings_by_severity),
        "findings_by_code": dict(result.findings_by_code),
        "audited_run_hashes": list(result.audited_run_hashes),
    }
