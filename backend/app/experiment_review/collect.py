"""
Phase 14 (commit 2) — read-only evidence collector.

``collect_experiment_evidence_pack`` orchestrates the **existing public** Phase 13
(structural integrity), Phase 12 (catalog / compatibility / ranking) and Phase 10
(compatible-run comparison) APIs for a caller-selected set of ``train_run_hash``
values, and assembles a deterministic :class:`ExperimentEvidencePack`.  It creates
no new analytical evidence, duplicates none of those phases' logic, and is strictly
read-only: it performs **no filesystem writes**, opens **no database**, runs and
retrains nothing, and mints no hashes.

Registry / dataset-lineage context is deliberately **not collected** in v1 (see
Appendix O §O.2): this module imports no registry package, no database module, and
no relational-database driver, and the neutral ``not_collected`` statuses generate
no finding and never downgrade completeness.

Failure policy: every selected run is collected independently, so a missing or
malformed run never aborts evidence for the others.  Exception *messages* are never
embedded in findings or reasons (store errors can contain absolute host paths) —
only the exception **type name** plus a fixed factual description is reported.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from pydantic import ValidationError

from app.experiment_audit import AuditError, AuditLevel, audit_experiment_run
from app.experiment_catalog import (
    CatalogError,
    ExperimentLeaderboardSpec,
    build_experiment_catalog,
    group_compatible_runs,
    rank_experiment_catalog,
)
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
    sort_and_number_evidence_findings,
)
from app.experiments import ExperimentError, ExperimentStore
from app.experiments.registry import DEFAULT_COMPARE_METRICS
from app.reporting import DISCLAIMERS as COMPARISON_DISCLAIMERS
from app.reporting import compare_experiment_runs

__all__ = ["collect_experiment_evidence_pack"]

# Phase 13 codes that describe a *referenced* artifact's on-disk state.
_MISSING_ARTIFACT_CODE = "MISSING_REFERENCED_ARTIFACT"
_NOT_A_FILE_CODE = "ARTIFACT_NOT_A_FILE"
_UNREADABLE_ARTIFACT_CODE = "UNREADABLE_ARTIFACT"
_SYMLINK_CODE = "SYMLINK_ENTRY"
_ORPHAN_CODE = "ORPHAN_ARTIFACT"
# Phase 13 codes meaning a declared artifact is unusable as evidence, not merely absent.
_BLOCKING_ARTIFACT_CODES = frozenset(
    {_MISSING_ARTIFACT_CODE, _NOT_A_FILE_CODE, _UNREADABLE_ARTIFACT_CODE}
)

# Stable machine-readable missing-evidence labels.
_LABEL_RUN_NOT_FOUND = "run_not_found"
_LABEL_RUN_UNLOADABLE = "run_unloadable"
_LABEL_REQUIRED_ARTIFACT_MISSING = "required_artifact_missing"
_LABEL_REQUESTED_METRIC_MISSING = "requested_metric_missing"

# Errors that mean "this run's persisted metadata cannot be loaded".
_LOAD_ERRORS = (ExperimentError, ValidationError, OSError, ValueError)
# Errors that mean "the store-level catalog pass could not complete".
_CATALOG_ERRORS = (CatalogError, ExperimentError, ValidationError, OSError, ValueError)


def _finding(code: EvidenceCode, severity: EvidenceSeverity, message: str, *, train_run_hash=None, context=None):
    return EvidenceFinding(
        severity=severity, code=code, message=message, train_run_hash=train_run_hash, context=context
    )


def _artifact_format(relative_path: Optional[str]) -> Optional[str]:
    """Descriptive format from the safe relative *filename* extension only.

    The final path segment is isolated first so a dotted directory name cannot be
    mistaken for an extension."""
    if not relative_path:
        return None
    filename = relative_path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[-1].lower() or None


def _merged_metrics(run) -> dict:
    """Persisted metrics merged with the repository's established backtest-first
    precedence (the same precedence the experiments registry / Phase 12 catalog use
    when resolving a metric).  No metric is computed here."""
    merged = dict(run.metrics or {})
    merged.update(dict(run.backtest_metrics or {}))
    return merged


def _hash_chain(run) -> dict:
    """The six persisted hash-chain fields, verbatim (nothing invented)."""
    return {
        "train_run_hash": run.train_run_hash,
        "continuous_config_hash": run.continuous_config_hash,
        "feature_config_hash": run.feature_config_hash,
        "label_config_hash": run.label_config_hash,
        "dataset_config_hash": run.dataset_config_hash,
        "model_config_hash": run.model_config_hash,
    }


def _codes_for_artifact(audit_findings, artifact_key: str, relative_path: str) -> tuple[str, ...]:
    """Phase 13 codes attached to one referenced artifact (deterministic, unique)."""
    codes = {
        f.code.value
        for f in audit_findings
        if f.artifact_name == artifact_key or (f.relative_path is not None and f.relative_path == relative_path)
    }
    return tuple(sorted(codes))


def _build_artifact_inventory(run, audit_findings, *, existence_checked: bool):
    """Inventory from schema-valid ``artifact_paths`` + Phase 13 findings only.

    No path re-validation, no ``stat``, no file opening, no content hashing.  At
    metadata-only level Phase 13 checked no existence, so both tri-state fields stay
    ``None``; at standard/deep the state is inferred from the findings Phase 13
    already produced for every safe referenced path."""
    entries: list[ArtifactInventoryEntry] = []
    # A blank artifact key cannot be used as an inventory name, but dropping the entry
    # would hide a declared artifact entirely (Phase 13 validates artifact_paths values,
    # not keys, so nothing else would report it).  It is surfaced under a synthesized
    # name instead, which also keeps one malformed run from aborting the pack.
    named = {
        (k if isinstance(k, str) and k.strip() else f"unnamed:{v}"): v
        for k, v in run.artifact_paths.items()
    }
    for artifact_key in sorted(named):
        relative_path = named[artifact_key]
        codes = _codes_for_artifact(audit_findings, artifact_key, relative_path)
        if not existence_checked:
            exists: Optional[bool] = None
            regular_file: Optional[bool] = None
        elif _MISSING_ARTIFACT_CODE in codes:
            exists, regular_file = False, False
        elif _NOT_A_FILE_CODE in codes or _SYMLINK_CODE in codes:
            exists, regular_file = True, False
        else:
            exists, regular_file = True, True
        entries.append(
            ArtifactInventoryEntry(
                artifact_name=artifact_key,
                relative_path=relative_path,
                exists=exists,
                regular_file=regular_file,
                format=_artifact_format(relative_path),
                audit_finding_codes=codes,
            )
        )

    # Orphan files Phase 13 already identified with a safe store-relative path.
    # Presence is established by Phase 13's enumeration; regular-file status is not
    # asserted by the orphan finding, so it stays None (never re-checked here).
    referenced = set(run.artifact_paths.values())
    for f in audit_findings:
        if f.code.value == _ORPHAN_CODE and f.relative_path and f.relative_path not in referenced:
            entries.append(
                ArtifactInventoryEntry(
                    artifact_name=f"orphan:{f.relative_path}",
                    relative_path=f.relative_path,
                    exists=True if existence_checked else None,
                    regular_file=None,
                    format=_artifact_format(f.relative_path),
                    audit_finding_codes=(_ORPHAN_CODE,),
                )
            )
    return tuple(entries)


def _collect_run(store: ExperimentStore, train_run_hash: str, level: AuditLevel):
    """Independent, tolerant collection for one selected run.

    Returns ``(load_status, audit_status, audit_findings, run_or_None)``."""
    try:
        audit = audit_experiment_run(store, train_run_hash, level=level)
    except (AuditError, ExperimentError, OSError, ValueError):
        # missing / unsafe / symlink / non-run entry — no structural evidence exists
        return EvidenceLoadStatus.UNAVAILABLE, "unavailable", (), None

    audit_findings = tuple(audit.findings)  # Phase 13 findings preserved verbatim
    audit_status = audit.status.value
    try:
        run = store.read_metadata(train_run_hash)
    except _LOAD_ERRORS:
        return EvidenceLoadStatus.UNLOADABLE, audit_status, audit_findings, None
    return EvidenceLoadStatus.LOADED, audit_status, audit_findings, run


def collect_experiment_evidence_pack(
    store: ExperimentStore,
    train_run_hashes: Sequence[str],
    *,
    metric: Optional[str] = None,
    maximize: bool = True,
    include_catalog_context: bool = True,
    audit_level: "AuditLevel | str" = AuditLevel.STANDARD,
) -> ExperimentEvidencePack:
    """Collect a deterministic, read-only evidence pack for the selected runs.

    Selection is deduplicated preserving first occurrence and never re-sorted.  Each
    run is audited (Phase 13) and loaded (public ``ExperimentStore``) independently;
    a single store-level Phase 12 catalog pass supplies optional compatibility /
    ranking context; Phase 10 comparison runs only for a fully-loaded, compatible
    multi-run selection and never bypasses its guard.  Raises
    :class:`EvidenceError` only for an invalid selection or audit level."""
    selected = dedupe_preserve_order(train_run_hashes)
    if not selected:
        raise EvidenceError("at least one train_run_hash must be selected")
    try:
        level = AuditLevel(audit_level)
    except ValueError as exc:
        raise EvidenceError(f"invalid audit level: {exc}") from exc
    if metric is not None:
        if not isinstance(metric, str) or not metric.strip():
            raise EvidenceError("metric must be None or a non-empty string")
        if not include_catalog_context:
            # Ranking evidence comes from the catalog pass; honouring a metric request
            # without it would silently drop the request.
            raise EvidenceError("metric requires include_catalog_context=True")
    existence_checked = level != AuditLevel.METADATA_ONLY

    findings: list[EvidenceFinding] = []

    # --- per-run collection (tolerant, independent) --------------------------- #
    collected: dict[str, tuple] = {}
    for train_run_hash in selected:
        collected[train_run_hash] = _collect_run(store, train_run_hash, level)

    loaded_hashes = tuple(h for h in selected if collected[h][0] == EvidenceLoadStatus.LOADED)

    # --- one store-level Phase 12 catalog pass -------------------------------- #
    catalog_status = EvidenceContextStatus.NOT_COLLECTED
    group_by_hash: dict[str, Any] = {}
    catalog_metrics = None
    if metric is not None:
        catalog_metrics = tuple(dict.fromkeys((*DEFAULT_COMPARE_METRICS, metric)))
    if include_catalog_context:
        try:
            rows = build_experiment_catalog(store, metrics=catalog_metrics)
            for group in group_compatible_runs(rows):
                for row in group.rows:
                    group_by_hash[row.train_run_hash] = group
            catalog_status = EvidenceContextStatus.COLLECTED
        except _CATALOG_ERRORS as exc:
            catalog_status = EvidenceContextStatus.UNAVAILABLE
            findings.append(
                _finding(
                    EvidenceCode.CATALOG_CONTEXT_UNAVAILABLE,
                    EvidenceSeverity.WARNING,
                    "the store-level catalog pass could not complete; per-run catalog "
                    "context is unavailable",
                    context={"error_type": type(exc).__name__},
                )
            )

    # --- per-run evidence ------------------------------------------------------ #
    runs: list[ExperimentRunEvidence] = []
    metric_missing_any = False
    catalog_missing_any = catalog_status == EvidenceContextStatus.UNAVAILABLE

    for train_run_hash in selected:
        load_status, audit_status, audit_findings, run = collected[train_run_hash]
        missing_evidence: set[str] = set()
        requested_metric_missing = False

        if load_status == EvidenceLoadStatus.UNAVAILABLE:
            findings.append(
                _finding(
                    EvidenceCode.RUN_NOT_FOUND,
                    EvidenceSeverity.ERROR,
                    "the selected run could not be located as an auditable run directory",
                    train_run_hash=train_run_hash,
                )
            )
            missing_evidence.add(_LABEL_RUN_NOT_FOUND)
        elif load_status == EvidenceLoadStatus.UNLOADABLE:
            findings.append(
                _finding(
                    EvidenceCode.RUN_UNLOADABLE,
                    EvidenceSeverity.ERROR,
                    "the selected run's persisted metadata could not be loaded",
                    train_run_hash=train_run_hash,
                )
            )
            missing_evidence.add(_LABEL_RUN_UNLOADABLE)

        # optional per-run catalog context (only meaningful for a loaded run)
        catalog_context: Optional[CatalogRunContext] = None
        if not include_catalog_context:
            catalog_context = CatalogRunContext(status=EvidenceContextStatus.NOT_COLLECTED)
        elif run is None:
            catalog_context = CatalogRunContext(status=EvidenceContextStatus.UNAVAILABLE)
        else:
            group = group_by_hash.get(train_run_hash)
            if catalog_status == EvidenceContextStatus.UNAVAILABLE or group is None:
                catalog_context = CatalogRunContext(status=EvidenceContextStatus.UNAVAILABLE)
                if catalog_status != EvidenceContextStatus.UNAVAILABLE:
                    # store catalog succeeded but this run was not in it
                    findings.append(
                        _finding(
                            EvidenceCode.CATALOG_CONTEXT_UNAVAILABLE,
                            EvidenceSeverity.WARNING,
                            "the selected run was not present in the store catalog pass",
                            train_run_hash=train_run_hash,
                        )
                    )
                    catalog_missing_any = True
                # Absent catalog context means the metric could not be *evaluated*; it
                # is not evidence that the run lacks the metric, so no metric finding is
                # fabricated here.  Catalog context is optional, so it is reported via
                # ``catalog_context.status`` and a finding, and degrades the selection to
                # a warning — it is never listed as missing *required* run evidence.
                catalog_missing_any = True
            else:
                rank, metric_value = None, None
                if metric is not None:
                    metric_value, rank = _rank_within_group(group, train_run_hash, metric, maximize)
                    if metric_value is None or rank is None:
                        requested_metric_missing = True
                catalog_context = CatalogRunContext(
                    status=EvidenceContextStatus.COLLECTED,
                    compatibility_group=group.group_id,
                    group_size=len(group.rows),
                    peer_train_run_hashes=tuple(group.train_run_hashes),
                    requested_metric=metric,
                    requested_metric_value=metric_value,
                    rank=rank,
                    maximize=maximize if metric is not None else None,
                )

        if requested_metric_missing:
            metric_missing_any = True
            missing_evidence.add(_LABEL_REQUESTED_METRIC_MISSING)
            findings.append(
                _finding(
                    EvidenceCode.REQUESTED_METRIC_MISSING,
                    EvidenceSeverity.ERROR,
                    "the explicitly requested metric is not available for the selected run",
                    train_run_hash=train_run_hash,
                    context={"metric": metric},
                )
            )

        artifact_inventory = ()
        required_evidence_missing = False
        if run is not None:
            artifact_inventory = _build_artifact_inventory(
                run, audit_findings, existence_checked=existence_checked
            )
            if any(f.code.value in _BLOCKING_ARTIFACT_CODES for f in audit_findings):
                required_evidence_missing = True
                missing_evidence.add(_LABEL_REQUIRED_ARTIFACT_MISSING)

        completeness = derive_run_completeness(
            load_status=load_status,
            audit_findings=audit_findings,
            required_evidence_missing=required_evidence_missing,
            requested_metric_missing=requested_metric_missing,
        )

        runs.append(
            ExperimentRunEvidence(
                train_run_hash=train_run_hash,
                # A run the audit could not even locate has no run directory to name.
                # This also keeps an unsafe caller-supplied hash out of a path field,
                # so one bad selection entry cannot abort the whole pack.
                run_directory=None if load_status == EvidenceLoadStatus.UNAVAILABLE else train_run_hash,
                load_status=load_status,
                completeness=completeness,
                audit_status=audit_status,
                audit_findings=audit_findings,
                created_at=None if run is None else run.created_at,
                train_start=None if run is None else run.train_start.isoformat(),
                train_end=None if run is None else run.train_end.isoformat(),
                validation_start=None if run is None else run.validation_start.isoformat(),
                validation_end=None if run is None else run.validation_end.isoformat(),
                feature_columns=None if run is None else tuple(run.feature_columns),
                label_column=None if run is None else run.label_column,
                model_type=None if run is None else run.model_type,
                task_type=None if run is None else run.task_type,
                metrics=None if run is None else _merged_metrics(run),
                baseline_metrics=None if run is None else dict(run.baseline_metrics or {}),
                hash_chain=None if run is None else _hash_chain(run),
                artifact_inventory=artifact_inventory,
                catalog_context=catalog_context,
                missing_evidence=tuple(sorted(missing_evidence)),
            )
        )

    # --- Phase 10 comparison --------------------------------------------------- #
    # The requested metric is threaded into the comparison too, so a rank the pack
    # reports is backed by a metric its own comparison rows actually carry.
    comparison, selection_warning, comparison_findings = _collect_comparison(
        store,
        selected,
        loaded_hashes,
        [collected[h][3] for h in loaded_hashes],
        catalog_metrics,
    )
    findings.extend(comparison_findings)
    if catalog_missing_any:
        selection_warning = True

    numbered = sort_and_number_evidence_findings(findings)
    completeness = derive_pack_completeness(
        [r.completeness for r in runs],
        selection_warning=selection_warning,
        selection_incomplete=metric_missing_any,
    )
    summary = EvidenceSummary(
        completeness=completeness,
        selected_runs_total=len(runs),
        runs_complete=sum(1 for r in runs if r.completeness == EvidenceCompleteness.COMPLETE),
        runs_with_warnings=sum(1 for r in runs if r.completeness == EvidenceCompleteness.WARNING),
        runs_incomplete=sum(1 for r in runs if r.completeness == EvidenceCompleteness.INCOMPLETE),
        runs_unavailable=sum(1 for r in runs if r.completeness == EvidenceCompleteness.UNAVAILABLE),
        phase14_findings_total=len(numbered),
        phase13_findings_total=sum(len(r.audit_findings) for r in runs),
    )
    return ExperimentEvidencePack(
        selected_run_hashes=selected,
        runs=tuple(runs),
        comparison=comparison,
        evidence_summary=summary,
        findings=numbered,
        disclaimers=(),  # renderer-owned (Commit 3)
        registry_context_status=EvidenceContextStatus.NOT_COLLECTED,
        dataset_lineage_context_status=EvidenceContextStatus.NOT_COLLECTED,
        catalog_context_status=catalog_status,
    )


def _rank_within_group(group, train_run_hash: str, metric: str, maximize: bool):
    """Descriptive rank of one run inside its compatibility group, via Phase 12.

    Returns ``(metric_value, rank)`` — both ``None`` when the metric is unavailable
    for this run or for the whole group.  Ranking behavior (order, tie-break,
    missing-metric handling) is entirely Phase 12's."""
    try:
        spec = ExperimentLeaderboardSpec(metric=metric, maximize=maximize, on_missing_metric="exclude")
        ranked = rank_experiment_catalog(group.rows, spec)
    except CatalogError:
        # rejected metric name, or metric absent from the catalog selection / whole group
        return None, None
    for position, row in enumerate(ranked, start=1):
        if row.train_run_hash == train_run_hash:
            return row.metrics.get(metric), position
    return None, None  # this run was excluded (its metric value is unavailable)


def _collect_comparison(store, selected, loaded_hashes, loaded_runs, metrics):
    """Phase 10 comparison context for the selection (never bypasses its guard)."""
    findings: list[EvidenceFinding] = []

    if len(selected) == 1:
        return (
            ComparisonEvidence(
                status=EvidenceComparisonStatus.NOT_APPLICABLE, selected_run_hashes=selected
            ),
            False,
            findings,
        )

    if len(loaded_hashes) != len(selected):
        findings.append(
            _finding(
                EvidenceCode.COMPARISON_UNAVAILABLE,
                EvidenceSeverity.WARNING,
                "comparison was not attempted because one or more selected runs are "
                "missing or unloadable",
                context={"loaded_runs": len(loaded_hashes), "selected_runs": len(selected)},
            )
        )
        return (
            ComparisonEvidence(
                status=EvidenceComparisonStatus.UNAVAILABLE,
                selected_run_hashes=selected,
                unavailable_reason="one or more selected runs are missing or unloadable",
            ),
            False,
            findings,
        )

    # Compatibility is decided *only* by Phase 10's own guard.  The Phase 12
    # compatibility key is strictly narrower (it also keys on the training window and
    # task type), so short-circuiting on Phase 12 groups here would suppress
    # comparisons Phase 10 would happily produce — and would duplicate the very guard
    # logic this module exists to delegate.
    #
    # The already-loaded run objects are passed instead of hashes: Phase 10 resolves a
    # hash by re-loading it, which also re-checks artifact existence, so a run with a
    # missing artifact would surface here as an error indistinguishable from a genuine
    # incompatibility.  Passing the runs leaves the guard as the only failure mode.
    try:
        rows = compare_experiment_runs(loaded_runs, store=store, metrics=metrics)
    except (ExperimentError, ValidationError, OSError, ValueError) as exc:
        findings.append(
            _finding(
                EvidenceCode.INCOMPATIBLE_SELECTED_RUNS,
                EvidenceSeverity.WARNING,
                "the comparison guard did not accept the selected runs as compatible",
                context={"error_type": type(exc).__name__},
            )
        )
        findings.append(
            _finding(
                EvidenceCode.COMPARISON_UNAVAILABLE,
                EvidenceSeverity.WARNING,
                "the comparison could not be produced for the selected runs",
                context={"error_type": type(exc).__name__},
            )
        )
        return (
            ComparisonEvidence(
                status=EvidenceComparisonStatus.UNAVAILABLE,
                selected_run_hashes=selected,
                unavailable_reason="the comparison could not be produced for the selected runs",
            ),
            True,
            findings,
        )

    return (
        ComparisonEvidence(
            status=EvidenceComparisonStatus.AVAILABLE,
            selected_run_hashes=selected,
            rows=tuple(_comparison_row_to_mapping(r) for r in rows),
            disclaimers=tuple(COMPARISON_DISCLAIMERS),
        ),
        False,
        findings,
    )


def _comparison_row_to_mapping(row) -> dict:
    """Public Phase 10 comparison row → a plain JSON-safe mapping (order preserved
    by the caller).  No rank / best-run field is added."""
    return {
        "train_run_hash": row.train_run_hash,
        "model_type": row.model_type,
        "task_type": row.task_type,
        "label_column": row.label_column,
        "validation_start": row.validation_start,
        "validation_end": row.validation_end,
        "same_window": row.same_window,
        "metrics": dict(row.metrics),
    }
